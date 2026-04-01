from __future__ import annotations

from collections import Counter
from threading import Lock
from time import time


def _label_key(name: str, labels: dict[str, str] | None = None) -> str:
    if not labels:
        return name
    parts = [f"{key}={labels[key]}" for key in sorted(labels)]
    return f"{name}|{'|'.join(parts)}"


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: Counter[str] = Counter()
        self._duration_ms_total = 0.0
        self._started_at_unix = time()
        self._in_flight_requests = 0
        self._peak_in_flight_requests = 0

    def request_started(self) -> None:
        with self._lock:
            self._in_flight_requests += 1
            if self._in_flight_requests > self._peak_in_flight_requests:
                self._peak_in_flight_requests = self._in_flight_requests

    def request_finished(self) -> None:
        with self._lock:
            if self._in_flight_requests > 0:
                self._in_flight_requests -= 1

    def incr(self, name: str, value: int = 1, **labels: str) -> None:
        with self._lock:
            self._counters[_label_key(name, labels)] += value

    def record_request(self, *, method: str, path: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._counters["requests_total"] += 1
            self._counters[_label_key("requests_by_method", {"method": method})] += 1
            self._counters[_label_key("requests_by_path", {"path": path})] += 1
            self._counters[_label_key("responses_by_status", {"status": str(status_code)})] += 1
            self._duration_ms_total += duration_ms

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counters = dict(self._counters)
            requests_total = counters.get("requests_total", 0)
            average_duration_ms = self._duration_ms_total / requests_total if requests_total else 0.0
            uptime_seconds = max(0.0, time() - self._started_at_unix)
            return {
                "counters": counters,
                "requests_total": requests_total,
                "average_duration_ms": round(average_duration_ms, 3),
                "requests_in_flight": self._in_flight_requests,
                "peak_requests_in_flight": self._peak_in_flight_requests,
                "uptime_seconds": round(uptime_seconds, 3),
                "started_at_unix": round(self._started_at_unix, 3),
            }
