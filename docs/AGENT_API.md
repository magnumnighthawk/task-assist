# Agent API Reference

This document describes the agent-friendly API for Task Assist, providing clean, high-level functions for managing work items, tasks, scheduling, and notifications.

## Overview

The refactored architecture consolidates scattered logic into domain-focused modules:

- **`core/work.py`**: Work status enums and lifecycle
- **`core/task.py`**: Task status enums with Google Tasks mapping
- **`core/storage.py`**: Database operations with filtering
- **`core/slack.py`**: Slack notifications (interactive, publish, plain)
- **`core/tasks_provider.py`**: Google Tasks API wrapper
- **`core/scheduling.py`**: Task scheduling and calendar sync
- **`core/due_dates.py`**: Due date management and snooze logic
- **`agent_api.py`**: High-level facade combining all modules

## Work Management

### List Works by Status

```python
import agent_api

# Get all works
works = agent_api.list_works_by_status('all')

# Filter by status
draft_works = agent_api.list_works_by_status('draft')
published_works = agent_api.list_works_by_status('published')
completed_works = agent_api.list_works_by_status('completed')

# Aliases
active_works = agent_api.list_works_by_status('in_progress')  # Same as 'published'
```

**Returns:** List of work dictionaries:
```python
{
    'id': 123,
    'title': 'Build dashboard',
    'description': 'Create Q4 metrics dashboard',
    'status': 'Published',
    'created_at': '2025-11-24T12:00:00',
    'task_count': 5,
    'completed_tasks': 2,
    'progress': '2/5'
}
```

### Get Work Details

```python
work = agent_api.get_work_details(work_id=123)
```

**Returns:** Work with full task list:
```python
{
    'id': 123,
    'title': 'Build dashboard',
    'description': '...',
    'status': 'Published',
    'created_at': '2025-11-24T12:00:00',
    'tasks': [
        {
            'id': 1,
            'title': 'Design UI',
            'status': 'Completed',
            'due_date': '2025-11-25T08:00:00',
            'snooze_count': 0,
            'has_calendar_event': True,
            'calendar_event_id': 'abc123'
        },
        ...
    ]
}
```

### Get Recently Completed Works

```python
# Works completed in last 7 days
recent = agent_api.get_recently_completed_works(days=7)
```

### Get Upcoming Works

```python
# Published works with upcoming tasks
upcoming = agent_api.get_upcoming_works()
```

**Returns:**
```python
{
    'id': 123,
    'title': 'Build dashboard',
    'status': 'Published',
    'next_task': {
        'id': 3,
        'title': 'Connect database',
        'due_date': '2025-11-26T08:00:00'
    },
    'remaining_tasks': 3
}
```

### Create Work

```python
work_id = agent_api.create_work_with_tasks(
    title='Build dashboard',
    description='Create Q4 metrics dashboard',
    task_titles=['Design UI', 'Connect database', 'Add charts'],
    auto_due_dates=True  # Auto-assign with 1-day spacing
)
```

### Publish Work

```python
# Publish and schedule first task
success = agent_api.publish_work_flow(
    work_id=123,
    schedule_first_task=True
)
```

## Task Management

### List Tasks by Status

```python
# All tasks
tasks = agent_api.list_tasks_by_status('all')

# Filter by status
pending = agent_api.list_tasks_by_status('pending')
published = agent_api.list_tasks_by_status('published')
tracked = agent_api.list_tasks_by_status('tracked')
completed = agent_api.list_tasks_by_status('completed')

# Filter by work
work_tasks = agent_api.list_tasks_by_status('all', work_id=123)
```

**Returns:** List of task dictionaries:
```python
{
    'id': 1,
    'title': 'Design UI',
    'status': 'Tracked',
    'work_id': 123,
    'work_title': 'Build dashboard',
    'due_date': '2025-11-25T08:00:00',
    'snooze_count': 0,
    'has_calendar_event': True
}
```

### Get Today's Tasks

```python
today_tasks = agent_api.get_today_tasks_summary()
```

### Get Overdue Tasks

```python
overdue = agent_api.get_overdue_tasks()
```

**Returns:**
```python
{
    'id': 2,
    'title': 'Connect database',
    'status': 'Tracked',
    'work_title': 'Build dashboard',
    'due_date': '2025-11-20T08:00:00',
    'days_overdue': 4
}
```

### Complete Task

```python
# Complete and schedule next task in work
success = agent_api.complete_task_flow(task_id=1)

# Just mark complete (no auto-scheduling)
success = agent_api.mark_task_complete(task_id=1)
```

### Set Due Date

```python
from datetime import datetime

success = agent_api.set_task_due_date(
    task_id=1,
    due_date=datetime(2025, 11, 26, 8, 0),
    source='agent'  # or 'slack', 'manual', 'sync'
)
```

### Snooze Task

