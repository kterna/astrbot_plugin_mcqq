"""
反向 WebSocket 自动化测试

模拟：
1. AstrBot 侧 WebSocketManager(mode=server) 监听
2. 鹊桥侧 Client 主动连入（带 x-self-name / Authorization）
3. 双向收发：事件上送 + API 下发
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import socket
import sys
import types
from pathlib import Path
from urllib.parse import quote_plus

import pytest
import websockets

ROOT = Path(__file__).resolve().parents[1]


def _load_websocket_manager():
    """直接加载 websocket_manager.py，避免触发插件根 __init__ / astrbot 依赖。"""
    # stub astrbot.logger
    if "astrbot" not in sys.modules:
        astrbot = types.ModuleType("astrbot")

        class _Logger:
            def info(self, *a, **k):
                pass

            def warning(self, *a, **k):
                pass

            def error(self, *a, **k):
                pass

            def debug(self, *a, **k):
                pass

        astrbot.logger = _Logger()
        sys.modules["astrbot"] = astrbot

    path = ROOT / "core" / "managers" / "websocket_manager.py"
    spec = importlib.util.spec_from_file_location(
        "mcqq_websocket_manager", path
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_wm = _load_websocket_manager()
WebSocketManager = _wm.WebSocketManager


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


@pytest.mark.asyncio
async def test_reverse_ws_connect_and_event():
    port = _free_port()
    received: asyncio.Queue = asyncio.Queue()

    async def on_message(raw: str):
        await received.put(json.loads(raw))

    manager = WebSocketManager(
        mode="server",
        server_host="127.0.0.1",
        server_port=port,
        server_path="/minecraft/ws",
        server_name="TestServer",
        access_token="secret-token",
    )
    manager.set_message_handler(on_message)

    task = asyncio.create_task(manager.start())
    try:
        ok = await _wait_until(
            lambda: manager._shared_server and manager._shared_server._running
        )
        assert ok, "server failed to start"

        headers = {
            "x-self-name": quote_plus("TestServer"),
            "x-client-origin": "minecraft",
            "Authorization": "Bearer secret-token",
        }
        uri = f"ws://127.0.0.1:{port}/minecraft/ws"

        async with websockets.connect(uri, additional_headers=headers) as ws:
            assert await _wait_until(lambda: manager.connected)

            event = {
                "server_name": "TestServer",
                "server_version": "1.21",
                "server_type": "mcdr",
                "event_name": "PlayerChatEvent",
                "post_type": "message",
                "sub_type": "chat",
                "message": "hello from mc",
                "player": {"nickname": "Steve", "uuid": "u-1"},
            }
            await ws.send(json.dumps(event))
            got = await asyncio.wait_for(received.get(), timeout=3)
            assert got["message"] == "hello from mc"
            assert got["player"]["nickname"] == "Steve"

            ok_send = await manager.send_message(
                {
                    "api": "broadcast",
                    "data": {"message": "hello from bot"},
                    "echo": "1",
                }
            )
            assert ok_send is True
            raw = await asyncio.wait_for(ws.recv(), timeout=3)
            payload = json.loads(raw)
            assert payload["api"] == "broadcast"
            assert payload["data"]["message"] == "hello from bot"
    finally:
        await manager.close()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_reverse_ws_auth_rejected():
    port = _free_port()
    manager = WebSocketManager(
        mode="server",
        server_host="127.0.0.1",
        server_port=port,
        server_path="/minecraft/ws",
        server_name="AuthServer",
        access_token="real-token",
    )
    task = asyncio.create_task(manager.start())
    try:
        assert await _wait_until(
            lambda: manager._shared_server and manager._shared_server._running
        )
        uri = f"ws://127.0.0.1:{port}/minecraft/ws"
        headers = {
            "x-self-name": quote_plus("AuthServer"),
            "Authorization": "Bearer wrong-token",
        }
        with pytest.raises(Exception):
            async with websockets.connect(uri, additional_headers=headers) as ws:
                await ws.recv()
    finally:
        await manager.close()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_reverse_ws_unknown_server_name_rejected():
    port = _free_port()
    manager = WebSocketManager(
        mode="server",
        server_host="127.0.0.1",
        server_port=port,
        server_path="/minecraft/ws",
        server_name="KnownServer",
        access_token="",
    )
    task = asyncio.create_task(manager.start())
    try:
        assert await _wait_until(
            lambda: manager._shared_server and manager._shared_server._running
        )
        uri = f"ws://127.0.0.1:{port}/minecraft/ws"
        headers = {"x-self-name": quote_plus("OtherServer")}
        with pytest.raises(Exception):
            async with websockets.connect(uri, additional_headers=headers) as ws:
                await ws.recv()
    finally:
        await manager.close()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_shared_port_two_servers():
    port = _free_port()
    q1: asyncio.Queue = asyncio.Queue()
    q2: asyncio.Queue = asyncio.Queue()

    m1 = WebSocketManager(
        mode="server",
        server_host="127.0.0.1",
        server_port=port,
        server_path="/minecraft/ws",
        server_name="S1",
        access_token="",
    )
    m2 = WebSocketManager(
        mode="server",
        server_host="127.0.0.1",
        server_port=port,
        server_path="/minecraft/ws",
        server_name="S2",
        access_token="",
    )
    m1.set_message_handler(lambda raw: q1.put(json.loads(raw)))
    m2.set_message_handler(lambda raw: q2.put(json.loads(raw)))

    t1 = asyncio.create_task(m1.start())
    assert await _wait_until(
        lambda: m1._shared_server and m1._shared_server._running
    )
    t2 = asyncio.create_task(m2.start())
    await asyncio.sleep(0.1)

    try:
        uri = f"ws://127.0.0.1:{port}/minecraft/ws"
        async with websockets.connect(
            uri, additional_headers={"x-self-name": quote_plus("S1")}
        ) as ws1:
            async with websockets.connect(
                uri, additional_headers={"x-self-name": quote_plus("S2")}
            ) as ws2:
                assert await _wait_until(lambda: m1.connected and m2.connected)
                await ws1.send(json.dumps({"from": "s1"}))
                await ws2.send(json.dumps({"from": "s2"}))
                g1 = await asyncio.wait_for(q1.get(), timeout=3)
                g2 = await asyncio.wait_for(q2.get(), timeout=3)
                assert g1["from"] == "s1"
                assert g2["from"] == "s2"
    finally:
        await m1.close()
        await m2.close()
        for t in (t1, t2):
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass


@pytest.mark.asyncio
async def test_mcdr_client_to_astrbot_server_roundtrip():
    port = _free_port()
    received: asyncio.Queue = asyncio.Queue()

    manager = WebSocketManager(
        mode="server",
        server_host="127.0.0.1",
        server_port=port,
        server_path="/minecraft/ws",
        server_name="MCDR-Server",
        access_token="tok",
    )
    manager.set_message_handler(lambda raw: received.put(json.loads(raw)))
    task = asyncio.create_task(manager.start())

    try:
        assert await _wait_until(
            lambda: manager._shared_server and manager._shared_server._running
        )

        headers = {
            "x-self-name": quote_plus("MCDR-Server"),
            "x-client-origin": "minecraft",
            "Authorization": "Bearer tok",
        }
        uri = f"ws://127.0.0.1:{port}/minecraft/ws"
        async with websockets.connect(uri, additional_headers=headers) as ws:
            assert await _wait_until(lambda: manager.connected)

            join_event = {
                "server_name": "MCDR-Server",
                "server_version": "1.20.4",
                "server_type": "mcdr",
                "event_name": "PlayerJoinEvent",
                "post_type": "notice",
                "sub_type": "join",
                "player": {"nickname": "Alex", "uuid": ""},
            }
            await ws.send(json.dumps(join_event))
            got = await asyncio.wait_for(received.get(), timeout=3)
            assert got["event_name"] == "PlayerJoinEvent"

            await manager.send_message(
                {"api": "broadcast", "data": {"message": "hi"}, "echo": "e1"}
            )
            raw = await asyncio.wait_for(ws.recv(), timeout=3)
            assert json.loads(raw)["api"] == "broadcast"
    finally:
        await manager.close()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
