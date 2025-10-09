
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

# Import db adapter
from db import create_work, create_task, get_db
from sqlalchemy.orm import Session

load_dotenv()

llm = ChatOpenAI()

def generate_subtasks(task_description: str, max_subtasks: int = 5):
    now = datetime.now().isoformat()
    system_prompt = (
        "You are a JSON formatter and project assistant. "
        "Given a user task, generate a crisp, short work item name (work_name), a concise work description (work_description), "
        "and break down the task into a few practical, actionable subtasks (subtasks) that can be added to a calendar or reminder app. "
        "Ensure the subtasks are necessary and avoid over-complicating simple tasks. "
        "Each subtask must be a JSON object with exactly two keys: 'description' and 'priority'. "
        "The 'description' should be a concise string, and 'priority' should be one of 'High', 'Medium', or 'Low'. "
        "Output only a valid JSON object with three keys: 'work_name', 'work_description', and 'subtasks'. "
        "Here is an example output:\n\n"
        "{\n"
        "  \"work_name\": \"Plan Team Offsite\",\n"
        "  \"work_description\": \"Organize and plan a productive team offsite event.\",\n"
        "  \"subtasks\": [\n"
        "    {\"description\": \"Book venue\", \"priority\": \"High\"},\n"
        "    {\"description\": \"Send invites\", \"priority\": \"Medium\"}\n"
        "  ]\n"
        "}"
    )
    user_prompt = (
        f"Given the following user task, output only a valid JSON object as described above, with a maximum of {max_subtasks} subtasks.\n"
        f"Task: {task_description}\n\nJSON:"
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    response = llm(messages)
    if hasattr(response, 'content'):
        response_content = response.content
    else:
        response_content = str(response)
    try:
        result = json.loads(response_content)
        # Validate structure
        if not all(k in result for k in ("work_name", "work_description", "subtasks")):
            raise ValueError("Missing required keys in LLM output.")
        for task in result["subtasks"]:
            if 'description' not in task:
                raise ValueError("Missing 'description' key in subtask.")
            if 'priority' not in task:
                task['priority'] = "Medium"
        print("[DEBUG] llm response for Generated Subtasks (raw):", result)
        return result
    except (json.JSONDecodeError, ValueError) as e:
        print("Error parsing JSON, using fallback parsing method.", e)
        # Fallback: use old logic for subtasks, and set work_name/description to input
        subtasks = []
        for line in response_content.strip().split('\n'):
            line = line.strip("- ").strip()
            if line:
                subtasks.append({"description": line, "priority": "Medium"})
        return {
            "work_name": task_description,
            "work_description": task_description,
            "subtasks": subtasks
        }

# New function to revise/modify subtasks
def revise_subtasks(original_subtasks, feedback, max_subtasks=5):
    now = datetime.now().isoformat()
    system_prompt = (
        "You are an expert project manager and JSON formatter. Given the following subtasks (in JSON), revise them according to the user's feedback. "
        "Also, generate a crisp, short work item name (work_name) and a concise work description (work_description) for the revised set. "
        "Follow these rules strictly: "
        "- If the user asks to add a new subtask, APPEND it to the list. Do NOT remove or replace any existing subtasks when adding. "
        "- If the user asks to update or remove a subtask, do so ONLY for the specified subtask(s). "
        "- Do NOT change, remove, or replace any subtask unless the feedback explicitly requests it. "
        "- Never replace the entire list unless the user asks for a full rewrite. "
        "Return the revised result as a JSON object with three keys: 'work_name', 'work_description', and 'subtasks'. "
        "Each subtask must be an object with 'description' and 'priority'. "
        f"\n\nCurrent subtasks: {json.dumps(original_subtasks)}\n\nFeedback: {feedback}\n\nRevised result:"
    )
    user_prompt = (
        f"Here are the current subtasks: {json.dumps(original_subtasks, ensure_ascii=False)}\n"
        f"User feedback: {feedback}\n"
        f"Update the subtasks as needed, output only a valid JSON object as described above, with a maximum of {max_subtasks} subtasks.\nJSON:"
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    response = llm(messages)
    if hasattr(response, 'content'):
        response_content = response.content
    else:
        response_content = str(response)
    try:
        result = json.loads(response_content)
        if not all(k in result for k in ("work_name", "work_description", "subtasks")):
            raise ValueError("Missing required keys in LLM output.")
        for task in result["subtasks"]:
            if 'description' not in task:
                raise ValueError("Missing 'description' key in subtask.")
            if 'priority' not in task:
                task['priority'] = "Medium"
        print("[DEBUG] llm reponse for Revised Subtasks (raw):", result)
        return result
    except (json.JSONDecodeError, ValueError) as e:
        print("Error parsing JSON, using fallback parsing method.", e)
        subtasks = []
        for line in response_content.strip().split('\n'):
            line = line.strip("- ").strip()
            if line:
                subtasks.append({"description": line, "priority": "Medium"})
        return {
            "work_name": "Revised Work",
            "work_description": feedback or "Revised work description",
            "subtasks": subtasks
        }

if __name__ == "__main__":
    task = input("Enter your task: ")
    result = generate_subtasks(task)
    subtasks = result['subtasks']
    print("Generated Subtasks (raw):", subtasks)
    print("Generated Subtasks:")
    for idx, subtask in enumerate(subtasks, 1):
        print(f"{idx}. {subtask}")

    # Save to DB
    db_gen = get_db()
    db: Session = next(db_gen)
    work = create_work(db, title=task, description=task, tasks=[{"title": s["description"], "status": "pending"} for s in subtasks])
    print(f"Saved Work ID: {work.id}")

    while True:
        further_action = input("Do you want to revise or break down any of these subtasks? (yes/no/exit): ").strip().lower()
        if further_action == "exit" or further_action == "no":
            print("Exiting.")
            break
        feedback = input("Describe how you want to revise or break down the subtasks (specify which if needed): ").strip()
        revised_result = revise_subtasks(subtasks, feedback)
        revised_subtasks = revised_result['subtasks']
        print("Revised Subtasks (raw):", revised_subtasks)
        subtasks = revised_subtasks
        print("Revised Subtasks:")
        for idx, subtask in enumerate(subtasks, 1):
            print(f"{idx}. {subtask}")

        # Optionally update DB (not implemented: update logic)
