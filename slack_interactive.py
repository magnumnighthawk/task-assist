
import os
import pickle
import datetime
import requests
import logging
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


# Set up debug logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
app = Flask(__name__)

# --- Health check endpoint ---
@app.route('/health', methods=['GET'])
def health_check():
    """Read-only health check route for deployment verification."""
    logging.debug("Health check endpoint called.")
    return jsonify({"status": "ok", "message": "Service is healthy."}), 200

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
    logging.debug("/slack/interactivity endpoint called.")
    payload = request.form.get('payload')
    logging.debug(f"Raw payload: {payload}")
    if not payload:
        logging.error('No payload received from Slack.')
        return jsonify({"response_type": "ephemeral", "text": "No payload received."}), 400
    import json
    try:
        data = json.loads(payload)
    except Exception as e:
        logging.exception("Failed to parse payload JSON:")
        return jsonify({"response_type": "ephemeral", "text": f"Invalid payload: {e}"}), 400
    logging.info(f"Received Slack interactivity payload: {json.dumps(data, indent=2)}")
    actions = data.get('actions', [])
    user = data.get('user', {}).get('username')
    response_url = data.get('response_url')
    work_id = None
    due_dates = {}
    # First, check for submit button and extract work_id
    for action in actions:
        logging.debug(f"Processing action: {action}")
        if action['type'] == 'button' and action['action_id'].startswith('submit_'):
            try:
                work_id = int(action['action_id'].replace('submit_', ''))
            except Exception as e:
                logging.error(f"Error parsing button action: {e}")
    # If submit, extract all datepicker values from state.values
    if work_id is not None:
        state = data.get('state', {}).get('values', {})
        for block in state.values():
            for action_id, value in block.items():
                if value.get('type') == 'datepicker' and value.get('selected_date'):
                    try:
                        task_id = int(action_id.replace('due_', ''))
                        due_dates[task_id] = value['selected_date']
                    except Exception as e:
                        logging.error(f"Error parsing datepicker in state: {e}")
        logging.debug(f"Parsed work_id: {work_id}, due_dates: {due_dates}")
        if due_dates:
            try:
                from db import get_db, Task
                db_gen = get_db()
                db = next(db_gen)
                for task_id, due_str in due_dates.items():
                    task = db.query(Task).filter(Task.id == task_id).first()
                    if task:
                        logging.debug(f"Updating Task {task_id} due_date to {due_str}")
                        task.due_date = datetime.datetime.strptime(due_str, '%Y-%m-%d')
                db.commit()
                db.close()
                # Respond to Slack
                slack_response = requests.post(response_url, json={
                    "text": f"Due dates updated for Work ID {work_id} by {user}."
                })
                logging.info(f"Slack response status: {slack_response.status_code}, body: {slack_response.text}")
                logging.info(f"Due dates updated for Work ID {work_id} by {user}.")
                return jsonify({"response_type": "ephemeral", "text": "Due dates updated!"}), 200
            except Exception as e:
                logging.exception("Error updating due dates:")
                return jsonify({"response_type": "ephemeral", "text": f"Error updating due dates: {e}"}), 500
        else:
            logging.debug(f"No due dates found in state for work_id {work_id}.")
            return jsonify({"response_type": "ephemeral", "text": "No due dates found to update."}), 200
    # If not a submit or missing data, just acknowledge
    logging.debug("No action taken (not a submit or missing data). Returning default response.")
    return jsonify({"response_type": "ephemeral", "text": "No action taken."}), 200

# --- Endpoint to trigger Slack interactive notification for a specific work item ---
@app.route('/api/notify-work/<int:work_id>', methods=['POST'])
def notify_work(work_id):
    """Trigger the interactive Slack notification for a specific work item."""
    try:
        from reminder import ReminderAgent
        from db import get_db, Work
        from sqlalchemy.orm import joinedload
        agent = ReminderAgent()
        db_gen = get_db()
        db = next(db_gen)
        work = db.query(Work).options(joinedload(Work.tasks)).filter(Work.id == work_id).first()
        db.close()
        if not work:
            logging.warning(f"No work found with id {work_id}.")
            return jsonify({"status": "error", "message": f"No work found with id {work_id}."}), 404
        agent.send_interactive_work_notification(work)
        logging.info(f"Interactive Slack notification triggered for work item {work_id}.")
        return jsonify({"status": "success", "message": f"Interactive Slack notification sent for work {work_id}."}), 200
    except Exception as e:
        logging.exception("Failed to trigger Slack interactive notification for work:")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Endpoint to trigger Slack interactive notification for the latest work item ---
@app.route('/api/notify-latest-work', methods=['POST'])
def notify_latest_work():
    """Trigger the interactive Slack notification for the latest work item."""
    try:
        from reminder import ReminderAgent
        agent = ReminderAgent()
        latest_work = agent.fetch_latest_work()
        if not latest_work:
            logging.warning("No latest work found to send interactive notification.")
            return jsonify({"status": "error", "message": "No latest work found."}), 404
        agent.send_interactive_work_notification(latest_work)
        logging.info("Interactive Slack notification triggered for latest work item.")
        return jsonify({"status": "success", "message": "Interactive Slack notification sent for latest work."}), 200
    except Exception as e:
        logging.exception("Failed to trigger Slack interactive notification for latest work:")
        return jsonify({"status": "error", "message": str(e)}), 500
    
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
