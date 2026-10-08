"""Bounded dispatch and factual delivery outcomes for connection alerts."""
import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Awaitable, Callable, Dict, Optional


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


@dataclass
class AlertPayload:
    server_name: str
    severity: AlertSeverity
    title: str
    message: str
    generation: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class AlertResult:
    status: str  # delivered, failed, suppressed, unconfigured
    attempted: bool
    delivered: bool
    error: Optional[str] = None


class AlertDispatcher:
    """Deduplicate per transition; failed sends may retry after a short window.

    No sender means no delivery claim. History is capped even if generations
    change frequently. A lock prevents simultaneous identical sends.
    """

    def __init__(
        self,
        dedup_window_sec: float = 60.0,
        webhook_sender: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
        failure_retry_sec: float = 5.0,
        max_history: int = 128,
        send_timeout: float = 3.0,
    ):
        if max_history < 1:
            raise ValueError("max_history must be positive")
        self.dedup_window_sec = dedup_window_sec
        self.failure_retry_sec = failure_retry_sec
        self.max_history = max_history
        self.send_timeout = send_timeout
        self.webhook_sender = webhook_sender
        self._history: OrderedDict[str, float] = OrderedDict()
        self._lock = asyncio.Lock()
        self.last_result: Optional[AlertResult] = None

    def _fingerprint(self, alert: AlertPayload) -> str:
        return f"{alert.server_name}:{alert.generation}:{alert.severity.value}:{alert.title}"

    async def dispatch(self, alert: AlertPayload) -> AlertResult:
        async with self._lock:
            fp = self._fingerprint(alert)
            now = time.monotonic()
            expiry = self._history.get(fp, 0)
            if now < expiry:
                result = AlertResult("suppressed", attempted=False, delivered=False)
            elif self.webhook_sender is None:
                result = AlertResult("unconfigured", attempted=False, delivered=False)
            else:
                payload = {
                    "server": alert.server_name,
                    "generation": alert.generation,
                    "severity": alert.severity.value,
                    "title": alert.title,
                    "message": alert.message,
                    "timestamp": alert.timestamp,
                }
                try:
                    await asyncio.wait_for(self.webhook_sender(payload), timeout=self.send_timeout)
                except Exception as exc:
                    result = AlertResult("failed", attempted=True, delivered=False,
                                         error=type(exc).__name__)
                    self._history[fp] = time.monotonic() + self.failure_retry_sec
                else:
                    result = AlertResult("delivered", attempted=True, delivered=True)
                    self._history[fp] = time.monotonic() + self.dedup_window_sec
                self._history.move_to_end(fp)
                while len(self._history) > self.max_history:
                    self._history.popitem(last=False)
            self.last_result = result
            return result
