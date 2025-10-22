import os
import pickle
import datetime
import requests
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Define the scopes and timezone.
SCOPES = ['https://www.googleapis.com/auth/calendar']
TIMEZONE = 'Europe/London'
load_dotenv()

def get_calendar_service():
    """Authenticate and return a Google Calendar API service instance."""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('calendar', 'v3', credentials=creds)
    return service

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
    def create_event_for_task(self, task, work_title):
        """Create a calendar event for a Task and update the DB with the event ID."""
        from db import get_db, update_task_calendar_event
        db_gen = get_db()
        db = next(db_gen)
        summary = f"{work_title}: {task.title}"
        start_time = task.due_date.isoformat() if task.due_date else (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat()
        end_time = (task.due_date + datetime.timedelta(hours=1)).isoformat() if task.due_date else (datetime.datetime.utcnow() + datetime.timedelta(days=1, hours=1)).isoformat()
        event = self.create_event(summary, start_time, end_time, description=None)
        update_task_calendar_event(db, task.id, event['id'])
        db.close()
        return event

    def complete_task_and_schedule_next(self, task, work):
        """Mark task as completed, create event for next task if any, and update work status if all done."""
        from db import get_db, update_task_status, get_tasks_by_work, complete_work
        db_gen = get_db()
        db = next(db_gen)
        update_task_status(db, task.id, 'Completed')
        # Find next uncompleted task
        tasks = get_tasks_by_work(db, work.id)
        next_task = next((t for t in tasks if t.status != 'Completed'), None)
        if next_task:
            self.create_event_for_task(next_task, work.title)
            update_task_status(db, next_task.id, 'Tracked')
        else:
            complete_work(db, work.id)
        db.close()

    def snooze_task(self, task, work, days=1):
        """Snooze a task by moving its event and due date, increment snooze count, and send follow-up if needed."""
        from db import get_db, increment_task_snooze, update_task_status
        db_gen = get_db()
        db = next(db_gen)
        new_due = (task.due_date or datetime.datetime.utcnow()) + datetime.timedelta(days=days)
        # Update event
        if task.calendar_event_id:
            self.reschedule_event(task.calendar_event_id, new_due.isoformat(), (new_due + datetime.timedelta(hours=1)).isoformat())
        # Update task due date and snooze count
        task.due_date = new_due
        increment_task_snooze(db, task.id)
        db.commit()
        # If snoozed > 3 times, send follow-up and allow user to break up or update Work
        if task.snooze_count >= 3:
            self.notify_snooze_followup(task, work)
            # Optionally, trigger a workflow to break up or update the Work (could be a Slack action or UI prompt)
        db.close()

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
        self.service = get_calendar_service()
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    
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
        created_event = self.service.events().insert(calendarId='primary', body=event).execute()
        print('Event created:', created_event.get('htmlLink'))
        return created_event
    
    def update_event(self, event_id, updated_data):
        """Update an existing event with new data."""
        event = self.service.events().get(calendarId='primary', eventId=event_id).execute()
        event.update(updated_data)
        updated_event = self.service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        print('Event updated:', updated_event.get('htmlLink'))
        return updated_event
    
    def delete_event(self, event_id):
        """Delete an event from the calendar."""
        self.service.events().delete(calendarId='primary', eventId=event_id).execute()
        print('Event deleted successfully.')
    
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
