"""Alert rule engine and webhook notification dispatcher with storm suppression."""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional
from dataclasses import dataclass, field


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
    timestamp: float = field(default_factory=time.time)


class AlertDispatcher:
    """Dispatches alerts to Webhook endpoints with anti-storm deduplication and timeout protection."""

    def __init__(
        self,
        dedup_window_sec: float = 60.0,
        webhook_sender: Optional[Callable[[Dict[str, Any]], Coroutine]] = None
    ):
        self.dedup_window_sec = dedup_window_sec
        self.webhook_sender = webhook_sender
        self._history: Dict[str, float] = {} # fingerprint -> last_sent_time

    def _fingerprint(self, alert: AlertPayload) -> str:
        return f"{alert.server_name}:{alert.severity.value}:{alert.title}"

    async def dispatch(self, alert: AlertPayload) -> bool:
        fp = self._fingerprint(alert)
        now = time.monotonic()

        # Check anti-storm deduplication
        if fp in self._history:
            last_time = self._history[fp]
            if (now - last_time) < self.dedup_window_sec:
                # Suppressed due to storm window
                return False

        self._history[fp] = now

        if self.webhook_sender:
            try:
                # P0: Timeout isolation
                payload = {
                    "server": alert.server_name,
                    "severity": alert.severity.value,
                    "title": alert.title,
                    "message": alert.message,
                    "timestamp": alert.timestamp
                }
                await asyncio.wait_for(self.webhook_sender(payload), timeout=3.0)
            except Exception:
                # P0: Must not bubble up network exceptions
                pass

        return True
