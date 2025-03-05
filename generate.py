import os
from dotenv import load_dotenv
from langchain_openai import OpenAI

load_dotenv()

llm = OpenAI()

def generate_subtasks(task_description: str, max_subtasks: int = 5):
    prompt = (
        f"Break down the following task into a few practical, actionable subtasks that can be added to a calendar or reminder app. "
        f"Ensure the subtasks are necessary and avoid over-complicating simple tasks that doesn't overwhelm the calendar. "
        f"Focus on key steps that help track and make progress. Provide the subtasks as a numbered list with a maximum of {max_subtasks} subtasks:\n\n"
        f"Task: {task_description}\n\nSubtasks:\n"
    )
    response = llm(prompt)
    subtasks = response.split("\n")
    
    subtasks = [s.strip() for s in subtasks if s.strip() and s.strip()[0].isdigit()]
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
