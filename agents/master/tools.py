"""Tool wrappers for Agent to call into the application.

Refactored to use agent_api facade for clean, agent-friendly operations.
Each tool delegates to agent_api functions with minimal logic.
"""
from typing import Any, Dict, List, Optional
import logging
from datetime import datetime
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from generate import generate_subtasks
import agent_api

logger = logging.getLogger('agent.tools')


def tool_generate_subtasks(task_description: str, max_subtasks: int = 4) -> Dict[str, Any]:
    """
    Generate subtasks for a given task description.
    Args:
        task_description (str): Description of the main task to decompose.
        max_subtasks (int, optional): Maximum number of subtasks to generate (default: 4).
    Example:
        tool_generate_subtasks(task_description="Prepare quarterly report", max_subtasks=5)
    Response:
        {
            "subtasks": ["Collect data", "Analyze trends", ...]
        }
    """
    res = generate_subtasks(task_description, max_subtasks=max_subtasks)
    return res


def tool_refine_subtasks(original_subtasks: List[str], feedback: str) -> Dict[str, Any]:
    """Refine existing subtasks based on user feedback.
    Simple heuristic implementation (no extra LLM call):
      - If feedback contains keywords 'remove <n>' drop matching indices.
      - If feedback contains 'add:' lines, append them.
      - If feedback contains 'reorder:' followed by comma-separated indices, reorder accordingly.
    Args:
        original_subtasks (List[str]): Current list of subtask titles.
        feedback (str): Freeform user feedback instructions.
    Response:
        {"refined_subtasks": ["..."]}
    """
    refined = list(original_subtasks)
    fb = feedback.lower()
    import re
    # Remove pattern: 'remove 2' (1-based index)
    for rem_match in re.findall(r'remove (\d+)', fb):
        try:
            idx = int(rem_match) - 1
            if 0 <= idx < len(refined):
                refined.pop(idx)
        except Exception:
            pass
    # Add pattern: lines after 'add:' separated by ';' or newlines
    if 'add:' in fb:
        add_part = feedback.split('add:')[1]
        candidates = re.split(r'[;\n]', add_part)
        for c in candidates:
            title = c.strip().strip('-').strip()
            if title:
                refined.append(title)
    # Reorder pattern: 'reorder: 3,1,2'
    if 'reorder:' in fb:
        try:
            reorder_part = fb.split('reorder:')[1].strip().split()[0]
            order_indices = [int(x)-1 for x in reorder_part.split(',') if x.strip().isdigit()]
            if len(order_indices) == len(refined):
                refined = [refined[i] for i in order_indices]
        except Exception:
            pass
    return {"refined_subtasks": refined}


def tool_create_work(title: str, description: str = '', tasks: List[Dict[str, str]] = [], status: str = 'Draft', expected_completion_hint: Optional[str] = None) -> Dict[str, Any]:
    """Create work item with optional tasks.
    
    Note: Due dates are NOT automatically assigned. After creation, use tool_propose_due_dates
    to get AI-suggested dates, then show them to user for confirmation.
    
    Args:
        title: Work title
        description: Work description
        tasks: List of task dicts with 'title' and optionally 'description' and 'priority'
        status: Initial status (default: 'Draft')
        expected_completion_hint: Expected deadline like "this week", "by Friday", "in 3 days", etc.
        
    Returns:
        {"id": work_id, "title": work_title}
    """
    work_id = agent_api.create_work_with_tasks(title, description, tasks, False, expected_completion_hint)
    if work_id:
        return {'id': work_id, 'title': title}
    return {'error': 'failed to create work'}


def tool_create_task(work_id: int, title: str, status: str = 'Draft', due_date: Optional[str] = None) -> Dict[str, Any]:
    """Create a single task under an existing work.
    
    Args:
        work_id: Parent work ID
        title: Task title
        status: Initial status (default Draft)
        due_date: Optional due date (ISO format string)
        
    Returns:
        {"task_id": id, "title": title, "status": status, "due_date": date_str}
    """
    from core.storage import create_task
    from core.task import TaskStatus
    
    parsed_due = None
    if due_date:
        try:
            parsed_due = datetime.fromisoformat(due_date)
        except Exception:
            pass
    
    task_status = TaskStatus.from_string(status)
    task = create_task(work_id, title, task_status, parsed_due)
    
    if task:
        return {
            "task_id": task.id,
            "title": task.title,
            "status": task.status,
            "due_date": task.due_date.isoformat() if task.due_date else None
        }
    return {'error': 'failed to create task'}


