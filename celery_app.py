import os
import logging
from celery import Celery
from datetime import datetime
from typing import Dict, Any
from db import get_db, update_task_status, get_work
from reminder import ReminderAgent
from contextlib import contextmanager

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
app = Celery('tasks', broker=BROKER_URL)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

@contextmanager
def with_db_session():
    db_gen = get_db()
    db = next(db_gen)
    try:
        yield db
    finally:
        db.close()

@app.task
def async_assign_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery task to assign a task asynchronously, update its status, create calendar event, and send Slack notification.
    """
    try:
        with with_db_session() as db:
            agent = ReminderAgent()
            update_task_status(db, task_data['id'], 'Tracked')
            work = get_work(db, task_data.get('work_id'))
            agent.notify_event_created(task_data, work)
            logging.info(f"Asynchronously assigned and notified for task: {task_data.get('title')} at {datetime.now()}")
            return task_data
    except Exception as e:
        logging.exception(f"Error in async_assign_task: {e}")
        raise