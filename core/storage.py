"""Storage layer with filtered query operations.

Consolidates CRUD operations from db.py with agent-friendly filtering
for work items and tasks by status.
"""

from typing import List, Optional, Generator
from contextlib import contextmanager
from datetime import datetime

from db import (
    SessionLocal, Work, Task,
    create_work as db_create_work,
    create_task as db_create_task,
    get_work as db_get_work,
    publish_work as db_publish_work,
    complete_work as db_complete_work,
    update_task_status as db_update_task_status,
    update_task_calendar_event as db_update_task_calendar_event,
    increment_task_snooze as db_increment_task_snooze,
)
from .work import WorkStatus
from .task import TaskStatus


@contextmanager
def get_session() -> Generator:
    """Context manager for database sessions.
    
    Note: Objects returned from queries will be expired after the session closes.
    Use session.expunge_all() before returning if you need to use objects after session close.
    """
    session = SessionLocal()
    try:
        yield session
        # Expunge all objects from session to make them usable after close
        # This prevents DetachedInstanceError when accessing attributes later
        session.expunge_all()
    finally:
        session.close()


# ===== Work Operations =====

def list_works(status: Optional[WorkStatus] = None, include_tasks: bool = False) -> List[Work]:
    """List work items with optional status filtering.
    
    Args:
        status: Filter by work status (None returns all)
        include_tasks: Whether to eagerly load tasks relationship
        
    Returns:
        List of Work objects matching criteria
    """
    with get_session() as session:
        query = session.query(Work)
        
        if status:
            query = query.filter(Work.status == str(status))
        
        if include_tasks:
            from sqlalchemy.orm import joinedload
            query = query.options(joinedload(Work.tasks))
        
        query = query.order_by(Work.created_at.desc())
        return query.all()


def get_work_by_id(work_id: int, include_tasks: bool = True) -> Optional[Work]:
    """Fetch a single work item by ID.
    
    Args:
        work_id: Work item ID
        include_tasks: Whether to eagerly load tasks
        
    Returns:
        Work object or None if not found
    """
    with get_session() as session:
        query = session.query(Work)
        
        if include_tasks:
            from sqlalchemy.orm import joinedload
            query = query.options(joinedload(Work.tasks))
        
        return query.filter(Work.id == work_id).first()


def create_work(title: str, description: str, tasks: Optional[List[dict]] = None, 
                status: WorkStatus = WorkStatus.DRAFT) -> Work:
    """Create a new work item with optional tasks.
    
    Args:
        title: Work title
        description: Work description
        tasks: List of task dicts with 'title', 'status', 'due_date' keys
        status: Initial work status
        
    Returns:
        Created Work object
    """
    with get_session() as session:
        work = db_create_work(session, title, description, tasks, str(status))
        session.refresh(work)
        return work


def update_work_status(work_id: int, new_status: WorkStatus) -> Optional[Work]:
    """Update work item status.
    
    Args:
        work_id: Work item ID
        new_status: New status to set
        
    Returns:
        Updated Work object or None if not found
    """
    with get_session() as session:
        if new_status == WorkStatus.PUBLISHED:
            work = db_publish_work(session, work_id)
        elif new_status == WorkStatus.COMPLETED:
            work = db_complete_work(session, work_id)
        else:
            work = db_get_work(session, work_id)
            if work:
                work.status = str(new_status)
                session.commit()
        
        # Refresh to ensure all attributes are loaded before session.expunge_all()
        if work:
            session.refresh(work)
        return work


# ===== Task Operations =====

def list_tasks(work_id: Optional[int] = None, status: Optional[TaskStatus] = None,
               due_before: Optional[datetime] = None, due_after: Optional[datetime] = None,
               exclude_completed: bool = False) -> List[Task]:
    """List tasks with flexible filtering.
    
    Args:
        work_id: Filter by work item (None returns all tasks)
        status: Filter by task status
        due_before: Filter tasks due before this datetime
        due_after: Filter tasks due after this datetime
        exclude_completed: Quick filter to exclude completed tasks
        
    Returns:
        List of Task objects matching criteria
    """
    with get_session() as session:
        from sqlalchemy.orm import joinedload
        query = session.query(Task).options(joinedload(Task.work))
        
        if work_id is not None:
            query = query.filter(Task.work_id == work_id)
        
        if status:
            query = query.filter(Task.status == str(status))
        
        if exclude_completed:
            query = query.filter(Task.status != str(TaskStatus.COMPLETED))
        
        if due_before:
            query = query.filter(Task.due_date < due_before)
        
        if due_after:
            query = query.filter(Task.due_date >= due_after)
        
        query = query.order_by(Task.due_date.asc().nullsfirst(), Task.created_at.asc())
        return query.all()


def get_task_by_id(task_id: int) -> Optional[Task]:
    """Fetch a single task by ID with work relationship loaded."""
    with get_session() as session:
        from sqlalchemy.orm import joinedload
        return session.query(Task).options(joinedload(Task.work)).filter(Task.id == task_id).first()


def get_task_by_calendar_id(calendar_event_id: str) -> Optional[Task]:
    """Fetch a task by its Google Calendar/Tasks event ID."""
    with get_session() as session:
        from sqlalchemy.orm import joinedload
        return session.query(Task).options(joinedload(Task.work)).filter(
            Task.calendar_event_id == calendar_event_id
        ).first()


def create_task(work_id: int, title: str, status: TaskStatus = TaskStatus.DRAFT,
                due_date: Optional[datetime] = None) -> Task:
    """Create a new task for a work item.
    
    Args:
        work_id: Parent work item ID
        title: Task title
        status: Initial task status
        due_date: Optional due date
        
    Returns:
        Created Task object
    """
    with get_session() as session:
        task = db_create_task(session, work_id, title, str(status), due_date)
        session.refresh(task)
        return task


def update_task_status(task_id: int, new_status: TaskStatus) -> Optional[Task]:
    """Update task status.
    
    Args:
        task_id: Task ID
        new_status: New status to set
        
    Returns:
        Updated Task object or None if not found
    """
    with get_session() as session:
        return db_update_task_status(session, task_id, str(new_status))


def update_task_due_date(task_id: int, due_date: datetime) -> Optional[Task]:
    """Update task due date.
    
    Args:
        task_id: Task ID
        due_date: New due date
        
    Returns:
        Updated Task object or None if not found
    """
    with get_session() as session:
        task = session.query(Task).filter(Task.id == task_id).first()
        if task:
            task.due_date = due_date
            session.commit()
            session.refresh(task)
        return task


def update_task_calendar_event(task_id: int, event_id: str) -> Optional[Task]:
    """Update task's calendar event ID.
    
    Args:
        task_id: Task ID
        event_id: Google Calendar/Tasks event ID
        
    Returns:
        Updated Task object or None if not found
    """
    with get_session() as session:
        return db_update_task_calendar_event(session, task_id, event_id)


def increment_task_snooze(task_id: int) -> Optional[Task]:
    """Increment task snooze counter.
    
    Args:
        task_id: Task ID
        
    Returns:
        Updated Task object or None if not found
    """
    with get_session() as session:
        return db_increment_task_snooze(session, task_id)


def get_today_tasks() -> List[Task]:
    """Get all non-completed tasks due today."""
    from datetime import date
    today = date.today()
    with get_session() as session:
        from sqlalchemy.orm import joinedload
        from sqlalchemy import func, Date, cast
        return session.query(Task).options(joinedload(Task.work)).filter(
            cast(Task.due_date, Date) == today,
            Task.status != str(TaskStatus.COMPLETED)
        ).all()
