"""Tool wrappers for Agent to call into the application.

Each tool is a simple function accepting keyword args and returning JSON-serializable results.
Keep wrappers minimal and side-effecting where appropriate (e.g., creating work, publishing, sending notifications).
"""
from typing import Any, Dict, List, Optional
import logging
import os
from db import (
    get_db,
    create_work,
    publish_work,
    get_work,
    get_tasks_by_work,
    complete_work,
    update_task_status,
    increment_task_snooze,
    mark_task_notified,
    mark_work_notified,
    create_task,
)
from generate import generate_subtasks
from reminder import ReminderAgent

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


def tool_create_work(title: str, description: str = '', tasks: List[str] = [], status: str = 'Draft') -> Dict[str, Any]:
    """
    Create work item and insert into the database.
    Args:
        title (str): Title of the work item.
        description (str, optional): Detailed description of the work.
        tasks (list, optional): List of initial tasks for the work.
        status (str, optional): Initial status (default: 'Draft').
    Example:
        tool_create_work(title="Build dashboard", description="Create a dashboard for Q4 metrics", tasks=["Design UI", "Connect database"], status="Draft")
    Response:
        {
            "id": 123,
            "title": "Build dashboard"
        }
    """
    db_gen = get_db()
    db = next(db_gen)
    try:
        # Convert list of strings to list of dicts with 'title' key
        task_dicts = [{'title': t} for t in tasks] if tasks else []
        work = create_work(db, title=title, description=description, tasks=task_dicts, status=status)
        return {'id': work.id, 'title': work.title}
    finally:
        db.close()


def tool_create_task(work_id: int, title: str, status: str = 'Draft', due_date: Optional[str] = None) -> Dict[str, Any]:
    """Create a single task under an existing work.
    Args:
        work_id (int): Parent work ID.
        title (str): Task title.
        status (str): Initial status (default Draft).
        due_date (str): ISO date/time string (optional).
    Response: {"task_id": <int>, "title": <str>}
    """
    from datetime import datetime
    db_gen = get_db()
    db = next(db_gen)
    try:
        parsed_due = None
        if due_date:
            try:
                parsed_due = datetime.fromisoformat(due_date)
            except Exception:
                parsed_due = None
        task = create_task(db, work_id=work_id, title=title, status=status, due_date=parsed_due)
        return {"task_id": task.id, "title": task.title, "status": task.status, "due_date": str(task.due_date)}
    finally:
        db.close()


def tool_publish_work(work_id: int) -> Dict[str, Any]:
    """
    Publish a work item and send notifications.
    Args:
        work_id (int): ID of the work item to publish.
    Example:
        tool_publish_work(work_id=123)
    Response:
        {
            "published": True,
            "work_id": 123
        }
    """
    db_gen = get_db()
    db = next(db_gen)
    try:
        work = publish_work(db, work_id)
        # Use ReminderAgent to send notification and potentially create calendar tasks
        try:
            agent = ReminderAgent()
            try:
                # Use the agent helper if the Slack webhook is configured
                if getattr(agent, 'slack_webhook_url', None):
                    agent.send_publish_work_notification(work, agent.slack_webhook_url)
                else:
                    # Fallback to slack_interactive helper if available
                    try:
                        from slack_interactive import send_publish_work_notification as _send_pub
                        _send_pub(work, os.getenv('SLACK_WEBHOOK_URL'))
                    except Exception:
                        logger.debug('No slack helper available for publish notification')
            except Exception:
                logger.exception('Failed to send publish notification via agent')
        except Exception:
            logger.exception('Failed to initialize ReminderAgent for publish notification')
        return {'published': True, 'work_id': work.id}
    finally:
        db.close()


def tool_send_due_date_confirmation(work_id: int) -> Dict[str, Any]:
    """Trigger interactive Slack due-date confirmation for a work.
    Response: {"sent": True, "work_id": id}
    """
    try:
        from reminder import ReminderAgent
        from db import get_db, Work
        from sqlalchemy.orm import joinedload
        db_gen = get_db()
        db = next(db_gen)
        try:
            work = db.query(Work).options(joinedload(Work.tasks)).filter(Work.id == work_id).first()
        finally:
            db.close()
        if not work:
            return {"error": "work not found"}
        agent = ReminderAgent()
        agent.send_interactive_work_notification(work)
        return {"sent": True, "work_id": work_id}
    except Exception as e:
        logger.exception('Failed to send due date confirmation')
        return {"error": str(e)}


