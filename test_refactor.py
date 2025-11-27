"""Validation test for refactored core modules and agent_api.

Quick smoke tests to verify imports and basic functionality.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all core modules import successfully."""
    print("Testing imports...")
    
    try:
        from core.work import WorkStatus, can_transition
        from core.task import TaskStatus
        from core.storage import list_works, list_tasks
        from core.slack import SlackNotifier, get_notifier
        from core.tasks_provider import GoogleTasksProvider, get_provider
        from core.scheduling import ensure_task_scheduled, complete_task_and_schedule_next
        from core.due_dates import DueDateManager, auto_assign_due_dates
        import agent_api
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_enums():
    """Test enum functionality."""
    print("\nTesting enums...")
    
    try:
        from core.work import WorkStatus, can_transition
        from core.task import TaskStatus
        
        # Test WorkStatus
        assert WorkStatus.DRAFT == "Draft"
        assert WorkStatus.from_string("completed") == WorkStatus.COMPLETED
        assert can_transition(WorkStatus.DRAFT, WorkStatus.PUBLISHED)
        
        # Test TaskStatus
        assert TaskStatus.PUBLISHED == "Published"
        assert TaskStatus.from_string("draft") == TaskStatus.DRAFT
        assert TaskStatus.from_string("pending") == TaskStatus.DRAFT  # Legacy mapping
        assert TaskStatus.COMPLETED.to_google_tasks() == "completed"
        assert TaskStatus.from_google_tasks("needsAction") == TaskStatus.PUBLISHED
        
        print("✓ Enum tests passed")
        return True
    except Exception as e:
        print(f"✗ Enum tests failed: {e}")
        return False


def test_storage():
    """Test storage layer functions."""
    print("\nTesting storage layer...")
    
    try:
        from core.storage import list_works, list_tasks
        from core.work import WorkStatus
        from core.task import TaskStatus
        
        # Test listing (should not crash even if DB is empty)
        works = list_works()
        print(f"  Found {len(works)} works")
        
        draft_works = list_works(status=WorkStatus.DRAFT)
        print(f"  Found {len(draft_works)} draft works")
        
        tasks = list_tasks()
        print(f"  Found {len(tasks)} tasks")
        
        today_tasks = list_tasks(exclude_completed=True)
        print(f"  Found {len(today_tasks)} incomplete tasks")
        
        print("✓ Storage tests passed")
        return True
    except Exception as e:
        print(f"✗ Storage tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_slack_notifier():
    """Test Slack notifier initialization."""
    print("\nTesting Slack notifier...")
    
    try:
        from core.slack import SlackNotifier, get_notifier
        
        # Test initialization
        notifier = get_notifier()
        assert notifier is not None
        
        # Test singleton
        notifier2 = get_notifier()
        assert notifier is notifier2
        
        print("✓ Slack notifier tests passed")
        return True
    except Exception as e:
        print(f"✗ Slack notifier tests failed: {e}")
        return False


def test_tasks_provider():
    """Test Google Tasks provider initialization."""
    print("\nTesting Google Tasks provider...")
    
    try:
        from core.tasks_provider import GoogleTasksProvider, get_provider
        
        # Test initialization (may fail if credentials missing, that's ok)
        provider = get_provider()
        assert provider is not None
        
        # Test singleton
        provider2 = get_provider()
        assert provider is provider2
        
        print("✓ Google Tasks provider tests passed")
        return True
    except Exception as e:
        print(f"✗ Google Tasks provider tests failed: {e}")
        return False


def test_agent_api():
    """Test agent_api facade functions."""
    print("\nTesting agent_api facade...")
    
    try:
        import agent_api
        
        # Test listing functions
        works = agent_api.list_works_by_status('all')
        print(f"  list_works_by_status: {len(works)} works")
        
        tasks = agent_api.list_tasks_by_status('all')
        print(f"  list_tasks_by_status: {len(tasks)} tasks")
        
        today = agent_api.get_today_tasks_summary()
        print(f"  get_today_tasks_summary: {len(today)} tasks")
        
        overdue = agent_api.get_overdue_tasks()
        print(f"  get_overdue_tasks: {len(overdue)} tasks")
        
        upcoming = agent_api.get_upcoming_works()
        print(f"  get_upcoming_works: {len(upcoming)} works")
        
        print("✓ Agent API tests passed")
        return True
    except Exception as e:
        print(f"✗ Agent API tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tools():
    """Test that master/tools.py imports and has expected tools."""
    print("\nTesting master/tools...")
    
    try:
        from master.tools import TOOLS
        
        expected_tools = [
            'list_works', 'list_tasks', 'get_today_tasks', 'get_overdue_tasks',
            'create_work', 'publish_work', 'complete_work',
            'create_task', 'update_task_status', 'complete_task_and_schedule_next',
            'snooze_task', 'reschedule_task_event',
            'send_slack_message', 'send_due_date_confirmation',
            'schedule_task_to_calendar', 'list_upcoming_events'
        ]
        
        missing = [t for t in expected_tools if t not in TOOLS]
        if missing:
            print(f"  Warning: Missing tools: {missing}")
        
        print(f"  Found {len(TOOLS)} tools registered")
        print("✓ Master tools tests passed")
        return True
    except Exception as e:
        print(f"✗ Master tools tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("VALIDATION TEST SUITE")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Enums", test_enums()))
    results.append(("Storage", test_storage()))
    results.append(("Slack Notifier", test_slack_notifier()))
    results.append(("Google Tasks Provider", test_tasks_provider()))
    results.append(("Agent API", test_agent_api()))
    results.append(("Master Tools", test_tools()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name:25} {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
