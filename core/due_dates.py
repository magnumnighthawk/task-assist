"""Due date management and normalization.

Provides centralized API for setting, updating, and managing task due dates
with conflict resolution and snooze logic.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from db import Task
from .storage import (
    get_task_by_id, update_task_due_date as storage_update_due,
    increment_task_snooze as storage_increment_snooze
)
from .scheduling import reschedule_task
from .slack import get_notifier

logger = logging.getLogger(__name__)


class DueDateManager:
    """Centralized manager for task due dates."""
    
    @staticmethod
    def set_due_date(task_id: int, new_due: datetime, source: str = "manual") -> bool:
        """Set a task's due date with source tracking.
        
        Args:
            task_id: Task ID
            new_due: New due datetime
            source: Source of the change (manual, slack, sync, snooze, auto)
            
        Returns:
            True if set successfully
        """
        task = get_task_by_id(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return False
        
        logger.info(f"Setting due date for task {task_id} to {new_due} (source: {source})")
        
        # Update via scheduling module to sync with calendar
        result = reschedule_task(task_id, new_due)
        
        if result:
            logger.info(f"Due date set for task {task_id}")
        
        return result
    
    @staticmethod
    def snooze_task(task_id: int, days: int = 1) -> bool:
        """Snooze a task by moving its due date forward.
        
        Increments snooze counter and sends follow-up notification if
        snoozed 3+ times.
        
        Args:
            task_id: Task ID
            days: Number of days to snooze
            
        Returns:
            True if snoozed successfully
        """
        task = get_task_by_id(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return False
        
        # Calculate new due date
        current_due = task.due_date if task.due_date else datetime.utcnow()
        new_due = current_due + timedelta(days=days)
        
        logger.info(f"Snoozing task {task_id} by {days} days to {new_due}")
        
        # Update due date
        result = DueDateManager.set_due_date(task_id, new_due, source="snooze")
        
        if not result:
            return False
        
        # Increment snooze counter
        storage_increment_snooze(task_id)
        
        # Refresh task to get updated snooze_count
        task = get_task_by_id(task_id)
        
        # Send follow-up notification if snoozed multiple times
        if task and task.snooze_count >= 3:
            from .storage import get_work_by_id
            work = get_work_by_id(task.work_id, include_tasks=False)
            if work:
                notifier = get_notifier()
                notifier.send_snooze_followup(task, work)
        
        return True
    
    @staticmethod
    def normalize_due_date(due: datetime) -> datetime:
        """Normalize a due date (ensure proper timezone, round to day boundary, etc.).
        
        Args:
            due: Due datetime to normalize
            
        Returns:
            Normalized datetime
        """
        # For now, just ensure it's not in the past by more than 1 day
        now = datetime.utcnow()
        if due < now - timedelta(days=1):
            logger.warning(f"Due date {due} is in the past, adjusting to tomorrow")
            return now + timedelta(days=1)
        
        return due
    
    @staticmethod
    def resolve_conflict(task_id: int, local_due: Optional[datetime], 
                        remote_due: Optional[datetime], source: str = "sync") -> Optional[datetime]:
        """Resolve conflicts between local and remote due dates.
        
        Strategy: Most recent update wins. If both exist and differ,
        prefer remote (Google Tasks) as source of truth.
        
        Args:
            task_id: Task ID
            local_due: Due date from local database
            remote_due: Due date from Google Tasks
            source: Source of the conflict
            
        Returns:
            Resolved due date or None
        """
        if not local_due and not remote_due:
            return None
        
        if not local_due:
            logger.info(f"Task {task_id}: Using remote due date {remote_due}")
            return remote_due
        
        if not remote_due:
            logger.info(f"Task {task_id}: Using local due date {local_due}")
            return local_due
        
        # Both exist - check if they differ
        if abs((local_due - remote_due).total_seconds()) < 60:
            # Within 1 minute - consider them the same
            return local_due
        
        # Different - prefer remote as source of truth for syncs
        if source == "sync":
            logger.info(f"Task {task_id}: Conflict resolved, using remote due date {remote_due}")
            return remote_due
        else:
            logger.info(f"Task {task_id}: Conflict resolved, using local due date {local_due}")
            return local_due


def bulk_set_due_dates(task_due_map: dict) -> dict:
    """Set due dates for multiple tasks at once.
    
    Args:
        task_due_map: Dict mapping task_id -> datetime
        
    Returns:
        Dict mapping task_id -> success boolean
    """
    results = {}
    manager = DueDateManager()
    
    for task_id, due_date in task_due_map.items():
        results[task_id] = manager.set_due_date(task_id, due_date, source="bulk")
    
    return results


def auto_assign_due_dates(work_id: int, start_date: Optional[datetime] = None,
                          spacing_days: int = 1) -> bool:
    """Auto-assign due dates to tasks in a work item with even spacing.
    
    Args:
        work_id: Work item ID
        start_date: Starting date (defaults to tomorrow)
        spacing_days: Days between each task
        
    Returns:
        True if assigned successfully
    """
    from .storage import list_tasks, get_work_by_id
    
    work = get_work_by_id(work_id, include_tasks=True)
    if not work:
        logger.error(f"Work {work_id} not found")
        return False
    
    tasks = list_tasks(work_id=work_id, exclude_completed=True)
    if not tasks:
        logger.info(f"No tasks to assign due dates for work {work_id}")
        return True
    
    # Start from tomorrow if not specified
    if not start_date:
        start_date = datetime.utcnow() + timedelta(days=1)
        # Set to 8am
        start_date = start_date.replace(hour=8, minute=0, second=0, microsecond=0)
    
    manager = DueDateManager()
    current_date = start_date
    
    for task in tasks:
        if not task.due_date:  # Only assign if not already set
            logger.info(f"Auto-assigning due date {current_date} to task {task.id}")
            manager.set_due_date(task.id, current_date, source="auto")
            current_date += timedelta(days=spacing_days)
    
    logger.info(f"Auto-assigned due dates for work {work_id}")
    return True
