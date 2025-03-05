import os
import json
from dotenv import load_dotenv
from langchain_openai import OpenAI

load_dotenv()

llm = OpenAI()

def generate_subtasks(task_description: str, max_subtasks: int = 5):
    prompt = (
        "You are a JSON formatter"
        "Break down the following task into a few practical, actionable subtasks that can be added to a calendar or reminder app. "
        "Ensure the subtasks are necessary and avoid over-complicating simple tasks that doesn't overwhelm the calendar. "
        "Focus on key steps that help track and make progress."
        "Each subtask must be a JSON object with exactly two keys: \"description\" and \"priority\". "
        "The \"description\" should be a concise string, and \"priority\" should be one of \"High\", \"Medium\", or \"Low\". "
        "Do not include any additional text, explanations, or markdown formatting in your output. "
        "Output only a valid JSON array. Here is an example output:\n\n"
        "[\n"
        "  {\"description\": \"Research requirements\", \"priority\": \"High\"},\n"
        "  {\"description\": \"Draft plan\", \"priority\": \"Medium\"}\n"
        "]\n\n"
        f"Now, given the following task, output only a valid JSON array with a maximum of {max_subtasks} subtasks.\n"
        f"Task: {task_description}\n\n"
        "JSON:"
    )
    response = llm(prompt)
    try:
        subtasks = json.loads(response)
        # Validate each subtask has the required keys
        for task in subtasks:
            if 'description' not in task:
                raise ValueError("Missing 'description' key.")
            if 'priority' not in task:
                task['priority'] = "Medium"  # Assign a default priority if missing
    except (json.JSONDecodeError, ValueError) as e:
        # Fallback: use basic text parsing if JSON parsing fails
        print("Error parsing JSON, using fallback parsing method.", e)
        subtasks = []
        for line in response.strip().split('\n'):
            # Remove list markers and whitespace
            line = line.strip("- ").strip()
            if line:
                subtasks.append({"description": line, "priority": "Medium"})
    return subtasks

if __name__ == "__main__":
    task = input("Enter your task: ")
    subtasks = generate_subtasks(task)
    print("Generated Subtasks:")
    for subtask in subtasks:
        print(f" - {subtask}")
    
    further_breakdown = input("Do you need to break down any of these subtasks further? (yes/no): ").strip().lower()
    if further_breakdown == "yes":
        subtask_to_breakdown = input("Enter the subtask number to break down further: ").strip()
        if subtask_to_breakdown.isdigit() and 1 <= int(subtask_to_breakdown) <= len(subtasks):
            detailed_subtasks = generate_subtasks(subtasks[int(subtask_to_breakdown) - 1])
            print("Detailed Subtasks:")
            for detailed_subtask in detailed_subtasks:
                print(f" - {detailed_subtask}")