def tool_publish_work(work_id: int, schedule_first_task: bool = True) -> Dict[str, Any]:
    """Publish a work item and send notifications.
    
    IMPORTANT: All tasks must have due dates before publishing. If any task is missing a due date,
    use tool_assign_smart_due_dates first to assign them.
    
    Args:
        work_id: Work item ID
        schedule_first_task: Whether to schedule first task to calendar
        
    Returns:
        {"published": True, "work_id": id} or {"error": "...", "tasks_without_dates": [...]}
    """
    from core.storage import get_work_by_id, list_tasks
    
    # Validate all tasks have due dates
    work = get_work_by_id(work_id, include_tasks=True)
    if not work:
        return {'error': 'work not found'}
    
    tasks = list_tasks(work_id=work_id, exclude_completed=True)
    tasks_without_dates = [t.id for t in tasks if not t.due_date]
    
    if tasks_without_dates:
        return {
            'error': 'cannot publish: some tasks missing due dates',
            'tasks_without_dates': tasks_without_dates,
            'message': f'{len(tasks_without_dates)} task(s) need due dates. Use tool_assign_smart_due_dates to set them.'
        }
    
    result = agent_api.publish_work_flow(work_id, schedule_first_task)
    if result:
        return {'published': True, 'work_id': work_id}
    return {'error': 'failed to publish work'}


def tool_send_due_date_confirmation(work_id: int) -> Dict[str, Any]:
    """Trigger interactive Slack due-date confirmation for a work.
    
    Args:
        work_id: Work item ID
        
    Returns:
        {"sent": True, "work_id": id}
    """
    result = agent_api.send_interactive_due_date_request(work_id)
    if result:
        return {"sent": True, "work_id": work_id}
    return {"error": "failed to send confirmation"}


def tool_schedule_first_untracked_task(work_id: int) -> Dict[str, Any]:
    """Schedule the first incomplete task for a work.
    
    Args:
        work_id: Work item ID
        
    Returns:
        {"scheduled_task_id": id}
    """
    from core.storage import list_tasks, update_task_status
    from core.task import TaskStatus
    
    tasks = list_tasks(work_id=work_id, exclude_completed=True)
    if not tasks:
        return {"error": "no schedulable task"}
    
    target = tasks[0]
    update_task_status(target.id, TaskStatus.TRACKED)
    result = agent_api.schedule_task_to_calendar(target.id)
    
    if result:
        return {"scheduled_task_id": target.id}
    return {"error": "failed to schedule task"}


def tool_update_task_status(task_id: int, status: str) -> Dict[str, Any]:
    """Update task status.
    
    Args:
        task_id: Task ID
        status: New status
        
    Returns:
        {"task_id": id, "status": status}
    """
    from core.storage import update_task_status
    from core.task import TaskStatus
    
    task_status = TaskStatus.from_string(status)
    task = update_task_status(task_id, task_status)
    
    if task:
        return {"task_id": task.id, "status": task.status}
    return {"error": "task not found"}


def tool_complete_task_and_schedule_next(task_id: int) -> Dict[str, Any]:
    """Complete a task and schedule the next pending one if any.
    
    Args:
        task_id: Task ID to complete
        
    Returns:
        {"completed_task_id": id, "work_id": work_id}
    """
    from core.storage import get_task_by_id
    
    task = get_task_by_id(task_id)
    if not task:
        return {"error": "task not found"}
    
    result = agent_api.complete_task_flow(task_id)
    if result:
        return {"completed_task_id": task_id, "work_id": task.work_id}
    return {"error": "failed to complete task"}


