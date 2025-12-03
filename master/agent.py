import os
import logging
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from .instructions import INSTRUCTION
from .tools import TOOLS
from .session_tracker import get_session_tracker

logger = logging.getLogger(__name__)
load_dotenv()
gmp_key = os.getenv('GMP_API_KEY')

# Create the base agent
_base_agent = Agent(
    model='gemini-2.0-flash',
    name='task_assist_master_agent',
    description='An intelligent assistant that manages work and tasks end-to-end: breaks down work into actionable tasks, schedules them, tracks progress, sends reminders, and notifies users via Slack and calendar. Handles the full workflow as described in LIFECYCLE.md and IDEA.md.',
    instruction=INSTRUCTION,
    tools=list(TOOLS.values())
)


class LearningAgentWrapper:
    """Wrapper around the agent that tracks conversations and logs feedback automatically."""
    
    def __init__(self, agent):
        self.agent = agent
        self.session_tracker = get_session_tracker()
        logger.info("LearningAgentWrapper initialized with automatic feedback logging")
    
    def __call__(self, message: str, session_id: str = 'default', **kwargs):
        """Process a message through the agent with session tracking.
        
        Args:
            message: User message
            session_id: Session identifier (e.g., from web session, user ID, etc.)
            **kwargs: Additional arguments passed to agent
            
        Returns:
            Agent response
        """
        # Track user message
        self.session_tracker.track_message(session_id, 'user', message)
        
        try:
            # Call the underlying agent
            response = self.agent(message, **kwargs)
            
            # Track agent response
            if response:
                response_text = str(response) if not isinstance(response, str) else response
                self.session_tracker.track_message(session_id, 'assistant', response_text)
            
            return response
            
        except Exception as e:
            logger.exception(f"Error in agent call: {e}")
            # Track the error
            self.session_tracker.track_message(session_id, 'assistant', f"Error: {str(e)}")
            raise
    
    def end_session(self, session_id: str):
        """Explicitly end a session and log feedback.
        
        Call this when you know a session has ended (e.g., user logout, tab close event).
        
        Args:
            session_id: Session to end
        """
        self.session_tracker.end_session(session_id, explicit=True)
        logger.info(f"Explicitly ended session: {session_id}")
    
    def __getattr__(self, name):
        """Delegate attribute access to the underlying agent."""
        return getattr(self.agent, name)


# Export the base agent directly as root_agent (ADK requirement)
# Session tracking will be handled via a separate middleware layer if needed
root_agent = _base_agent

# Make wrapper available for custom integrations
learning_agent = LearningAgentWrapper(_base_agent)
