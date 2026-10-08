"""Passive WebSocket lifecycle health, driven only by transport observations.

The websockets library owns ping/pong and closes a connection after a missing
acknowledgement exceeds ping_timeout. This recorder never sends another ping or
infers a missing pong from scheduler ticks.
"""
from dataclasses import dataclass, replace
import time


@dataclass
class ConnectionHealthState:
    server_name: str
    generation: int = 0
    connected: bool = False
    connected_at: float | None = None
    disconnected_at: float | None = None
    disconnect_cause: str | None = None
    disconnect_count: int = 0


class WebSocketWatchdog:
    """Record at most one disconnect transition per connected generation."""

    def __init__(self, server_name: str):
        self.state = ConnectionHealthState(server_name=server_name)

    def record_connected(self, generation: int) -> bool:
        if generation <= self.state.generation:
            return False
        self.state.generation = generation
        self.state.connected = True
        self.state.connected_at = time.monotonic()
        self.state.disconnected_at = None
        self.state.disconnect_cause = None
        return True

    def record_disconnected(self, generation: int, cause: str) -> bool:
        if not self.state.connected or self.state.generation != generation:
            return False
        self.state.connected = False
        self.state.disconnected_at = time.monotonic()
        self.state.disconnect_cause = cause
        self.state.disconnect_count += 1
        return True

    def snapshot(self) -> ConnectionHealthState:
        return replace(self.state)
