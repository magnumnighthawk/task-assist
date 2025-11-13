from flask import Flask, request, jsonify
from agents.agent import Agent
from agents.tools import TOOLS
import os

app = Flask(__name__)

# Instantiate agent (will operate in safe mode if no OPENAI_API_KEY is present)
agent = Agent(tools=TOOLS)


@app.route('/agent', methods=['POST'])
def agent_endpoint():
    data = request.get_json(force=True) or {}
    instr = data.get('instruction') or data.get('prompt') or ''
    if not instr:
        return jsonify({'error': 'no instruction provided'}), 400
    execute = bool(data.get('execute', True))
    res = agent.run_instruction(instr, execute=execute)
    return jsonify(res)


@app.route('/agent/tools', methods=['GET'])
def list_tools():
    return jsonify({'tools': sorted(list(TOOLS.keys()))})


@app.route('/agent/plan', methods=['POST'])
def agent_plan():
    data = request.get_json(force=True) or {}
    instr = data.get('instruction') or data.get('prompt') or ''
    if not instr:
        return jsonify({'error': 'no instruction provided'}), 400
    res = agent.plan_instruction(instr)
    return jsonify(res)


if __name__ == '__main__':
    port = int(os.environ.get('AGENT_PORT', '5600'))
    app.run(host='0.0.0.0', port=port)
