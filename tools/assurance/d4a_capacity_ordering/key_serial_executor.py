from __future__ import annotations

from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
from typing import Callable, Deque, Dict, Generic, Hashable, TypeVar

T = TypeVar("T")


@dataclass
class _WorkItem(Generic[T]):
    future: Future[T]
    fn: Callable[[], T]


class KeySerialExecutor:
    """Serialize work per logical key while allowing unrelated keys to overlap.

    This is a bounded source-evidence component for D4-A ordering conformance. It
    deliberately models consumer-side key-level virtual sequencing; it is not a
    production executor selection or sizing authority.
    """

    def __init__(self, *, max_workers: int = 4) -> None:
        if type(max_workers) is not int or max_workers < 2:
            raise ValueError("max_workers must be an integer >= 2")
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="jlmirror-keyserial")
        self._lock = Lock()
        self._queues: Dict[Hashable, Deque[_WorkItem[object]]] = {}
        self._running: set[Hashable] = set()
        self._closed = False

    def submit(self, key: Hashable, fn: Callable[[], T]) -> Future[T]:
        if key is None:
            raise ValueError("ordering key cannot be None")
        if not callable(fn):
            raise TypeError("fn must be callable")
        future: Future[T] = Future()
        with self._lock:
            if self._closed:
                raise RuntimeError("executor is closed")
            queue = self._queues.setdefault(key, deque())
            queue.append(_WorkItem(future=future, fn=fn))  # type: ignore[arg-type]
            if key not in self._running:
                self._running.add(key)
                self._pool.submit(self._drain_key, key)
        return future

    def _drain_key(self, key: Hashable) -> None:
        while True:
            with self._lock:
                queue = self._queues.get(key)
                if not queue:
                    self._queues.pop(key, None)
                    self._running.discard(key)
                    return
                item = queue.popleft()
            if item.future.set_running_or_notify_cancel():
                try:
                    item.future.set_result(item.fn())
                except BaseException as exc:  # propagate task failure without killing the key drain
                    item.future.set_exception(exc)

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._closed = True
        self._pool.shutdown(wait=wait)
