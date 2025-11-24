"""Tool wrappers for Agent to call into the application.

Each tool is a simple function accepting keyword args and returning JSON-serializable results.
Keep wrappers minimal and side-effecting where appropriate (e.g., creating work, publishing, sending notifications).
"""
from typing import Any, Dict, List
import logging
import os
from db import get_db, create_work, publish_work, get_work, get_tasks_by_work
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
    'create_work': tool_create_work,
    'publish_work': tool_publish_work,
    'get_work': tool_get_work,
    'send_slack_message': tool_send_slack_message,
    'schedule_task_to_calendar': tool_schedule_task_to_calendar,
    'queue_celery_task': tool_queue_celery_task,
}
