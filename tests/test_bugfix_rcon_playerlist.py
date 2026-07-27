"""issue #32 / #33 的回归测试

#32 RCON 断线自动重连在事件循环线程内自锁
#33 mc玩家列表 先发请求后注册响应处理器，快速响应会被漏掉

修复前：#32 的用例会永久挂起（被 asyncio.wait_for 判超时），
#33 的 fast-reply 用例会拿不到响应。
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
from pathlib import Path
from urllib.parse import quote_plus

import pytest
import websockets

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.handlers.command_handler import CommandHandler  # noqa: E402
from core.managers.rcon_manager import RconManager  # noqa: E402
from core.managers.websocket_manager import WebSocketManager  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _wait_until(pred, timeout=5.0, interval=0.05):
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        if pred():
            return True
        await asyncio.sleep(interval)
    return False


class _FakeAdapter:
    """只提供 RconManager 需要的 config"""

    def __init__(self, **overrides):
        self.config = {
            "rcon_enabled": True,
            "rcon_password": "pw",
            "rcon_host": "127.0.0.1",
            "rcon_port": 25575,
        }
        self.config.update(overrides)


# ---------------------------------------------------------------------------
# #32 RCON 自动重连
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rcon_autoreconnect_does_not_deadlock(monkeypatch):
    """断线状态下执行指令会自动重连，且不会卡死事件循环。"""
    import aiomcrcon

    connect_calls = 0

    class CountingClient:
        def __init__(self, host, port, password):
            self.host, self.port, self.password = host, port, password

        async def connect(self):
            nonlocal connect_calls
            connect_calls += 1
            # 让出控制权：修复前 .result() 阻塞线程，这里永远不会被调度回来
            await asyncio.sleep(0)

        async def close(self):
            await asyncio.sleep(0)

        async def send_cmd(self, command):
            return (f"executed: {command}", 0)

    monkeypatch.setattr(aiomcrcon, "Client", CountingClient)

    manager = RconManager()
    manager.rcon_enabled = True  # 已初始化过，但当前处于断开状态
    adapter = _FakeAdapter()

    success, message = await asyncio.wait_for(
        manager.execute_command("list", "tester", adapter), timeout=5
    )

    assert success is True, message
    assert message == "executed: list"
    assert connect_calls == 1
    assert manager.rcon_connected is True


@pytest.mark.asyncio
async def test_rcon_concurrent_reconnect_only_once(monkeypatch):
    """并发指令触发的重连被串行化，只真正重连一次。"""
    import aiomcrcon

    connect_calls = 0

    class SlowClient:
        def __init__(self, host, port, password):
            pass

        async def connect(self):
            nonlocal connect_calls
            connect_calls += 1
            await asyncio.sleep(0.2)  # 拉长窗口，制造并发

        async def close(self):
            await asyncio.sleep(0)

        async def send_cmd(self, command):
            return (f"executed: {command}", 0)

    monkeypatch.setattr(aiomcrcon, "Client", SlowClient)

    manager = RconManager()
    manager.rcon_enabled = True
    adapter = _FakeAdapter()

    results = await asyncio.wait_for(
        asyncio.gather(
            manager.execute_command("list", "a", adapter),
            manager.execute_command("seed", "b", adapter),
            manager.execute_command("time query day", "c", adapter),
        ),
        timeout=5,
    )

    assert all(ok for ok, _ in results), results
    assert connect_calls == 1


@pytest.mark.asyncio
async def test_rcon_disabled_short_circuits():
    """未启用 RCON 时直接返回，不触发重连。"""
    manager = RconManager()
    manager.rcon_enabled = False

    success, message = await asyncio.wait_for(
        manager.execute_command("list", "tester", _FakeAdapter()), timeout=3
    )

    assert success is False
    assert "未启用" in message


# ---------------------------------------------------------------------------
# #33 API 请求-响应分发
# ---------------------------------------------------------------------------


def _new_manager(**kwargs) -> WebSocketManager:
    kwargs.setdefault("mode", "client")
    kwargs.setdefault("ws_url", "ws://127.0.0.1:1/ws")
    kwargs.setdefault("server_host", "127.0.0.1")
    kwargs.setdefault("server_port", 0)
    kwargs.setdefault("server_path", "/minecraft/ws")
    kwargs.setdefault("server_name", "TestServer")
    return WebSocketManager(**kwargs)


@pytest.mark.asyncio
async def test_waiter_receives_response_by_echo():
    manager = _new_manager()
    future = manager.register_api_waiter("echo-1", "get_player_list")

    await manager._dispatch_message(
        json.dumps(
            {
                "status": "ok",
                "message": "Player list retrieved",
                "echo": "echo-1",
                "data": {"players": [], "count": 0, "max_players": 20},
            }
        )
    )

    assert future.done()
    assert (await future)["echo"] == "echo-1"


@pytest.mark.asyncio
async def test_concurrent_waiters_are_not_crossed():
    """并发两个请求，响应乱序返回也各归各的（修复前后者会覆盖前者）。"""
    manager = _new_manager()
    first = manager.register_api_waiter("echo-1", "get_player_list")
    second = manager.register_api_waiter("echo-2", "get_player_list")

    # 故意先回第二个
    for echo, count in (("echo-2", 2), ("echo-1", 1)):
        await manager._dispatch_message(
            json.dumps(
                {
                    "status": "ok",
                    "echo": echo,
                    "data": {"players": [], "count": count, "max_players": 20},
                }
            )
        )

    assert (await first)["data"]["count"] == 1
    assert (await second)["data"]["count"] == 2


@pytest.mark.asyncio
async def test_api_response_not_leaked_to_message_handler():
    """API 响应被等待者消费后，不应再进普通消息处理器。"""
    manager = _new_manager()
    seen: list = []
    manager.set_message_handler(lambda raw: seen.append(json.loads(raw)) or asyncio.sleep(0))

    manager.register_api_waiter("echo-1", "get_player_list")
    await manager._dispatch_message(
        json.dumps({"status": "ok", "echo": "echo-1", "data": {"players": []}})
    )
    assert seen == []

    # 普通事件照常放行
    await manager._dispatch_message(
        json.dumps({"event_name": "PlayerChatEvent", "message": "hi"})
    )
    assert len(seen) == 1
    assert seen[0]["event_name"] == "PlayerChatEvent"


@pytest.mark.asyncio
async def test_legacy_response_without_echo_still_matches():
    """兼容不回显 echo 的旧版鹊桥：唯一等待者按 api 名兜底匹配。"""
    manager = _new_manager()
    future = manager.register_api_waiter("echo-1", "get_player_list")

    await manager._dispatch_message(
        json.dumps(
            {
                "status": "ok",
                "data": {"players": [{"nickname": "Steve"}], "count": 1},
            }
        )
    )

    assert (await future)["data"]["players"][0]["nickname"] == "Steve"


@pytest.mark.asyncio
async def test_cancel_api_waiter_cleans_registry():
    manager = _new_manager()
    manager.register_api_waiter("echo-1", "get_player_list")
    assert manager._pending_api
    manager.cancel_api_waiter("echo-1")
    assert not manager._pending_api


# ---------------------------------------------------------------------------
# #33 端到端：真实 WebSocket + 秒回响应
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_player_list_request_catches_immediate_response():
    """鹊桥收到请求立刻回包，_request_api 也必须接得住。

    修复前是「先 send 再装 handler」，这种秒回会被原 handler 吃掉并最终超时。
    """
    port = _free_port()
    manager = WebSocketManager(
        mode="server",
        server_host="127.0.0.1",
        server_port=port,
        server_path="/minecraft/ws",
        server_name="TestServer",
    )
    manager.set_message_handler(lambda raw: asyncio.sleep(0))

    handler = CommandHandler.__new__(CommandHandler)  # 只用 _request_api，跳过 __init__
    adapter = type("A", (), {"websocket_manager": manager})()

    server_task = asyncio.create_task(manager.start())
    client_task = None
    try:
        assert await _wait_until(
            lambda: manager._shared_server and manager._shared_server._running
        ), "server failed to start"

        uri = f"ws://127.0.0.1:{port}/minecraft/ws"
        headers = {
            "x-self-name": quote_plus("TestServer"),
            "x-client-origin": "minecraft",
        }

        async def fake_queqiao():
            async with websockets.connect(uri, additional_headers=headers) as ws:
                async for raw in ws:
                    data = json.loads(raw)
                    if data.get("api") != "get_player_list":
                        continue
                    # 立刻回包，不做任何等待
                    await ws.send(
                        json.dumps(
                            {
                                "status": "ok",
                                "message": "Player list retrieved",
                                "echo": data.get("echo"),
                                "data": {
                                    "players": [
                                        {"nickname": "Steve", "is_op": True},
                                        {"nickname": "Alex", "is_op": False},
                                    ],
                                    "count": 2,
                                    "max_players": 20,
                                },
                            }
                        )
                    )

        client_task = asyncio.create_task(fake_queqiao())
        assert await _wait_until(lambda: manager.connected), "client not connected"

        response = await handler._request_api(
            adapter, "get_player_list", {}, timeout=5
        )
        assert response["status"] == "ok"
        assert response["data"]["count"] == 2

        text = handler._format_player_list_response(response)
        assert "Steve" in text and "Alex" in text

        # 连发两次并发请求，互不串号
        both = await asyncio.gather(
            handler._request_api(adapter, "get_player_list", {}, timeout=5),
            handler._request_api(adapter, "get_player_list", {}, timeout=5),
        )
        assert all(r["data"]["count"] == 2 for r in both)
        assert not manager._pending_api, "等待者未清理干净"
    finally:
        if client_task:
            client_task.cancel()
        await manager.close()
        server_task.cancel()
        for t in (server_task, client_task):
            if t:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass


@pytest.mark.asyncio
async def test_player_list_request_times_out_without_response():
    """没有响应时抛 TimeoutError 并清理等待者，不会泄漏。"""
    manager = _new_manager()
    manager.connected = True
    manager.websocket = type(
        "WS", (), {"send": staticmethod(lambda payload: asyncio.sleep(0))}
    )()

    handler = CommandHandler.__new__(CommandHandler)
    adapter = type("A", (), {"websocket_manager": manager})()

    with pytest.raises(asyncio.TimeoutError):
        await handler._request_api(adapter, "get_player_list", {}, timeout=0.3)

    assert not manager._pending_api
