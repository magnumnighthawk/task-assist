from generate import generate_subtasks, revise_subtasks
from datetime import datetime


class Task:
    def __init__(self, item: dict, deadline=None):
        self.description = item['description']
        self.priority = item['priority'] if 'priority' in item else "Medium"
        self.status = item.get('status', "Pending")
        # Handle due_date if present
        due_date_str = item.get('due_date')
        if due_date_str:
            try:
                # Try parsing as full datetime first, then as date
                self.deadline = datetime.fromisoformat(due_date_str)
            except Exception:
                self.deadline = None
        else:
            self.deadline = deadline  # datetime object or None
        self.created_at = datetime.fromisoformat(item['created_at']) if 'created_at' in item else datetime.now()

    def mark_complete(self):
        self.status = "Completed"

    def to_dict(self):
        return {
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "created_at": self.created_at.isoformat()
        }

def display_tasks(tasks):
    for task in tasks:
        deadline_str = f" || Due: {task.deadline.isoformat()}" if task.deadline else ""
        print(f"{task.description} || Priority: {task.priority} || Status: {task.status}{deadline_str}")

def verify_task(task: Task):
    user_input = input(f"Mark task '{task.description}' as complete? (y/n): ")
    if user_input.lower() == 'y':
        task.mark_complete()

def main():
    tasks = []
    while True:
        print("\nOptions:")
        print("1. Generate tasks")
        print("2. Show current statuses")
        print("3. Update statuses")
        print("4. Revise tasks")
        print("5. Exit")
        choice = input("Choose an option: ")

        if choice == '1':
            description = input("Enter task description: ")
            subtasks = generate_subtasks(description)
            print("Generated Subtasks:")
            for idx, subtask in enumerate(subtasks, 1):
                print(f"{idx}. {subtask}")
            revise = input("Do you want to revise these tasks? (yes/no): ").strip().lower()
            if revise == "yes":
                feedback = input("Describe how you want to revise or break down the tasks: ").strip()
                subtasks = revise_subtasks(subtasks, feedback)
                print("Revised Subtasks:")
                for idx, subtask in enumerate(subtasks, 1):
                    print(f"{idx}. {subtask}")
            tasks = [Task(subtask) for subtask in subtasks]
            display_tasks(tasks)
        elif choice == '2':
            display_tasks(tasks)
        elif choice == '3':
            for idx, task in enumerate(tasks):
                verify_task(task)
                print(f"Task '{idx+1}' is now {task.status}")
        elif choice == '4':
            if not tasks:
                print("No tasks to revise.")
                continue
            feedback = input("Describe how you want to revise or break down the tasks: ").strip()
            subtasks = revise_subtasks([task.to_dict() for task in tasks], feedback)
            print("Revised Subtasks:")
            for idx, subtask in enumerate(subtasks, 1):
                print(f"{idx}. {subtask}")
            tasks = [Task(subtask) for subtask in subtasks]
        elif choice == '5':
            break
        else:
            print("Invalid option. Please try again.")

if __name__ == "__main__":
    main()

