# Roadmap / TODO

This document tracks future improvements and architectural considerations for the project.

## Model Context Protocol (MCP) Integration

- [ ] **Evaluate open-source MCP servers**
    - Research and test servers like [Open Interpreter MCP](https://github.com/OpenInterpreter/mcp) and [LangChain MCP](https://python.langchain.com/docs/ecosystem/mcp/).
- [ ] **Write adapters/wrappers for Google services**
    - Create MCP-compatible tool endpoints for Google Calendar and other services as needed.
- [ ] **Wrap ReminderAgent logic as MCP tool endpoints**
    - Refactor methods (create, update, delete, reschedule, list events, send Slack notification) to be callable via MCP.
- [ ] **Document MCP integration process**
    - Add setup and usage instructions for MCP server integration.

---

_This checklist uses GitHub-flavored markdown for easy tracking and progress updates._
