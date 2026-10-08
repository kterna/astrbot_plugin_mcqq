"""Production handler -> manager -> fake RCON transport acceptance cases."""

import asyncio
import json

import aiomcrcon
import pytest

from core.handlers.command_handler import CommandHandler
from core.managers.rcon_manager import OutcomeStatus, RconManager


class Adapter:
    def __init__(self, name, **config):
        self.adapter_id = name
        self.server_name = name
        self.config = {
            "rcon_enabled": True, "rcon_password": "test-only", "rcon_host": name,
            "rcon_port": 25575, "rcon_allowed_commands": ["whitelist add", "whitelist remove"],
            "rcon_rate_limit_per_sec": 20,
        }
        self.config.update(config)


class Event:
    def __init__(self, text, admin=True):
        self.message_str = text
        self.admin = admin

    def is_admin(self):
        return self.admin

    def get_sender_id(self):
        return "admin-test"


class Router:
    def __init__(self, adapters):
        self.adapters = adapters

    def get_all_adapters(self):
        return self.adapters


class Plugin:
    def __init__(self, manager, adapters):
        self.rcon_manager = manager
        self.adapter_router = Router(adapters)
        self.primary = adapters[0]

    async def get_minecraft_adapter(self):
        return self.primary


@pytest.fixture
def rig(monkeypatch):
    calls = []
    connections = []
    replies = {}

    class Client:
        def __init__(self, host, port, password):
            self.host = host

        async def connect(self):
            connections.append(self.host)

        async def close(self):
            pass

        async def send_cmd(self, command):
            calls.append((self.host, command))
            reply = replies.get((self.host, command), f"OK: {command}")
            if reply == "disconnect":
                raise aiomcrcon.ClientNotConnectedError()
            if reply == "timeout":
                await asyncio.sleep(0.2)
            if reply == "cancel":
                raise asyncio.CancelledError()
            return (reply, 0)

    monkeypatch.setattr(aiomcrcon, "Client", Client)
    manager = RconManager()
    a, b = Adapter("srv-a"), Adapter("srv-b")
    handler = CommandHandler(Plugin(manager, [a, b]))
    return handler, manager, a, b, calls, connections, replies


@pytest.mark.asyncio
async def test_admin_and_policy_precede_transport(rig):
    handler, manager, a, b, calls, connections, _ = rig
    await manager.initialize(a)
    assert await handler.handle_rcon_command(Event("/rcon say hi", False)) == "⛔ 只有管理员才能使用此命令"
    for command in ("op Steve", "/OP Steve", "MiNeCrAfT:StOp", "bukkit:op Steve",
                    "  /op Steve", "whitelist   off", "restart", "stop\nsay hi", "//op Steve",
                    "unknown_alias Steve"):
        ok, _ = await manager.execute_command(command, "admin", a)
        assert not ok, command
    assert not calls
    assert len(connections) == 1
    assert (await manager.execute_detailed("op Steve", "admin", b)).status == OutcomeStatus.REJECTED
    assert len(connections) == 1  # A rejected secondary-server command does not even connect.
    assert await handler.handle_rcon_command(Event("/rcon 重启")) == "✅ RCON连接已成功重启。"
    assert not calls  # local reconnect is never a server restart command
    assert len(connections) == 2


@pytest.mark.asyncio
async def test_allowed_commands_preserve_response_and_policy_syntax(rig):
    handler, manager, a, _, calls, _, replies = rig
    await manager.initialize(a)
    replies[("srv-a", "list")] = "§aPlayers online"
    assert await handler.handle_rcon_command(Event("/rcon /list")) == "Players online"
    assert (await manager.execute_command("  /MINECRAFT:seed  ", "admin", a))[0]
    assert (await manager.execute_command("say  Hello Minecraft", "admin", a))[0]
    assert calls == [("srv-a", "list"), ("srv-a", "MINECRAFT:seed"),
                     ("srv-a", "say  Hello Minecraft")]


