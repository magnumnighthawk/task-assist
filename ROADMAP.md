
# Roadmap / TODO

This document tracks completed features, future improvements, and architectural considerations for the project.

## ✅ Completed
- Slack interactive notification integration (due date confirmation, updates from Slack)
- Dockerized multi-service app (Flask API, Streamlit UI, Nginx, Supervisor)
- Azure Web App for Containers deployment (cloud-ready, log streaming, env config)
- Google Calendar integration for reminders and scheduling
- Robust error handling and logging for all services

## 🚧 In Progress / Next
- [ ] Advanced Slack workflows (multi-step, reminders, snooze, feedback)
- [ ] Container image size optimization (multi-stage builds, .dockerignore, Alpine base)
- [ ] Cloud monitoring and alerting (Azure Monitor, Slack alerts)
- [ ] Model Context Protocol (MCP) integration
    - [ ] Evaluate open-source MCP servers
    - [ ] Write adapters/wrappers for Google services
    - [ ] Wrap ReminderAgent logic as MCP tool endpoints
    - [ ] Document MCP integration process

---

_This checklist uses GitHub-flavored markdown for easy tracking and progress updates._
