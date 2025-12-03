"""Session tracking and automatic feedback logging for agent conversations.

Tracks conversation sessions and automatically logs feedback when sessions end,
either through explicit completion or timeout/inactivity.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from threading import Lock, Thread
import atexit

logger = logging.getLogger(__name__)


class ConversationSession:
    """Tracks a single conversation session with the agent."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.started_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.messages: List[Tuple[str, str, datetime]] = []  # (role, content, timestamp)
        self.context_tags = set()
        self.completed = False
        
    def add_message(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.messages.append((role, content, datetime.utcnow()))
        self.last_activity = datetime.utcnow()
        
        # Extract context tags from conversation
        content_lower = content.lower()
        if any(word in content_lower for word in ['create work', 'new work', 'work item']):
            self.context_tags.add('work_creation')
        if any(word in content_lower for word in ['due date', 'deadline', 'when', 'schedule']):
            self.context_tags.add('due_dates')
        if any(word in content_lower for word in ['publish', 'start tracking']):
            self.context_tags.add('publishing')
        if any(word in content_lower for word in ['status', 'progress', 'how is']):
            self.context_tags.add('status_check')
        if any(word in content_lower for word in ['snooze', 'postpone', 'later']):
            self.context_tags.add('snoozing')
        if any(word in content_lower for word in ['replan', 're-plan', 'adjust', 'change']):
            self.context_tags.add('replanning')
    
    def is_inactive(self, timeout_minutes: int = 10) -> bool:
        """Check if session has been inactive for timeout period."""
        return (datetime.utcnow() - self.last_activity) > timedelta(minutes=timeout_minutes)
    
    def is_substantial(self) -> bool:
        """Check if conversation is substantial enough to log feedback."""
        # At least 3 messages (user + agent + user) or contains important actions
        return len(self.messages) >= 3 or bool(self.context_tags & {
            'work_creation', 'publishing', 'replanning'
        })
    
    def generate_summary(self) -> str:
        """Generate a brief summary of the conversation."""
        if not self.messages:
            return "Empty conversation"
        
        # Count message types
        user_messages = sum(1 for role, _, _ in self.messages if role == 'user')
        agent_messages = sum(1 for role, _, _ in self.messages if role == 'assistant')
        
        # Extract key topics
        topics = list(self.context_tags) if self.context_tags else ['general query']
        
        summary = f"{user_messages}-turn conversation about {', '.join(topics)}"
        
        # Add specifics if present
        for role, content, _ in self.messages:
            if role == 'user' and len(content) > 20:
                # Extract potential work/task names
                if 'create' in content.lower() or 'new' in content.lower():
                    summary += f" - initiated via: '{content[:60]}...'"
                    break
        
        return summary
    
    def analyze_quality(self) -> Dict[str, Any]:
        """Analyze conversation quality for feedback logging."""
        analysis = {
            'what_went_well': [],
            'what_could_improve': [],
            'user_satisfaction': 'Medium'  # Default
        }
        
        # Analyze message patterns
        if len(self.messages) < 5:
            analysis['what_went_well'].append("Quick resolution")
        
        if len(self.messages) > 10:
            analysis['what_could_improve'].append("Conversation took many turns - could be more efficient")
        
        # Check for repeated questions (agent asking same thing multiple times)
        agent_questions = [content for role, content, _ in self.messages 
                          if role == 'assistant' and '?' in content]
        if len(agent_questions) > len(set(agent_questions)):
            analysis['what_could_improve'].append("Repeated similar questions - listen better to user responses")
        
        # Check for confirmation patterns
        confirmations = sum(1 for role, content, _ in self.messages 
                          if role == 'assistant' and any(word in content.lower() 
                          for word in ['confirm', 'should i', 'proceed', 'go ahead']))
        if confirmations > 3:
            analysis['what_could_improve'].append(f"Asked {confirmations} confirmations - could combine related confirmations")
        elif confirmations <= 2:
            analysis['what_went_well'].append("Appropriate number of confirmations")
        
        # Check for work creation success
        if 'work_creation' in self.context_tags:
            if any('created work' in content.lower() or 'work id' in content.lower() 
                   for _, content, _ in self.messages):
                analysis['what_went_well'].append("Successfully completed work creation flow")
                analysis['user_satisfaction'] = 'High'
        
        # Check for errors or confusion
        if any(word in ' '.join(content for _, content, _ in self.messages).lower() 
               for word in ['error', 'failed', "don't understand", 'confused']):
            analysis['what_could_improve'].append("Encountered errors or user confusion")
            analysis['user_satisfaction'] = 'Low'
        
        # Format as strings
        went_well = '; '.join(analysis['what_went_well']) if analysis['what_went_well'] else None
        could_improve = '; '.join(analysis['what_could_improve']) if analysis['what_could_improve'] else None
        
        return {
            'what_went_well': went_well,
            'what_could_improve': could_improve,
            'user_satisfaction': analysis['user_satisfaction']
        }


class SessionTracker:
    """Tracks multiple conversation sessions and logs feedback automatically."""
    
    def __init__(self, inactivity_timeout: int = 10, check_interval: int = 60):
        """Initialize session tracker.
        
        Args:
            inactivity_timeout: Minutes of inactivity before session considered ended
            check_interval: Seconds between session cleanup checks
        """
        self.sessions: Dict[str, ConversationSession] = {}
        self.lock = Lock()
        self.inactivity_timeout = inactivity_timeout
        self.check_interval = check_interval
        self.running = True
        
        # Start background cleanup thread
        self.cleanup_thread = Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        # Register cleanup on exit
        atexit.register(self.shutdown)
        
        logger.info(f"SessionTracker initialized (timeout={inactivity_timeout}min, check_interval={check_interval}s)")
    
    def track_message(self, session_id: str, role: str, content: str):
        """Track a message in a conversation session.
        
        Args:
            session_id: Unique session identifier
            role: Message role ('user' or 'assistant')
            content: Message content
        """
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = ConversationSession(session_id)
                logger.info(f"Started tracking session: {session_id}")
            
            self.sessions[session_id].add_message(role, content)
    
    def end_session(self, session_id: str, explicit: bool = True):
        """End a session and log feedback.
        
        Args:
            session_id: Session to end
            explicit: Whether session was explicitly ended or timed out
        """
        with self.lock:
            if session_id not in self.sessions:
                return
            
            session = self.sessions[session_id]
            
            if session.completed:
                return  # Already logged
            
            # Only log if substantial
            if not session.is_substantial():
                logger.debug(f"Session {session_id} not substantial enough to log feedback")
                del self.sessions[session_id]
                return
            
            # Generate feedback
            summary = session.generate_summary()
            analysis = session.analyze_quality()
            
            # Log the feedback
            try:
                import agent_api
                
                feedback_id = agent_api.record_conversation_feedback(
                    conversation_summary=summary,
                    what_went_well=analysis['what_went_well'],
                    what_could_improve=analysis['what_could_improve'],
                    user_satisfaction=analysis['user_satisfaction'],
                    tags=list(session.context_tags)
                )
                
                if feedback_id:
                    logger.info(f"Logged feedback for session {session_id}: feedback_id={feedback_id} "
                              f"({'explicit' if explicit else 'timeout'})")
                else:
                    logger.warning(f"Failed to log feedback for session {session_id}")
                
            except Exception as e:
                logger.exception(f"Error logging feedback for session {session_id}: {e}")
            
            # Mark as completed and remove
            session.completed = True
            del self.sessions[session_id]
    
    def _cleanup_loop(self):
        """Background thread that checks for inactive sessions."""
        while self.running:
            try:
                time.sleep(self.check_interval)
                self._cleanup_inactive_sessions()
            except Exception as e:
                logger.exception(f"Error in session cleanup loop: {e}")
    
    def _cleanup_inactive_sessions(self):
        """Check for and clean up inactive sessions."""
        with self.lock:
            inactive_sessions = [
                session_id for session_id, session in self.sessions.items()
                if session.is_inactive(self.inactivity_timeout) and not session.completed
            ]
        
        for session_id in inactive_sessions:
            logger.info(f"Session {session_id} inactive for {self.inactivity_timeout} minutes, ending...")
            self.end_session(session_id, explicit=False)
    
    def shutdown(self):
        """Shutdown tracker and log feedback for all active sessions."""
        logger.info("Shutting down SessionTracker...")
        self.running = False
        
        # End all active sessions
        with self.lock:
            session_ids = list(self.sessions.keys())
        
        for session_id in session_ids:
            self.end_session(session_id, explicit=False)
        
        logger.info("SessionTracker shutdown complete")


# Global session tracker instance
_session_tracker: Optional[SessionTracker] = None


def get_session_tracker() -> SessionTracker:
    """Get or create the global session tracker instance."""
    global _session_tracker
    if _session_tracker is None:
        _session_tracker = SessionTracker(
            inactivity_timeout=10,  # 10 minutes
            check_interval=60  # Check every minute
        )
    return _session_tracker
