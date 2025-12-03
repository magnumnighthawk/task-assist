# Agent Learning & Optimization System

## Overview

The Task Assist agent includes a self-learning and optimization system that allows it to improve its behavior over time based on conversation feedback. After each interaction, the agent can record what went well and what could be improved, building up a knowledge base of learnings that inform future behavior.

## Architecture

### Components

1. **Database Models** (`db.py`)
   - `ConversationLog`: Stores individual conversation feedback entries
   - `FeedbackSummary`: Stores periodic summaries of learning patterns

2. **Core Module** (`core/feedback.py`)
   - Functions for logging feedback
   - Retrieving recent feedback
   - Generating learning summaries
   - Managing active learning context

3. **Agent API** (`agent_api.py`)
   - High-level facade functions for agent tools
   - `record_conversation_feedback()`: Log feedback
   - `get_learning_insights()`: Retrieve active learnings
   - `generate_and_apply_learning_summary()`: Create summaries

4. **Agent Tools** (`master/tools.py`)
   - `tool_log_conversation_feedback`: Record feedback about conversation
   - `tool_get_learning_context`: Retrieve behavior adjustments
   - `tool_generate_behavior_summary`: Generate periodic summaries

5. **Spec & Instructions** (`master/master_v1.spec.yaml`, `master/instructions.py`)
   - Defines learning skills and policies
   - Instructions for when/how to log feedback
   - Guidelines for applying learnings

## How It Works

### Automatic vs Manual Feedback Logging

The system supports **two modes** of feedback logging:

1. **Automatic (Recommended)**: Session tracker monitors all conversations and automatically logs feedback when sessions end
2. **Manual (Optional)**: Agent explicitly calls `log_conversation_feedback()` tool for detailed self-assessment

Both modes work together - automatic provides baseline coverage, manual adds detailed insights.

### 1a. Automatic Conversation Tracking (Session-End Hook)

The `LearningAgentWrapper` wraps the base agent and tracks all conversations automatically:

```python
# In master/agent.py
root_agent = LearningAgentWrapper(_base_agent)

# Every message is automatically tracked
response = root_agent(message, session_id="user_123")
```

**How it works:**
- Tracks every user message and agent response
- Extracts context tags automatically (work_creation, due_dates, etc.)
- Monitors session activity and detects inactivity (default: 10 minutes)
- When session ends (timeout or explicit end), automatically logs feedback
- Analyzes conversation patterns (confirmations, errors, efficiency)
- Generates quality assessment (what went well, what could improve)

**Session ends when:**
- ✅ Explicit end: `root_agent.end_session(session_id)`
- ⏰ Inactivity timeout: No activity for 10 minutes
- 🛑 App shutdown: Logs all active sessions on exit

**Feedback is logged only for substantial conversations:**
- At least 3 messages (user → agent → user)
- OR contains important actions (work_creation, publishing, replanning)

**This approach ensures:**
- ✅ Learning data captured even if user closes tab
- ✅ No reliance on agent remembering to log feedback
- ✅ Works for incomplete conversations
- ✅ Background cleanup handles abandoned sessions

### 1b. Manual Conversation Feedback Logging

At the end of multi-turn interactions, the agent can optionally call `log_conversation_feedback()` for detailed self-assessment:

```python
tool_log_conversation_feedback(
    conversation_summary="Created work 'Build landing page' with 4 tasks and published",
    what_went_well="User provided clear requirements, smooth due date confirmation",
    what_could_improve="Could have combined the persist and publish confirmations",
    user_satisfaction="High",
    context_tags=["work_creation", "due_dates", "publishing"]
)
```

**What to log:**
- Brief summary of what happened
- Things that worked well
- Areas that could improve (be honest!)
- Estimated user satisfaction (Low/Medium/High)
- Context tags for categorization

**When to log manually (optional - automatic tracking covers most cases):**
- When agent wants to provide detailed self-assessment
- After particularly complex or novel interactions
- When explicit insights beyond automatic analysis are valuable

**When NOT to log manually:**
- Don't need to - automatic tracking handles it
- Simple conversations (already filtered by automatic system)
- The agent should focus on the task, not constantly self-assessing

### 2. Learning Context Retrieval

Before complex operations, the agent calls `get_learning_context()` to retrieve accumulated insights:

