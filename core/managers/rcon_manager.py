"""RCON connection owner and the shared command-policy boundary."""

import asyncio
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

import aiomcrcon
from astrbot import logger

from ..adapters.rcon_guard import RconSecurityGuard
from .whitelist_manager import WhitelistManager
from ..utils.minecraft_utils import strip_minecraft_formatting_codes


class OutcomeStatus(str, Enum):
    REJECTED = "rejected"
    PRE_SEND_FAILURE = "pre_send_failure"
    CONFIRMED = "confirmed"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class RconOutcome:
    status: OutcomeStatus
    message: str
    server_id: str

    @property
    def success(self):
        return self.status == OutcomeStatus.CONFIRMED


class RconManager:
    """One connection per adapter, with a guard shared across direct and batch calls."""

    def __init__(self, guard: Optional[RconSecurityGuard] = None, whitelist_manager=None):
        self.guard = guard or RconSecurityGuard()
        self.whitelist_manager = whitelist_manager or WhitelistManager()
        self.rcon_client: Optional[aiomcrcon.Client] = None
        self.rcon_enabled = False
        self.rcon_host = None
        self.rcon_port = None
        self.rcon_password = None
        self.rcon_connected = False
        self._reconnect_lock: Optional[asyncio.Lock] = None
        self._primary_key = None
        self._children = {}
        self._allowed_writes = None
        self._rate = self.guard.rate_limit_per_sec
        self._timeout = 10.0
        self._needs_initialize = False

    @staticmethod
    def server_identity(adapter) -> str:
        if adapter is None:
            return "default"
        config = getattr(adapter, "config", {}) or {}
        adapter_id = getattr(adapter, "adapter_id", None) or config.get("adapter_id")
        if adapter_id:
            return f"adapter:{adapter_id}@{config.get('rcon_host', 'localhost')}:{config.get('rcon_port', 25575)}"
        return f"endpoint:{config.get('rcon_host', 'localhost')}:{config.get('rcon_port', 25575)}"

    def _get_reconnect_lock(self):
        if self._reconnect_lock is None:
            self._reconnect_lock = asyncio.Lock()
        return self._reconnect_lock

    def _policy_for(self, adapter):
        config = getattr(adapter, "config", {}) or {}
        writes = config.get("rcon_allowed_commands")
        RconSecurityGuard.validate_write_commands(writes)
        rate = config.get("rcon_rate_limit_per_sec", self.guard.rate_limit_per_sec)
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate < 1:
            raise ValueError("rcon_rate_limit_per_sec must be a finite number of at least 1")
        timeout = config.get("rcon_command_timeout_sec", 10.0)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError("rcon_command_timeout_sec must be finite and within (0, 120]")
        return writes, float(rate), float(timeout)

    def _validate_config(self, adapter) -> Tuple[bool, str]:
        if not adapter:
            return False, "等待Minecraft平台适配器可用..."
        try:
            self._allowed_writes, self._rate, self._timeout = self._policy_for(adapter)
        except ValueError as exc:
            return False, f"RCON策略配置无效: {exc}"
        self.rcon_enabled = adapter.config.get("rcon_enabled", False)
        if not self.rcon_enabled:
            return False, "RCON功能未在适配器配置中启用，跳过RCON初始化。"
        self.rcon_password = adapter.config.get("rcon_password", "")
        if not self.rcon_password:
            return False, "RCON密码未在适配器配置中配置，无法初始化RCON连接。"
        self.rcon_host = adapter.config.get("rcon_host", "localhost")
        if not self.rcon_host:
            return False, "RCON主机未在适配器配置中配置，无法初始化RCON连接。"
        self.rcon_port = adapter.config.get("rcon_port", 25575)
        return True, ""

    async def initialize(self, adapter):
        if adapter is not None and self._primary_key is None:
            self._primary_key = self.server_identity(adapter)
        self._needs_initialize = False
        valid, message = self._validate_config(adapter)
        if not valid:
            logger.warning("RCON初始化推迟：%s", message)
            return
        await self._connect()

    async def _connect(self):
        self.rcon_client = aiomcrcon.Client(self.rcon_host, self.rcon_port, self.rcon_password)
        try:
            await self.rcon_client.connect()
            self.rcon_connected = True
        except Exception:
            logger.error("RCON连接失败")
            self.rcon_client = None
            self.rcon_connected = False

    async def reconnect(self, adapter) -> bool:
        await self.close(include_children=False)
        await self.initialize(adapter)
        return self.rcon_connected

    async def close(self, include_children=True):
        if self.rcon_client:
            try:
                await self.rcon_client.close()
            except Exception:
                logger.error("RCON关闭连接失败")
        self.rcon_connected = False
        self.rcon_client = None
        if include_children:
            for child in self._children.values():
                await child.close()

    async def _check_rcon_availability(self, sender_id: str, adapter=None) -> Tuple[bool, str]:
        if not self.rcon_enabled:
            return False, "❌ RCON 功能当前未启用。请联系管理员在插件配置中启用。"
        if not self.rcon_client or not self.rcon_connected:
            async with self._get_reconnect_lock():
                if self.rcon_client and self.rcon_connected:
                    return True, ""
                if not await self.reconnect(adapter):
                    return False, "❌ RCON未连接到Minecraft服务器，自动重连失败。请手动使用 'rcon 重启' 命令。"
        return True, ""

    async def _for_adapter(self, adapter):
        key = self.server_identity(adapter)
        if self._primary_key is None:
            self._primary_key = key
        if key == self._primary_key:
            return self
        if key not in self._children:
            if len(self._children) >= self.guard.MAX_SERVERS - 1:
                return None
            child = RconManager(self.guard, self.whitelist_manager)
            child._primary_key = key
            child._needs_initialize = True
            self._children[key] = child
        return self._children[key]

    async def execute_detailed(self, command: str, sender_id: str, adapter=None) -> RconOutcome:
        key = self.server_identity(adapter)
        owner = await self._for_adapter(adapter)
        if owner is None:
            return RconOutcome(OutcomeStatus.REJECTED, "❌ RCON服务器数量超出上限", key)
        if owner is not self:
            return await owner.execute_detailed(command, sender_id, adapter)
        try:
            # Validation precedes both reconnect and send. Local reconnect is exact and never a server command.
            normalized = self.guard.normalize_command(command)
            if normalized == "重启" and isinstance(command, str) and command.strip(" ") == "重启":
                async with self._get_reconnect_lock():
                    success = await self.reconnect(adapter)
                return RconOutcome(OutcomeStatus.CONFIRMED if success else OutcomeStatus.PRE_SEND_FAILURE,
                                   "✅ RCON连接已成功重启。" if success else "❌ RCON连接重启失败。请检查服务器状态和配置。", key)
            writes, rate, timeout = self._policy_for(adapter)
        except ValueError as exc:
            return RconOutcome(OutcomeStatus.REJECTED, f"❌ RCON指令或配置无效: {exc}", key)
        guard_result = self.guard.check_command(key, normalized, writes, rate)
        if not guard_result.allowed:
            return RconOutcome(OutcomeStatus.REJECTED, f"⛔ RCON指令被拒绝: {guard_result.reason}", key)
        if self._needs_initialize:
            await self.initialize(adapter)
        available, error = await self._check_rcon_availability(sender_id, adapter)
        if not available:
            return RconOutcome(OutcomeStatus.PRE_SEND_FAILURE, error, key)
        try:
            response = await asyncio.wait_for(self.rcon_client.send_cmd(guard_result.command), timeout)
        except aiomcrcon.ClientNotConnectedError:
            self.rcon_connected = False
            return RconOutcome(OutcomeStatus.PRE_SEND_FAILURE, "❌ RCON客户端未连接，指令未发送。", key)
        except asyncio.TimeoutError:
            self.rcon_connected = False
            logger.error("RCON等待响应超时；结果未知")
            return RconOutcome(OutcomeStatus.UNKNOWN, "⚠️ RCON响应超时；指令可能已执行，请勿自动重试。", key)
        except asyncio.CancelledError:
            self.rcon_connected = False
            raise
        except Exception:
            self.rcon_connected = False
            logger.error("RCON发送或等待响应失败；结果未知")
            return RconOutcome(OutcomeStatus.UNKNOWN, "⚠️ RCON结果未知；指令可能已执行，请勿自动重试。", key)
        raw = response[0] if response else None
        if not isinstance(raw, str) or not raw:
            return RconOutcome(OutcomeStatus.UNKNOWN, "⚠️ RCON无明确响应；结果未知，请勿自动重试。", key)
        cleaned = strip_minecraft_formatting_codes(raw)
        words = guard_result.command.split()
        root = words[0].lower().split(":")[-1]
        if root == "whitelist" and len(words) == 3 and words[1].lower() in ("add", "remove"):
            action, player = words[1].lower(), words[2]
            expected = ("Added" if action == "add" else "Removed") + f" {player} " + ("to" if action == "add" else "from") + " the whitelist"
            if cleaned.strip().rstrip(".").casefold() != expected.casefold():
                return RconOutcome(OutcomeStatus.UNKNOWN, "⚠️ 白名单操作没有可确认的成功响应；状态未更新，请先核对服务器。", key)
            if action == "add":
                self.whitelist_manager.add_player(key, player, sender_id)
            else:
                self.whitelist_manager.remove_player(key, player)
        return RconOutcome(OutcomeStatus.CONFIRMED, cleaned, key)

    async def execute_command(self, command: str, sender_id: str, adapter=None) -> Tuple[bool, str]:
        outcome = await self.execute_detailed(command, sender_id, adapter)
        return outcome.success, outcome.message

    async def execute_batch(self, commands, sender_id: str, adapter=None, policy="continue"):
        if policy not in ("abort", "continue") or not isinstance(commands, list) or not 1 <= len(commands) <= 20 or not all(isinstance(c, str) for c in commands):
            raise ValueError("Batch requires 1-20 commands and policy abort or continue")
        results = []
        aborted = False
        for command in commands:
            if aborted:
                results.append(RconOutcome(OutcomeStatus.SKIPPED, "未执行：批次已中止", self.server_identity(adapter)))
                continue
            outcome = await self.execute_detailed(command, sender_id, adapter)
            results.append(outcome)
            if policy == "abort" and not outcome.success:
                aborted = True
        return results

    def is_enabled(self) -> bool:
        return self.rcon_enabled

    def is_connected(self) -> bool:
        return self.rcon_connected
