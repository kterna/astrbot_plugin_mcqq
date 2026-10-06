"""Reverse WebSocket Heartbeat Watchdog and Zombie Connection Auto-Healer."""

import asyncio
import time
from typing import Callable, Coroutine, Dict, Optional, Set
from dataclasses import dataclass


@dataclass
class ConnectionHeartbeatState:
    server_name: str
    last_ping_time: float
    last_pong_time: float
    unanswered_pings: int = 0
    is_alive: bool = True


class WebSocketWatchdog:
    """
    Watches reverse websocket connections, emitting heartbeats and
    terminating zombie connections exceeding unacknowledged threshold.
    """
    def __init__(
        self,
        ping_interval: float = 3.0,
        pong_timeout: float = 5.0,
        max_missed_pings: int = 3,
        disconnect_callback: Optional[Callable[[str], Coroutine]] = None
    ):
        self.ping_interval = ping_interval
        self.pong_timeout = pong_timeout
        self.max_missed_pings = max_missed_pings
        self.disconnect_callback = disconnect_callback
        self.states: Dict[str, ConnectionHeartbeatState] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def register_connection(self, server_name: str):
        now = time.monotonic()
        self.states[server_name] = ConnectionHeartbeatState(
            server_name=server_name,
            last_ping_time=now,
            last_pong_time=now,
            unanswered_pings=0,
            is_alive=True
        )

    def record_pong(self, server_name: str):
        now = time.monotonic()
        if server_name in self.states:
            st = self.states[server_name]
            st.last_pong_time = now
            st.unanswered_pings = 0
            st.is_alive = True

    def unregister_connection(self, server_name: str):
        self.states.pop(server_name, None)

    async def check_once(self) -> Set[str]:
        """Run single healthcheck pass, returning zombie servers that timed out."""
        zombies = set()
        for srv, state in list(self.states.items()):
            state.unanswered_pings += 1
            if state.unanswered_pings >= self.max_missed_pings:
                state.is_alive = False
                zombies.add(srv)
                if self.disconnect_callback:
                    try:
                        # P0: Timeout protected callback
                        await asyncio.wait_for(self.disconnect_callback(srv), timeout=2.0)
                    except Exception:
                        pass
        return zombies