```python
context = tool_get_learning_context()
# Returns:
# {
#     "has_learning": True,
#     "combined_adjustments": "Learning Period 1:\n- Ask fewer confirmation questions...",
#     "total_summaries": 2
# }
```

The agent then applies these behavior adjustments to optimize the current interaction.

### 3. Periodic Summary Generation

Weekly (or on-demand), the system analyzes recent feedback to generate learning summaries:

```python
tool_generate_behavior_summary(days=7)
```

This:
1. Retrieves all feedback from the past N days
2. Analyzes patterns (what worked, what didn't)
3. Generates specific behavior adjustments
4. Creates a new `FeedbackSummary` record
5. Deactivates older summaries to keep context fresh

### 4. Applying Learnings

When the agent retrieves learning context, it receives behavior adjustments like:

```
Learning Period 1:
- Ask fewer confirmation questions; combine related confirmations
- Be more explicit and clear in explanations
- Improve due date handling and clarity
```

The agent integrates these into its decision-making:
- Combines confirmation steps when possible
- Provides clearer explanations
- Asks about due dates more explicitly

## Agent Behavior Flow

### Work Creation with Learning

```
[AUTOMATIC] Session tracking starts on first message
   └─> Every message is tracked automatically

0. [OPTIONAL] Call get_learning_context()
   └─> Apply behavior adjustments if available

1. Greet & collect requirements

2. Generate subtasks

3. Propose tasks (incorporating learnings)
   └─> If learned "ask fewer questions", combine steps

4. Get user confirmation

5. Persist work

6. Propose due dates

7. Confirm due dates

8. Publish work

9. [OPTIONAL] Call log_conversation_feedback() for detailed self-assessment
   └─> Manual feedback adds to automatic tracking

[AUTOMATIC] Session ends via timeout or explicit end
   └─> Feedback automatically logged with quality analysis
```

## Feedback Quality Guidelines

### Be Specific
❌ "Too many questions"  
✅ "Asked 3 confirmation questions when 1 would suffice"

### Capture User Friction
- Note when user repeated themselves
- Log when user seemed confused
- Record when flow felt clunky

### Acknowledge Successes
- Note smooth flows
- Record quick completions
- Log positive user reactions

### Tag Appropriately
Use context tags to categorize:
- `work_creation`
- `due_dates`
- `publishing`
- `status_check`
- `replanning`
- `snoozing`

### Estimate Honestly
- **Low**: User frustrated, had to repeat, confused
- **Medium**: Okay but could improve, some friction
- **High**: Smooth, efficient, user satisfied

## Session Tracking Architecture

### SessionTracker (`master/session_tracker.py`)

The `SessionTracker` class manages multiple conversation sessions:

```python
from master.session_tracker import get_session_tracker

tracker = get_session_tracker()

# Automatically happens in LearningAgentWrapper
tracker.track_message(session_id, 'user', 'Create a work item')
tracker.track_message(session_id, 'assistant', 'I can help with that...')

# Explicit end (optional)
tracker.end_session(session_id, explicit=True)
```

**Features:**
- Tracks all messages with timestamps
- Extracts context tags automatically
- Detects inactivity (default 10 min timeout)
- Background thread checks for inactive sessions every 60 seconds
- Logs feedback automatically when sessions end
- Shutdown handler ensures no sessions are lost

### ConversationSession

Each session maintains:
- Message history (role, content, timestamp)
- Context tags (work_creation, due_dates, etc.)
- Activity timestamps
- Completion status

**Automatic Analysis:**
- Conversation length and turn count
- Confirmation patterns (too many vs appropriate)
- Error detection and user confusion
- Success indicators (work created, tasks completed)
- Generates quality ratings: Low/Medium/High

### LearningAgentWrapper (`master/agent.py`)

Wraps the base agent to provide automatic tracking:

```python
# The wrapper is transparent - use like normal agent
response = root_agent(message, session_id='user_123')

# Explicit end when session truly ends
root_agent.end_session('user_123')
```

**Session ID Guidelines:**
- Use web session ID if available
- Or user ID for multi-device persistence
- Or 'default' for single-user scenarios
- Consistent IDs group related conversations

## Database Schema

### ConversationLog Table

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| conversation_summary | Text | Brief summary of conversation |
| what_went_well | Text | Things that worked well |
| what_could_improve | Text | Areas for improvement |
| user_satisfaction_estimate | String | Low/Medium/High |
| context_tags | String | Comma-separated tags |
| created_at | DateTime | Timestamp |

### FeedbackSummary Table

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| period_start | DateTime | Summary period start |
| period_end | DateTime | Summary period end |
| total_conversations | Integer | Number of conversations analyzed |
| key_learnings | Text | Main insights and patterns |
| behavior_adjustments | Text | Specific changes to apply |
| active | Boolean | Whether currently used |
| created_at | DateTime | Timestamp |

## API Examples

### Logging Feedback

```python
import agent_api

feedback_id = agent_api.record_conversation_feedback(
    conversation_summary="User created work with 5 tasks",
    what_went_well="Clear breakdown, smooth flow",
    what_could_improve="Could propose dates earlier",
    user_satisfaction="High",
    tags=["work_creation", "due_dates"]
)
```

### Retrieving Learning Context

```python
import agent_api

context = agent_api.get_learning_insights()

if context['has_learning']:
    print(context['combined_adjustments'])
    # Apply adjustments to current behavior
```

### Generating Summary

```python
import agent_api

summary_id = agent_api.generate_and_apply_learning_summary(days=7)
# Analyzes past 7 days of feedback and creates summary
```

## Testing

Run the test script to verify the system:

```bash
python test_feedback_system.py
```

This tests:
- Feedback logging
- Feedback retrieval
- Summary generation
- Summary application
- Learning context retrieval
- Old summary deactivation

## Maintenance

### Keep Summaries Fresh

The system automatically keeps only the 3 most recent summaries active. Older summaries are deactivated but preserved in the database.

### Periodic Summary Generation

Set up a weekly job to generate summaries:

```python
# In celery_app.py or scheduler
@celery.task
def weekly_learning_summary():
    summary_id = agent_api.generate_and_apply_learning_summary(days=7)
    if summary_id:
        logger.info(f"Generated weekly learning summary: {summary_id}")
```

### Review Feedback Quality

Periodically review logged feedback to ensure:
- Agent is being honest and specific
- Satisfaction estimates are reasonable
- Context tags are consistent
- Improvements are actionable

## Future Enhancements

1. **LLM-Powered Analysis**: Use LLM to analyze feedback patterns and generate more sophisticated behavior adjustments

2. **User Feedback Integration**: Allow users to explicitly rate interactions or provide feedback

3. **A/B Testing**: Test different behavior adjustments and measure effectiveness

4. **Feedback Dashboard**: Create UI to visualize learning patterns and trends

5. **Contextual Learning**: Apply different learnings based on context (work_creation vs status_check)

6. **Learning Decay**: Gradually reduce weight of older learnings

## Best Practices

### For Agent Developers

1. **Update the spec first**: Always update `master_v1.spec.yaml` when changing learning behavior
2. **Test feedback flow**: Ensure agent logs feedback after substantial interactions
3. **Monitor learning context**: Check that summaries are being generated and applied
4. **Review feedback logs**: Periodically check if feedback is useful and actionable

### For Agent Operation

1. **Let it learn**: Don't override too quickly - give learnings time to take effect
2. **Review patterns**: Check if same issues appear repeatedly
3. **Adjust policies**: Update spec if learnings suggest structural changes
4. **Celebrate improvements**: Note when learnings lead to better behavior

## Integration Points

- **Spec**: `master/master_v1.spec.yaml` - Defines learning tools and skills
- **Instructions**: `master/instructions.py` - Guides agent on when/how to learn
- **Tools**: `master/tools.py` - Implements feedback tools
- **Core**: `core/feedback.py` - Business logic for learning system
- **API**: `agent_api.py` - High-level facade for tools
- **Database**: `db.py` - Persistence layer for feedback data

## Troubleshooting

### Agent Not Logging Feedback

- Check if `log_conversation_feedback` tool is registered in TOOLS
- Verify instructions include feedback logging guidance
- Ensure database tables are created (`ConversationLog`, `FeedbackSummary`)

### Learning Context Empty

- Run `generate_behavior_summary()` to create initial summary
- Check if any feedback logs exist in database
- Verify summaries have `active=True`

### Summaries Not Applied

- Check `get_active_learning_context()` returns data
- Verify agent calls `get_learning_context()` at start of interactions
- Ensure instructions guide agent to apply learnings

---

**Source of Truth**: This documentation describes the implementation. Always refer to `master/master_v1.spec.yaml` for canonical behavior definitions.
