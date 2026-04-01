from __future__ import annotations

from collections import Counter
from threading import Lock


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
            return {
                "counters": counters,
                "requests_total": requests_total,
                "average_duration_ms": round(average_duration_ms, 3),
            }
