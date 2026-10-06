"""Performance telemetry metrics counter and Prometheus exporter."""

import time
from typing import Dict, List, Any
from dataclasses import dataclass, field
import threading


class MetricsCollector:
    """Thread-safe metrics collector for messages, latency and throughput."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
            return cls._instance

    def _init(self):
        self._counters: Dict[str, int] = {}
        self._latencies: Dict[str, List[float]] = {}
        self._mtx = threading.Lock()

    def increment(self, metric: str, value: int = 1):
        with self._mtx:
            self._counters[metric] = self._counters.get(metric, 0) + value

    def record_latency(self, metric: str, duration_sec: float):
        with self._mtx:
            if metric not in self._latencies:
                self._latencies[metric] = []
            self._latencies[metric].append(duration_sec)
            if len(self._latencies[metric]) > 500:
                self._latencies[metric].pop(0)

    def get_summary(self) -> Dict[str, Any]:
        with self._mtx:
            summary = {"counters": dict(self._counters), "latencies": {}}
            for k, v in self._latencies.items():
                if v:
                    summary["latencies"][k] = {
                        "avg": sum(v) / len(v),
                        "max": max(v),
                        "min": min(v),
                        "count": len(v)
                    }
            return summary

    def export_prometheus(self) -> str:
        lines = []
        with self._mtx:
            for k, v in self._counters.items():
                clean_name = k.replace(".", "_").replace("-", "_")
                lines.append(f"# TYPE mcqq_{clean_name} counter")
                lines.append(f"mcqq_{clean_name} {v}")
        return "\n".join(lines)
