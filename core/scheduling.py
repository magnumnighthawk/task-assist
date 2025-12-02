"""Task scheduling and calendar synchronization.

Consolidates logic for scheduling tasks to Google Tasks, completing tasks
with automatic next-task scheduling, and managing calendar sync.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from db import Task, Work
from .storage import (
    get_task_by_id, get_work_by_id, update_task_calendar_event,
    update_task_status, list_tasks
)
from .task import TaskStatus
from .tasks_provider import get_provider
from .slack import get_notifier

logger = logging.getLogger(__name__)


def ensure_task_scheduled(task_id: int, work_title: Optional[str] = None) -> bool:
    """Ensure a task has a corresponding Google Tasks entry.
    
    Creates a Google Task if one doesn't exist, or verifies existing one.
    Updates the task's calendar_event_id in the database.
    
    Args:
        task_id: Task ID to schedule
        work_title: Work title for context (fetched if not provided)
        
    Returns:
        True if scheduled successfully, False otherwise
    """
    task = get_task_by_id(task_id)
    if not task:
        logger.error(f"Task {task_id} not found")
        return False
    
    # If already scheduled, verify it exists
    if task.calendar_event_id:
        provider = get_provider()
        existing = provider.get_task(task.calendar_event_id)
        if existing:
            logger.info(f"Task {task_id} already scheduled: {task.calendar_event_id}")
            return True
        else:
            logger.warning(f"Task {task_id} has invalid calendar_event_id, rescheduling")
    
    # Get work context
    if not work_title and hasattr(task, 'work'):
        work_title = task.work.title
    elif not work_title:
        work = get_work_by_id(task.work_id, include_tasks=False)
        work_title = work.title if work else "Unknown"
    
    # Create Google Task
    provider = get_provider()
    title = task.title
    
    # Use task due date, or default to tomorrow 8am if missing
    due = task.due_date if task.due_date else datetime.utcnow() + timedelta(days=1, hours=8)
    
    # Determine status
    status = TaskStatus.from_string(task.status) if task.status else TaskStatus.PUBLISHED
    
    google_task = provider.create_task(
        title=title,
        notes=f"Work: {work_title}",
        due=due,
        status=status
    )
    
    if not google_task:
        logger.error(f"Failed to create Google Task for task {task_id}")
        return False
    
    # Update database with event ID
    event_id = google_task.get('id')
    update_task_calendar_event(task_id, event_id)
    logger.info(f"Scheduled task {task_id} as Google Task {event_id}")
    
    # Send Slack notification
    notifier = get_notifier()
    work = get_work_by_id(task.work_id, include_tasks=False)
    if work:
        notifier.send_event_created(task, work)
    
    return True


def update_task_due_date_in_calendar(task_id: int, new_due: datetime) -> bool:
    """Update a task's due date in both database and Google Tasks.
    
    Args:
        task_id: Task ID
        new_due: New due datetime
        
    Returns:
        True if updated successfully, False otherwise
    """
    task = get_task_by_id(task_id)
    if not task:
        logger.error(f"Task {task_id} not found")
        return False
    
    # Update in Google Tasks if scheduled
    if task.calendar_event_id:
        provider = get_provider()
        result = provider.update_task(task.calendar_event_id, due=new_due)
        if not result:
            logger.warning(f"Failed to update Google Task for task {task_id}")
    
    # Update database (handled by due_dates module, but can be called directly)
    from .storage import update_task_due_date
    updated_task = update_task_due_date(task_id, new_due)
    
    if updated_task:
        logger.info(f"Updated due date for task {task_id} to {new_due}")
        return True
    
    return False


def reschedule_task(task_id: int, new_due: datetime) -> bool:
    """Reschedule a task to a new due date.
    
    Updates both database and Google Tasks.
    
    Args:
        task_id: Task ID
        new_due: New due datetime
        
    Returns:
        True if rescheduled successfully
    """
    return update_task_due_date_in_calendar(task_id, new_due)


def complete_task_and_schedule_next(task_id: int) -> bool:
    """Complete a task and automatically schedule the next task in the work.
    
    Args:
        task_id: Task ID to complete
        
    Returns:
        True if completed successfully
    """
    task = get_task_by_id(task_id)
    if not task:
        logger.error(f"Task {task_id} not found")
        return False
    
    work = get_work_by_id(task.work_id, include_tasks=True)
    if not work:
        logger.error(f"Work {task.work_id} not found for task {task_id}")
        return False
    
    # Mark task as completed in database
    update_task_status(task_id, TaskStatus.COMPLETED)
    
    # Mark as completed in Google Tasks
    if task.calendar_event_id:
        provider = get_provider()
        provider.complete_task(task.calendar_event_id)
    
    logger.info(f"Completed task {task_id}")
    
    # Send notification
    notifier = get_notifier()
    notifier.send_task_completed(task, work)
    
    # Find next incomplete task
    all_tasks = list_tasks(work_id=work.id, exclude_completed=True)
    
    if all_tasks:
        # Schedule first incomplete task
        next_task = all_tasks[0]
        logger.info(f"Scheduling next task {next_task.id} for work {work.id}")
        
        # Set it to tracked status
        update_task_status(next_task.id, TaskStatus.TRACKED)
        
        # Ensure it's scheduled
        ensure_task_scheduled(next_task.id, work.title)
    else:
        # All tasks completed, mark work as completed
        logger.info(f"All tasks completed for work {work.id}, marking work as completed")
        from .storage import update_work_status
        from .work import WorkStatus
        update_work_status(work.id, WorkStatus.COMPLETED)
        
        # Send work completion notification
        notifier.send_work_completed(work)
    
    return True


def sync_from_google_tasks(task_id: int) -> bool:
    """Sync a task's state from Google Tasks to the database.
    
    Args:
        task_id: Task ID to sync
        
    Returns:
        True if synced successfully
    """
    task = get_task_by_id(task_id)
    if not task or not task.calendar_event_id:
        logger.warning(f"Cannot sync task {task_id}: not found or not scheduled")
        return False
    
    provider = get_provider()
    google_task = provider.get_task(task.calendar_event_id)
    
    if not google_task:
        logger.warning(f"Google Task {task.calendar_event_id} not found")
        return False
    
    # Sync status
    google_status = google_task.get('status')
    if google_status == 'completed' and task.status != str(TaskStatus.COMPLETED):
        logger.info(f"Syncing completed status from Google Tasks for task {task_id}")
        update_task_status(task_id, TaskStatus.COMPLETED)
    
    # Sync due date
    if 'due' in google_task:
        try:
            google_due = provider._parse_datetime(google_task['due'])
            if task.due_date != google_due:
                logger.info(f"Syncing due date from Google Tasks for task {task_id}")
                from .storage import update_task_due_date
                update_task_due_date(task_id, google_due)
        except Exception as e:
            logger.warning(f"Failed to parse due date from Google Tasks: {e}")
    
    return True


def delete_task_from_calendar(task_id: int) -> bool:
    """Delete a task's Google Tasks entry.
    
    Args:
        task_id: Task ID
        
    Returns:
        True if deleted successfully
    """
    task = get_task_by_id(task_id)
    if not task or not task.calendar_event_id:
        logger.info(f"Task {task_id} not scheduled or not found, nothing to delete")
        return True
    
    provider = get_provider()
    result = provider.delete_task(task.calendar_event_id)
    
    if result:
        # Clear calendar_event_id in database
        update_task_calendar_event(task_id, None)
        logger.info(f"Deleted Google Task for task {task_id}")
    
    return result
