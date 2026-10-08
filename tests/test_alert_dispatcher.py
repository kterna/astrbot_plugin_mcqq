"""Alert delivery outcome and bounded deduplication tests."""
import asyncio

import pytest

from core.routing.alert_dispatcher import AlertDispatcher, AlertPayload, AlertSeverity


def alert(generation=1):
    return AlertPayload(
        server_name="lobby", severity=AlertSeverity.WARN,
        title="connection_disconnected", message="transport_closed",
        generation=generation,
    )


@pytest.mark.asyncio
async def test_delivered_suppressed_and_bounded_history():
    sent = []
    async def sender(payload):
        sent.append(payload)

    dispatcher = AlertDispatcher(dedup_window_sec=0.03, max_history=2, webhook_sender=sender)
    first = await dispatcher.dispatch(alert())
    assert first.status == "delivered" and first.attempted and first.delivered
    duplicate = await dispatcher.dispatch(alert())
    assert duplicate.status == "suppressed" and not duplicate.attempted
    assert len(sent) == 1
    await asyncio.sleep(0.04)
    assert (await dispatcher.dispatch(alert())).status == "delivered"
    assert len(sent) == 2
    await dispatcher.dispatch(alert(2))
    await dispatcher.dispatch(alert(3))
    assert len(dispatcher._history) == 2


@pytest.mark.asyncio
async def test_failure_observable_and_retry_bounded():
    calls = 0
    async def failing(payload):
        nonlocal calls
        calls += 1
        raise OSError("test sender failure")

    dispatcher = AlertDispatcher(webhook_sender=failing, failure_retry_sec=0.02)
    failed = await dispatcher.dispatch(alert())
    assert failed.status == "failed" and failed.attempted and not failed.delivered
    assert failed.error == "OSError"
    assert (await dispatcher.dispatch(alert())).status == "suppressed"
    assert calls == 1
    await asyncio.sleep(0.03)
    assert (await dispatcher.dispatch(alert())).status == "failed"
    assert calls == 2


@pytest.mark.asyncio
async def test_timeout_and_unconfigured_are_not_delivery():
    async def slow(payload):
        await asyncio.sleep(10)

    dispatcher = AlertDispatcher(webhook_sender=slow, send_timeout=0.02)
    result = await dispatcher.dispatch(alert())
    assert result.status == "failed" and result.error == "TimeoutError"
    assert (await AlertDispatcher().dispatch(alert())).status == "unconfigured"
