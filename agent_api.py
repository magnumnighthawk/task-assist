"""Agent API facade for task management operations.

Provides high-level, agent-friendly functions that combine core modules
for common workflows: listing works/tasks by status, managing due dates,
completing tasks, sending notifications, and syncing with Google Tasks.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date

from db import Work, Task
from core.work import WorkStatus
from core.task import TaskStatus
from core.storage import (
    list_works, list_tasks, get_work_by_id, get_task_by_id,
    create_work, create_task, update_work_status, update_task_status,
    get_today_tasks
)
from core.slack import get_notifier
from core.tasks_provider import get_provider
from core.scheduling import (
    ensure_task_scheduled, complete_task_and_schedule_next,
    sync_from_google_tasks, delete_task_from_calendar
)
from core.due_dates import DueDateManager, bulk_set_due_dates

logger = logging.getLogger(__name__)


# ===== Work Listing & Management =====

def list_works_by_status(status: str) -> List[Dict[str, Any]]:
    """List work items filtered by status.
    
    Args:
        status: Status filter - 'draft', 'published', 'completed', 'in_progress' (alias for published), or 'all'
        
    Returns:
        List of work dictionaries with basic info
    """
    # Map common aliases
    status_map = {
        'in_progress': 'published',
        'active': 'published',
        'done': 'completed',
        'all': None
    }
    
    status_key = status_map.get(status.lower(), status.lower())
    
    if status_key:
        work_status = WorkStatus.from_string(status_key)
        works = list_works(status=work_status, include_tasks=True)
    else:
        works = list_works(include_tasks=True)
    
    result = []
    for work in works:
        task_count = len(work.tasks) if hasattr(work, 'tasks') else 0
        completed_count = sum(1 for t in work.tasks if t.status == str(TaskStatus.COMPLETED)) if hasattr(work, 'tasks') else 0
        
        result.append({
            'id': work.id,
            'title': work.title,
            'description': work.description,
            'status': work.status,
            'created_at': work.created_at.isoformat() if work.created_at else None,
            'task_count': task_count,
            'completed_tasks': completed_count,
            'progress': f"{completed_count}/{task_count}" if task_count > 0 else "0/0"
        })
    
    return result


def compute_work_snooze_count(work) -> int:
    """Compute total snooze count for a work item from its tasks.
    
    Args:
        work: Work object with tasks relationship loaded
        
    Returns:
        Sum of all task snooze counts
    """
    if not hasattr(work, 'tasks'):
        return 0
    return sum(task.snooze_count for task in work.tasks)


def get_work_details(work_id: int) -> Optional[Dict[str, Any]]:
    """Get detailed information about a work item including all tasks.
    
    Args:
        work_id: Work item ID
        
    Returns:
        Work dictionary with tasks or None if not found
    """
    work = get_work_by_id(work_id, include_tasks=True)
    if not work:
        return None
    
    tasks = []
    if hasattr(work, 'tasks'):
        for task in work.tasks:
            tasks.append({
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'order_index': task.order_index,
                'priority': task.priority,
                'status': task.status,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'snooze_count': task.snooze_count,
                'has_calendar_event': bool(task.calendar_event_id),
                'calendar_event_id': task.calendar_event_id
            })
    
    return {
        'id': work.id,
        'title': work.title,
        'description': work.description,
        'status': work.status,
        'expected_completion_hint': work.expected_completion_hint,
        'created_at': work.created_at.isoformat() if work.created_at else None,
        'snooze_count': compute_work_snooze_count(work),
        'tasks': tasks
    }


def get_recently_completed_works(days: int = 7) -> List[Dict[str, Any]]:
    """List works completed within the last N days.
    
    Args:
        days: Number of days to look back
        
    Returns:
        List of completed work dictionaries
    """
    completed_works = list_works(status=WorkStatus.COMPLETED, include_tasks=True)
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    recent = []
    for work in completed_works:
        # Filter by completion (approximated by created_at for now, could add completed_at field)
        if work.created_at and work.created_at >= cutoff:
            task_count = len(work.tasks) if hasattr(work, 'tasks') else 0
            recent.append({
                'id': work.id,
                'title': work.title,
                'status': work.status,
                'task_count': task_count,
                'created_at': work.created_at.isoformat()
            })
    
    return recent


def get_upcoming_works() -> List[Dict[str, Any]]:
    """List published works with upcoming tasks.
    
    Returns:
        List of work dictionaries with next task info
    """
    works = list_works(status=WorkStatus.PUBLISHED, include_tasks=True)
    
    result = []
    for work in works:
        if not hasattr(work, 'tasks') or not work.tasks:
            continue
        
        # Find next incomplete task
        incomplete_tasks = [t for t in work.tasks if t.status != str(TaskStatus.COMPLETED)]
        if not incomplete_tasks:
            continue
        
        # Sort by due date
        incomplete_tasks.sort(key=lambda t: t.due_date if t.due_date else datetime.max)
        next_task = incomplete_tasks[0]
        
        result.append({
            'id': work.id,
            'title': work.title,
            'status': work.status,
            'next_task': {
                'id': next_task.id,
                'title': next_task.title,
                'due_date': next_task.due_date.isoformat() if next_task.due_date else None
            },
            'remaining_tasks': len(incomplete_tasks)
        })
    
    return result


# ===== Task Listing & Management =====

def list_tasks_by_status(status: str, work_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """List tasks filtered by status.
    
    Args:
        status: Status filter - 'draft', 'published', 'tracked', 'completed', 'active' (tracked), or 'all'
        work_id: Optional work ID to filter by
        
    Returns:
        List of task dictionaries
    """
    # Map common aliases
    status_map = {
        'active': 'tracked',
        'in_progress': 'tracked',
        'done': 'completed',
        'all': None
    }
    
    status_key = status_map.get(status.lower(), status.lower())
    
    if status_key:
        task_status = TaskStatus.from_string(status_key)
        tasks = list_tasks(work_id=work_id, status=task_status)
    else:
        tasks = list_tasks(work_id=work_id)
    
    result = []
    for task in tasks:
        work_title = task.work.title if hasattr(task, 'work') else "Unknown"
        
        result.append({
            'id': task.id,
            'title': task.title,
            'status': task.status,
            'work_id': task.work_id,
            'work_title': work_title,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'snooze_count': task.snooze_count,
            'has_calendar_event': bool(task.calendar_event_id)
        })
    
    return result


def get_today_tasks_summary() -> List[Dict[str, Any]]:
    """Get all tasks due today.
    
    Returns:
        List of task dictionaries due today
    """
    tasks = get_today_tasks()
    
    result = []
    for task in tasks:
        work_title = task.work.title if hasattr(task, 'work') else "Unknown"
        
        result.append({
            'id': task.id,
            'title': task.title,
            'status': task.status,
            'work_title': work_title,
            'due_date': task.due_date.isoformat() if task.due_date else None
        })
    
    return result


def get_overdue_tasks() -> List[Dict[str, Any]]:
    """Get all tasks past their due date.
    
    Returns:
        List of overdue task dictionaries
    """
    now = datetime.utcnow()
    tasks = list_tasks(due_before=now, exclude_completed=True)
    
    result = []
    for task in tasks:
        work_title = task.work.title if hasattr(task, 'work') else "Unknown"
        days_overdue = (now - task.due_date).days if task.due_date else 0
        
        result.append({
            'id': task.id,
            'title': task.title,
            'status': task.status,
            'work_title': work_title,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'days_overdue': days_overdue
        })
    
    return result


def get_weekly_tasks_summary(start_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Get all tasks for the current or specified week.
    
    Args:
        start_date: Start of week (defaults to current week Monday)
        
    Returns:
        Dictionary with week info and categorized tasks
    """
    from datetime import timedelta
    
    # Default to current week (Monday to Sunday)
    if start_date is None:
        today = datetime.now()
        # Get Monday of current week (0 = Monday, 6 = Sunday)
        start_date = today - timedelta(days=today.weekday())
    
    # Set to start of day
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=7)
    
    # Get all non-completed tasks in the date range
    tasks = list_tasks(due_after=start_date, due_before=end_date, exclude_completed=False)
    
    # Categorize tasks
    completed = []
    pending = []
    in_progress = []
    
    for task in tasks:
        work_title = task.work.title if hasattr(task, 'work') else "Unknown"
        task_dict = {
            'id': task.id,
            'title': task.title,
            'status': task.status,
            'work_id': task.work_id,
            'work_title': work_title,
            'due_date': task.due_date.isoformat() if task.due_date else None
        }
        
        if task.status.lower() == 'completed':
            completed.append(task_dict)
        elif task.status.lower() == 'tracked':
            in_progress.append(task_dict)
        else:
            pending.append(task_dict)
    
    return {
        'week_start': start_date.strftime('%Y-%m-%d'),
        'week_end': end_date.strftime('%Y-%m-%d'),
        'total_tasks': len(tasks),
        'completed': completed,
        'in_progress': in_progress,
        'draft': pending,
        'completion_rate': f"{len(completed)}/{len(tasks)}" if tasks else "0/0"
    }


