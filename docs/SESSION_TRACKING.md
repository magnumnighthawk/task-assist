# Session Tracking Quick Reference

## Overview

Automatic session tracking ensures learning data is captured from every conversation, even if the user closes the tab or the session times out.

## How to Use

### Basic Usage (Automatic)

```python
from master.agent import root_agent

# Just use the agent normally - tracking happens automatically
response = root_agent("Create a work item for my project")

# Session tracking happens in the background
# No explicit action needed!
```

### With Session IDs (Recommended)

```python
# Use session ID to group related conversations
response = root_agent(
    message="Create work item",
    session_id="user_abc_session_xyz"
)

# Same session ID groups the conversation
response = root_agent(
    message="Yes, go ahead",
    session_id="user_abc_session_xyz"
)
```

### Explicit Session End (Optional)

```python
# When you know session has truly ended
root_agent.end_session("user_abc_session_xyz")

# Immediately logs feedback instead of waiting for timeout
```

## Session ID Best Practices

Choose session IDs based on your architecture:

### Web Application
```python
# Use web session ID from Flask/Streamlit
session_id = flask.session['id']  # or
session_id = st.session_state.session_id
```

### Multi-User System
```python
# Use user ID + timestamp or request ID
session_id = f"user_{user_id}_{request_id}"
```

### Single User (Default)
```python
# Use 'default' or omit (wrapper uses 'default')
response = root_agent(message)  # Uses session_id='default'
```

## Configuration

Default settings in `master/session_tracker.py`:

```python
SessionTracker(
    inactivity_timeout=10,  # Minutes of inactivity before session ends
    check_interval=60       # Seconds between cleanup checks
)
```

To customize:

```python
from master.session_tracker import SessionTracker

# Create custom tracker
tracker = SessionTracker(
    inactivity_timeout=5,   # 5 minutes
    check_interval=30       # Check every 30 seconds
)
```

## What Gets Tracked

### Automatically Captured
- ✅ All user messages
- ✅ All agent responses
- ✅ Message timestamps
- ✅ Context tags (work_creation, due_dates, etc.)
- ✅ Session start/end times
- ✅ Inactivity detection

### Automatic Analysis
- ✅ Conversation efficiency (turn count)
- ✅ Confirmation patterns (too many vs appropriate)
- ✅ Error detection
- ✅ Success indicators (work created, tasks completed)
- ✅ User satisfaction estimate (Low/Medium/High)

### Feedback Generated
- Summary of conversation
- What went well
- What could improve
- Satisfaction estimate
- Context tags

## When Feedback is Logged

### Automatic Triggers
1. **Inactivity timeout**: No messages for 10 minutes (configurable)
2. **Explicit end**: `root_agent.end_session(session_id)`
3. **App shutdown**: All active sessions logged on exit

### Filtering
Only substantial conversations are logged:
- At least 3 messages (user → agent → user), OR
- Contains important actions (work_creation, publishing, replanning)

Simple queries like "What's the status?" are not logged.

## Integration Examples

### Flask API
```python
from master.agent import root_agent
from flask import session

@app.route('/agent/chat', methods=['POST'])
def chat():
    message = request.json['message']
    session_id = session['id']
    
    # Automatic tracking
    response = root_agent(message, session_id=session_id)
    
    return jsonify({'response': response})

@app.route('/logout', methods=['POST'])
def logout():
    session_id = session['id']
    
    # Explicitly end session
    root_agent.end_session(session_id)
    session.clear()
    
    return jsonify({'status': 'logged out'})
```

### Streamlit App
```python
from master.agent import root_agent
import streamlit as st

# Initialize session ID
if 'session_id' not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())

# Chat interface
user_input = st.chat_input("Message")
if user_input:
    # Automatic tracking with session ID
    response = root_agent(
        user_input, 
        session_id=st.session_state.session_id
    )
    st.write(response)

# Optional: End session button
if st.button("End Session"):
    root_agent.end_session(st.session_state.session_id)
    st.session_state.session_id = str(uuid.uuid4())
```

### ADK Web Server
The agent runs via `adk web` command. Session tracking is built into the wrapper, so it works automatically. Session IDs are derived from the web framework's session management.

## Monitoring

### View Active Sessions
```python
from master.session_tracker import get_session_tracker

tracker = get_session_tracker()
print(f"Active sessions: {len(tracker.sessions)}")

for session_id, session in tracker.sessions.items():
    print(f"  {session_id}: {len(session.messages)} messages, "
          f"last activity: {session.last_activity}")
```

### Check Recent Feedback
```python
from core.feedback import get_recent_feedback

# Get feedback from last 7 days
feedback = get_recent_feedback(days=7, limit=20)

for log in feedback:
    print(f"Session: {log['conversation_summary']}")
    print(f"  Satisfaction: {log['user_satisfaction_estimate']}")
    print(f"  Tags: {', '.join(log['context_tags'])}")
```

## Troubleshooting

### Sessions Not Being Tracked
- Check that `LearningAgentWrapper` is being used (it is in `master/agent.py`)
- Verify session IDs are being passed consistently
- Check logs for errors

### Feedback Not Logged
- Ensure conversation is substantial (3+ messages or important actions)
- Check database tables exist (`ConversationLog`, `FeedbackSummary`)
- Verify `agent_api.record_conversation_feedback()` is working

### Sessions Not Timing Out
- Check `SessionTracker` configuration (inactivity_timeout, check_interval)
- Verify cleanup thread is running (should start automatically)
- Look for exceptions in logs

### Too Much/Too Little Feedback
Adjust the "substantial" criteria in `ConversationSession.is_substantial()`:

```python
def is_substantial(self) -> bool:
    # Customize thresholds
    return len(self.messages) >= 5 or bool(self.context_tags & {
        'work_creation', 'publishing'
    })
```

## Performance Considerations

- **Memory**: Each session stores full message history. Sessions are cleaned up on timeout.
- **Storage**: One database row per session (substantial ones only)
- **Background Thread**: Cleanup thread runs every 60s by default, minimal CPU usage
- **Shutdown**: Graceful shutdown ensures no data loss

## Best Practices

1. **Use consistent session IDs** to group related conversations
2. **Explicitly end sessions** when you know they're done (faster feedback logging)
3. **Monitor feedback quality** periodically to ensure useful data
4. **Adjust timeout** based on your use case (shorter for quick interactions, longer for complex workflows)
5. **Review automatic analysis** and customize if needed for your domain

---

**See also:**
- `docs/LEARNING_SYSTEM.md` - Full documentation
- `master/session_tracker.py` - Implementation
- `master/agent.py` - Wrapper integration
- `test_session_tracking.py` - Test examples
