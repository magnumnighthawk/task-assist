#!/usr/bin/env python3
"""Test script for the learning and feedback system.

Tests the core functionality of logging feedback, generating summaries,
and retrieving learning context.
"""

import sys
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, '.')

from core.feedback import (
    log_conversation_feedback,
    get_recent_feedback,
    generate_learning_summary_from_feedback,
    apply_learning_summary,
    get_active_learning_context,
    deactivate_old_summaries
)


def test_log_feedback():
    """Test logging conversation feedback."""
    print("\n=== Testing Feedback Logging ===")
    
    # Log some sample feedback
    feedback_id1 = log_conversation_feedback(
        conversation_summary="Created work 'Build landing page' with 4 tasks",
        what_went_well="User provided clear requirements, quick confirmation",
        what_could_improve="Asked too many confirmation questions - could combine them",
        user_satisfaction_estimate="High",
        context_tags=["work_creation", "due_dates"]
    )
    
    print(f"✓ Logged feedback 1: ID {feedback_id1}")
    
    feedback_id2 = log_conversation_feedback(
        conversation_summary="User requested weekly status report",
        what_went_well="Quick retrieval, clear formatting",
        what_could_improve="Could add more context about upcoming deadlines",
        user_satisfaction_estimate="Medium",
        context_tags=["status_check", "weekly_report"]
    )
    
    print(f"✓ Logged feedback 2: ID {feedback_id2}")
    
    feedback_id3 = log_conversation_feedback(
        conversation_summary="Re-planned work 'Q4 report' with adjusted dates",
        what_went_well="Successfully proposed new dates",
        what_could_improve="User had to explain deadline twice - listen better",
        user_satisfaction_estimate="Medium",
        context_tags=["replanning", "due_dates"]
    )
    
    print(f"✓ Logged feedback 3: ID {feedback_id3}")
    
    return feedback_id1, feedback_id2, feedback_id3


def test_retrieve_feedback():
    """Test retrieving recent feedback."""
    print("\n=== Testing Feedback Retrieval ===")
    
    recent = get_recent_feedback(days=30, limit=10)
    print(f"✓ Retrieved {len(recent)} feedback logs")
    
    for log in recent[:3]:  # Show first 3
        print(f"\n  Feedback {log['id']}:")
        print(f"    Summary: {log['conversation_summary']}")
        print(f"    Satisfaction: {log['user_satisfaction_estimate']}")
        print(f"    Tags: {', '.join(log['context_tags'])}")
    
    return recent


def test_generate_summary():
    """Test generating learning summary."""
    print("\n=== Testing Summary Generation ===")
    
    summary_data = generate_learning_summary_from_feedback(days=30)
    
    if summary_data:
        print("✓ Generated learning summary:")
        print(f"  Period: {summary_data['period_start']} to {summary_data['period_end']}")
        print(f"  Conversations: {summary_data['total_conversations']}")
        print(f"\n  Key Learnings:")
        for line in summary_data['key_learnings'].split('\n'):
            if line.strip():
                print(f"    {line}")
        print(f"\n  Behavior Adjustments:")
        for line in summary_data['behavior_adjustments'].split('\n'):
            if line.strip():
                print(f"    {line}")
        
        return summary_data
    else:
        print("✗ No feedback data to generate summary from")
        return None


def test_apply_summary(summary_data):
    """Test applying learning summary."""
    print("\n=== Testing Summary Application ===")
    
    if not summary_data:
        print("✗ No summary data to apply")
        return None
    
    summary_id = apply_learning_summary(summary_data)
    
    if summary_id:
        print(f"✓ Applied learning summary: ID {summary_id}")
        return summary_id
    else:
        print("✗ Failed to apply summary")
        return None


def test_get_learning_context():
    """Test retrieving learning context."""
    print("\n=== Testing Learning Context Retrieval ===")
    
    context = get_active_learning_context()
    
    print(f"Has learning: {context['has_learning']}")
    
    if context['has_learning']:
        print(f"Total summaries: {context['total_summaries']}")
        print("\nCombined Adjustments:")
        print(context['combined_adjustments'])
        
        print("\nSummary Details:")
        for i, summary in enumerate(context['summaries'], 1):
            print(f"\n  Summary {i} ({summary['period']}):")
            print(f"    Conversations: {summary['conversations']}")
            print(f"    Key Learnings: {summary['key_learnings'][:100]}...")
    else:
        print("No active learning summaries found")
    
    return context


def test_deactivate_old():
    """Test deactivating old summaries."""
    print("\n=== Testing Old Summary Deactivation ===")
    
    count = deactivate_old_summaries(keep_recent=2)
    print(f"✓ Deactivated {count} old summaries")
    
    return count


def run_all_tests():
    """Run all tests in sequence."""
    print("=" * 60)
    print("Testing Task Assist Learning & Feedback System")
    print("=" * 60)
    
    try:
        # Test feedback logging
        ids = test_log_feedback()
        
        # Test retrieval
        feedback_logs = test_retrieve_feedback()
        
        # Test summary generation
        summary_data = test_generate_summary()
        
        # Test summary application
        summary_id = test_apply_summary(summary_data)
        
        # Test learning context retrieval
        context = test_get_learning_context()
        
        # Test deactivation
        deactivate_count = test_deactivate_old()
        
        # Final context check
        print("\n=== Final Learning Context Check ===")
        final_context = get_active_learning_context()
        print(f"Active summaries: {final_context['total_summaries']}")
        
        print("\n" + "=" * 60)
        print("✓ All tests completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
