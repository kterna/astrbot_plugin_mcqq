"""Deterministic lifecycle races through WebSocketManager's public entry points."""
import asyncio

import pytest

from core.managers import websocket_manager as module


async def until(predicate):
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(0)


class Listener:
    def __init__(self):
        self.closed = False
        self.close_gate = asyncio.Event()

    def close(self):
        self.closed = True

    async def wait_closed(self):
        await self.close_gate.wait()


@pytest.mark.asyncio
async def test_simultaneous_managers_bind_once_and_both_detach(monkeypatch):
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def serve(*args, **kwargs):
        listener = Listener()
        listener.close_gate.set()
        calls.append(listener)
        entered.set()
        await release.wait()
        return listener

    monkeypatch.setattr(module.websockets, "serve", serve)
    managers = [module.WebSocketManager(mode="server", server_host="127.0.0.1",
                                        server_port=48231, server_name=name)
                for name in ("first", "second")]
    tasks = [asyncio.create_task(manager.start()) for manager in managers]
    try:
        await entered.wait()
        await asyncio.sleep(0)  # Let the second manager contend during bind.
        assert len(calls) == 1
        release.set()
        await until(lambda: all(manager._shared_server and manager._shared_server._running
                                for manager in managers))
        assert managers[0]._shared_server is managers[1]._shared_server
        await asyncio.gather(*(manager.close() for manager in managers))
        assert all(task.done() for task in tasks)
        assert len(calls) == 1 and calls[0].closed
        assert not module._SHARED_SERVERS
    finally:
        release.set()
        for listener in calls:
            listener.close_gate.set()
        await asyncio.gather(*(manager.close() for manager in managers))
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_new_manager_waits_for_previous_listener_to_close(monkeypatch):
    listeners = []

    async def serve(*args, **kwargs):
        listener = Listener()
        listeners.append(listener)
        return listener

    monkeypatch.setattr(module.websockets, "serve", serve)
    first = module.WebSocketManager(mode="server", server_host="127.0.0.1",
                                    server_port=48232, server_name="first")
    second = module.WebSocketManager(mode="server", server_host="127.0.0.1",
                                     server_port=48232, server_name="second")
    first_task = asyncio.create_task(first.start())
    second_task = None
    try:
        await until(lambda: first._shared_server and first._shared_server._running)
        close_task = asyncio.create_task(first.close())
        await until(lambda: listeners[0].closed)
        second_task = asyncio.create_task(second.start())
        await asyncio.sleep(0)  # Contend while the old listener is closing.
        assert len(listeners) == 1
        assert second._shared_server is None
        listeners[0].close_gate.set()
        await close_task
        await until(lambda: second._shared_server and second._shared_server._running)
        assert len(listeners) == 2
        listeners[1].close_gate.set()
        await second.close()
        assert first_task.done() and second_task.done()
        assert not module._SHARED_SERVERS
    finally:
        for listener in listeners:
            listener.close_gate.set()
        await first.close()
        await second.close()
        await asyncio.gather(first_task, *(task for task in (second_task,) if task),
                             return_exceptions=True)


def test_manager_rejects_cross_loop_lifecycle_use():
    manager = module.WebSocketManager(mode="server", server_host="127.0.0.1",
                                      server_port=48233, server_name="owned")

    async def bind_owner_loop():
        await manager.close()

    async def use_replacement_loop():
        with pytest.raises(RuntimeError, match="cannot move between event loops"):
            await manager.start()

    asyncio.run(bind_owner_loop())
    asyncio.run(use_replacement_loop())
