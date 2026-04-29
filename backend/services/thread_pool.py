from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable
import logging
import threading

import config

logger = logging.getLogger(__name__)


class ThreadPool:
    _instance: "ThreadPool | None" = None

    def __init__(self, max_workers: int = config.MAX_WORKERS):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="stock-quant")
        self._futures: dict[str, Future] = {}
        self._submit_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ThreadPool":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def submit(self, task_id: str, fn: Callable, *args: Any, **kwargs: Any) -> Future:
        with self._submit_lock:
            if task_id in self._futures and not self._futures[task_id].done():
                logger.warning("Task %s already running, cancelling previous", task_id)
                self._futures[task_id].cancel()

            future = self._executor.submit(fn, *args, **kwargs)
            future.add_done_callback(lambda f: self._futures.pop(task_id, None))
            self._futures[task_id] = future
            return future

    def shutdown(self, wait: bool = True):
        self._executor.shutdown(wait=wait)
        self._futures.clear()
        ThreadPool._instance = None