@pytest.mark.asyncio
async def test_server_identity_rate_and_invalid_configuration(rig):
    _, manager, a, b, calls, _, _ = rig
    a.config["rcon_rate_limit_per_sec"] = 1
    b.config["rcon_rate_limit_per_sec"] = 1
    await manager.initialize(a)
    outcomes = await asyncio.gather(*(manager.execute_detailed(f"say {i}", "admin", a) for i in range(10)))
    assert sum(result.success for result in outcomes) == 1
    assert (await manager.execute_detailed("say other", "admin", b)).success
    assert calls == [("srv-a", "say 0"), ("srv-b", "say other")]
    same_name_different_endpoint = Adapter("srv-a", rcon_host="srv-c", rcon_rate_limit_per_sec=1)
    assert (await manager.execute_detailed("say third", "admin", same_name_different_endpoint)).success
    assert manager.server_identity(a) != manager.server_identity(same_name_different_endpoint)
    assert calls[-1] == ("srv-c", "say third")
    for bad in (0, -1, float("nan"), float("inf")):
        b.config["rcon_rate_limit_per_sec"] = bad
        result = await manager.execute_detailed("say blocked", "admin", b)
        assert result.status == OutcomeStatus.REJECTED
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_whitelist_confirmation_and_server_scope(rig):
    handler, manager, a, b, calls, _, replies = rig
    await manager.initialize(a)
    command = '/rcon whitelist {"action":"add","player":"Steve","server":"srv-b"}'
    replies[("srv-b", "whitelist add Steve")] = "Added Steve to the whitelist"
    assert "Added Steve" in await handler.handle_rcon_command(Event(command))
    assert manager.whitelist_manager.is_whitelisted(manager.server_identity(b), "Steve")
    assert not manager.whitelist_manager.is_whitelisted(manager.server_identity(a), "Steve")
    replies[("srv-b", "whitelist remove Steve")] = "Unknown player"
    result = await handler.handle_rcon_command(Event('/rcon whitelist {"action":"remove","player":"Steve","server":"srv-b"}'))
    assert "状态未更新" in result
    assert manager.whitelist_manager.is_whitelisted(manager.server_identity(b), "Steve")
    replies[("srv-b", "whitelist remove Steve")] = "Removed Steve from the whitelist"
    assert "Removed Steve" in await handler.handle_rcon_command(Event('/rcon whitelist {"action":"remove","player":"Steve","server":"srv-b"}'))
    assert not manager.whitelist_manager.is_whitelisted(manager.server_identity(b), "Steve")
    before = len(calls)
    for bad in ('/rcon whitelist {"action":"add","player":"Steve; op Bob"}',
                '/rcon whitelist {"action":"add","player":" Steve"}',
                '/rcon whitelist {"action":"add","action":"remove","player":"Steve"}',
                '/rcon whitelist add Steve;op Bob'):
        await handler.handle_rcon_command(Event(bad))
    assert len(calls) == before


@pytest.mark.asyncio
async def test_batch_abort_continue_unknown_presend_and_cancellation(rig):
    handler, manager, a, _, calls, _, replies = rig
    a.config["rcon_command_timeout_sec"] = 0.01
    await manager.initialize(a)
    def batch(commands, policy):
        return Event("/rcon batch " + json.dumps({"commands": commands, "policy": policy}))
    text = await handler.handle_rcon_command(batch(["say first", "op Steve", "say last"], "abort"))
    assert [line.split(":")[0].split(". ")[1] for line in text.splitlines()] == ["confirmed", "rejected", "skipped"]
    assert calls == [("srv-a", "say first")]
    text = await handler.handle_rcon_command(batch(["say second", "op Steve", "say third"], "continue"))
    assert [line.split(":")[0].split(". ")[1] for line in text.splitlines()] == ["confirmed", "rejected", "confirmed"]
    replies[("srv-a", "say disconnect")] = "disconnect"
    replies[("srv-a", "say timeout")] = "timeout"
    results = await manager.execute_batch(["say disconnect", "say timeout"], "admin", a)
    assert [r.status for r in results] == [OutcomeStatus.PRE_SEND_FAILURE, OutcomeStatus.UNKNOWN]
    assert calls.count(("srv-a", "say timeout")) == 1
    replies[("srv-a", "say cancel")] = "cancel"
    with pytest.raises(asyncio.CancelledError):
        await handler.handle_rcon_command(batch(["say cancel", "say later"], "continue"))
    assert ("srv-a", "say later") not in calls
