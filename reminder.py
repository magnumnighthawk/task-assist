import os
import pickle
import datetime
import requests
import time
import logging
import socket
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Keep scopes/timezone simple. Assume credentials and service will work.
SCOPES = ['https://www.googleapis.com/auth/tasks']
TIMEZONE = 'Europe/London'
load_dotenv()


def get_calendar_service():
    """Return a Google Tasks API service instance (keeps function name for compatibility).

    The project previously used Calendar events; this changes to Tasks API v1.
    """
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # Build service for Google Tasks
    service = build('tasks', 'v1', credentials=creds, cache_discovery=False)
    return service


def get_calendar_credentials():
    """Load and return Google credentials from token.pickle if present."""
    creds = None
    # Try to load existing token.pickle
    if os.path.exists('token.pickle'):
        try:
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        except Exception:
            creds = None

    # If we have credentials and they're still valid, return them immediately
    try:
        if creds and not getattr(creds, 'expired', False):
            return creds
    except Exception:
        # If inspection fails, fall back to the normal flow below
        creds = None

    # If we have credentials and they're expired, try to refresh using the refresh token
    try:
        if creds and getattr(creds, 'expired', False) and getattr(creds, 'refresh_token', None):
            creds.refresh(Request())
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
            return creds
    except Exception:
        # Fall through to re-run the flow
        creds = None

    # If no valid creds, attempt interactive OAuth flow using credentials.json
    creds_file = 'credentials.json'
    if os.path.exists(creds_file):
        try:
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            # run_local_server will open a browser for the user to consent and perform redirect
            creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
            return creds
        except Exception:
            # If interactive flow fails (headless), just return None
            return None
    # No ADC/service-account fallback: keep behavior simple for local interactive auth only
    return None


def _check_google_connectivity(*args, **kwargs):
    """Connectivity check stub: always assume connectivity."""
    return True