def tool_propose_due_dates(work_id: int, expected_completion_hint: Optional[str] = None) -> Dict[str, Any]:
    """Generate AI-proposed due dates for tasks (does NOT persist them).
    
    Uses LLM to analyze task difficulty and propose realistic due dates.
    ALWAYS show the proposed dates to user for review before calling tool_confirm_due_dates.
    
    Args:
        work_id: Work item ID
        expected_completion_hint: Deadline like "this week", "by Friday", "in 3 days". Uses work's hint if not provided.
        
    Returns:
        {
            "work_id": int,
            "schedule": [{"task_id": id, "task_title": title, "due_date": "YYYY-MM-DD", "due_date_formatted": "Monday, Dec 1, 2025"}],
            "schedule_map": {task_id: "YYYY-MM-DD", ...}  # Use this for tool_confirm_due_dates
        }
    """
    result = agent_api.propose_due_dates_for_work(work_id, expected_completion_hint)
    if result:
        # Add schedule_map for easy confirmation
        if 'schedule' in result:
            schedule_map = {item['task_id']: item['due_date'] for item in result['schedule']}
            result['schedule_map'] = schedule_map
        return result
    return {"error": "failed to propose due dates"}


def tool_confirm_due_dates(work_id: int, schedule: Dict[int, str]) -> Dict[str, Any]:
    """Apply user-confirmed due dates to tasks.
    
    Only call this AFTER user has reviewed and confirmed the proposed dates.
    Use the 'schedule_map' from tool_propose_due_dates output as the 'schedule' parameter here.
    
    Args:
        work_id: Work item ID
        schedule: Dict mapping task_id (int) -> due_date ("YYYY-MM-DD" string)
                  Example: {16: "2025-12-02", 17: "2025-12-05", 18: "2025-12-09"}
                  Use the 'schedule_map' field from tool_propose_due_dates response
        
    Returns:
        {"work_id": id, "confirmed": True, "count": number_of_tasks}
    """
    result = agent_api.confirm_due_dates_for_work(work_id, schedule)
    if result:
        return {"work_id": work_id, "confirmed": True, "count": len(schedule)}
    return {"error": "failed to confirm due dates"}


def tool_snooze_task(task_id: int, days: int = 1) -> Dict[str, Any]:
    """Snooze a task by moving its due date forward.
    
    Args:
        task_id: Task ID
        days: Number of days to snooze
        
    Returns:
        {"task_id": id, "snoozed_days": days, "snooze_count": count}
    """
    from core.storage import get_task_by_id
    
    result = agent_api.snooze_task(task_id, days)
    if result:
        task = get_task_by_id(task_id)
        return {
            "task_id": task_id,
            "snoozed_days": days,
            "snooze_count": task.snooze_count if task else 0
        }
    return {"error": "failed to snooze task"}


def tool_reschedule_task_event(task_id: int, new_due: str) -> Dict[str, Any]:
    """Reschedule a task to a new due datetime.
    
    Args:
        task_id: Task ID
        new_due: ISO datetime string
        
    Returns:
        {"task_id": id, "new_due": date_str}
    """
    from core.storage import get_task_by_id
    
    try:
        parsed_due = datetime.fromisoformat(new_due)
    except Exception:
        return {"error": "invalid new_due format"}
    
    result = agent_api.set_task_due_date(task_id, parsed_due, source="reschedule")
    if result:
        task = get_task_by_id(task_id)
        return {
            "task_id": task_id,
            "new_due": task.due_date.isoformat() if task and task.due_date else new_due
        }
    return {"error": "failed to reschedule task"}


def tool_list_upcoming_events(max_results: int = 10) -> Dict[str, Any]:
    """List upcoming tasks from Google Tasks.
    
    Args:
        max_results: Maximum number of tasks to return
        
    Returns:
        {"upcoming": [task_dicts]}
    """
    try:
        events = agent_api.fetch_calendar_tasks()
        return {"upcoming": events[:max_results]}
    except Exception as e:
        logger.exception('Failed to list upcoming events')
        return {"error": str(e)}


