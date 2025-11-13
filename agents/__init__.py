"""Agents package - exposes the AI agent core and tools.

This package provides a small orchestration layer so the LLM can call
existing application capabilities as named tools. The first iteration
uses a simple JSON action protocol: the model should return a JSON
object with keys `action` (tool name) and `args` (object of arguments).

Keep this module minimal so future agents can import Agent and the
tools registry.
"""

from .agent import Agent
from .tools import TOOLS

__all__ = ["Agent", "TOOLS"]
