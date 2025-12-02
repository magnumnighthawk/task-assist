"""Slack notification and interactive messaging.

Consolidates all Slack formatting and sending logic with Block Kit support.
"""

import os
import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, date

from dotenv import load_dotenv
from db import Work, Task

load_dotenv()
logger = logging.getLogger(__name__)


class SlackNotifier:
    """Centralized Slack notification manager."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """Initialize with Slack webhook URL from env or parameter."""
        self.webhook_url = webhook_url or os.getenv('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            logger.warning("SLACK_WEBHOOK_URL not set. Slack notifications will be disabled.")
    
    def send_plain(self, message: str) -> bool:
        """Send a simple text message to Slack.
        
        Args:
            message: Plain text message
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.webhook_url:
            logger.warning("Cannot send Slack message: webhook URL not configured")
            return False
        
        payload = {"text": message}
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Slack notification failed: {response.status_code} - {response.text}")
                return False
            logger.info("Slack notification sent successfully")
            return True
        except Exception as e:
            logger.exception(f"Failed to send Slack notification: {e}")
            return False
    
    def send_interactive(self, work: Work) -> bool:
        """Send interactive Slack message for due date confirmation.
        
        Args:
            work: Work object with tasks to confirm dates for
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.webhook_url:
            logger.warning("Cannot send interactive message: webhook URL not configured")
            return False
        
        blocks = self._build_interactive_blocks(work)
        payload = {
            "blocks": blocks,
            "text": f"Please confirm or update due dates for work: {work.title}"
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Slack interactive message failed: {response.status_code} - {response.text}")
                return False
            logger.info(f"Slack interactive notification sent for Work ID {work.id}")
            return True
        except Exception as e:
            logger.exception(f"Failed to send Slack interactive message: {e}")
            return False
    
    def send_publish(self, work: Work, calendar_task: Optional[Task] = None) -> bool:
        """Send publication notification for a work item.
        
        Args:
            work: Published work item
            calendar_task: Task that was added to calendar (optional)
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.webhook_url:
            logger.warning("Cannot send publish message: webhook URL not configured")
            return False
        
        blocks = self._build_publish_blocks(work, calendar_task)
        payload = {
            "blocks": blocks,
            "text": f"Work '{work.title}' published"
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Slack publish notification failed: {response.status_code} - {response.text}")
                return False
            logger.info(f"Slack publish notification sent for Work ID {work.id}")
            return True
        except Exception as e:
            logger.exception(f"Failed to send Slack publish notification: {e}")
            return False
    
    def send_task_completed(self, task: Task, work: Work) -> bool:
        """Send notification that a task was completed.
        
        Args:
            task: Completed task
            work: Parent work item
            
        Returns:
            True if sent successfully
        """
        message = f"✅ Task completed: '{task.title}' in work '{work.title}'"
        return self.send_plain(message)
    
    def send_work_completed(self, work: Work) -> bool:
        """Send notification that a work item was completed.
        
        Args:
            work: Completed work item
            
        Returns:
            True if sent successfully
        """
        task_count = len(work.tasks) if hasattr(work, 'tasks') else 0
        message = f"🎉 Work completed: '{work.title}' ({task_count} tasks finished)"
        return self.send_plain(message)
    
    def send_snooze_followup(self, task: Task, work: Work) -> bool:
        """Send notification for tasks snoozed multiple times.
        
        Args:
            task: Snoozed task
            work: Parent work item
            
        Returns:
            True if sent successfully
        """
        message = f"⏰ *{task.title}* snoozed {task.snooze_count}x - Consider breaking it down?"
        return self.send_plain(message)
    
    def send_daily_reminder(self, tasks: List[Task]) -> bool:
        """Send daily reminder with today's planned tasks.
        
        Args:
            tasks: List of tasks due today
            
        Returns:
            True if sent successfully
        """
        if not tasks:
            return True  # No reminder needed
        
        task_lines = [f"📌 {t.title}" for t in tasks]
        message = "☀️ *Today's Tasks*\n" + "\n".join(task_lines)
        return self.send_plain(message)
    
    def send_grouped_alert(self, work: Work, changes: List[str]) -> bool:
        """Send grouped notification for multiple changes to a work item.
        
        Args:
            work: Work item with changes
            changes: List of change descriptions
            
        Returns:
            True if sent successfully
        """
        message = f"🔔 *{work.title}* - Updates\n" + "\n".join([f"  • {c}" for c in changes])
        return self.send_plain(message)
    
    def send_event_created(self, task: Task, work: Work) -> bool:
        """Send notification that a calendar event was created.
        
        Args:
            task: Task with created event
            work: Parent work item
            
        Returns:
            True if sent successfully
        """
        due_str = task.due_date.strftime('%b %d') if task.due_date else ''
        message = f"📅 *Scheduled:* {task.title}" + (f" - {due_str}" if due_str else "")
        return self.send_plain(message)
    
    def send_event_updated(self, task: Task, work: Work) -> bool:
        """Send notification that a calendar event was updated.
        
        Args:
            task: Task with updated event
            work: Parent work item
            
        Returns:
            True if sent successfully
        """
        due_str = task.due_date.strftime('%b %d') if task.due_date else ''
        message = f"📆 *Rescheduled:* {task.title}" + (f" - {due_str}" if due_str else "")
        return self.send_plain(message)
    
    def _build_interactive_blocks(self, work: Work) -> List[Dict[str, Any]]:
        """Build Block Kit blocks for interactive due date confirmation.
        
        Args:
            work: Work object with tasks
            
        Returns:
            List of Block Kit block dictionaries
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📋 Confirm Due Dates"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{work.title}*\n{work.description or 'No description'}"
                }
            },
            {"type": "divider"}
        ]
        
        # Add a block for each task with datepicker
        for task in work.tasks:
            due_str = task.due_date.strftime('%Y-%m-%d') if task.due_date else date.today().strftime('%Y-%m-%d')
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📌 *{task.title}*\nDue: {due_str}"
                },
                "accessory": {
                    "type": "datepicker",
                    "action_id": f"due_{task.id}",
                    "initial_date": due_str,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select date"
                    }
                }
            })
        
        # Add submit button
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Submit Due Dates"
                    },
                    "style": "primary",
                    "action_id": f"submit_{work.id}"
                }
            ]
        })
        
        return blocks
    
    def _build_publish_blocks(self, work: Work, calendar_task: Optional[Task] = None) -> List[Dict[str, Any]]:
        """Build Block Kit blocks for publish notification.
        
        Args:
            work: Published work item
            calendar_task: Task added to calendar
            
        Returns:
            List of Block Kit block dictionaries
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚀 Work Published"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{work.title}*\n{work.description or ''}"
                }
            }
        ]
        
        # Add calendar task info if present
        if calendar_task:
            due_str = calendar_task.due_date.strftime('%B %d, %Y') if calendar_task.due_date else 'No due date'
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📅 *First task scheduled*\n{calendar_task.title}\nDue: {due_str}"
                }
            })
        
        return blocks


# Global singleton instance
_default_notifier: Optional[SlackNotifier] = None


def get_notifier() -> SlackNotifier:
    """Get or create the default SlackNotifier instance."""
    global _default_notifier
    if _default_notifier is None:
        _default_notifier = SlackNotifier()
    return _default_notifier
