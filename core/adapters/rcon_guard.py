"""Policy for commands sent over the shared RCON execution boundary."""

import math
import re
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Set


class RateLimitExceeded(Exception):
    """Compatibility exception for callers of the former guard helper."""


class BlacklistedCommandError(PermissionError):
    """Compatibility exception for callers of the former guard helper."""


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""
    is_rate_limited: bool = False
    is_blacklisted: bool = False
    command: str = ""


class TokenBucket:
    """A bucket owned by one server identity. All mutation holds its lock."""

    def __init__(self, capacity: float = 5.0, refill_rate: float = 5.0):
        self._validate(capacity)
        self._validate(refill_rate)
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.tokens = self.capacity
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    @staticmethod
    def _validate(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError("RCON rate and capacity must be finite positive numbers")

    def acquire(self, tokens: float = 1.0, rate: Optional[float] = None) -> bool:
        self._validate(tokens)
        with self._lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + max(0, now - self.last_refill) * self.refill_rate)
            self.last_refill = now
            if rate is not None and rate != self.refill_rate:
                self._validate(rate)
                self.refill_rate = float(rate)
                self.capacity = float(rate)
                self.tokens = min(self.tokens, self.capacity)
            if self.tokens < tokens:
                return False
            self.tokens -= tokens
            return True


class RconSecurityGuard:
    """Fail-closed command syntax and allowlist, followed by per-server limiting."""

    DEFAULT_BLACKLIST: Set[str] = {
        "op", "deop", "stop", "ban", "ban-ip", "pardon", "pardon-ip",
        "whitelist off", "save-off", "reload", "restart", "kick",
    }
    READONLY_COMMANDS: Set[str] = {"list", "seed", "status", "tps", "ping", "help"}
    READONLY_PHRASES: Set[str] = {"time query", "whitelist list"}
    DEFAULT_WRITES: Set[str] = {"say"}  # Legacy /rcon say compatibility.
    PLAYER_NAME = re.compile(r"[A-Za-z0-9_]{3,16}\Z")
    COMMAND_NAME = re.compile(r"[A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)?\Z")
    MAX_SERVERS = 128

    def __init__(self, blacklist: Optional[Set[str]] = None, rate_limit_per_sec: float = 5.0,
                 enable_rate_limit: bool = True):
        TokenBucket._validate(rate_limit_per_sec)
        if rate_limit_per_sec < 1:
            raise ValueError("RCON rate must be at least 1 to admit write commands")
        if not isinstance(enable_rate_limit, bool):
            raise ValueError("enable_rate_limit must be boolean")
        self.blacklist = set(blacklist) if blacklist is not None else set(self.DEFAULT_BLACKLIST)
        self.rate_limit_per_sec = float(rate_limit_per_sec)
        self.enable_rate_limit = enable_rate_limit
        self._limiters: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    @staticmethod
    def normalize_command(command: str) -> str:
        if not isinstance(command, str) or len(command) > 4096:
            raise ValueError("Invalid command text")
        if any(ch.isspace() and ch != " " for ch in command) or any(ord(ch) < 32 or ord(ch) == 127 for ch in command):
            raise ValueError("Only single-line commands with ASCII spaces are accepted")
        cmd = command.strip(" ")
        if cmd.startswith("/"):
            cmd = cmd[1:].strip(" ")
        if not cmd or cmd.startswith("/"):
            raise ValueError("Empty or ambiguous command")
        return cmd

    @classmethod
    def validate_write_commands(cls, commands) -> Set[str]:
        if commands is None:
            return set()
        if not isinstance(commands, list) or len(commands) > 64:
            raise ValueError("rcon_allowed_commands must be a list of at most 64 command names")
        result = set()
        for entry in commands:
            normalized = cls.normalize_command(entry)
            parts = normalized.lower().split(" ")
            if len(parts) > 2 or not all(parts) or not cls.COMMAND_NAME.fullmatch(parts[0]) or (len(parts) == 2 and not cls.COMMAND_NAME.fullmatch(parts[1])):
                raise ValueError("Invalid rcon_allowed_commands entry")
            root = parts[0].split(":")[-1]
            if root in {item for item in cls.DEFAULT_BLACKLIST if " " not in item} or normalized.lower() in cls.DEFAULT_BLACKLIST:
                raise ValueError("A protected RCON command cannot be allowed")
            result.add(normalized.lower())
        return result

    def _get_limiter(self, server_name: str, rate: float) -> Optional[TokenBucket]:
        with self._lock:
            if server_name not in self._limiters:
                if len(self._limiters) >= self.MAX_SERVERS:
                    return None
                self._limiters[server_name] = TokenBucket(rate, rate)
            return self._limiters[server_name]

    def check_command(self, server_name: str, raw_command: str,
                      allowed_write_commands=None, rate_limit_per_sec: Optional[float] = None) -> GuardResult:
        try:
            normalized = self.normalize_command(raw_command)
            allowed_writes = self.validate_write_commands(allowed_write_commands)
            rate = self.rate_limit_per_sec if rate_limit_per_sec is None else rate_limit_per_sec
            TokenBucket._validate(rate)
            if rate < 1:
                raise ValueError("RCON rate must be at least 1")
        except ValueError as exc:
            return GuardResult(False, str(exc))

        parts = normalized.lower().split(" ")
        parts = [part for part in parts if part]
        root = parts[0]
        if not self.COMMAND_NAME.fullmatch(root):
            return GuardResult(False, "Invalid command name")
        namespace, _, base = root.rpartition(":")
        effective_root = base if namespace else root
        effective = [effective_root, *parts[1:]]
        if any(effective[:len(blocked.split(" "))] == blocked.split(" ") for blocked in self.blacklist):
            return GuardResult(False, "Protected command", is_blacklisted=True)
        if namespace and namespace != "minecraft" and not any(
            parts[:len(write.split(" "))] == write.split(" ") for write in allowed_writes
        ):
            return GuardResult(False, "Namespace is not configured")
        is_read = (effective_root in self.READONLY_COMMANDS or
                   any(effective[:len(phrase.split(" "))] == phrase.split(" ") for phrase in self.READONLY_PHRASES))
        is_write = any(parts[:len(write.split(" "))] == write.split(" ") or
                       (namespace == "minecraft" and effective[:len(write.split(" "))] == write.split(" "))
                       for write in self.DEFAULT_WRITES | allowed_writes)
        if effective[:2] in (["whitelist", "add"], ["whitelist", "remove"]):
            if len(effective) != 3 or not self.PLAYER_NAME.fullmatch(effective[2]):
                return GuardResult(False, "Invalid player name or whitelist syntax")
        if not (is_read or is_write):
            return GuardResult(False, "Command is not allowed")
        if self.enable_rate_limit:
            limiter = self._get_limiter(server_name, rate)
            if limiter is None or not limiter.acquire(0.2 if is_read else 1.0, rate):
                return GuardResult(False, "RCON rate limit exceeded", is_rate_limited=True)
        return GuardResult(True, "Command authorized", command=normalized)