# ===== Task Operations =====

def set_task_due_date(task_id: int, due_date: datetime, source: str = "agent") -> bool:
    """Set due date for a task.
    
    Args:
        task_id: Task ID
        due_date: New due datetime
        source: Source of the update
        
    Returns:
        True if set successfully
    """
    manager = DueDateManager()
    return manager.set_due_date(task_id, due_date, source=source)


def snooze_task(task_id: int, days: int = 1) -> bool:
    """Snooze a task by moving its due date forward.
    
    Args:
        task_id: Task ID
        days: Number of days to snooze
        
    Returns:
        True if snoozed successfully
    """
    manager = DueDateManager()
    return manager.snooze_task(task_id, days)


def complete_task_flow(task_id: int) -> bool:
    """Complete a task and schedule the next one in the work.
    
    Args:
        task_id: Task ID to complete
        
    Returns:
        True if completed successfully
    """
    return complete_task_and_schedule_next(task_id)


def mark_task_complete(task_id: int) -> bool:
    """Mark a task as complete (without scheduling next).
    
    Args:
        task_id: Task ID
        
    Returns:
        True if marked successfully
    """
    result = update_task_status(task_id, TaskStatus.COMPLETED)
    if result:
        # Also mark in Google Tasks
        task = get_task_by_id(task_id)
        if task and task.calendar_event_id:
            provider = get_provider()
            provider.complete_task(task.calendar_event_id)
        return True
    return False


