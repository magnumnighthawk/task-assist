
import time
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from reminder import ReminderAgent
from db import get_db, get_all_tasks, get_all_works, Work, Task
from celery_app import async_assign_task

# TODO: Expand to schedule actions like reminders to finish tasks

def scheduled_task(task):
    # This function is triggered by APScheduler at the scheduled time.
    print(f"[Scheduler] Triggered at {datetime.now().isoformat()} for task: {task.title}")
    # Convert the Task object to a dictionary and queue it for asynchronous processing.
    task_data = {"id": task.id, "title": task.title, "status": task.status, "due_date": str(task.due_date)}
    async_assign_task.delay(task_data)
    print("[Scheduler] Task has been queued for asynchronous processing via Celery.")

def overnight_batch():
    print(f"[Scheduler] Running overnight batch at {datetime.now().isoformat()}")
    agent = ReminderAgent()
    db_gen = get_db()
    db = next(db_gen)
    # 1. Sync calendar event statuses & update DB
    tasks = get_all_tasks(db)
    for task in tasks:
        if task.calendar_event_id:
            event = agent.service.events().get(calendarId='primary', eventId=task.calendar_event_id).execute()
            changes = []
            if event.get('status') == 'completed' or event.get('status') == 'cancelled':
                agent.complete_task_and_schedule_next(task, task.work)
                agent.notify_task_completed(task, task.work)
                changes.append(f"Task '{task.title}' completed.")
            elif 'start' in event and 'dateTime' in event['start']:
                event_due = datetime.fromisoformat(event['start']['dateTime'])
                if task.due_date and event_due > task.due_date:
                    agent.snooze_task(task, task.work, days=(event_due - task.due_date).days)
                    if task.snooze_count >= 3:
                        agent.notify_snooze_followup(task, task.work)
                    changes.append(f"Task '{task.title}' snoozed to {event_due.date()}.")
            if changes:
                agent.notify_grouped_alert(task.work, changes)
    # 2. Broadcast clean-up or changes from DB to calendar
    works = get_all_works(db)
    for work in works:
        if work.status == 'Completed':
            for task in work.tasks:
                if task.calendar_event_id:
                    agent.delete_event(task.calendar_event_id)
            agent.notify_work_completed(work)
    db.close()

def daily_reminder():
    agent = ReminderAgent()
    agent.send_daily_reminder()


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    # Schedule overnight batch at 2am every day
    scheduler.add_job(overnight_batch, 'cron', hour=2, minute=0)
    # Schedule daily Slack reminder at 6am
    scheduler.add_job(daily_reminder, 'cron', hour=6, minute=0)
    # Schedule watch renewal every 30 minutes
    from reminder import ReminderAgent
    def renew_watches_job():
        agent = ReminderAgent()
        agent.renew_all_watches()
    scheduler.add_job(renew_watches_job, 'interval', minutes=30)
    scheduler.start()
    print("Scheduler started. Overnight batch at 2am, daily reminder at 6am.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("Scheduler shutdown.")
