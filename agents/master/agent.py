import os
import logging
import sys
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.sessions.session import Session

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from .instructions import INSTRUCTION
from .tools import TOOLS
from .session_tracker import get_session_tracker

logger = logging.getLogger(__name__)
load_dotenv()
gmp_key = os.getenv('GMP_API_KEY')

# Global session tracker - shared across agent instances
_session_tracker = get_session_tracker()


def _extract_session_id(session: Optional[Session]) -> str:
    """Extract session ID from ADK session object."""
    if session and hasattr(session, 'id'):
        return str(session.id)
    elif session and hasattr(session, 'session_id'):
        return str(session.session_id)
    return 'default'


def _extract_message_content(message: Any) -> str:
    """Extract text content from various message formats."""
    if isinstance(message, str):
        return message
    elif hasattr(message, 'content'):
        return str(message.content)
    elif hasattr(message, 'text'):
        return str(message.text)
    elif isinstance(message, dict):
        return message.get('content', message.get('text', str(message)))
    return str(message)


class LearningAgent(Agent):
    """Agent subclass that includes automatic session tracking and feedback logging.
    
    This class extends the Google ADK Agent to add learning capabilities while
    maintaining full compatibility with the ADK framework. Uses a global session
    tracker to avoid Pydantic field validation issues.
    """
    
    async def send(self, message: Any, session: Optional[Session] = None, **kwargs) -> Any:
        """Override send method to track messages."""
        session_id = _extract_session_id(session)
        message_text = _extract_message_content(message)
        
        # Track user message using global tracker
        _session_tracker.track_message(session_id, 'user', message_text)
        
        try:
            # Call parent send method
            response = await super().send(message, session=session, **kwargs)
            
            # Track agent response
            if response:
                response_text = _extract_message_content(response)
                _session_tracker.track_message(session_id, 'assistant', response_text)
            
            return response
            
        except Exception as e:
            logger.exception(f"Error in agent send: {e}")
            # Track the error
            _session_tracker.track_message(session_id, 'assistant', f"Error: {str(e)}")
            raise


# Create the learning agent - this is ADK-compatible and includes session tracking
root_agent = LearningAgent(
    model='gemini-2.0-flash',
    name='task_assist_master_agent',
    description='An intelligent assistant that manages work and tasks end-to-end: breaks down work into actionable tasks, schedules them, tracks progress, sends reminders, and notifies users via Slack and calendar. Handles the full workflow as described in LIFECYCLE.md and IDEA.md.',
    instruction=INSTRUCTION,
    tools=list(TOOLS.values())
)

logger.info("LearningAgent initialized with automatic feedback logging")


def end_session(session_id: str):
    """Explicitly end a session and log feedback.
    
    Args:
        session_id: Session to end
    """
    _session_tracker.end_session(session_id, explicit=True)
    logger.info(f"Explicitly ended session: {session_id}")
