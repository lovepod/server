from __future__ import annotations

from collections import deque
from threading import Lock
from time import time


class InMemoryRateLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int]:
        now = time()
        with self._lock:
            bucket = self._events.setdefault(key, deque())
            cutoff = now - self._window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self._limit:
                retry_after = max(1, int(bucket[0] + self._window_seconds - now))
                return False, retry_after

            bucket.append(now)
            return True, 0
