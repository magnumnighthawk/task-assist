# Task Assist

An AI-powered workflow automation tool that streamlines task management through intelligent decomposition, scheduling, and integration with productivity tools.

## Overview

Task Assist breaks down complex tasks into actionable subtasks using AI, tracks their progress, and manages reminders with calendar integration. The application leverages asynchronous processing to handle task scheduling and execution efficiently.

## Features

- **AI-Powered Task Decomposition**: Breaks down high-level tasks into actionable subtasks with priority levels
- **Web Interface**: Simple dashboard built with Streamlit for task management
- **Asynchronous Processing**: Uses Celery with Redis for efficient task handling
- **Scheduled Execution**: Implements APScheduler for timed task execution
- **Calendar Integration**: Connects with Google Calendar for deadlines and reminders
- **Notification Support**: Includes Slack notification capabilities

## Technology Stack

- Python
- LangChain and OpenAI
- Streamlit
- Celery and Redis
- APScheduler
- Google Calendar API

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/task-assist.git
   cd task-assist
   ```

2. **Set up the environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.sample .env
   # Edit .env with your API keys and configurations
   ```

4. **Set up Google Calendar (if using reminder features)**
   - Configure OAuth credentials following Google's documentation
   - Save OAuth token as `token.pickle` in the project root

## Usage

### Web Interface
```bash
streamlit run streamlit_app.py
```

### Command Line Interface
```bash
python execute_and_verify.py
```

### Start Celery Worker (for async processing)
```bash
celery -A celery_app worker --loglevel=info
```

### Start Scheduler
```bash
python schedule.py
```

## Implementation Components

- **generate.py**: AI-based task decomposition
- **execute_and_verify.py**: Task management and CLI
- **streamlit_app.py**: Web interface
- **reminder.py**: Calendar integration
- **celery_app.py**: Asynchronous task processing
- **schedule.py**: Task scheduling

## Contributing

Contributions welcome. Please fork the repository and submit pull requests.