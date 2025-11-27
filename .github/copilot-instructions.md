# Copilot Instructions for AI Coding Agents

## Project Overview
- **Task Assist** is an AI-powered workflow automation tool that decomposes high-level work into actionable subtasks, schedules them, and integrates with Slack and Google Calendar for notifications and reminders.
- The app is a multi-service Python project: **AI Agent (ADK)**, Flask API, Streamlit UI, Celery workers, Redis, and Nginx, orchestrated via Docker and Supervisor.

## CRITICAL: Source of Truth
- **`master/master_v1.spec.yaml`** is the **SINGLE SOURCE OF TRUTH** for the agent's behavior, tools, skills, domain model, and workflows.
- **ALWAYS consult and update the spec** when:
  - Adding/modifying agent tools (`master/tools.py`)
  - Changing work/task lifecycle logic
  - Adding new skills or workflows
  - Modifying agent behavior or constraints
  - Updating domain models or status values
- **DO NOT use `docs/` as source of truth** - the spec supersedes all other documentation.
- Keep the spec synchronized with code changes to maintain system integrity.

## Architecture & Key Components
- **AI Agent** (`master/agent.py`): Google ADK-powered agent that orchestrates work breakdown, task management, and user interactions. Runs on port 3000, accessible at `/agent` via nginx.
- **Agent Tools** (`master/tools.py`): Tool functions called by the agent to perform actions (create work, schedule tasks, send notifications, etc.).
- **Agent Spec** (`master/master_v1.spec.yaml`): Canonical specification defining agent behavior, tools, skills, domain model, and lifecycle flows.
- **Flask API** (`application.py`): REST endpoints for Slack interactivity, health checks, and legacy API operations.
- **Streamlit UI** (`streamlit_app.py`): User interface for managing work and tasks.
- **Core Modules** (`core/`): Business logic layer (storage, scheduling, Slack, tasks provider, work/task models).
- **Agent API** (`agent_api.py`): Facade providing high-level functions for agent tools to call.
- **Celery** (`celery_app.py`): Asynchronous task processing and scheduled jobs.
- **Redis**: Message broker for Celery and caching.
- **Database** (`db.py`): SQLAlchemy models and session management for Work and Task persistence.
- **Supervisor/Nginx**: Process management and reverse proxying in production.

## Developer Workflows
- **Local Development**: Use `honcho start` to launch all services (agent, flask, streamlit, celery, redis, schedule, slack).
- **Agent Development**: 
  - Agent runs via `adk web --port 3000 --agent-path master.agent:root_agent`
  - Accessible at `http://localhost:8000/agent` (proxied via nginx)
  - Direct access: `http://localhost:3000` when running standalone
- **Production/Cloud**: Use Docker/Podman with Supervisor managing all services.
- **Testing**: Add tests in a `tests/` directory and use `pytest`.

## Project Conventions & Patterns
- **Work/Task Lifecycle**: Defined in `master/master_v1.spec.yaml` under `work_lifecycle` and `behaviour` sections. Always reference the spec for lifecycle flows.
- **Status Values**:
  - Work: `Draft`, `Published`, `Completed` (per spec)
  - Task: `Pending`, `Published`, `Tracked`, `Completed` (per spec and code)
- **Agent Tools**: All tools in `master/tools.py` must be registered in the `TOOLS` dictionary and documented in the spec.
- **Core Modules Pattern**:
  - `core/storage.py`: Database query layer (with session management)
  - `core/work.py` / `core/task.py`: Domain models and enums
  - `core/scheduling.py`: Calendar/task scheduling logic
  - `core/slack.py`: Slack notification client
  - `core/tasks_provider.py`: Google Tasks API integration
- **Environment Variables**: Managed via `.env` (see `.env.sample`). Required: `GMP_API_KEY` for agent, `SLACK_WEBHOOK_URL`, OAuth credentials.
- **Service Startup**: All-in-one via `honcho start` (uses `Procfile`) or Supervisor in Docker.
- **UI/UX**: Prioritize clean, modern design with good typography, visual hierarchy, spacing, and accessible colors.

## Integration Points
- **Slack**: Configure app with interactivity endpoint at `/api/slack/interactivity`. Webhook URL in `.env`.
- **Google Calendar/Tasks**: Requires OAuth credentials (`credentials.json`) and token (`token.pickle`) in project root.
- **AI Agent (ADK)**: Uses Google Gemini API via `GMP_API_KEY` environment variable.

## Agent Development Guidelines
When modifying the agent system:

1. **Always Update the Spec First**: Before implementing changes to agent behavior, tools, or workflows, update `master/master_v1.spec.yaml` to reflect the intended design.

2. **Keep Spec and Code Synchronized**:
   - Adding a tool? Add it to spec's `tools` section AND `master/tools.py` AND the `TOOLS` dictionary
   - Changing workflow? Update spec's `work_lifecycle` or `behaviour` sections first
   - Modifying domain models? Update spec's `domain_model` section AND `db.py` / core models
   - Adding new skills? Document in spec's `skills` section

3. **Tool Development Pattern**:
   ```python
   def tool_my_feature(param: type) -> Dict[str, Any]:
       """Clear docstring explaining when to use this tool.
       
       Args:
           param: Description
           
       Returns:
           {"result": value}
       """
       result = agent_api.high_level_function(param)
       return {"result": result}
   ```
   Then register in `TOOLS = {...}` dictionary.

4. **Verification Steps**:
   - Check spec is updated
   - Check implementation matches spec
   - Check tool is registered
   - Verify status values match spec
   - Test agent can call the tool

## Service Access Points
- **Agent**: `http://localhost:8000/agent` (nginx) or `http://localhost:3000` (direct)
- **Flask API**: `http://localhost:8000/api` or `http://localhost:9000` (direct)
- **Streamlit UI**: `http://localhost:8000/app` or `http://localhost:8501` (direct)
- **Health Check**: `http://localhost:8000/`

## Examples
- Start all services: `honcho start`
- Run agent standalone: `adk web --port 3000 --agent-path master.agent:root_agent`
- Trigger Slack notification: `POST /api/notify-work/<work_id>`
- Get weekly status via agent: Use `tool_get_weekly_status()` (not `tool_daily_planner_digest()`)

## Critical Reminders
- **Spec is source of truth** - not docs, not comments, the spec file
- **Update spec when changing agent behavior** - this includes tools, workflows, domain models
- **Test agent after changes** - verify tools are callable and spec is accurate
- **Keep status values consistent** - match spec definitions exactly

---

*Always update both this file AND the spec when making architectural changes.*
