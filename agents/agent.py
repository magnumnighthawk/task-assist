import os
import json
import logging
from typing import Any, Dict
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger('agent')


class Agent:
    """A minimal LLM-driven agent that can call registered tools.

    Usage: instantiate with an OpenAI client (or default using env vars).
    Call `run_instruction` with a natural instruction and the agent will
    ask the model for an action to perform, parse the JSON response, and
    dispatch to the matching tool in the provided registry.
    """

    def __init__(self, client: OpenAI = None, tools: Dict[str, Any] = None, model: str = None):
        # Allow initializing without an OpenAI client for local/offline use. If no
        # client and no OPENAI_API_KEY is present, the agent will return safe
        # descriptive responses instead of calling the model.
        api_key = os.environ.get('OPENAI_API_KEY')
        if client:
            self.client = client
        elif api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None
        self.tools = tools or {}
        self.model = model or os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')

    def _build_prompt(self, instruction: str) -> str:
        # Build a verbose system prompt describing the agent's responsibilities and the
        # JSON output contract. Keep the prompt explicit so the model plans safely and
        # includes optional explanatory/context fields the UI can display.
        tool_list = ', '.join(sorted(self.tools.keys())) or 'none'
        return (
            "You are an autonomous assistant integrated into a task management application.\n"
            "You have access to a set of tools which perform actions in the application.\n"
            f"Available tools: {tool_list}.\n\n"
            "OUTPUT CONTRACT (strict JSON):\n"
            "When you decide on a next step, output ONLY a single JSON object (no surrounding text)\n"
            "matching the following schema: {\n"
            "  \"action\": string | null,          // the tool name to call, or null to only reply\n"
            "  \"args\": object,                  // key/value parameters to pass to the tool (may be {}),\n"
            "  \"explain\": string (optional),    // short human-readable explanation of your plan,\n"
            "  \"confirm\": boolean (optional)    // true if the action is mutating and requires user confirmation\n"
            "}\n\n"
            "Rules:\n"
            "- If you do not want to call a tool, set \"action\": null and provide a human message in \"args.message\".\n"
            "- Avoid side effects unless the requested action is explicit. If the action will change state (create/publish/schedule), set \"confirm\": true to indicate the UI should ask the user to confirm.\n"
            "- Keep \"args\" minimal and use clear parameter names. Use integers for numeric counts like max_subtasks.\n"
            "- If a numeric parameter (e.g., number of subtasks) is implied by the instruction but missing from args, include it when you can, e.g. \"max_subtasks\": 4.\n\n"
            "Examples:\n"
            "1) Plan-only reply (no tool call):\n"
            "{\"action\": null, \"args\": {\"message\": \"I recommend creating a Work titled 'Birthday Party' with 4 subtasks.\"}, \"explain\": \"Outline and recommended subtasks\" }\n\n"
            "2) Tool call that needs confirmation:\n"
            "{\"action\": \"publish_work\", \"args\": {\"work_id\": 42}, \"explain\": \"Publish work and notify stakeholders\", \"confirm\": true}\n\n"
            "3) Create work using a natural 'task' field and a max_subtasks hint:\n"
            "{\"action\": \"create_work\", \"args\": {\"task\": \"Plan a team offsite\", \"max_subtasks\": 5}, \"explain\": \"Create a work item and generate subtasks\" }\n\n"
            f"Instruction: {instruction}\n\nPlease output the JSON now."
        )

    def plan_instruction(self, instruction: str) -> Dict[str, Any]:
        """Ask the model to PLAN an action without executing any tool.

        Returns the parsed JSON payload the model would use (action + args).
        If no LLM client is configured, returns a safe descriptive payload.
        """
        prompt = self._build_prompt(instruction)
        logger.info('Planning instruction: %s', instruction)
        if not self.client:
            return {'action': None, 'args': {'message': f"No LLM client configured. Available tools: {', '.join(sorted(self.tools.keys()))}"}}

        resp = self.client.chat.completions.create(model=self.model, messages=[{'role': 'user', 'content': prompt}], temperature=0.2)
        try:
            content = resp.choices[0].message.content
        except Exception:
            content = str(resp)

        # Try parse JSON from content
        import json, re

        try:
            payload = json.loads(content)
        except Exception:
            m = re.search(r"\{.*\}", content, re.S)
            if m:
                try:
                    payload = json.loads(m.group(0))
                except Exception:
                    payload = {'action': None, 'args': {'message': content}}
            else:
                payload = {'action': None, 'args': {'message': content}}
        return payload

    def run_instruction(self, instruction: str, execute: bool = True, max_retries: int = 1) -> Dict[str, Any]:
        """Plan and optionally execute an instruction.

        If execute=False, returns the planned payload without calling any tool.
        If execute=True, will call the requested tool (if any) and return the result.
        """
        planned = self.plan_instruction(instruction)
        action = planned.get('action')
        args = planned.get('args', {}) or {}

        if not action:
            return {'action': None, 'result': args.get('message')}

        if not execute:
            return {'action': action, 'args': args}

        tool = self.tools.get(action)
        if not tool:
            return {'action': action, 'error': f"Tool '{action}' not found"}

        try:
            result = tool(**args)
            return {'action': action, 'result': result}
        except Exception as e:
            logger.exception('Tool call failed')
            return {'action': action, 'error': str(e)}
