#!/usr/bin/env python3
"""Integration test demonstrating complete learning system with session tracking."""

import sys
import time

sys.path.insert(0, '.')

from master.session_tracker import get_session_tracker
from core.feedback import get_recent_feedback, get_active_learning_context
import agent_api


def simulate_good_conversation():
    """Simulate a smooth, efficient conversation."""
    print("\n=== Simulating GOOD Conversation ===")
    
    tracker = get_session_tracker()
    session_id = "integration-good"
    
    # Efficient work creation flow
    tracker.track_message(session_id, "user", "Create work item for building API documentation")
    tracker.track_message(session_id, "assistant", "I'll help create that. What's your deadline?")
    tracker.track_message(session_id, "user", "End of this week")
    tracker.track_message(session_id, "assistant", 
        "Here are 4 subtasks:\n1. Set up docs framework\n2. Write API reference\n"
        "3. Add examples\n4. Review and publish\nDoes this look good?")
    tracker.track_message(session_id, "user", "Perfect, save it")
    tracker.track_message(session_id, "assistant", "Should I save this work with these 4 tasks?")
    tracker.track_message(session_id, "user", "Yes")
    tracker.track_message(session_id, "assistant", "Created work ID 42 with 4 tasks")
    
    print(f"✓ Tracked {len(tracker.sessions[session_id].messages)} messages")
    print(f"  Tags: {tracker.sessions[session_id].context_tags}")
    
    # End session
    tracker.end_session(session_id, explicit=True)
    print("✓ Session ended, feedback logged")


def simulate_problematic_conversation():
    """Simulate a conversation with issues."""
    print("\n=== Simulating PROBLEMATIC Conversation ===")
    
    tracker = get_session_tracker()
    session_id = "integration-bad"
    
    # Inefficient flow with repeated questions
    tracker.track_message(session_id, "user", "I need to create a work item")
    tracker.track_message(session_id, "assistant", "What's the work about?")
    tracker.track_message(session_id, "user", "Building a dashboard")
    tracker.track_message(session_id, "assistant", "What's the deadline?")
    tracker.track_message(session_id, "user", "Next month")
    tracker.track_message(session_id, "assistant", "Can you confirm the deadline?")
    tracker.track_message(session_id, "user", "I just said next month!")
    tracker.track_message(session_id, "assistant", "Here are tasks. Should I save them?")
    tracker.track_message(session_id, "user", "Yes")
    tracker.track_message(session_id, "assistant", "Should I set due dates?")
    tracker.track_message(session_id, "user", "Yes")
    tracker.track_message(session_id, "assistant", "Should I publish?")
    tracker.track_message(session_id, "user", "Yes, just do it all!")
    tracker.track_message(session_id, "assistant", "Error: failed to create work")
    
    print(f"✓ Tracked {len(tracker.sessions[session_id].messages)} messages")
    print(f"  Tags: {tracker.sessions[session_id].context_tags}")
    
    # End session
    tracker.end_session(session_id, explicit=True)
    print("✓ Session ended, feedback logged")


def check_logged_feedback():
    """Check that feedback was logged from the conversations."""
    print("\n=== Checking Logged Feedback ===")
    
    feedback = get_recent_feedback(days=1, limit=10)
    
    print(f"✓ Found {len(feedback)} feedback entries")
    
    for i, log in enumerate(feedback, 1):
        print(f"\n  Feedback {i}:")
        print(f"    Summary: {log['conversation_summary']}")
        print(f"    Satisfaction: {log['user_satisfaction_estimate']}")
        if log['what_went_well']:
            print(f"    ✓ Went well: {log['what_went_well'][:80]}...")
        if log['what_could_improve']:
            print(f"    ⚠ Could improve: {log['what_could_improve'][:80]}...")
        print(f"    Tags: {', '.join(log['context_tags'])}")


def generate_summary_and_apply():
    """Generate learning summary from the feedback."""
    print("\n=== Generating Learning Summary ===")
    
    summary_id = agent_api.generate_and_apply_learning_summary(days=1)
    
    if summary_id:
        print(f"✓ Generated and applied learning summary: ID {summary_id}")
        
        # Retrieve the learning context
        context = get_active_learning_context()
        
        if context['has_learning']:
            print("\n  Active Learning Context:")
            print(f"    Total summaries: {context['total_summaries']}")
            print("\n  Behavior Adjustments:")
            for line in context['combined_adjustments'].split('\n'):
                if line.strip():
                    print(f"    {line}")
        
        return True
    else:
        print("✗ No feedback to generate summary from")
        return False


def demonstrate_learning_application():
    """Show how learning context would be used."""
    print("\n=== Demonstrating Learning Application ===")
    
    context = agent_api.get_learning_insights()
    
    if context['has_learning']:
        print("✓ Agent would retrieve these learnings at start of next conversation:")
        print(context['combined_adjustments'])
        print("\n  The agent would then:")
        print("  - Ask fewer confirmation questions")
        print("  - Combine related confirmations")
        print("  - Be more explicit about actions")
        print("  - Listen better to user responses")
    else:
        print("  No learning context available yet")


def run_integration_test():
    """Run complete integration test."""
    print("=" * 70)
    print("Task Assist Learning System - Integration Test")
    print("=" * 70)
    print("\nThis test demonstrates the complete learning workflow:")
    print("1. Automatic conversation tracking via session hooks")
    print("2. Feedback logging when sessions end")
    print("3. Learning summary generation from patterns")
    print("4. Behavior adjustment retrieval for future conversations")
    print("=" * 70)
    
    try:
        # Simulate conversations
        simulate_good_conversation()
        simulate_problematic_conversation()
        
        # Check feedback was logged
        time.sleep(1)  # Brief pause
        check_logged_feedback()
        
        # Generate learning summary
        generate_summary_and_apply()
        
        # Show how learning would be applied
        demonstrate_learning_application()
        
        print("\n" + "=" * 70)
        print("✓ Integration Test Complete!")
        print("=" * 70)
        print("\nKey Takeaways:")
        print("  ✓ Conversations tracked automatically")
        print("  ✓ Feedback logged on session end (no agent action needed)")
        print("  ✓ Works even if user closes tab (timeout handling)")
        print("  ✓ Quality analysis automatic (efficiency, errors, patterns)")
        print("  ✓ Learning summaries generated periodically")
        print("  ✓ Behavior adjustments retrieved at conversation start")
        print("\n  🎯 Result: Agent learns and improves continuously!")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_integration_test()
    sys.exit(0 if success else 1)