class ReminderAgent:
    def notify_event_created(self, task, work):
        self.send_slack_notification(f"Google Task created for Task '{task.title}' in Work '{work.title}'.")

    def notify_event_updated(self, task, work):
        self.send_slack_notification(f"Google Task updated for Task '{task.title}' in Work '{work.title}'.")

    def notify_task_completed(self, task, work):
        self.send_slack_notification(f"Task '{task.title}' in Work '{work.title}' marked as completed!")

    def notify_work_completed(self, work):
        # Summarize stats
        stats = f"Work '{work.title}' completed! {len(work.tasks)} tasks done."
        self.send_slack_notification(stats)

    def notify_snooze_followup(self, task, work):
        self.send_slack_notification(f"Task '{task.title}' in Work '{work.title}' has been snoozed {task.snooze_count} times. Please review if it needs to be broken up or updated.")

    def send_daily_reminder(self):
        from db import get_db, get_all_tasks
        db_gen = get_db()
        db = next(db_gen)
        today = datetime.datetime.now().date()
        tasks = get_all_tasks(db)
        planned = [t for t in tasks if t.due_date and t.due_date.date() == today and t.status != 'Completed']
        if planned:
            msg = "Planned events for today:\n" + "\n".join([f"- {t.title} (Work: {t.work.title})" for t in planned])
            self.send_slack_notification(msg)
        db.close()

    def notify_grouped_alert(self, work, changes):
        # changes: list of strings
        msg = f"Updates for Work '{work.title}':\n" + "\n".join(changes)
        self.send_slack_notification(msg)

    def create_event_for_task(self, task, work_title: str):
        """
        Create a calendar event for a Task and update the DB with the event ID.
        """
        from contextlib import contextmanager
        from db import get_db, update_task_calendar_event

        @contextmanager
        def db_session():
            db_gen = get_db()
            db = next(db_gen)
            try:
                yield db
            finally:
                db.close()

        summary = f"{work_title}: {task.title}"
        start_time = task.due_date.isoformat() if task.due_date else (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat()
        end_time = (task.due_date + datetime.timedelta(hours=1)).isoformat() if task.due_date else (datetime.datetime.utcnow() + datetime.timedelta(days=1, hours=1)).isoformat()
        event = self.create_event(summary, start_time, end_time, description=None)
        with db_session() as db:
            update_task_calendar_event(db, task.id, event['id'])
        return event

    def complete_task_and_schedule_next(self, task, work):
        """
        Mark task as completed, create event for next task if any, and update work status if all done.
        """
        from contextlib import contextmanager
        from db import get_db, update_task_status, get_tasks_by_work, complete_work

        @contextmanager
        def db_session():
            db_gen = get_db()
            db = next(db_gen)
            try:
                yield db
            finally:
                db.close()

        with db_session() as db:
            update_task_status(db, task.id, 'Completed')
            tasks = get_tasks_by_work(db, work.id)
            next_task = next((t for t in tasks if t.status != 'Completed'), None)
            if next_task:
                self.create_event_for_task(next_task, work.title)
                update_task_status(db, next_task.id, 'Tracked')
            else:
                complete_work(db, work.id)

    def snooze_task(self, task, work, days: int = 1):
        """
        Snooze a task by moving its event and due date, increment snooze count, and send follow-up if needed.
        """
        from contextlib import contextmanager
        from db import get_db, increment_task_snooze, update_task_status

        @contextmanager
        def db_session():
            db_gen = get_db()
            db = next(db_gen)
            try:
                yield db
            finally:
                db.close()

        new_due = (task.due_date or datetime.datetime.utcnow()) + datetime.timedelta(days=days)
        if task.calendar_event_id:
            self.reschedule_event(task.calendar_event_id, new_due.isoformat(), (new_due + datetime.timedelta(hours=1)).isoformat())
        with db_session() as db:
            task.due_date = new_due
            increment_task_snooze(db, task.id)
            db.commit()
            if task.snooze_count >= 3:
                self.notify_snooze_followup(task, work)

    def sync_event_update_to_db(self, event_id, updates):
        """When a calendar event is updated directly, sync changes to the DB (due date, title, description, completion, deletion, snooze)."""
        from db import get_db, Task
        db_gen = get_db()
        db = next(db_gen)
        task = db.query(Task).filter(Task.calendar_event_id == event_id).first()
        if not task:
            db.close()
            return
        if 'dateTime' in updates.get('start', {}):
            task.due_date = datetime.datetime.fromisoformat(updates['start']['dateTime'])
        if 'summary' in updates:
            task.title = updates['summary']
        if 'description' in updates:
            task.description = updates['description']
        if updates.get('status') == 'completed':
            task.status = 'Completed'
        db.commit()
        db.close()

    def process_event_by_id(self, event_id):
        """Fetch an event from Google Calendar by event_id and sync it to the DB.

        This helper is useful for webhook handlers that receive an event_id and want
        the application to reconcile changes.
        """
        event = self.service.events().get(calendarId='primary', eventId=event_id).execute()
        updates = {}
        if 'start' in event:
            updates['start'] = event['start']
        if 'end' in event:
            updates['end'] = event['end']
        if 'summary' in event:
            updates['summary'] = event['summary']
        if 'description' in event:
            updates['description'] = event['description']
        if 'status' in event:
            updates['status'] = event['status']
        self.sync_event_update_to_db(event_id, updates)
    
    def fetch_latest_work(self):
        """Fetch the latest Work item from the database, eagerly loading tasks."""
        from db import get_db, Work
        from sqlalchemy.orm import joinedload
        db_gen = get_db()
        db = next(db_gen)
        latest_work = db.query(Work).options(joinedload(Work.tasks)).order_by(Work.created_at.desc()).first()
        db.close()
        return latest_work
    
    def __init__(self):
        # Initialize credentials/service with better logging and graceful fallbacks
        logger = logging.getLogger('reminder.init')
        try:
            self.creds = get_calendar_credentials()
            if self.creds:
                logger.info('Google credentials loaded successfully.')
            else:
                logger.warning('No Google credentials found. Google Tasks functionality will be limited.')
        except Exception as e:
            self.creds = None
            logger.exception('Error while loading Google credentials: %s', e)

        # Attempt to build the Tasks service if credentials are present; otherwise set to None
        try:
            if self.creds:
                self.service = build('tasks', 'v1', credentials=self.creds, cache_discovery=False)
            else:
                self.service = None
        except Exception as e:
            self.service = None
            logger.exception('Failed to initialize Google Tasks service: %s', e)

        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        # Cache for the tasklist id to avoid repeated lookups
        self._tasklist_id = None

    def get_tasklist_id(self, title: str = "Task manager"):
        """Return the tasklist id for a given title, creating the list if necessary.

        Uses the service if available; otherwise uses direct HTTP requests with the stored credentials.
        Caches the id in-memory for subsequent calls.
        """
        if self._tasklist_id:
            return self._tasklist_id

        # Try using the service client first
        try:
            if self.service:
                resp = self.service.tasklists().list(maxResults=100).execute()
                items = resp.get('items', []) if isinstance(resp, dict) else []
                for it in items:
                    if it.get('title') == title:
                        self._tasklist_id = it.get('id')
                        return self._tasklist_id
                # Not found - create it
                created = self.service.tasklists().insert(body={'title': title}).execute()
                self._tasklist_id = created.get('id')
                return self._tasklist_id
        except Exception:
            # Fall back to requests-based approach below
            pass

        # If we don't have a service but have credentials, use requests to list/create
        if self.creds:
            try:
                access_token = getattr(self.creds, 'token', None)
                if not access_token and getattr(self.creds, 'refresh_token', None):
                    try:
                        self.creds.refresh(Request())
                        with open('token.pickle', 'wb') as token:
                            pickle.dump(self.creds, token)
                        access_token = getattr(self.creds, 'token', None)
                    except Exception:
                        access_token = None
                if access_token:
                    headers = {'Authorization': f'Bearer {access_token}'}
                    url = 'https://tasks.googleapis.com/tasks/v1/users/@me/lists'
                    r = requests.get(url, headers=headers, timeout=20)
                    if r.status_code == 200:
                        items = r.json().get('items', [])
                        for it in items:
                            if it.get('title') == title:
                                self._tasklist_id = it.get('id')
                                return self._tasklist_id
                    # Create list
                    r2 = requests.post(url, json={'title': title}, headers=headers, timeout=20)
                    if r2.status_code in (200, 201):
                        self._tasklist_id = r2.json().get('id')
                        return self._tasklist_id
            except Exception:
                pass

        # As a last resort, return the default string (deprecated) so calls don't blow up
        return '@default'

    # --- Watch management (in-app) ---
    def create_calendar_watch(self, channel_id: str, address: str, ttl_seconds: int = 3600):
        """Tasks API does not support push/watch channels like Calendar.

        This method is retained for compatibility but will raise NotImplementedError.
        """
        raise NotImplementedError('Google Tasks API does not support watch channels; remove usage or implement polling instead')

    def stop_calendar_watch(self, channel_id: str, resource_id: str = None):
        """Stop a watch channel - not supported for Tasks API. Will remove DB record if present."""
        from db import get_db, delete_watch_channel
        db_gen = get_db()
        db = next(db_gen)
        try:
            delete_watch_channel(db, channel_id)
        finally:
            db.close()

    def renew_all_watches(self):
        """Renew watch channels found in DB by creating new watch channels before expiration.

        This is a simple approach: for channels expiring within next N minutes, recreate the watch and update DB.
        """
        from db import get_db, get_all_watch_channels, update_watch_channel_expiration
        db_gen = get_db()
        db = next(db_gen)
        try:
            channels = get_all_watch_channels(db)
            now = datetime.datetime.utcnow()
            for ch in channels:
                # Tasks API doesn't support watches; clear or mark expired watches so DB doesn't pile up
                if not ch.expiration or (ch.expiration - now).total_seconds() < 300:
                    update_watch_channel_expiration(db, ch.channel_id, None)
        finally:
            db.close()
    
    def create_event(self, summary, start_time, end_time, description=None):
        """Create a new Google Task (keeps name create_event for compatibility).

        start_time/end_time are legacy params (from calendar); Tasks only supports a single due time.
        We use start_time as the Task 'due' timestamp if provided.
        Returns the created task resource.
        """
        task_body = {
            'title': summary,
            'notes': description,
        }
        # Prefer start_time as due if present
        if start_time:
            # Ensure RFC3339 format. If naive ISO string provided, append 'Z' if missing timezone.
            due = start_time
            if due.endswith('Z') is False and ('+' not in due and '-' not in due[10:]):
                due = due + 'Z'
            task_body['due'] = due

        logger = logging.getLogger('reminder.create_task')
        max_retries = 3
        backoff = 2
        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                if self.service:
                    tl = self.get_tasklist_id()
                    created_task = self.service.tasks().insert(tasklist=tl, body=task_body).execute()
                    logger.info('Task created: %s', created_task.get('selfLink'))
                    return created_task
                if self.creds:
                    created_task = self._create_event_via_requests(task_body)
                    logger.info('Task created via requests fallback: %s', created_task.get('selfLink'))
                    return created_task
                raise RuntimeError('No tasks service or credentials available to create task')
            except socket.timeout as e:
                last_exception = e
                logger.warning('Timeout when creating task (attempt %s/%s): %s', attempt, max_retries, e)
            except Exception as e:
                last_exception = e
                logger.exception('Error when creating task (attempt %s/%s): %s', attempt, max_retries, e)
            if attempt < max_retries:
                sleep_time = backoff * attempt
                logger.info('Retrying create_task in %s seconds...', sleep_time)
                time.sleep(sleep_time)
        logger.error('Failed to create task after %s attempts', max_retries)
        raise last_exception
    
    def update_event(self, event_id, updated_data):
        """Update an existing Google Task. `updated_data` should map to Task fields (title, notes, due, status).

        Keeps name update_event for compatibility.
        """
        logger = logging.getLogger('reminder.update_task')
        max_retries = 3
        backoff = 2
        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                tl = self.get_tasklist_id()
                task = self.service.tasks().get(tasklist=tl, task=event_id).execute()
                # Map calendar-like structure to tasks fields if necessary
                if 'summary' in updated_data:
                    task['title'] = updated_data['summary']
                if 'description' in updated_data:
                    task['notes'] = updated_data['description']
                if 'start' in updated_data and isinstance(updated_data['start'], dict) and 'dateTime' in updated_data['start']:
                    due = updated_data['start']['dateTime']
                    # Normalize to RFC3339 for Tasks API (append 'Z' if naive)
                    if isinstance(due, str):
                        if due.endswith('Z') is False and ('+' not in due and '-' not in due[10:]):
                            due = due + 'Z'
                    task['due'] = due
                if 'status' in updated_data:
                    # Map 'completed' to tasks status
                    if updated_data['status'] == 'completed':
                        task['status'] = 'completed'
                    else:
                        # Tasks API expects 'needsAction' (or 'completed'). Map other internal states to 'needsAction'
                        task['status'] = 'needsAction'
                tl = self.get_tasklist_id()
                updated_task = self.service.tasks().update(tasklist=tl, task=event_id, body=task).execute()
                logger.info('Task updated: %s', updated_task.get('selfLink'))
                return updated_task
            except socket.timeout as e:
                last_exception = e
                logger.warning('Timeout when updating task (attempt %s/%s): %s', attempt, max_retries, e)
            except Exception as e:
                last_exception = e
                logger.exception('Error when updating task (attempt %s/%s): %s', attempt, max_retries, e)
            if attempt < max_retries:
                sleep_time = backoff * attempt
                logger.info('Retrying update_task in %s seconds...', sleep_time)
                time.sleep(sleep_time)
        logger.error('Failed to update task after %s attempts', max_retries)
        raise last_exception
    
    def delete_event(self, event_id):
        """Delete a Google Task by id (keeps name delete_event)."""
        try:
            tl = self.get_tasklist_id()
            self.service.tasks().delete(tasklist=tl, task=event_id).execute()
            print('Task deleted successfully.')
        except Exception as e:
            print(f'Failed to delete task: {e}')

    def _create_event_via_requests(self, event_body):
        """Fallback: create a Task using the Tasks REST API via requests.

        Accepts a task-like dict and returns the created Task resource.
        """
        logger = logging.getLogger('reminder.create_task_requests')
        if not self.creds:
            raise RuntimeError('No credentials available for requests-based task create')
        # Ensure the token is fresh
        if getattr(self.creds, 'expired', False) and getattr(self.creds, 'refresh_token', None):
            try:
                self.creds.refresh(Request())
                with open('token.pickle', 'wb') as token:
                    pickle.dump(self.creds, token)
            except Exception as e:
                logger.warning('Failed to refresh creds before requests call: %s', e)

        access_token = getattr(self.creds, 'token', None)
        if not access_token:
            raise RuntimeError('No access token available on credentials')

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        tl = self.get_tasklist_id()
        # Use REST endpoint for tasks in a specific list
        url = f'https://www.googleapis.com/tasks/v1/lists/{tl}/tasks'
        resp = requests.post(url, json=event_body, headers=headers, timeout=30)
        if resp.status_code not in (200, 201):
            logger.error('Requests-based task create failed: %s - %s', resp.status_code, resp.text)
            resp.raise_for_status()
        return resp.json()
    
    def reschedule_event(self, event_id, new_start_time, new_end_time):
        """Reschedule a Task by updating its due timestamp.

        new_start_time is used as the Task 'due' value. end time is ignored (Tasks have a single due).
        """
        updated_data = {}
        if new_start_time:
            updated_data['start'] = {'dateTime': new_start_time}
        return self.update_event(event_id, updated_data)
    
    def list_upcoming_events(self, max_results=10):
        """List upcoming Tasks from the default tasklist and return those with due dates in the future.

        Note: Tasks API doesn't support time-based querying; we fetch recent tasks and filter by due.
        """
        tl = self.get_tasklist_id()
        tasks_result = self.service.tasks().list(tasklist=tl, maxResults=100, showCompleted=False).execute()
        items = tasks_result.get('items', [])
        now = datetime.datetime.utcnow()
        upcoming = []
        for t in items:
            if 'due' in t:
                try:
                    due_dt = datetime.datetime.fromisoformat(t['due'].replace('Z', '+00:00'))
                    if due_dt >= now:
                        upcoming.append(t)
                except Exception:
                    continue
        if not upcoming:
            print('No upcoming tasks found.')
        else:
            print('Upcoming tasks:')
            for t in upcoming[:max_results]:
                print(f"ID: {t.get('id')}, Due: {t.get('due')}, Title: {t.get('title')}")
        return upcoming[:max_results]
    
    def send_slack_notification(self, message):
        """Send a Slack notification using an incoming webhook."""
        if not self.slack_webhook_url:
            print('Slack webhook URL not set in environment variables.')
            return
        payload = {
            "text": message
        }
        response = requests.post(self.slack_webhook_url, json=payload)
        if response.status_code != 200:
            print('Failed to send Slack notification:', response.text)
        else:
            print('Slack notification sent successfully.')

    def send_interactive_work_notification(self, work):
        """Send an interactive Slack message for due date confirmation and update."""
        from slack_interactive import send_interactive_work_notification
        send_interactive_work_notification(work, self.slack_webhook_url)

    def send_publish_notification(self, work):
        """Send a simpler publish Slack notification (non-interactive) when work is published."""
        try:
            from slack_interactive import send_publish_work_notification
            send_publish_work_notification(work, self.slack_webhook_url)
        except Exception as e:
            print(f"Failed to send publish notification: {e}")

def main():
    agent = ReminderAgent()
    while True:
        print("\nOptions:")
        print("1. Create a new event")
        print("2. Update an existing event")
        print("3. Delete an event")
        print("4. Reschedule an event")
        print("5. List upcoming events")
        print("6. Send a Slack notification")
        print("7. Fetch latest Work item and send Slack confirmation")
        print("8. Exit")

        choice = input("Choose an option (1-8): ")

        if choice == '1':
            summary = input("Enter event summary: ")
            start_time = input("Enter start time (YYYY-MM-DDTHH:MM:SS+00:00): ")
            end_time = input("Enter end time (YYYY-MM-DDTHH:MM:SS+00:00): ")
            description = input("Enter event description (optional): ")
            agent.create_event(summary, start_time, end_time, description)

        elif choice == '2':
            event_id = input("Enter event ID to update: ")
            updated_data = {}
            summary = input("Enter new summary (leave blank to keep current): ")
            if summary:
                updated_data['summary'] = summary
            description = input("Enter new description (leave blank to keep current): ")
            if description:
                updated_data['description'] = description
            start_time = input("Enter new start time (leave blank to keep current): ")
            if start_time:
                updated_data['start'] = {'dateTime': start_time, 'timeZone': TIMEZONE}
            end_time = input("Enter new end time (leave blank to keep current): ")
            if end_time:
                updated_data['end'] = {'dateTime': end_time, 'timeZone': TIMEZONE}
            agent.update_event(event_id, updated_data)

        elif choice == '3':
            event_id = input("Enter event ID to delete: ")
            agent.delete_event(event_id)

        elif choice == '4':
            event_id = input("Enter event ID to reschedule: ")
            new_start_time = input("Enter new start time (YYYY-MM-DDTHH:MM:SS+00:00): ")
            new_end_time = input("Enter new end time (YYYY-MM-DDTHH:MM:SS+00:00): ")
            agent.reschedule_event(event_id, new_start_time, new_end_time)

        elif choice == '5':
            max_results = int(input("Enter the number of upcoming events to list: "))
            agent.list_upcoming_events(max_results)

        elif choice == '6':
            message = input("Enter message to send: ")
            agent.send_slack_notification(message)

        elif choice == '7':
            latest_work = agent.fetch_latest_work()
            if not latest_work:
                print("No Work items found in the database.")
            else:
                agent.send_interactive_work_notification(latest_work)
                print("Interactive Slack notification sent for latest Work item.\nMake sure the Flask server is running to handle Slack interactivity.")

        elif choice == '8':
            print("Exiting...")
            break

        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
