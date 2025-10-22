
# Task Assist: Concept & Real-World Flow

Task Assist is a personal assistant that helps you break down work into manageable actions, track progress, and get reminders/notifications via Slack and calendar.

## How it Works

- Takes a work & break down into manageable tasks using AI
- User reviews and approves the breakdown, sets tentative due dates and confirms
- Work & tasks breakdown is stored and each work is tracked to completion smartly
- Tasks are added one at a time to Google Calendar & it's progress in monitored.
- Upon completion, subsequent tasks from the Work are added to tracked to completion
- Progress is monitored & user is nudged/notified periodically through Slack

## Deployment & Architecture

- Runs as a multi-service Docker container (Flask API, Streamlit UI, Nginx, Supervisor)
- Deployable to Azure Web App for Containers (cloud-ready, log streaming, environment config)
- All logs and errors are visible in Azure Log Stream for easy debugging