
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
    # We'll collect changes grouped by work to avoid duplicate notifications within a single run.
    tasks = get_all_tasks(db)
    work_changes = {}  # work_id -> {'work': Work, 'changes': set()}
    for task in tasks:
        if not task.calendar_event_id:
            continue
        # calendar_event_id now stores the Google Tasks task id
        try:
            remote = agent.service.tasks().get(tasklist='@default', task=task.calendar_event_id).execute()
        except Exception:
            remote = None
        if not remote:
            continue

        # If remote indicates completed, process it
        if remote.get('status') == 'completed':
            # perform completion steps
            agent.complete_task_and_schedule_next(task, task.work)
            # queue a single message for this task under its work
            wk = task.work
            entry = work_changes.setdefault(wk.id, {'work': wk, 'changes': set(), 'tasks': []})
            entry['changes'].add(f"Task '{task.title}' completed.")
            entry['tasks'].append(('task_completed', task))

        # Check for snooze / due date changes
        elif 'due' in remote:
            try:
                # remote['due'] is RFC3339; parse safely
                event_due = datetime.fromisoformat(remote['due'].replace('Z', '+00:00'))
                if task.due_date and event_due > task.due_date:
                    agent.snooze_task(task, task.work, days=(event_due - task.due_date).days)
                    if task.snooze_count >= 3:
                        # send follow-up immediately (once) and include in grouped changes
                        agent.notify_snooze_followup(task, task.work)
                    wk = task.work
                    entry = work_changes.setdefault(wk.id, {'work': wk, 'changes': set(), 'tasks': []})
                    entry['changes'].add(f"Task '{task.title}' snoozed to {event_due.date()}.")
                    entry['tasks'].append(('task_snoozed', task))
            except Exception:
                pass

    # 1b. Send grouped notifications for works
    for wk_id, info in work_changes.items():
        work = info['work']
        changes = list(dict.fromkeys(info['changes']))  # preserve order, de-dupe
        if changes:
            agent.notify_grouped_alert(work, changes)

    # 2. Broadcast clean-up or changes from DB to calendar
    # (Simplified: removed notified tracking - notifications are idempotent or handled elsewhere)
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
