
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from execute_and_verify import Task
from celery_app import async_assign_task

# TODO: Expand to schedule actions like reminders to finish tasks
def scheduled_task(task):
    # This function is triggered by APScheduler at the scheduled time.
    print(f"[Scheduler] Triggered at {datetime.now().isoformat()} for task: {task.description}")
    # Convert the Task object to a dictionary and queue it for asynchronous processing.
    task_data = task.to_dict()
    async_assign_task.delay(task_data)
    print("[Scheduler] Task has been queued for asynchronous processing via Celery.")

if __name__ == "__main__":
    # Create a sample task with a deadline 2 minutes from now.
    task = Task({"description": "Prepare quarterly report", "priority":"High"}, deadline=datetime.now() + timedelta(minutes=2))
    
    # Schedule the job to trigger 1 minute from now (before the deadline).
    scheduled_time = datetime.now() + timedelta(minutes=1)
    print(f"Scheduling task '{task.description}' for asynchronous processing at {scheduled_time.isoformat()}.")

    # Initialize the background scheduler.
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_task, 'date', run_date=scheduled_time, args=[task])
    scheduler.start()

    try:
        # Keep the main thread alive so that the scheduler can trigger the job.
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("Scheduler shutdown.")
