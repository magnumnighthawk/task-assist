"""Tool wrappers for Agent to call into the application.

Refactored to use agent_api facade for clean, agent-friendly operations.
Each tool delegates to agent_api functions with minimal logic.
"""
from typing import Any, Dict, List, Optional
import logging
from datetime import datetime

from generate import generate_subtasks
import agent_api

logger = logging.getLogger('agent.tools')


def tool_generate_subtasks(task_description: str, max_subtasks: int = 5) -> Dict[str, Any]:
    """
    Generate subtasks for a given task description.
    Args:
        task_description (str): Description of the main task to decompose.
        max_subtasks (int, optional): Maximum number of subtasks to generate (default: 5).
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


def tool_create_work(title: str, description: str = '', tasks: List[Dict[str, str]] = [], status: str = 'Draft', auto_due_dates: bool = False) -> Dict[str, Any]:
    """Create work item with optional tasks.
    
    Args:
        title: Work title
        description: Work description
        tasks: List of task dicts with 'title' and optionally 'description' and 'priority'
        status: Initial status (default: 'Draft')
        auto_due_dates: Whether to auto-assign due dates with spacing
        
    Returns:
        {"id": work_id, "title": work_title}
    """
    work_id = agent_api.create_work_with_tasks(title, description, tasks, auto_due_dates)
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
    
    Args:
        work_id: Work item ID
        schedule_first_task: Whether to schedule first task to calendar
        
    Returns:
        {"published": True, "work_id": id}
    """
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
}