def tool_schedule_first_untracked_task(work_id: int) -> Dict[str, Any]:
    """Schedule the first task without 'Tracked' or 'Completed' status for a work.
    Sets task status to Tracked after scheduling. Returns event info.
    """
    from db import get_db, Task
    db_gen = get_db()
    db = next(db_gen)
    try:
        tasks = db.query(Task).filter(Task.work_id == work_id).order_by(Task.id.asc()).all()
        target = next((t for t in tasks if t.status not in ('Tracked', 'Completed')), None)
        if not target:
            return {"error": "no schedulable task"}
        agent = ReminderAgent()
        if not getattr(agent, 'service', None) and not getattr(agent, 'creds', None):
            return {"error": "google credentials not configured"}
        event = agent.create_event_for_task(target, target.work.title if target.work else 'Work')
        update_task_status(db, target.id, 'Tracked')
        return {"scheduled_task_id": target.id, "event": event}
    finally:
        db.close()


def tool_update_task_status(task_id: int, status: str) -> Dict[str, Any]:
    db_gen = get_db()
    db = next(db_gen)
    try:
        task = update_task_status(db, task_id, status)
        if not task:
            return {"error": "task not found"}
        return {"task_id": task.id, "status": task.status}
    finally:
        db.close()


def tool_complete_task_and_schedule_next(task_id: int) -> Dict[str, Any]:
    """Complete a task and schedule the next pending one if any."""
    from db import Task
    db_gen = get_db()
    db = next(db_gen)
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"error": "task not found"}
        agent = ReminderAgent()
        agent.complete_task_and_schedule_next(task, task.work)
        return {"completed_task_id": task_id, "work_id": task.work_id}
    finally:
        db.close()


def tool_snooze_task(task_id: int, days: int = 1) -> Dict[str, Any]:
    from db import Task
    db_gen = get_db()
    db = next(db_gen)
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"error": "task not found"}
        agent = ReminderAgent()
        agent.snooze_task(task, task.work, days=days)
        return {"task_id": task_id, "snoozed_days": days, "snooze_count": task.snooze_count}
    finally:
        db.close()


def tool_reschedule_task_event(task_id: int, new_due: str) -> Dict[str, Any]:
    """Reschedule a tracked task event to a new due datetime (ISO)."""
    from datetime import datetime, timedelta
    from db import Task
    db_gen = get_db()
    db = next(db_gen)
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task or not task.calendar_event_id:
            return {"error": "task or event not found"}
        try:
            parsed_due = datetime.fromisoformat(new_due)
        except Exception:
            return {"error": "invalid new_due format"}
        agent = ReminderAgent()
        start_iso = parsed_due.isoformat()
        end_iso = (parsed_due + timedelta(hours=1)).isoformat()
        agent.reschedule_event(task.calendar_event_id, start_iso, end_iso)
        task.due_date = parsed_due
        db.commit()
        return {"task_id": task_id, "new_due": str(task.due_date)}
    finally:
        db.close()


def tool_list_upcoming_events(max_results: int = 10) -> Dict[str, Any]:
    try:
        agent = ReminderAgent()
        events = agent.list_upcoming_events(max_results=max_results)
        return {"upcoming": events}
    except Exception as e:
        logger.exception('Failed to list upcoming events')
        return {"error": str(e)}


def tool_sync_event_update(event_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    try:
        agent = ReminderAgent()
        agent.sync_event_update_to_db(event_id, updates)
        return {"synced": True, "event_id": event_id}
    except Exception as e:
        logger.exception('Failed to sync event update')
        return {"error": str(e)}


def tool_notify_task_completed(task_id: int) -> Dict[str, Any]:
    from db import Task
    db_gen = get_db()
    db = next(db_gen)
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"error": "task not found"}
        agent = ReminderAgent()
        agent.notify_task_completed(task, task.work)
        mark_task_notified(db, task.id)
        return {"notified_task_id": task_id}
    finally:
        db.close()


def tool_notify_work_completed(work_id: int) -> Dict[str, Any]:
    db_gen = get_db()
    db = next(db_gen)
    try:
        work = get_work(db, work_id)
        if not work:
            return {"error": "work not found"}
        agent = ReminderAgent()
        agent.notify_work_completed(work)
        mark_work_notified(db, work.id)
        return {"notified_work_id": work_id}
    finally:
        db.close()


def tool_grouped_work_alert(work_id: int, changes: List[str]) -> Dict[str, Any]:
    db_gen = get_db()
    db = next(db_gen)
    try:
        work = get_work(db, work_id)
        if not work:
            return {"error": "work not found"}
        agent = ReminderAgent()
        agent.notify_grouped_alert(work, changes)
        return {"work_id": work_id, "changes_count": len(changes)}
    finally:
        db.close()


def tool_complete_work(work_id: int) -> Dict[str, Any]:
    db_gen = get_db()
    db = next(db_gen)
    try:
        work = complete_work(db, work_id)
        if not work:
            return {"error": "work not found"}
        return {"work_id": work.id, "status": work.status}
    finally:
        db.close()


def tool_daily_planner_digest() -> Dict[str, Any]:
    try:
        agent = ReminderAgent()
        agent.send_daily_reminder()
        return {"sent": True}
    except Exception as e:
        logger.exception('Failed daily planner digest')
        return {"error": str(e)}


