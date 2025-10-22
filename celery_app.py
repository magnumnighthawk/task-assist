
from celery import Celery
from datetime import datetime

# Initialize Celery with Redis as the broker
app = Celery('tasks', broker='redis://localhost:6379/0')

# Expanded: update statuses, manage calendar, send Slack notifications
@app.task
def async_assign_task(task_data):
    from db import get_db, update_task_status, get_work
    from reminder import ReminderAgent
    db_gen = get_db()
    db = next(db_gen)
    agent = ReminderAgent()
    # Update status to Tracked
    update_task_status(db, task_data['id'], 'Tracked')
    # Fetch task and work
    work = get_work(db, task_data.get('work_id'))
    # Create calendar event if not already present
    # (Assume task_data has enough info, or fetch from DB)
    # Send Slack notification
    agent.notify_event_created(task_data, work)
    db.close()
    print(f"Asynchronously assigned and notified for task: {task_data.get('title')} at {datetime.now()}")
    return task_data