from generate import generate_subtasks

class Task:
    def __init__(self, description):
        self.description = description
        self.status = "Pending"

    def mark_complete(self):
        self.status = "Completed"

def display_tasks(tasks):
    for task in tasks:
        print(f"{task.description} - Status: {task.status}")

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
        print("4. Exit")
        choice = input("Choose an option: ")

        if choice == '1':
            description = input("Enter task description: ")
            tasks = [Task(subtask) for subtask in generate_subtasks(description)]
        elif choice == '2':
            display_tasks(tasks)
        elif choice == '3':
            for idx, task in enumerate(tasks):
                verify_task(task)
                print(f"Task '{idx+1}' is now {task.status}")
        elif choice == '4':
            break
        else:
            print("Invalid option. Please try again.")

if __name__ == "__main__":
    main()