def tool_sync_event_update(task_id: int) -> Dict[str, Any]:
    """Sync a task's state from Google Tasks.
    
    Args:
        task_id: Task ID to sync
        
    Returns:
        {"synced": True, "task_id": id}
    """
    result = agent_api.sync_task_from_calendar(task_id)
    if result:
        return {"synced": True, "task_id": task_id}
    return {"error": "failed to sync task"}


def tool_notify_task_completed(task_id: int) -> Dict[str, Any]:
    """Send notification that a task was completed.
    
    Args:
        task_id: Task ID
        
    Returns:
        {"sent": True/False}
    """
    from core.storage import get_task_by_id, get_work_by_id
    from core.slack import get_notifier
    
    task = get_task_by_id(task_id)
    if not task:
        return {"error": "task not found"}
    
    work = get_work_by_id(task.work_id, include_tasks=False)
    if work:
        notifier = get_notifier()
        result = notifier.send_task_completed(task, work)
        return {"sent": result}
    
    return {"sent": False}


def tool_notify_work_completed(work_id: int) -> Dict[str, Any]:
    """Send notification that a work was completed.
    
    Args:
        work_id: Work ID
        
    Returns:
        {"sent": True/False}
    """
    from core.storage import get_work_by_id
    from core.slack import get_notifier
    
    work = get_work_by_id(work_id, include_tasks=True)
    if not work:
        return {"error": "work not found"}
    
    notifier = get_notifier()
    result = notifier.send_work_completed(work)
    return {"sent": result}


def tool_grouped_work_alert(work_id: int, changes: List[str]) -> Dict[str, Any]:
    """Send grouped notification for multiple changes to a work.
    
    Args:
        work_id: Work ID
        changes: List of change descriptions
        
    Returns:
        {"work_id": id, "changes_count": count}
    """
    from core.storage import get_work_by_id
    from core.slack import get_notifier
    
    work = get_work_by_id(work_id, include_tasks=False)
    if not work:
        return {"error": "work not found"}
    
    notifier = get_notifier()
    notifier.send_grouped_alert(work, changes)
    
    return {"work_id": work_id, "changes_count": len(changes)}


def tool_complete_work(work_id: int) -> Dict[str, Any]:
    """Mark a work item as completed.
    
    Args:
        work_id: Work ID
        
    Returns:
        {"work_id": id, "status": status}
    """
    from core.storage import update_work_status
    from core.work import WorkStatus
    
    work = update_work_status(work_id, WorkStatus.COMPLETED)
    if work:
        return {"work_id": work.id, "status": work.status}
    return {"error": "work not found"}


def tool_daily_planner_digest() -> Dict[str, Any]:
    """Send daily reminder notification of today's tasks via Slack.
    
    This tool sends a Slack notification with today's tasks. Use tool_get_today_tasks() 
    if you want to retrieve and display today's tasks to the user instead.
    
    Returns:
        {"sent": True/False}
    """
    try:
        result = agent_api.send_daily_reminder()
        return {"sent": result}
    except Exception as e:
        logger.exception('Failed daily planner digest')
        return {"error": str(e)}


def tool_get_weekly_status() -> Dict[str, Any]:
    """Get current week's task status and summary.
    
    Returns detailed breakdown of this week's tasks including completed, 
    in-progress, and pending tasks. Week runs from Monday to Sunday.
    
    Returns:
        {
            "week_start": "YYYY-MM-DD",
            "week_end": "YYYY-MM-DD",
            "total_tasks": int,
            "completed": [task_dicts],
            "in_progress": [task_dicts],
            "pending": [task_dicts],
            "completion_rate": "X/Y"
        }
    """
    try:
        result = agent_api.get_weekly_tasks_summary()
        return result
    except Exception as e:
        logger.exception('Failed to get weekly status')
        return {"error": str(e)}


def tool_get_work(work_id: int) -> Dict[str, Any]:
    """Get detailed information about a work item.
    
    Args:
        work_id: Work item ID
        
    Returns:
        Work dict with id, title, description, status, tasks
    """
    result = agent_api.get_work_details(work_id)
    if result:
        return result
    return {'error': 'work not found'}