def schedule_task_to_calendar(task_id: int) -> bool:
    """Schedule a task to Google Tasks.
    
    Args:
        task_id: Task ID
        
    Returns:
        True if scheduled successfully
    """
    return ensure_task_scheduled(task_id)


def remove_task_from_calendar(task_id: int) -> bool:
    """Remove a task from Google Tasks.
    
    Args:
        task_id: Task ID
        
    Returns:
        True if removed successfully
    """
    return delete_task_from_calendar(task_id)


# ===== Slack Notifications =====

def send_slack_notification(message: str) -> bool:
    """Send a plain text Slack notification.
    
    Args:
        message: Message text
        
    Returns:
        True if sent successfully
    """
    notifier = get_notifier()
    return notifier.send_plain(message)


def send_interactive_due_date_request(work_id: int) -> bool:
    """Send interactive Slack message to set due dates for work tasks.
    
    Args:
        work_id: Work item ID
        
    Returns:
        True if sent successfully
    """
    work = get_work_by_id(work_id, include_tasks=True)
    if not work:
        logger.error(f"Work {work_id} not found")
        return False
    
    notifier = get_notifier()
    return notifier.send_interactive(work)


def send_work_publish_notification(work_id: int) -> bool:
    """Send notification that a work was published.
    
    Args:
        work_id: Work item ID
        
    Returns:
        True if sent successfully
    """
    work = get_work_by_id(work_id, include_tasks=True)
    if not work:
        logger.error(f"Work {work_id} not found")
        return False
    
    # Find the tracked/scheduled task
    calendar_task = None
    if hasattr(work, 'tasks'):
        for task in work.tasks:
            if task.calendar_event_id or task.status == str(TaskStatus.TRACKED):
                calendar_task = task
                break
    
    notifier = get_notifier()
    return notifier.send_publish(work, calendar_task)


def send_daily_reminder() -> bool:
    """Send daily reminder of today's tasks.
    
    Returns:
        True if sent successfully
    """
    tasks = get_today_tasks()
    notifier = get_notifier()
    return notifier.send_daily_reminder(tasks)


# ===== Calendar/Tasks Sync =====

def fetch_calendar_tasks() -> List[Dict[str, Any]]:
    """Fetch upcoming tasks from Google Tasks.
    
    Returns:
        List of task dictionaries from Google Tasks
    """
    provider = get_provider()
    google_tasks = provider.list_upcoming_tasks(max_results=20)
    
    result = []
    for gtask in google_tasks:
        result.append({
            'id': gtask.get('id'),
            'title': gtask.get('title'),
            'due': gtask.get('due'),
            'status': gtask.get('status'),
            'notes': gtask.get('notes')
        })
    
    return result


def sync_task_from_calendar(task_id: int) -> bool:
    """Sync a task's state from Google Tasks to database.
    
    Args:
        task_id: Task ID
        
    Returns:
        True if synced successfully
    """
    return sync_from_google_tasks(task_id)


# ===== Workflow Helpers =====

