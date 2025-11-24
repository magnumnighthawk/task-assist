"""Work status management and lifecycle.

Defines canonical work statuses and validation logic.
"""

from enum import Enum


class WorkStatus(str, Enum):
    """Canonical work item statuses."""
    DRAFT = "Draft"
    PUBLISHED = "Published"
    COMPLETED = "Completed"

    @classmethod
    def from_string(cls, value: str):
        """Parse a status string, handling legacy/alternate values."""
        if not value:
            return cls.DRAFT
        
        normalized = value.strip().lower()
        mapping = {
            'draft': cls.DRAFT,
            'published': cls.PUBLISHED,
            'completed': cls.COMPLETED,
            'done': cls.COMPLETED,
        }
        return mapping.get(normalized, cls.DRAFT)

    def __str__(self):
        return self.value


def can_transition(from_status: WorkStatus, to_status: WorkStatus) -> bool:
    """Check if a work status transition is valid.
    
    Valid transitions:
    - DRAFT -> PUBLISHED
    - PUBLISHED -> COMPLETED
    - Any status -> DRAFT (re-opening)
    """
    if from_status == to_status:
        return True
    
    valid_transitions = {
        WorkStatus.DRAFT: {WorkStatus.PUBLISHED},
        WorkStatus.PUBLISHED: {WorkStatus.COMPLETED, WorkStatus.DRAFT},
        WorkStatus.COMPLETED: {WorkStatus.DRAFT}
    }
    
    return to_status in valid_transitions.get(from_status, set())