def tool_get_work(work_id: int) -> Dict[str, Any]:
    """
    Get details of a work item by ID.
    Args:
        work_id (int): ID of the work item to retrieve.
    Example:
        tool_get_work(work_id=123)
    Response:
        {
            "id": 123,
            "title": "Build dashboard",
            "description": "Create a dashboard for Q4 metrics",
            "status": "Draft",
            "tasks": [
                {"id": 1, "title": "Design UI", "status": "Pending", "due_date": "2025-11-22"}
            ]
        }
    """
    db_gen = get_db()
    db = next(db_gen)
    try:
        work = get_work(db, work_id)
        if not work:
            return {'error': 'not found'}
        tasks = []
        for t in get_tasks_by_work(db, work_id):
            tasks.append({'id': t.id, 'title': t.title, 'status': t.status, 'due_date': str(t.due_date)})
        return {'id': work.id, 'title': work.title, 'description': work.description, 'status': work.status, 'tasks': tasks}
    finally:
        db.close()


def tool_send_slack_message(text: str) -> Dict[str, Any]:
    """
    Send a slack notification message via configured webhook.
    Args:
        text (str): Message text to send to Slack.
    Example:
        tool_send_slack_message(text="Hello team, the dashboard is live!")
    Response:
        {
            "status_code": 200,
            "body": "ok"
        }
    """
    try:
        agent = ReminderAgent()
        webhook = getattr(agent, 'slack_webhook_url', None)
        if not webhook:
            return {'error': 'no slack webhook configured'}
        import requests

        resp = requests.post(webhook, json={'text': text}, timeout=10)
        return {'status_code': resp.status_code, 'body': resp.text}
    except Exception as e:
        logger.exception('Failed to send slack message')
        return {'error': str(e)}


def tool_schedule_task_to_calendar(task_id: int) -> Dict[str, Any]:
    """
    Schedule a task in Google Calendar.
    Args:
        task_id (int): ID of the task to schedule in Google Calendar.
    Example:
        tool_schedule_task_to_calendar(task_id=1)
    Response:
        {
            "event": {"id": "abc123", "summary": "Design UI", ...}
        }
    """
    try:
        from db import get_db, Task
        db_gen = get_db()
        db = next(db_gen)
        try:
            t = db.query(Task).filter(Task.id == int(task_id)).first()
            if not t:
                return {'error': 'task not found'}
            agent = ReminderAgent()
            if not getattr(agent, 'service', None) and not getattr(agent, 'creds', None):
                return {'error': 'google credentials not configured'}
            ev = agent.create_event_for_task(t, t.work.title if t.work else 'Work')
            return {'event': ev}
        finally:
            db.close()
    except Exception as e:
        logger.exception('Failed to schedule task to calendar')
        return {'error': str(e)}


def tool_queue_celery_task(task_id: int) -> Dict[str, Any]:
    """
    Queue a task for asynchronous assignment using Celery.
    Args:
        task_id (int): ID of the task to queue for asynchronous assignment.
    Example:
        tool_queue_celery_task(task_id=1)
    Response:
        {
            "queued": True,
            "task_id": 1
        }
    """
    try:
        from celery_app import async_assign_task
        from db import get_db, Task

        db_gen = get_db()
        db = next(db_gen)
        try:
            t = db.query(Task).filter(Task.id == int(task_id)).first()
            if not t:
                return {'error': 'task not found'}
            payload = {"id": t.id, "title": t.title, "status": t.status, "due_date": str(t.due_date)}
            async_assign_task.delay(payload)
            return {'queued': True, 'task_id': t.id}
        finally:
            db.close()
    except Exception as e:
        logger.exception('Failed to queue celery task')
        return {'error': str(e)}


# Registry of tools the agent can call
TOOLS = {
    'generate_subtasks': tool_generate_subtasks,
    'refine_subtasks': tool_refine_subtasks,
    'create_work': tool_create_work,
    'create_task': tool_create_task,
    'publish_work': tool_publish_work,
    'get_work': tool_get_work,
    'send_slack_message': tool_send_slack_message,
    'schedule_task_to_calendar': tool_schedule_task_to_calendar,
    'queue_celery_task': tool_queue_celery_task,
    'send_due_date_confirmation': tool_send_due_date_confirmation,
    'schedule_first_untracked_task': tool_schedule_first_untracked_task,
    'update_task_status': tool_update_task_status,
    'complete_task_and_schedule_next': tool_complete_task_and_schedule_next,
    'snooze_task': tool_snooze_task,
    'reschedule_task_event': tool_reschedule_task_event,
    'list_upcoming_events': tool_list_upcoming_events,
    'sync_event_update': tool_sync_event_update,
    'notify_task_completed': tool_notify_task_completed,
    'notify_work_completed': tool_notify_work_completed,
    'grouped_work_alert': tool_grouped_work_alert,
    'complete_work': tool_complete_work,
    'daily_planner_digest': tool_daily_planner_digest,
}
