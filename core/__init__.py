"""Core domain modules for Task Assist agent-centric architecture.

This package provides clean abstractions for:
- Work and Task status management (work.py, task.py)
- Storage operations with status filtering (storage.py)
- Slack notifications and interactive messaging (slack.py)
- Google Tasks provider integration (tasks_provider.py)
- Task scheduling and calendar sync (scheduling.py)
- Due date management and normalization (due_dates.py)
"""

from .work import WorkStatus
from .task import TaskStatus

__all__ = ['WorkStatus', 'TaskStatus']
