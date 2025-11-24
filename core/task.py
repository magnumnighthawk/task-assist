"""Task status management and lifecycle.

Defines canonical task statuses with Google Tasks API mapping.
"""

from enum import Enum


class TaskStatus(str, Enum):
    """Canonical task statuses.
    
    Maps to Google Tasks API statuses:
    - PENDING, PUBLISHED, TRACKED -> needsAction
    - COMPLETED -> completed
    """
    PENDING = "Pending"      # Created but not yet published
    PUBLISHED = "Published"  # Published and visible
    TRACKED = "Tracked"      # Currently active/in-progress
    COMPLETED = "Completed"  # Done
    
    @classmethod
    def from_string(cls, value: str):
        """Parse a status string, handling legacy/alternate values."""
        if not value:
            return cls.PENDING
        
        normalized = value.strip().lower()
        mapping = {
            'pending': cls.PENDING,
            'draft': cls.PENDING,  # Legacy mapping
            'published': cls.PUBLISHED,
            'tracked': cls.TRACKED,
            'completed': cls.COMPLETED,
            'done': cls.COMPLETED,
            'needsaction': cls.PUBLISHED,  # From Google Tasks
            'needs_action': cls.PUBLISHED,
        }
        return mapping.get(normalized, cls.PENDING)
    
    @classmethod
    def from_google_tasks(cls, google_status: str):
        """Convert Google Tasks API status to internal status."""
        if google_status == 'completed':
            return cls.COMPLETED
        else:  # 'needsAction' or default
            return cls.PUBLISHED
    
    def to_google_tasks(self) -> str:
        """Convert internal status to Google Tasks API status."""
        if self == TaskStatus.COMPLETED:
            return 'completed'
        else:
            return 'needsAction'

    def __str__(self):
        return self.value


def can_transition(from_status: TaskStatus, to_status: TaskStatus) -> bool:
    """Check if a task status transition is valid.
    
    Valid transitions:
    - PENDING -> PUBLISHED
    - PUBLISHED -> TRACKED
    - TRACKED -> COMPLETED
    - Any -> COMPLETED (can complete any time)
    - COMPLETED -> PUBLISHED (re-open)
    """
    if from_status == to_status:
        return True
    
    # Can always complete
    if to_status == TaskStatus.COMPLETED:
        return True
    
    # Can re-open completed tasks
    if from_status == TaskStatus.COMPLETED and to_status == TaskStatus.PUBLISHED:
        return True
    
    valid_transitions = {
        TaskStatus.PENDING: {TaskStatus.PUBLISHED},
        TaskStatus.PUBLISHED: {TaskStatus.TRACKED},
        TaskStatus.TRACKED: {TaskStatus.PUBLISHED},  # Can go back
    }
    
    return to_status in valid_transitions.get(from_status, set())
