import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

load_dotenv()

llm = ChatOpenAI()

def generate_subtasks(task_description: str, max_subtasks: int = 5):
    system_prompt = (
        "You are a JSON formatter. "
        "Break down the following task into a few practical, actionable subtasks that can be added to a calendar or reminder app. "
        "Ensure the subtasks are necessary and avoid over-complicating simple tasks that doesn't overwhelm the calendar. "
        "Focus on key steps that help track and make progress. "
        "The goal is to break-up in parts that can help the user complete the action. "
        "Too few might feel overwhelming & too much unnessary, so break it up appropriately that can warrant creating calendar event to use for tracking & reminders."
        "Each subtask must be a JSON object with exactly two keys: 'description' and 'priority'. "
        "The 'description' should be a concise string, and 'priority' should be one of 'High', 'Medium', or 'Low'. "
        "Do not include any additional text, explanations, or markdown formatting in your output. "
        "Output only a valid JSON array. Here is an example output:\n\n"
        "[\n"
        "  {\"description\": \"Research requirements\", \"priority\": \"High\"},\n"
        "  {\"description\": \"Draft plan\", \"priority\": \"Medium\"}\n"
        "]\n"
    )
    user_prompt = (
        f"Now, given the following task, output only a valid JSON array with a maximum of {max_subtasks} subtasks.\n"
        f"Task: {task_description}\n\nJSON:"
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    response = llm(messages)
    # Extract content from AIMessage if needed
    if hasattr(response, 'content'):
        response_content = response.content
    else:
        response_content = str(response)
    try:
        subtasks = json.loads(response_content)
        for task in subtasks:
            if 'description' not in task:
                raise ValueError("Missing 'description' key.")
            if 'priority' not in task:
                task['priority'] = "Medium"
    except (json.JSONDecodeError, ValueError) as e:
        print("Error parsing JSON, using fallback parsing method.", e)
        subtasks = []
        for line in response_content.strip().split('\n'):
            line = line.strip("- ").strip()
            if line:
                subtasks.append({"description": line, "priority": "Medium"})
    return subtasks

# New function to revise/modify subtasks
def revise_subtasks(original_subtasks, feedback, max_subtasks=5):
    system_prompt = (
        "You are a JSON editor. Given a list of subtasks and user feedback, update the subtasks to better fit the user's needs. "
        "You must output only a valid JSON array of subtasks, each with exactly two keys: 'description' and 'priority'. "
        "Do not include any explanations, markdown, or extra text. "
        "If the user requests a breakdown of a specific subtask, replace that subtask with its breakdown. "
        "Keep the list concise and actionable for calendar/reminder use. "
        "Example output:\n\n"
        "[\n"
        "  {\"description\": \"Research requirements\", \"priority\": \"High\"},\n"
        "  {\"description\": \"Draft plan\", \"priority\": \"Medium\"}\n"
        "]\n"
    )
    user_prompt = (
        f"Here are the current subtasks: {json.dumps(original_subtasks, ensure_ascii=False)}\n"
        f"User feedback: {feedback}\n"
        f"Update the subtasks as needed, output only a valid JSON array with a maximum of {max_subtasks} subtasks.\nJSON:"
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
        subtasks = json.loads(response_content)
        for task in subtasks:
            if 'description' not in task:
                raise ValueError("Missing 'description' key.")
            if 'priority' not in task:
                task['priority'] = "Medium"
    except (json.JSONDecodeError, ValueError) as e:
        print("Error parsing JSON, using fallback parsing method.", e)
        subtasks = []
        for line in response_content.strip().split('\n'):
            line = line.strip("- ").strip()
            if line:
                subtasks.append({"description": line, "priority": "Medium"})
    return subtasks

if __name__ == "__main__":
    task = input("Enter your task: ")
    subtasks = generate_subtasks(task)
    print("Generated Subtasks:")
    for idx, subtask in enumerate(subtasks, 1):
        print(f"{idx}. {subtask}")

    while True:
        further_action = input("Do you want to revise or break down any of these subtasks? (yes/no/exit): ").strip().lower()
        if further_action == "exit" or further_action == "no":
            print("Exiting.")
            break
        feedback = input("Describe how you want to revise or break down the subtasks (specify which if needed): ").strip()
        revised_subtasks = revise_subtasks(subtasks, feedback)
        subtasks = revised_subtasks
        print("Revised Subtasks:")
        for idx, subtask in enumerate(subtasks, 1):
            print(f"{idx}. {subtask}")
