from agentic_traveler.task_manager_demo.repository import REPO


def print_tasks():
    tasks = REPO.list_tasks()
    if not tasks:
        print("No tasks yet.")
    for task in tasks:
        status = "Done" if task.done else "Not Done"
        print(f"[{task.id}] {task.title} - {status}")


def main():
    print("Welcome to the interactive task manager!")
    print("Available commands: list, add <title>, complete <id>, quit")

    while True:
        command_input = input("> ").strip().split(maxsplit=1)
        command = command_input[0] if command_input else ""
        args = command_input[1] if len(command_input) > 1 else ""

        if command == "list":
            print_tasks()
        elif command == "add":
            if args:
                task = REPO.add_task(args)
                print(f"Added task: '{task.title}' with ID: {task.id}")
            else:
                print("Please provide a title for the task.")
        elif command == "complete":
            if args:
                try:
                    task_id = int(args)
                    task = REPO.complete_task(task_id)
                    if task:
                        print(f"Completed task: '{task.title}'")
                    else:
                        print(f"Task with ID {task_id} not found.")
                except ValueError:
                    print("Invalid task ID.")
            else:
                print("Please provide a task ID.")
        elif command == "quit":
            print("Goodbye!")
            break
        else:
            print(
                "Unknown command. Available commands: list, add <title>, complete <id>, quit"
            )


if __name__ == "__main__":
    main()
