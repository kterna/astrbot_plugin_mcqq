"""Unit tests for WebSocketWatchdog."""

import pytest
import asyncio
from core.managers.watchdog import WebSocketWatchdog


@pytest.mark.asyncio
async def test_watchdog_registration_and_pong():
    disconnected = []
    async def on_dc(srv):
        disconnected.append(srv)

    dog = WebSocketWatchdog(max_missed_pings=2, disconnect_callback=on_dc)
    dog.register_connection("mc_survival")

    # Pass 1
    zombies = await dog.check_once()
    assert len(zombies) == 0
    assert dog.states["mc_survival"].unanswered_pings == 1

    # Receive pong -> resets count
    dog.record_pong("mc_survival")
    assert dog.states["mc_survival"].unanswered_pings == 0

    # Pass 1 & 2 without pong
    await dog.check_once()
    zombies = await dog.check_once()
    assert "mc_survival" in zombies
    assert "mc_survival" in disconnected
