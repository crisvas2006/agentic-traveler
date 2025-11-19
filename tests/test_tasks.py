import pytest
from agentic_traveler.task_manager_demo.repository import TaskRepository

@pytest.fixture
def repo():
    return TaskRepository()

def test_add_task(repo: TaskRepository):
    task = repo.add_task("Test Task")
    assert task.title == "Test Task"
    assert task.id == 1
    assert not task.done

def test_list_tasks(repo: TaskRepository):
    repo.add_task("Task 1")
    repo.add_task("Task 2")
    tasks = repo.list_tasks()
    assert len(tasks) == 2
    assert tasks[0].title == "Task 1"
    assert tasks[1].title == "Task 2"

def test_complete_task(repo: TaskRepository):
    task = repo.add_task("Test Task")
    completed_task = repo.complete_task(task.id)
    assert completed_task is not None
    assert completed_task.done
    assert repo.get_task(task.id).done

def test_get_task(repo: TaskRepository):
    task = repo.add_task("Test Task")
    retrieved_task = repo.get_task(task.id)
    assert retrieved_task is not None
    assert retrieved_task.title == "Test Task"

def test_get_nonexistent_task(repo: TaskRepository):
    retrieved_task = repo.get_task(999)
    assert retrieved_task is None

def test_complete_nonexistent_task(repo: TaskRepository):
    completed_task = repo.complete_task(999)
    assert completed_task is None
