# Copilot Instructions for AI Coding Agents

## Project Overview
- **Task Assist** is a workflow automation tool that decomposes high-level work into actionable subtasks, schedules them, and integrates with Slack and Google Calendar for notifications and reminders.
- The app is a multi-service Python project: Flask API, Streamlit UI, Celery workers, Redis, and Nginx, orchestrated via Docker and Supervisor.
- All major documentation is in the `docs/` directory. The root `README.md` provides a full project overview and setup instructions.

## Architecture & Key Components
- **Flask API** (`application.py`): Handles REST endpoints for Slack interactivity, health checks, and task management.
- **Streamlit UI** (`streamlit_app.py`): Main user interface for managing work and tasks.
- **Celery** (`celery_app.py`): Asynchronous task processing, scheduled via APScheduler.
- **Redis**: Used as a message broker for Celery and for caching.
- **Database** (`db.py`): Handles persistent storage of work and task items.
- **Slack Integration** (`slack_interactive.py`): Manages Slack notifications and interactive message handling.
- **Google Calendar Integration**: Managed via reminders and scheduling logic in `reminder.py` and `schedule.py`.
- **Supervisor/Nginx**: Used for process management and reverse proxying in production (see `supervisord.conf`, `nginx.conf`).

## Developer Workflows
- **Local Development**: Use `honcho start` to launch all services as defined in the `Procfile`.
- **Production/Cloud**: Use Docker (`docker build -t task-assist .` and `docker run ...`) or Podman. See `README.md` for full instructions.
- **Testing**: No dedicated test suite is present by default; add tests in a `tests/` directory and use `pytest`.
- **Celery Worker**: Start with `celery -A celery_app worker --loglevel=info`.
- **Streamlit UI**: Run with `streamlit run streamlit_app.py`.

## Project Conventions & Patterns
- **Task/Work Lifecycle**: See `docs/LIFECYCLE.md` for the canonical flow from work creation to completion, including calendar and Slack integration.
- **Environment Variables**: Managed via `.env` (see `.env.sample`).
- **Secrets**: OAuth tokens and credentials are expected in the project root (e.g., `token.pickle`, `credentials.json`).
- **Service Startup**: All-in-one startup via `honcho` (uses `Procfile`).
- **UI/UX**: Improve project's UI to look modern and beautiful. Please prioritize suggestions that refine typography, enhance visual hierarchy, improve spacing, and involve well-chosen, accessible color schemes. Ensure the UI looks clean, professional, and appealing.
- **Documentation**: All non-README documentation is in `docs/`.

## Integration Points
- **Slack**: Configure your Slack app and set the interactivity endpoint to `/slack/interactivity`.
- **Google Calendar**: Requires OAuth credentials and token setup.
- **Azure**: Deployment instructions for Azure Kubernetes and Web App for Containers are in `docs/DEPLOYMENT.md`.

## Examples
- To trigger a Slack notification for a work item: `POST /api/notify-work/<work_id>` (see `application.py`).
- To start all services locally: `honcho start` (uses `Procfile`).
- To run the Streamlit UI: `streamlit run streamlit_app.py`.

## References
- See `README.md` for setup, architecture, and usage.
- See `docs/` for deployment, lifecycle, and roadmap details.

---

*Update this file if you add new services, change integration patterns, or adopt new conventions. Keep instructions concise and actionable for future AI agents and developers.*
