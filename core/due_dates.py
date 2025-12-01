"""Due date management and normalization.

Provides centralized API for setting, updating, and managing task due dates
with conflict resolution and snooze logic.
"""

import logging
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI

from db import Task
from .storage import (
    get_task_by_id, update_task_due_date as storage_update_due,
    increment_task_snooze as storage_increment_snooze
)
from .scheduling import reschedule_task
from .slack import get_notifier

load_dotenv()
logger = logging.getLogger(__name__)
openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))


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








def llm_assign_due_dates(tasks: List[Task], expected_completion_hint: Optional[str], 
                        current_date: datetime) -> Dict[int, datetime]:
    """Use LLM to intelligently assign due dates based on task difficulty and context.
    
    Args:
        tasks: List of Task objects to assign due dates for
        expected_completion_hint: Deadline hint like "this week", "by Friday", "in 3 days"
        current_date: Current datetime for reference
        
    Returns:
        Dict mapping task_id -> assigned due datetime
    """
    # Prepare task data for LLM
    task_info = []
    for task in tasks:
        task_info.append({
            "id": task.id,
            "title": task.title,
            "description": task.description or "",
            "priority": task.priority
        })
    
    current_date_str = current_date.strftime("%Y-%m-%d %A")
    
    system_prompt = (
        "You are an expert project planner and task scheduler. "
        "Given a list of tasks, analyze each task's title, description, and priority to estimate "
        "the realistic time and effort required. Then assign appropriate due dates that:\n"
        "1. Consider the difficulty and time required for each task\n"
        "2. Respect the overall deadline/completion hint\n"
        "3. Schedule harder/longer tasks earlier to avoid last-minute crunches\n"
        "4. Prioritize High priority tasks to be done sooner\n"
        "5. Allow reasonable time for each task (don't over-schedule)\n"
        "6. Prefer weekdays (Mon-Fri) over weekends when possible\n"
        "7. Consider dependencies (e.g., research before implementation)\n\n"
        "Return a JSON object with a 'schedule' array where each item has:\n"
        "- task_id: the task ID (integer)\n"
        "- due_date: assigned date in YYYY-MM-DD format\n"
        "- reasoning: brief explanation of why this date makes sense\n\n"
        "Be realistic about time estimates. Most tasks take longer than expected."
    )
    
    user_prompt = (
        f"Current date: {current_date_str}\n"
        f"Expected completion: {expected_completion_hint or 'No specific deadline'}\n\n"
        f"Tasks to schedule:\n{json.dumps(task_info, indent=2)}\n\n"
        "Please provide a realistic schedule for these tasks in JSON format."
    )
    
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = openai_client.chat.completions.create(
            model=os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo'),
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        logger.info(f"LLM schedule response: {json.dumps(result, indent=2)}")
        
        # Parse the schedule
        schedule = {}
        for item in result.get('schedule', []):
            task_id = item.get('task_id')
            due_date_str = item.get('due_date')
            reasoning = item.get('reasoning', '')
            
            if task_id and due_date_str:
                try:
                    # Parse date and set to 8am
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
                    due_date = due_date.replace(hour=8, minute=0, second=0, microsecond=0)
                    schedule[task_id] = due_date
                    logger.info(f"Task {task_id}: {due_date_str} - {reasoning}")
                except ValueError as e:
                    logger.error(f"Invalid date format from LLM: {due_date_str}")
        
        return schedule
        
    except Exception as e:
        logger.error(f"Error calling LLM for due date assignment: {e}")
        return {}


def propose_due_dates(work_id: int, expected_completion_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Generate proposed due dates using LLM without persisting them.
    
    Uses AI to analyze task difficulty, complexity, and context to propose realistic due dates.
    Returns the proposal for user review and confirmation.
    
    Args:
        work_id: Work item ID
        expected_completion_hint: Deadline hint like "this week", "by Friday", "in 3 days"
        
    Returns:
        Dict with 'schedule' (list of {task_id, task_title, due_date, reasoning}) or None if failed
    """
    from .storage import list_tasks, get_work_by_id
    
    work = get_work_by_id(work_id, include_tasks=True)
    if not work:
        logger.error(f"Work {work_id} not found")
        return None
    
    tasks = list_tasks(work_id=work_id, exclude_completed=True)
    if not tasks:
        logger.info(f"No tasks to assign due dates for work {work_id}")
        return {'schedule': []}
    
    # Filter out tasks that already have due dates
    tasks_to_schedule = [t for t in tasks if not t.due_date]
    if not tasks_to_schedule:
        logger.info(f"All tasks already have due dates for work {work_id}")
        return {'schedule': []}
    
    now = datetime.utcnow()
    
    # Use LLM to generate schedule
    logger.info(f"Using LLM to propose due dates for {len(tasks_to_schedule)} tasks")
    schedule = llm_assign_due_dates(tasks_to_schedule, expected_completion_hint, now)
    
    if not schedule:
        logger.error(f"LLM failed to generate schedule")
        return None
    
    # Build response with task details
    result = []
    for task in tasks_to_schedule:
        if task.id in schedule:
            result.append({
                'task_id': task.id,
                'task_title': task.title,
                'due_date': schedule[task.id].strftime('%Y-%m-%d'),
                'due_date_formatted': schedule[task.id].strftime('%A, %B %d, %Y')
            })
    
    return {'schedule': result, 'work_id': work_id}


def confirm_and_apply_due_dates(work_id: int, schedule_data: Dict[int, str]) -> bool:
    """Apply confirmed due dates to tasks.
    
    Args:
        work_id: Work item ID
        schedule_data: Dict mapping task_id -> 'YYYY-MM-DD' date string
        
    Returns:
        True if all dates applied successfully
    """
    from .storage import get_work_by_id
    
    work = get_work_by_id(work_id, include_tasks=True)
    if not work:
        logger.error(f"Work {work_id} not found")
        return False
    
    manager = DueDateManager()
    success_count = 0
    now = datetime.utcnow()
    
    for task_id, date_str in schedule_data.items():
        try:
            # Parse date and set to 8am
            due_date = datetime.strptime(date_str, '%Y-%m-%d')
            due_date = due_date.replace(hour=8, minute=0, second=0, microsecond=0)
            
            # Ensure date is in the future
            if due_date < now:
                logger.warning(f"Due date {due_date} is in the past, adjusting to tomorrow")
                due_date = now + timedelta(days=1)
                due_date = due_date.replace(hour=8, minute=0, second=0, microsecond=0)
            
            if manager.set_due_date(task_id, due_date, source="user_confirmed"):
                success_count += 1
            else:
                logger.error(f"Failed to set due date for task {task_id}")
        except ValueError as e:
            logger.error(f"Invalid date format for task {task_id}: {date_str} - {e}")
    
    logger.info(f"Successfully applied {success_count}/{len(schedule_data)} due dates for work {work_id}")
    return success_count == len(schedule_data)
