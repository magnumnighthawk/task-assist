import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
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
        # Save the credentials for the next run.
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)
    return service

def add_event_to_calendar(task_description, start_time, end_time):
    service = get_calendar_service()

    event = {
        'summary': task_description,
        'start': {
            'dateTime': start_time,  # e.g., '2025-03-01T09:00:00-07:00'
            'timeZone': 'Europe/London',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'Europe/London',
        },
    }
    
    event_result = service.events().insert(calendarId='primary', body=event).execute()
    print('Event created:', event_result.get('htmlLink'))

if __name__ == '__main__':
    add_event_to_calendar(
        "Review Task Assist Reminder 2",
        "2025-03-03T16:00:00+00:00",
        "2025-03-03T17:00:00+00:00"
    )