def publish_work_flow(work_id: int, schedule_first_task: bool = True) -> bool:
    """Publish a work item and optionally schedule its first task.
    
    Args:
        work_id: Work item ID
        schedule_first_task: Whether to schedule the first task to calendar
        
    Returns:
        True if published successfully
    """
    # Update work status
    work = update_work_status(work_id, WorkStatus.PUBLISHED)
    if not work:
        logger.error(f"Failed to publish work {work_id}")
        return False
    
    # Schedule first task if requested
    if schedule_first_task:
        # Reload work with tasks to avoid detached instance error
        work = get_work_by_id(work_id, include_tasks=True)
        if work and hasattr(work, 'tasks') and work.tasks:
            first_task = work.tasks[0]
            update_task_status(first_task.id, TaskStatus.TRACKED)
            # Skip notification here since publish notification will include the scheduled task
            ensure_task_scheduled(first_task.id, work.title, skip_notification=True)
    
    # Send publish notification
    send_work_publish_notification(work_id)
    
    logger.info(f"Published work {work_id}")
    return True


def create_work_with_tasks(title: str, description: str, task_data: List[Dict[str, str]],
                           auto_due_dates: bool = False, expected_completion_hint: Optional[str] = None) -> Optional[int]:
    """Create a work item with multiple tasks.
    
    Args:
        title: Work title
        description: Work description
        task_data: List of task dicts with 'title' and optionally 'description' and 'priority'
        auto_due_dates: Whether to auto-assign due dates with spacing
        expected_completion_hint: Optional deadline hint like "this week", "by Friday", etc.
        
    Returns:
        Created work ID or None on failure
    """
    # Create tasks list - support both dict format and string format for backwards compatibility
    tasks = []
    for t in task_data:
        if isinstance(t, dict):
            task_dict = {
                'title': t.get('title', t.get('description', 'Untitled')),
                'description': t.get('description', ''),
                'priority': t.get('priority', 'Medium'),
                'status': str(TaskStatus.DRAFT)
            }
        else:
            # Fallback for string format
            task_dict = {
                'title': str(t),
                'description': '',
                'status': str(TaskStatus.DRAFT)
            }
        tasks.append(task_dict)
    
    # Create work
    work = create_work(title, description, tasks, WorkStatus.DRAFT, expected_completion_hint)
    if not work:
        logger.error("Failed to create work")
        return None
    
    logger.info(f"Created work {work.id} with {len(task_data)} tasks")
    
    # Note: Due dates will be proposed separately for user confirmation
    # Do not auto-assign here
    
    return work.id


def propose_due_dates_for_work(work_id: int, expected_completion_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Generate proposed due dates for user review and confirmation.
    
    Args:
        work_id: Work item ID
        expected_completion_hint: Deadline hint like "this week", "by Friday", etc.
        
    Returns:
        Dict with proposed schedule or None if failed
    """
    from core.due_dates import propose_due_dates
    
    work = get_work_by_id(work_id, include_tasks=True)
    if not work:
        logger.error(f"Work {work_id} not found")
        return None
    
    # Use work's expected_completion_hint if not provided
    hint = expected_completion_hint or work.expected_completion_hint
    
    if not hint:
        logger.warning(f"No deadline hint for work {work_id}")
        return None
    
    return propose_due_dates(work_id, hint)


def confirm_due_dates_for_work(work_id: int, schedule_data: Dict[int, str]) -> bool:
    """Apply user-confirmed due dates to tasks.
    
    Args:
        work_id: Work item ID
        schedule_data: Dict mapping task_id -> 'YYYY-MM-DD' date string
        
    Returns:
        True if all dates applied successfully
    """
    from core.due_dates import confirm_and_apply_due_dates
    
    return confirm_and_apply_due_dates(work_id, schedule_data)


def update_tasks_due_dates_from_slack(due_date_map: Dict[int, str]) -> bool:
    """Update multiple task due dates from Slack interactive response.
    
    Args:
        due_date_map: Dict mapping task_id -> 'YYYY-MM-DD' date string
        
    Returns:
        True if all updated successfully
    """
    datetime_map = {}
    for task_id, date_str in due_date_map.items():
        try:
            # Parse YYYY-MM-DD and set to 8am
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            dt = dt.replace(hour=8, minute=0, second=0, microsecond=0)
            datetime_map[task_id] = dt
        except ValueError:
            logger.error(f"Invalid date format for task {task_id}: {date_str}")
            return False
    
    results = bulk_set_due_dates(datetime_map)
    return all(results.values())
