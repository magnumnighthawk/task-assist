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
        tool_list = ', '.join(sorted(self.tools.keys())) or 'none'
        return (
            f"You are an assistant that can call tools. Available tools: {tool_list}.\n"
            "When you want to use a tool, output ONLY a single-line valid JSON object with keys: 'action' and 'args'.\n"
            "action must be the tool name. args must be an object with parameters.\n"
            "If you want to just reply to the user without calling a tool, return action: null and a string in args.message.\n"
            f"Instruction: {instruction}\nJSON:"
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
