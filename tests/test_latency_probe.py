"""Unit tests for ServerLatencyProbe."""

import asyncio
import pytest
from core.adapters.latency_probe import ServerLatencyProbe


@pytest.mark.asyncio
async def test_probe_mock_echo_server():
    # Start mock server
    async def handle_client(reader, writer):
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    probe = ServerLatencyProbe(default_timeout_sec=1.0)
    res = await probe.ping_server("local_mc", "127.0.0.1", port)

    assert res.is_online is True
    assert res.latency_ms >= 0
    assert res.server_name == "local_mc"

    server.close()
    await server.wait_closed()


@pytest.mark.asyncio
async def test_probe_offline_server():
    probe = ServerLatencyProbe(default_timeout_sec=0.2)
    # Port 59999 is unlikely to be listening
    res = await probe.ping_server("offline_mc", "127.0.0.1", 59999)

    assert res.is_online is False
    assert res.latency_ms == -1.0
    assert res.error_message is not None
