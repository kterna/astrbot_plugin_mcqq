"""Unit tests for AlertDispatcher."""

import pytest
import asyncio
from core.routing.alert_dispatcher import AlertDispatcher, AlertPayload, AlertSeverity


@pytest.mark.asyncio
async def test_alert_dispatch_and_dedup():
    sent_payloads = []
    async def mock_sender(payload):
        sent_payloads.append(payload)

    dispatcher = AlertDispatcher(dedup_window_sec=0.5, webhook_sender=mock_sender)

    alert1 = AlertPayload(
        server_name="lobby",
        severity=AlertSeverity.WARN,
        title="High Memory Usage",
        message="Memory exceeds 90%"
    )

    # First dispatch succeeds
    res1 = await dispatcher.dispatch(alert1)
    assert res1 is True
    assert len(sent_payloads) == 1

    # Immediate duplicate is suppressed
    res2 = await dispatcher.dispatch(alert1)
    assert res2 is False
    assert len(sent_payloads) == 1

    # After window expires, dispatch allowed again
    await asyncio.sleep(0.55)
    res3 = await dispatcher.dispatch(alert1)
    assert res3 is True
    assert len(sent_payloads) == 2


@pytest.mark.asyncio
async def test_alert_timeout_tolerance():
    async def slow_sender(payload):
        await asyncio.sleep(10.0) # Hangs

    dispatcher = AlertDispatcher(dedup_window_sec=1.0, webhook_sender=slow_sender)
    alert = AlertPayload(
        server_name="survival",
        severity=AlertSeverity.CRITICAL,
        title="Crash Alert",
        message="Server down"
    )

    # Must complete safely without raising TimeoutError
    res = await dispatcher.dispatch(alert)
    assert res is True
