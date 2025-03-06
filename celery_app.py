from celery import Celery
from datetime import datetime

# Initialize Celery with Redis as the broker
app = Celery('tasks', broker='redis://localhost:6379/0')

# TODO: Expand by adding tasks to update statuses of individual & related items,
# manage google calendar updates, etc
@app.task
def async_assign_task(task_data):
    print(f"Asynchronously assigning task: {task_data['description']} at {datetime.now()}")
    task_data['status'] = "In Progress"
    return task_data