def tool_list_works(status: str = 'all') -> Dict[str, Any]:
    """List work items by status.
    
    Args:
        status: Status filter - 'draft', 'published', 'completed', 'in_progress', 'all'
        
    Returns:
        {"works": [work_dicts]}
    """
    works = agent_api.list_works_by_status(status)
    return {"works": works}


def tool_list_tasks(status: str = 'all', work_id: Optional[int] = None) -> Dict[str, Any]:
    """List tasks by status.
    
    Args:
        status: Status filter - 'draft', 'published', 'tracked', 'completed', 'all'
        work_id: Optional work ID filter
        
    Returns:
        {"tasks": [task_dicts]}
    """
    tasks = agent_api.list_tasks_by_status(status, work_id)
    return {"tasks": tasks}


def tool_get_today_tasks() -> Dict[str, Any]:
    """Get all tasks due today for display to user.
    
    Use this tool when user asks about today's tasks, today's schedule, 
    or what's due today. Returns task data for the agent to present.
    
    Returns:
        {"tasks": [task_dicts]}
    """
    tasks = agent_api.get_today_tasks_summary()
    return {"tasks": tasks}


def tool_get_overdue_tasks() -> Dict[str, Any]:
    """Get all overdue tasks for display to user.
    
    Use this tool when user asks about overdue tasks, missed deadlines,
    or what tasks are past due. Returns task data for the agent to present.
    
    Returns:
        {"tasks": [task_dicts]}
    """
    tasks = agent_api.get_overdue_tasks()
    return {"tasks": tasks}


def tool_send_slack_message(text: str) -> Dict[str, Any]:
    """Send a Slack notification message.
    
    Args:
        text: Message text
        
    Returns:
        {"sent": True}
    """
    result = agent_api.send_slack_notification(text)
    return {'sent': result}


def tool_schedule_task_to_calendar(task_id: int) -> Dict[str, Any]:
    """Schedule a task to Google Tasks.
    
    Args:
        task_id: Task ID
        
    Returns:
        {"scheduled": True, "task_id": id}
    """
    result = agent_api.schedule_task_to_calendar(task_id)
    if result:
        return {'scheduled': True, 'task_id': task_id}
    return {'error': 'failed to schedule task'}


def tool_queue_celery_task(task_id: int) -> Dict[str, Any]:
    """Queue a task for asynchronous processing using Celery.
    
    Args:
        task_id: Task ID
        
    Returns:
        {"queued": True, "task_id": id}
    """
    try:
        from celery_app import async_assign_task
        from core.storage import get_task_by_id
        
        task = get_task_by_id(task_id)
        if not task:
            return {'error': 'task not found'}
        
        payload = {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "due_date": task.due_date.isoformat() if task.due_date else None
        }
        async_assign_task.delay(payload)
        return {'queued': True, 'task_id': task.id}
    except Exception as e:
        logger.exception('Failed to queue celery task')
        return {'error': str(e)}


# ===== Learning & Feedback Tools =====

