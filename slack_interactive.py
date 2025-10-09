import os
import pickle
import datetime
import requests
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from flask import Flask, request, jsonify
import threading

# Define the scopes and timezone.
SCOPES = ['https://www.googleapis.com/auth/calendar']
TIMEZONE = 'Europe/London'
load_dotenv()

app = Flask(__name__)

# --- IMPORTANT: For Slack interactivity to work, your Flask app must be accessible from the public internet.
# Use ngrok (https://ngrok.com/) for local development:
#   ngrok http 5050
# Then set your Slack app's Interactivity Request URL to:
#   https://<your-ngrok-subdomain>.ngrok.io/slack/interactivity
#
# Watch your Flask logs for incoming POSTs and errors.

# --- Google Calendar/Slack/DB logic (copied from reminder.py, with necessary imports) ---
# ...existing ReminderAgent and DB logic will be here...

# --- Flask endpoint for Slack interactive events ---
@app.route('/slack/interactivity', methods=['POST'])
def slack_interactivity():
    import logging
    logging.basicConfig(level=logging.INFO)
    payload = request.form.get('payload')
    if not payload:
        logging.error('No payload received from Slack.')
        return jsonify({"response_type": "ephemeral", "text": "No payload received."}), 400
    import json
    data = json.loads(payload)
    logging.info(f"Received Slack interactivity payload: {json.dumps(data, indent=2)}")
    actions = data.get('actions', [])
    user = data.get('user', {}).get('username')
    response_url = data.get('response_url')
    work_id = None
    due_dates = {}
    for action in actions:
        if action['type'] == 'datepicker':
            task_id = int(action['action_id'].replace('due_', ''))
            due_dates[task_id] = action['selected_date']
        elif action['type'] == 'button' and action['action_id'].startswith('submit_'):
            work_id = int(action['action_id'].replace('submit_', ''))
    if work_id and due_dates:
        try:
            from db import get_db, Task
            db_gen = get_db()
            db = next(db_gen)
            for task_id, due_str in due_dates.items():
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.due_date = datetime.datetime.strptime(due_str, '%Y-%m-%d')
            db.commit()
            db.close()
            # Respond to Slack
            requests.post(response_url, json={
                "text": f"Due dates updated for Work ID {work_id} by {user}."
            })
            logging.info(f"Due dates updated for Work ID {work_id} by {user}.")
            return jsonify({"response_type": "ephemeral", "text": "Due dates updated!"}), 200
        except Exception as e:
            logging.exception("Error updating due dates:")
            return jsonify({"response_type": "ephemeral", "text": f"Error updating due dates: {e}"}), 500
    # If not a submit or missing data, just acknowledge
    return jsonify({"response_type": "ephemeral", "text": "No action taken."}), 200

# --- Helper to send interactive Slack message ---
def send_interactive_work_notification(work, slack_webhook_url):
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Work Item Confirmation Needed*\n*Title:* {work.title}\n*Description:* {work.description}"}
        },
        {"type": "divider"}
    ]
    for task in work.tasks:
        due = task.due_date.strftime('%Y-%m-%d') if task.due_date else 'No due date'
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Task:* {task.title}\nCurrent Due: {due}"},
            "accessory": {
                "type": "datepicker",
                "action_id": f"due_{task.id}",
                "initial_date": task.due_date.strftime('%Y-%m-%d') if task.due_date else datetime.date.today().strftime('%Y-%m-%d'),
                "placeholder": {"type": "plain_text", "text": "Select due date"}
            }
        })
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Submit Due Dates"},
                "style": "primary",
                "action_id": f"submit_{work.id}"
            }
        ]
    })
    payload = {"blocks": blocks, "text": "Please confirm or update due dates for these tasks."}
    requests.post(slack_webhook_url, json=payload)

# --- Threaded Flask server start ---
def start_flask():
    app.run(host='0.0.0.0', port=5000)

def main():
    # ...existing CLI logic...
    # For option 7:
    # latest_work = agent.fetch_latest_work()
    # send_interactive_work_notification(latest_work, agent.slack_webhook_url)
    # print("Interactive Slack notification sent for latest Work item.")
    pass

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5050)
