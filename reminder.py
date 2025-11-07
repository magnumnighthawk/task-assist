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
SCOPES = ['https://www.googleapis.com/auth/calendar']
TIMEZONE = 'Europe/London'
load_dotenv()


def get_calendar_service():
    """Return a Google Calendar API service instance.

    This version removes safety gates and assumes credentials/service are available.
    """
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # Build service (credentials may be None; assume environment provides access)
    service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
    return service


def get_calendar_credentials():
    """Load and return Google credentials from token.pickle if present."""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # Try a silent refresh if possible
    try:
        if creds and getattr(creds, 'expired', False) and getattr(creds, 'refresh_token', None):
            creds.refresh(Request())
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
    except Exception:
        pass
    return creds


def _check_google_connectivity(*args, **kwargs):
    """Connectivity check stub: always assume connectivity."""
    return True

class ReminderAgent:
    def notify_event_created(self, task, work):
        self.send_slack_notification(f"Calendar event created for Task '{task.title}' in Work '{work.title}'.")

    def notify_event_updated(self, task, work):
        self.send_slack_notification(f"Calendar event updated for Task '{task.title}' in Work '{work.title}'.")

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
        # Initialize credentials/service without extra guards
        self.creds = get_calendar_credentials()
        self.service = build('calendar', 'v3', credentials=self.creds, cache_discovery=False)
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')

    # --- Watch management (in-app) ---
    def create_calendar_watch(self, channel_id: str, address: str, ttl_seconds: int = 3600):
        """Create a calendar watch channel for the primary calendar events collection.

        Stores the channel info in DB so the app can manage renewals and stop channels later.
        """
        body = {
            'id': channel_id,
            'type': 'web_hook',
            'address': address,
            'params': {'ttl': str(ttl_seconds)}
        }
        resp = self.service.events().watch(calendarId='primary', body=body).execute()
        # resp contains 'id', 'resourceId', 'expiration' (ms since epoch)
        resource_id = resp.get('resourceId')
        expiration_ms = resp.get('expiration')
        expiration = None
        if expiration_ms:
            expiration = datetime.datetime.fromtimestamp(int(expiration_ms) / 1000.0)
        # Save to DB
        from db import get_db, create_watch_channel
        db_gen = get_db()
        db = next(db_gen)
        try:
            wc = create_watch_channel(db, channel_id=resp.get('id', channel_id), resource_id=resource_id, address=address, expiration=expiration)
        finally:
            db.close()
        return resp

    def stop_calendar_watch(self, channel_id: str, resource_id: str = None):
        """Stop a watch channel and remove it from DB."""
        body = {'id': channel_id}
        if resource_id:
            body['resourceId'] = resource_id
        self.service.channels().stop(body=body).execute()
        # Remove from DB
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
                if not ch.expiration or (ch.expiration - now).total_seconds() < 300:
                    # Needs renewal (create a new channel with a new channel_id)
                    new_channel_id = f"channel-{int(datetime.datetime.utcnow().timestamp())}-{ch.id}"
                    resp = self.create_calendar_watch(new_channel_id, ch.address)
                    expiration_ms = resp.get('expiration')
                    expiration = None
                    if expiration_ms:
                        expiration = datetime.datetime.fromtimestamp(int(expiration_ms) / 1000.0)
                    update_watch_channel_expiration(db, resp.get('id', new_channel_id), expiration)
        finally:
            db.close()
    
    def create_event(self, summary, start_time, end_time, description=None):
        """Create a new calendar event."""
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time,  # Format: 'YYYY-MM-DDTHH:MM:SS+00:00'
                'timeZone': TIMEZONE,
            },
            'end': {
                'dateTime': end_time,
                'timeZone': TIMEZONE,
            }
        }
        logger = logging.getLogger('reminder.create_event')
        max_retries = 3
        backoff = 2
        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                # Prefer using the googleapiclient service if available
                if self.service:
                    created_event = self.service.events().insert(calendarId='primary', body=event).execute()
                    logger.info('Event created: %s', created_event.get('htmlLink'))
                    return created_event
                # If service is not available but we have creds, try a direct REST call using requests
                if self.creds:
                    created_event = self._create_event_via_requests(event)
                    logger.info('Event created via requests fallback: %s', created_event.get('htmlLink'))
                    return created_event
                raise RuntimeError('No calendar service or credentials available to create event')
            except socket.timeout as e:
                last_exception = e
                logger.warning('Timeout when creating calendar event (attempt %s/%s): %s', attempt, max_retries, e)
            except Exception as e:
                # Some other network or API error - log and retry for transient cases
                last_exception = e
                logger.exception('Error when creating calendar event (attempt %s/%s): %s', attempt, max_retries, e)
            if attempt < max_retries:
                sleep_time = backoff * attempt
                logger.info('Retrying create_event in %s seconds...', sleep_time)
                time.sleep(sleep_time)
        # If we reach here, all retries failed
        logger.error('Failed to create calendar event after %s attempts', max_retries)
        raise last_exception
    
    def update_event(self, event_id, updated_data):
        """Update an existing event with new data."""
        logger = logging.getLogger('reminder.update_event')
        max_retries = 3
        backoff = 2
        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                event = self.service.events().get(calendarId='primary', eventId=event_id).execute()
                event.update(updated_data)
                updated_event = self.service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
                logger.info('Event updated: %s', updated_event.get('htmlLink'))
                return updated_event
            except socket.timeout as e:
                last_exception = e
                logger.warning('Timeout when updating calendar event (attempt %s/%s): %s', attempt, max_retries, e)
            except Exception as e:
                last_exception = e
                logger.exception('Error when updating calendar event (attempt %s/%s): %s', attempt, max_retries, e)
            if attempt < max_retries:
                sleep_time = backoff * attempt
                logger.info('Retrying update_event in %s seconds...', sleep_time)
                time.sleep(sleep_time)
        logger.error('Failed to update calendar event after %s attempts', max_retries)
        raise last_exception
    
    def delete_event(self, event_id):
        """Delete an event from the calendar."""
        self.service.events().delete(calendarId='primary', eventId=event_id).execute()
        print('Event deleted successfully.')

    def _create_event_via_requests(self, event_body):
        """Fallback: create an event using the Calendar REST API via requests.

        This avoids using httplib2 and relies on the credentials' valid access token.
        """
        logger = logging.getLogger('reminder.create_event_requests')
        if not self.creds:
            raise RuntimeError('No credentials available for requests-based event create')
        # Ensure the token is fresh
        if getattr(self.creds, 'expired', False) and getattr(self.creds, 'refresh_token', None):
            try:
                self.creds.refresh(Request())
                with open('token.pickle', 'wb') as token:
                    pickle.dump(self.creds, token)
            except Exception as e:
                logger.warning('Failed to refresh creds before requests call: %s', e)

        # Build request
        access_token = getattr(self.creds, 'token', None)
        if not access_token:
            raise RuntimeError('No access token available on credentials')

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events'
        resp = requests.post(url, json=event_body, headers=headers, timeout=30)
        if resp.status_code not in (200, 201):
            logger.error('Requests-based event create failed: %s - %s', resp.status_code, resp.text)
            resp.raise_for_status()
        return resp.json()
    
    def reschedule_event(self, event_id, new_start_time, new_end_time):
        """Reschedule an event by updating its start and end times."""
        updated_data = {
            'start': {
                'dateTime': new_start_time,
                'timeZone': TIMEZONE,
            },
            'end': {
                'dateTime': new_end_time,
                'timeZone': TIMEZONE,
            }
        }
        return self.update_event(event_id, updated_data)
    
    def list_upcoming_events(self, max_results=10):
        """List upcoming events from the calendar."""
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        events_result = self.service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime').execute()
        events = events_result.get('items', [])
        if not events:
            print('No upcoming events found.')
        else:
            print("Upcoming events:")
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                print(f"ID: {event['id']}, Start: {start}, Summary: {event['summary']}")
        return events
    
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