```python
# Snooze by 1 day (default)
success = agent_api.snooze_task(task_id=1)

# Snooze by custom days
success = agent_api.snooze_task(task_id=1, days=3)
```

## Calendar & Google Tasks

### Schedule Task to Calendar

```python
success = agent_api.schedule_task_to_calendar(task_id=1)
```

### Remove from Calendar

```python
success = agent_api.remove_task_from_calendar(task_id=1)
```

### Fetch Calendar Tasks

```python
# Get upcoming tasks from Google Tasks
google_tasks = agent_api.fetch_calendar_tasks()
```

**Returns:**
```python
{
    'id': 'abc123',
    'title': 'Build dashboard: Design UI',
    'due': '2025-11-25T08:00:00Z',
    'status': 'needsAction',
    'notes': 'Work: Build dashboard'
}
```

### Sync Task from Calendar

```python
# Sync task state from Google Tasks to DB
success = agent_api.sync_task_from_calendar(task_id=1)
```

## Slack Notifications

### Send Plain Message

```python
success = agent_api.send_slack_notification(
    "✅ Dashboard deployment complete!"
)
```

### Send Interactive Due Date Request

```python
# Send interactive message with datepickers for all tasks
success = agent_api.send_interactive_due_date_request(work_id=123)
```

### Send Publish Notification

```python
success = agent_api.send_work_publish_notification(work_id=123)
```

### Send Daily Reminder

```python
success = agent_api.send_daily_reminder()
```

### Update Due Dates from Slack

```python
# After interactive Slack response
due_date_map = {
    1: '2025-11-25',  # task_id: date string
    2: '2025-11-26',
    3: '2025-11-27'
}
success = agent_api.update_tasks_due_dates_from_slack(due_date_map)
```

## Status Enums

### Work Statuses

- `Draft`: Initial state, not yet published
- `Published`: Active work with tasks in progress
- `Completed`: All tasks finished

### Task Statuses

- `Pending`: Created but not published
- `Published`: Visible and schedulable
- `Tracked`: Currently active/in-progress
- `Completed`: Finished

**Google Tasks Mapping:**
- `Pending`, `Published`, `Tracked` → `needsAction`
- `Completed` → `completed`

## Usage Examples

### Example 1: Create and Publish Work

```python
import agent_api

# Create work with tasks
work_id = agent_api.create_work_with_tasks(
    title='Deploy to production',
    description='Q4 dashboard production deployment',
    task_titles=[
        'Run tests',
        'Review code',
        'Deploy to staging',
        'Deploy to production'
    ],
    auto_due_dates=True
)

# Send interactive Slack message for due date confirmation
agent_api.send_interactive_due_date_request(work_id)

# After dates confirmed, publish
agent_api.publish_work_flow(work_id, schedule_first_task=True)
```

### Example 2: Daily Task Management

```python
import agent_api

# Get today's tasks
today = agent_api.get_today_tasks_summary()
if today:
    agent_api.send_daily_reminder()

# Check overdue
overdue = agent_api.get_overdue_tasks()
for task in overdue:
    # Notify or snooze
    if task['days_overdue'] > 3:
        agent_api.send_slack_notification(
            f"⚠️ Task '{task['title']}' is {task['days_overdue']} days overdue!"
        )
```

### Example 3: Track Work Progress

```python
import agent_api

# List active works
active = agent_api.list_works_by_status('published')

for work in active:
    details = agent_api.get_work_details(work['id'])
    progress = f"{work['completed_tasks']}/{work['task_count']}"
    
    print(f"{work['title']}: {progress}")
    
    # Get tracked (current) task
    tracked = [t for t in details['tasks'] if t['status'] == 'Tracked']
    if tracked:
        print(f"  Current: {tracked[0]['title']}")
```

### Example 4: Complete Task Flow

```python
import agent_api

# Complete current task and schedule next
task_id = 42
success = agent_api.complete_task_flow(task_id)

if success:
    # This automatically:
    # 1. Marks task as completed in DB
    # 2. Marks as completed in Google Tasks
    # 3. Sends Slack notification
    # 4. Schedules next task (or completes work if all done)
    print("✓ Task completed and next task scheduled")
```

## Architecture Notes

- All functions use the centralized `core/` modules
- Google Tasks API replaces Calendar (legacy code remains for compatibility)
- Slack notifications use Block Kit for interactive messages
- Due dates are normalized and synced between DB and Google Tasks
- Status enums ensure consistency across DB, UI, and external APIs
- Functions return simple success booleans or data dictionaries (no exceptions thrown to agent)

## Migration from Old Code

**Old pattern:**
```python
from db import get_db, publish_work
from reminder import ReminderAgent

db = next(get_db())
work = publish_work(db, work_id)
agent = ReminderAgent()
agent.send_publish_notification(work)
db.close()
```

**New pattern:**
```python
import agent_api

agent_api.publish_work_flow(work_id, schedule_first_task=True)
```

The agent API handles session management, error handling, and cross-module coordination automatically.
