import asyncio
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class TaskManager:
    def __init__(self):
        self.tasks: dict[str, asyncio.Task] = {}

    async def _execute_task(
        self, task_id: str, function: Callable, *args, **kwargs
    ):
        try:
            await function(*args, **kwargs)
        except asyncio.CancelledError:
            logger.info("Task cancelled")
        except Exception:
            logger.exception(f"Task {task_id} failed")
        del self.tasks[task_id]

    def add_task(
        self, task_id: str, function: Callable, *args, **kwargs
    ) -> None:
        task = asyncio.create_task(
            self._execute_task(task_id, function, *args, **kwargs)
        )
        self.tasks[task_id] = task

    def cancel_task(self, task_id: str) -> None:
        task = self.tasks.get(task_id)
        if task and not task.done():
            task.cancel()
        else:
            logger.info(f"Task {task_id} not found or already done")

    def cancel_all_tasks(self):
        for task in self.tasks.values():
            task.cancel()
        self.tasks = {}


task_manager = TaskManager()
