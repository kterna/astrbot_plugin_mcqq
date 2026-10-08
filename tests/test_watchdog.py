"""Passive health recorder never infers a missing pong from time alone."""
import asyncio

import pytest

from core.managers.watchdog import WebSocketWatchdog


@pytest.mark.asyncio
async def test_passive_health_requires_transport_transition():
    health = WebSocketWatchdog("survival")
    assert health.record_connected(7)
    first = health.snapshot()
    assert first.connected and first.connected_at is not None
    await asyncio.sleep(0.02)  # A scheduler tick is no disconnect evidence.
    assert health.snapshot().connected
    assert health.record_disconnected(6, "stale_socket") is False
    assert health.record_disconnected(7, "keepalive_timeout") is True
    assert health.record_disconnected(7, "keepalive_timeout") is False
    state = health.snapshot()
    assert state.disconnect_count == 1
    assert state.disconnect_cause == "keepalive_timeout"
    assert state.disconnected_at >= first.connected_at
    assert health.record_connected(8)
    assert health.snapshot().connected
