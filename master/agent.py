import os
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from .instructions import INSTRUCTION
from .tools import TOOLS

load_dotenv()
gmp_key = os.getenv('GMP_API_KEY')

root_agent = Agent(
    model='gemini-2.0-flash',
    name='task_assist_master_agent',
    description='An intelligent assistant that manages work and tasks end-to-end: breaks down work into actionable tasks, schedules them, tracks progress, sends reminders, and notifies users via Slack and calendar. Handles the full workflow as described in LIFECYCLE.md and IDEA.md.',
    instruction=INSTRUCTION,
    tools=list(TOOLS.values())
)