def tool_log_conversation_feedback(
    conversation_summary: str,
    what_went_well: Optional[str] = None,
    what_could_improve: Optional[str] = None,
    user_satisfaction: Optional[str] = None,
    context_tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Log feedback about the current conversation for learning and optimization.
    
    Call this at the end of multi-turn interactions to record what went well and what
    could be improved. The agent should self-assess its performance honestly.
    
    Args:
        conversation_summary: Brief summary of what happened (e.g., "Created work with 4 tasks, set due dates")
        what_went_well: Things that worked well (e.g., "User confirmed quickly, clear breakdown")
        what_could_improve: Areas for improvement (e.g., "Asked too many confirmation questions")
        user_satisfaction: Estimated satisfaction - "Low", "Medium", or "High"
        context_tags: List of context tags like ["work_creation", "due_dates", "publishing"]
        
    Returns:
        {"feedback_id": id, "logged": True}
        
    Example:
        tool_log_conversation_feedback(
            conversation_summary="Created work 'Build landing page' with 4 tasks and published",
            what_went_well="User provided clear requirements, smooth due date confirmation",
            what_could_improve="Could have combined the persist and publish confirmations",
            user_satisfaction="High",
            context_tags=["work_creation", "due_dates", "publishing"]
        )
    """
    feedback_id = agent_api.record_conversation_feedback(
        conversation_summary=conversation_summary,
        what_went_well=what_went_well,
        what_could_improve=what_could_improve,
        user_satisfaction=user_satisfaction,
        tags=context_tags
    )
    
    if feedback_id:
        return {"feedback_id": feedback_id, "logged": True}
    return {"error": "failed to log feedback"}


def tool_get_learning_context() -> Dict[str, Any]:
    """Retrieve accumulated learning insights to inform current behavior.
    
    Call this at the start of complex interactions (like work creation) to get
    behavior adjustments from past feedback. Use the insights to optimize your approach.
    
    Returns:
        {
            "has_learning": True/False,
            "summaries": [list of learning period summaries],
            "combined_adjustments": "formatted text with all behavior adjustments",
            "total_summaries": count
        }
        
    Example Response:
        {
            "has_learning": True,
            "combined_adjustments": "Learning Period 1:\n- Ask fewer confirmation questions...",
            "total_summaries": 2
        }
    """
    learning_context = agent_api.get_learning_insights()
    return learning_context


def tool_generate_behavior_summary(days: int = 7) -> Dict[str, Any]:
    """Generate a new learning summary from recent feedback logs.
    
    Analyzes feedback from the past N days to identify patterns and generate
    behavior adjustments. This is typically called periodically (weekly) or when
    requested by a user/admin.
    
    Args:
        days: Number of days of feedback to analyze (default: 7)
        
    Returns:
        {"summary_id": id, "generated": True, "conversations_analyzed": count}
    """
    summary_id = agent_api.generate_and_apply_learning_summary(days)
    
    if summary_id:
        from core.feedback import get_recent_feedback
        recent = get_recent_feedback(days=days)
        return {
            "summary_id": summary_id,
            "generated": True,
            "conversations_analyzed": len(recent)
        }
    return {"error": "no feedback to analyze or generation failed"}


# Registry of tools the agent can call
TOOLS = {
    # Task generation
    'generate_subtasks': tool_generate_subtasks,
    'refine_subtasks': tool_refine_subtasks,
    
    # Work management
    'create_work': tool_create_work,
    'publish_work': tool_publish_work,
    'get_work': tool_get_work,
    'list_works': tool_list_works,
    'complete_work': tool_complete_work,
    
    # Task management
    'create_task': tool_create_task,
    'list_tasks': tool_list_tasks,
    'get_today_tasks': tool_get_today_tasks,
    'get_weekly_status': tool_get_weekly_status,
    'get_overdue_tasks': tool_get_overdue_tasks,
    'update_task_status': tool_update_task_status,
    'complete_task_and_schedule_next': tool_complete_task_and_schedule_next,
    'snooze_task': tool_snooze_task,
    'reschedule_task_event': tool_reschedule_task_event,
    'propose_due_dates': tool_propose_due_dates,
    'confirm_due_dates': tool_confirm_due_dates,
    
    # Calendar/Google Tasks
    'schedule_task_to_calendar': tool_schedule_task_to_calendar,
    'schedule_first_untracked_task': tool_schedule_first_untracked_task,
    'list_upcoming_events': tool_list_upcoming_events,
    'sync_event_update': tool_sync_event_update,
    
    # Slack notifications
    'send_slack_message': tool_send_slack_message,
    'send_due_date_confirmation': tool_send_due_date_confirmation,
    'notify_task_completed': tool_notify_task_completed,
    'notify_work_completed': tool_notify_work_completed,
    'grouped_work_alert': tool_grouped_work_alert,
    'daily_planner_digest': tool_daily_planner_digest,
    
    # Celery async
    'queue_celery_task': tool_queue_celery_task,
    
    # Learning & feedback
    'log_conversation_feedback': tool_log_conversation_feedback,
    'get_learning_context': tool_get_learning_context,
    'generate_behavior_summary': tool_generate_behavior_summary,
}
