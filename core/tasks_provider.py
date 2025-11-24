"""Google Tasks API provider wrapper.

Clean abstraction for Google Tasks operations with status normalization
and time format handling.
"""

import os
import pickle
import logging
import time
import socket
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .task import TaskStatus

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/tasks']
DEFAULT_TASKLIST_NAME = "Task manager"


class GoogleTasksProvider:
    """Wrapper for Google Tasks API operations."""
    
    def __init__(self, credentials_path: str = 'credentials.json', 
                 token_path: str = 'token.pickle'):
        """Initialize the Google Tasks provider.
        
        Args:
            credentials_path: Path to OAuth credentials JSON
            token_path: Path to store/load token pickle
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None
        self.service = None
        self._tasklist_id_cache = None
        
        self._initialize_credentials()
    
    def _initialize_credentials(self):
        """Load or refresh Google credentials."""
        # Try loading existing token
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'rb') as token:
                    self.creds = pickle.load(token)
                logger.info("Loaded credentials from token file")
            except Exception as e:
                logger.warning(f"Failed to load token: {e}")
                self.creds = None
        
        # Check if credentials are valid
        try:
            if self.creds and not getattr(self.creds, 'expired', False):
                self._build_service()
                return
        except Exception:
            pass
        
        # Refresh expired credentials
        try:
            if self.creds and getattr(self.creds, 'expired', False) and getattr(self.creds, 'refresh_token', None):
                self.creds.refresh(Request())
                with open(self.token_path, 'wb') as token:
                    pickle.dump(self.creds, token)
                logger.info("Refreshed credentials")
                self._build_service()
                return
        except Exception as e:
            logger.warning(f"Failed to refresh credentials: {e}")
            self.creds = None
        
        # Interactive OAuth flow if needed
        if not self.creds and os.path.exists(self.credentials_path):
            try:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                self.creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
                with open(self.token_path, 'wb') as token:
                    pickle.dump(self.creds, token)
                logger.info("Completed OAuth flow and saved credentials")
                self._build_service()
            except Exception as e:
                logger.error(f"OAuth flow failed: {e}")
                self.creds = None
    
    def _build_service(self):
        """Build the Google Tasks API service client."""
        if self.creds:
            try:
                self.service = build('tasks', 'v1', credentials=self.creds, cache_discovery=False)
                logger.info("Google Tasks service initialized")
            except Exception as e:
                logger.error(f"Failed to build service: {e}")
                self.service = None
    
    def get_tasklist_id(self, title: str = DEFAULT_TASKLIST_NAME) -> str:
        """Get or create a tasklist by title.
        
        Args:
            title: Tasklist title
            
        Returns:
            Tasklist ID
        """
        if self._tasklist_id_cache:
            return self._tasklist_id_cache
        
        if not self.service:
            logger.warning("No service available, returning default tasklist")
            return '@default'
        
        try:
            # List existing tasklists
            resp = self.service.tasklists().list(maxResults=100).execute()
            items = resp.get('items', [])
            
            for item in items:
                if item.get('title') == title:
                    self._tasklist_id_cache = item.get('id')
                    logger.info(f"Found tasklist '{title}': {self._tasklist_id_cache}")
                    return self._tasklist_id_cache
            
            # Create if not found
            created = self.service.tasklists().insert(body={'title': title}).execute()
            self._tasklist_id_cache = created.get('id')
            logger.info(f"Created tasklist '{title}': {self._tasklist_id_cache}")
            return self._tasklist_id_cache
        
        except Exception as e:
            logger.exception(f"Failed to get/create tasklist: {e}")
            return '@default'
    
    def create_task(self, title: str, notes: Optional[str] = None, 
                    due: Optional[datetime] = None, status: TaskStatus = TaskStatus.PUBLISHED) -> Optional[Dict[str, Any]]:
        """Create a new Google Task.
        
        Args:
            title: Task title
            notes: Task notes/description
            due: Due datetime
            status: Internal task status (converted to Google Tasks format)
            
        Returns:
            Created task resource or None on failure
        """
        if not self.service:
            logger.error("Cannot create task: service not initialized")
            return None
        
        task_body = {'title': title}
        
        if notes:
            task_body['notes'] = notes
        
        if due:
            # Ensure RFC3339 format with timezone
            due_str = self._format_datetime(due)
            task_body['due'] = due_str
        
        task_body['status'] = status.to_google_tasks()
        
        tasklist_id = self.get_tasklist_id()
        max_retries = 3
        
        for attempt in range(1, max_retries + 1):
            try:
                created = self.service.tasks().insert(tasklist=tasklist_id, body=task_body).execute()
                logger.info(f"Created task: {created.get('id')}")
                return created
            except socket.timeout as e:
                logger.warning(f"Timeout creating task (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    time.sleep(2 * attempt)
            except Exception as e:
                logger.exception(f"Error creating task (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    time.sleep(2 * attempt)
        
        logger.error(f"Failed to create task after {max_retries} attempts")
        return None
    
    def update_task(self, task_id: str, title: Optional[str] = None, 
                    notes: Optional[str] = None, due: Optional[datetime] = None,
                    status: Optional[TaskStatus] = None) -> Optional[Dict[str, Any]]:
        """Update an existing Google Task.
        
        Args:
            task_id: Google Task ID
            title: New title (None to keep current)
            notes: New notes (None to keep current)
            due: New due datetime (None to keep current)
            status: New status (None to keep current)
            
        Returns:
            Updated task resource or None on failure
        """
        if not self.service:
            logger.error("Cannot update task: service not initialized")
            return None
        
        tasklist_id = self.get_tasklist_id()
        
        try:
            # Fetch current task
            task = self.service.tasks().get(tasklist=tasklist_id, task=task_id).execute()
            
            # Apply updates
            if title is not None:
                task['title'] = title
            if notes is not None:
                task['notes'] = notes
            if due is not None:
                task['due'] = self._format_datetime(due)
            if status is not None:
                task['status'] = status.to_google_tasks()
            
            # Update
            updated = self.service.tasks().update(tasklist=tasklist_id, task=task_id, body=task).execute()
            logger.info(f"Updated task: {task_id}")
            return updated
        
        except Exception as e:
            logger.exception(f"Failed to update task {task_id}: {e}")
            return None
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a Google Task.
        
        Args:
            task_id: Google Task ID
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.service:
            logger.error("Cannot delete task: service not initialized")
            return False
        
        tasklist_id = self.get_tasklist_id()
        
        try:
            self.service.tasks().delete(tasklist=tasklist_id, task=task_id).execute()
            logger.info(f"Deleted task: {task_id}")
            return True
        except Exception as e:
            logger.exception(f"Failed to delete task {task_id}: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single Google Task.
        
        Args:
            task_id: Google Task ID
            
        Returns:
            Task resource or None if not found
        """
        if not self.service:
            logger.error("Cannot get task: service not initialized")
            return None
        
        tasklist_id = self.get_tasklist_id()
        
        try:
            task = self.service.tasks().get(tasklist=tasklist_id, task=task_id).execute()
            return task
        except Exception as e:
            logger.exception(f"Failed to get task {task_id}: {e}")
            return None
    
    def list_tasks(self, show_completed: bool = False, max_results: int = 100) -> List[Dict[str, Any]]:
        """List tasks from the default tasklist.
        
        Args:
            show_completed: Whether to include completed tasks
            max_results: Maximum number of tasks to return
            
        Returns:
            List of task resources
        """
        if not self.service:
            logger.error("Cannot list tasks: service not initialized")
            return []
        
        tasklist_id = self.get_tasklist_id()
        
        try:
            result = self.service.tasks().list(
                tasklist=tasklist_id,
                maxResults=max_results,
                showCompleted=show_completed
            ).execute()
            
            tasks = result.get('items', [])
            logger.info(f"Listed {len(tasks)} tasks")
            return tasks
        except Exception as e:
            logger.exception(f"Failed to list tasks: {e}")
            return []
    
    def list_upcoming_tasks(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """List upcoming tasks with due dates in the future.
        
        Args:
            max_results: Maximum number of tasks to return
            
        Returns:
            List of upcoming task resources
        """
        tasks = self.list_tasks(show_completed=False, max_results=100)
        now = datetime.utcnow()
        upcoming = []
        
        for task in tasks:
            if 'due' in task:
                try:
                    due_dt = self._parse_datetime(task['due'])
                    if due_dt >= now:
                        upcoming.append(task)
                except Exception:
                    continue
        
        return upcoming[:max_results]
    
    def complete_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Mark a Google Task as completed.
        
        Args:
            task_id: Google Task ID
            
        Returns:
            Updated task resource or None on failure
        """
        return self.update_task(task_id, status=TaskStatus.COMPLETED)
    
    def _format_datetime(self, dt: datetime) -> str:
        """Format datetime for Google Tasks API (RFC3339).
        
        Args:
            dt: Datetime to format
            
        Returns:
            RFC3339 formatted string
        """
        # Ensure timezone info
        iso_str = dt.isoformat()
        if iso_str.endswith('Z') or '+' in iso_str or (iso_str.count('-') > 2):
            return iso_str
        return iso_str + 'Z'
    
    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime from Google Tasks API format.
        
        Args:
            dt_str: RFC3339 formatted string
            
        Returns:
            Parsed datetime
        """
        # Handle Z suffix
        if dt_str.endswith('Z'):
            dt_str = dt_str.replace('Z', '+00:00')
        return datetime.fromisoformat(dt_str)


# Global singleton instance
_default_provider: Optional[GoogleTasksProvider] = None


def get_provider() -> GoogleTasksProvider:
    """Get or create the default GoogleTasksProvider instance."""
    global _default_provider
    if _default_provider is None:
        _default_provider = GoogleTasksProvider()
    return _default_provider
