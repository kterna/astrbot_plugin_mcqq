"""Job B regressions against the live command and WebSocket manager paths.

AstrBot's event/plugin objects and the Minecraft peer are test doubles. The
WebSocket frames and shared reverse listener are real loopback transports.
"""
import asyncio
import json
import socket
from types import SimpleNamespace

import pytest
import websockets

from core.handlers.command_handler import CommandHandler
from core.managers.websocket_manager import WebSocketManager


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def until(predicate, timeout=3):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.01)


class Adapter:
    def __init__(self, manager, name):
        self.websocket_manager = manager
        self.server_name = name
        self.adapter_id = name
        self.config = {"server_name": name}

    async def is_connected(self):
        return self.websocket_manager.connected


def handler_for(adapter):
    plugin = SimpleNamespace(get_minecraft_adapter=lambda: asyncio.sleep(0, result=adapter))
    return CommandHandler(plugin)


def answer(echo, names, status="ok"):
    return {
        "status": status,
        "echo": echo,
        "data": {
            "players": [{"nickname": name} for name in names],
            "count": len(names),
            "max_players": 20,
        },
    }


@pytest.mark.asyncio
async def test_live_player_command_coalesces_per_adapter_and_ttl():
    port = free_port()
    managers = [
        WebSocketManager(mode="server", server_host="127.0.0.1", server_port=port,
                         server_name=name)
        for name in ("S1", "S2")
    ]
    tasks = []
    peer_tasks = []
    try:
        for manager in managers:
            task = asyncio.create_task(manager.start())
            tasks.append(task)
            await until(lambda: manager._shared_server and manager._shared_server._running)
        uri = f"ws://127.0.0.1:{port}/minecraft/ws"
        sockets = [
            await websockets.connect(uri, additional_headers={"x-self-name": name})
            for name in ("S1", "S2")
        ]
        await until(lambda: all(manager.connected for manager in managers))
        gate = asyncio.Event()
        first_seen = asyncio.Event()
        counts = [0, 0]

        async def peer(index, socket):
            async for raw in socket:
                request = json.loads(raw)
                counts[index] += 1
                if index == 0 and counts[index] == 1:
                    first_seen.set()
                    await gate.wait()
                await socket.send(json.dumps(
                    answer(request["echo"], [] if index == 0 else ["Alex"])
                ))

        peer_tasks = [asyncio.create_task(peer(i, ws)) for i, ws in enumerate(sockets)]
        first = handler_for(Adapter(managers[0], "S1"))
        second = handler_for(Adapter(managers[1], "S2"))
        one = asyncio.create_task(first.handle_player_list_command(None))
        two = asyncio.create_task(first.handle_player_list_command(None))
        await first_seen.wait()
        other = asyncio.create_task(second.handle_player_list_command(None))
        gate.set()
        result1, result2, result_other = await asyncio.gather(one, two, other)
        assert result1 == result2 == "🎮 服务器当前无玩家在线 (0/20)"
        assert "Alex" in result_other
        assert counts == [1, 1]
        assert await first.handle_player_list_command(None) == result1
        assert counts == [1, 1]

        # Deep copy at the cache boundary protects nested player dictionaries.
        cache = managers[1].player_list_cache
        key = next(iter(cache._cache))
        snapshot = cache.get(key)
        snapshot["data"]["players"][0]["nickname"] = "corrupted"
        again = cache.get(key)
        assert again["data"]["players"][0]["nickname"] == "Alex"

        managers[0].player_list_cache.default_ttl = 0.02
        managers[0].invalidate_player_list()
        await first.handle_player_list_command(None)
        assert counts[0] == 2
        await asyncio.sleep(0.03)
        await first.handle_player_list_command(None)
        assert counts[0] == 3
    finally:
        for peer_task in peer_tasks:
            peer_task.cancel()
        for manager in managers:
            await manager.close()
        for task in tasks + peer_tasks:
            task.cancel()
        await asyncio.gather(*(tasks + peer_tasks), return_exceptions=True)


@pytest.mark.asyncio
async def test_generation_and_event_invalidation_fence_late_reply():
    manager = WebSocketManager(server_name="S")
    manager._activate_connection(object())
    old_reply = asyncio.get_running_loop().create_future()
    started = asyncio.Event()
    fetches = 0

    async def old_fetch():
        nonlocal fetches
        fetches += 1
        started.set()
        return await old_reply

    old = asyncio.create_task(manager.query_player_list(old_fetch))
    await started.wait()
    manager.invalidate_player_list()  # observed join or quit
    fresh = await manager.query_player_list(lambda: asyncio.sleep(0, result=answer("new", ["New"])))
    old_reply.set_result(answer("old", ["Old"]))
    assert (await old)["data"]["players"][0]["nickname"] == "New"
    assert fresh["data"]["players"][0]["nickname"] == "New"
    assert fetches == 1

    manager._activate_connection(object())  # reconnect / replacement
    reconnect = await manager.query_player_list(
        lambda: asyncio.sleep(0, result=answer("reconnect", ["Reconnected"]))
    )
    assert reconnect["data"]["players"][0]["nickname"] == "Reconnected"
    await manager.close()


@pytest.mark.asyncio
async def test_failed_malformed_empty_and_caller_cancellation():
    manager = WebSocketManager()
    manager._activate_connection(object())
    calls = 0

    async def fetch(value):
        nonlocal calls
        calls += 1
        return value

    for value in ({"status": "error"}, {"status": "ok", "data": {"players": []}}):
        await manager.query_player_list(lambda value=value: fetch(value))
    assert calls == 2
    await manager.query_player_list(lambda: fetch(answer("empty", [])))
    await manager.query_player_list(lambda: pytest.fail("valid empty answer was not cached"))
    assert calls == 3

    manager.invalidate_player_list()
    gate = asyncio.Event()
    async def slow():
        nonlocal calls
        calls += 1
        await gate.wait()
        return answer("shared", ["Shared"])
    one = asyncio.create_task(manager.query_player_list(slow))
    two = asyncio.create_task(manager.query_player_list(slow))
    await until(lambda: calls == 4)
    one.cancel()
    with pytest.raises(asyncio.CancelledError):
        await one
    gate.set()
    assert (await two)["data"]["players"][0]["nickname"] == "Shared"
    assert calls == 4
    await manager.close()
