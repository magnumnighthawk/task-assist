# Task Assist

An AI-powered workflow automation tool that streamlines task management through intelligent decomposition, scheduling, Slack notifications, and integration with productivity tools. The app runs as a multi-service container (Flask API, Streamlit UI, Nginx reverse proxy) and is deployable to Azure Web App for Containers.

## Overview

Task Assist breaks down complex tasks into actionable subtasks using AI, tracks their progress, and manages reminders with calendar integration. The application leverages asynchronous processing to handle task scheduling and execution efficiently.

## Features

- **AI-Powered Task Decomposition**: Breaks down high-level tasks into actionable subtasks with priority levels
- **Web Interface**: Streamlit dashboard for task/work management
- **Flask API**: REST endpoints for Slack interactive notifications and health checks
- **Slack Integration**: Interactive Slack notifications for due date confirmation and updates, triggered from the UI or API
- **Asynchronous Processing**: Uses Celery with Redis for efficient task handling
- **Scheduled Execution**: Implements APScheduler for timed task execution
- **Calendar Integration**: Connects with Google Calendar for deadlines and reminders
- **Dockerized Multi-Service App**: Flask, Streamlit, and Nginx run in a single container
- **Azure Web App Deployment**: Ready for cloud deployment as a container

## Technology Stack

- Python
- LangChain and OpenAI
- Streamlit
- Flask
- Celery and Redis
- APScheduler
- Google Calendar API
- Slack API
- Docker, Supervisor, Nginx
- Azure Web App for Containers

## Installation

docker build -t task-assist .
docker run -p 80:80 --env-file .env task-assist

### Local Development (All-in-One)
1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/task-assist.git
   cd task-assist
   ```
2. **Install system dependencies**
   - On macOS:
     ```bash
     brew install nginx redis
     ```
   - On Linux (Debian/Ubuntu):
     ```bash
     sudo apt-get update && sudo apt-get install -y nginx redis-server
     ```
   - On Windows: Use WSL or install via package manager.
3. **Set up Python environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install honcho
   ```
4. **Configure environment variables**
   ```bash
   cp .env.sample .env
   # Edit .env with your API keys and configurations
   ```
5. **Set up Google Calendar (if using reminder features)**
   - Configure OAuth credentials following Google's documentation
   - Save OAuth token as `token.pickle` in the project root
6. **Start all services locally**
   ```bash
   honcho start
   ```
   This uses the `Procfile` to launch Flask, Streamlit, Celery, Redis, Nginx, and other services in parallel.

### Docker (Recommended for Production/Cloud)
Build and run the multi-service container:
```bash
podman build -t task-assist .
podman run -p 8000:8000 --env-file .env task-assist
```
This launches all services (Flask, Streamlit, Celery, Redis, Nginx, etc.) in a single container using Supervisor. Access the app at `http://localhost:8000`.

### Azure Web App for Containers
1. Push your Docker image to a registry (ACR or Docker Hub).
2. Create an Azure Web App for Containers and configure it to use your image.
3. Set environment variables in the Azure portal.
4. Use Azure Log Stream to view logs from all services.

## Usage

### Web Interface (Streamlit)
Access at `http://localhost/` (or your Azure Web App URL). Manage tasks, works, and trigger Slack notifications from the UI.

### Slack Integration
- Configure your Slack app and set the interactivity endpoint to `/slack/interactivity` (e.g., `https://<your-app>.azurewebsites.net/slack/interactivity`).
- Use the "Notify" button in the UI to send interactive Slack messages for due date confirmation and updates.
- Slack users can update due dates directly from Slack; changes sync back to the database.

## Implementation Components

- **generate.py**: AI-based task decomposition
- **execute_and_verify.py**: Task management and CLI
- **streamlit_app.py**: Web interface (UI)
- **reminder.py**: Calendar and Slack integration
- **slack_interactive.py**: Flask API for Slack endpoints and notifications
- **celery_app.py**: Asynchronous task processing
- **schedule.py**: Task scheduling
- **supervisord.conf**: Multi-service process management
- **nginx.conf**: Reverse proxy for Flask and Streamlit

## Contributing

Contributions welcome. Please fork the repository and submit pull requests.