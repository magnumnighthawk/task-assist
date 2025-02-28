import os
from dotenv import load_dotenv
from langchain_openai import OpenAI

load_dotenv()  # Load environment variables from .env file

llm = OpenAI()

def generate_subtasks(task_description: str):
    prompt = (
        f"Break down the following task into a few practical, actionable subtasks that can be added to a calendar or reminder app. "
        f"Ensure the subtasks are necessary and avoid over-complicating simple tasks. "
        f"Focus on key steps that help track and make progress:\n\n"
        f"Task: {task_description}\n\nSubtasks:"
    )
    response = llm(prompt)
    subtasks = response.split("\n")  # Simple splitting; refine as needed
    return [s.strip() for s in subtasks if s.strip()]

if __name__ == "__main__":
    task = input("Enter your task: ")
    subtasks = generate_subtasks(task)
    print("Generated Subtasks:")
    for subtask in subtasks:
        print(f" - {subtask}")
