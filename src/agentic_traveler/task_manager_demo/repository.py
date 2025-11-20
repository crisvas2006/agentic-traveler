from typing import List, Optional

from .models import Task


class TaskRepository:
    def __init__(self):
        self._tasks: List[Task] = []
        self._next_id = 1

    def add_task(self, title: str) -> Task:
        task = Task(id=self._next_id, title=title)
        self._tasks.append(task)
        self._next_id += 1
        return task

    def list_tasks(self) -> List[Task]:
        return self._tasks

    def complete_task(self, task_id: int) -> Optional[Task]:
        for task in self._tasks:
            if task.id == task_id:
                task.done = True
                return task
        return None

    def get_task(self, task_id: int) -> Optional[Task]:
        for task in self._tasks:
            if task.id == task_id:
                return task
        return None


REPO = TaskRepository()
