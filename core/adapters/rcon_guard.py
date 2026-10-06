"""RCON Command Security Policy and Rate Limiter Guard."""

import time
import re
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass


class RateLimitExceeded(Exception):
    """Raised when an RCON command invocation exceeds token bucket limits."""
    pass


class BlacklistedCommandError(PermissionError):
    """Raised when an RCON command matches security blacklists."""
    pass


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""
    is_rate_limited: bool = False
    is_blacklisted: bool = False


class TokenBucket:
    """Thread-safe token bucket rate limiter for rate limiting command executions."""
    def __init__(self, capacity: float = 5.0, refill_rate: float = 5.0):
        self.capacity = capacity
        self.refill_rate = refill_rate # tokens per second
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def acquire(self, tokens: float = 1.0) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.last_refill = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class RconSecurityGuard:
    """
    RCON Security Guard implementing P0 command blacklists, whitelists,
    and token-bucket rate limiting per server.
    """
    DEFAULT_BLACKLIST: Set[str] = {
        "op", "deop", "stop", "ban", "ban-ip", "pardon", "pardon-ip",
        "whitelist off", "save-off", "reload", "restart", "kick"
    }

    READONLY_COMMANDS: Set[str] = {
        "list", "seed", "status", "tps", "ping", "help"
    }

    def __init__(
        self,
        blacklist: Optional[Set[str]] = None,
        rate_limit_per_sec: float = 5.0,
        enable_rate_limit: bool = True
    ):
        self.blacklist = set(blacklist) if blacklist is not None else set(self.DEFAULT_BLACKLIST)
        self.rate_limit_per_sec = rate_limit_per_sec
        self.enable_rate_limit = enable_rate_limit
        self._limiters: Dict[str, TokenBucket] = {}

    def _get_limiter(self, server_name: str) -> TokenBucket:
        if server_name not in self._limiters:
            self._limiters[server_name] = TokenBucket(
                capacity=self.rate_limit_per_sec,
                refill_rate=self.rate_limit_per_sec
            )
        return self._limiters[server_name]

    @staticmethod
    def normalize_command(command: str) -> str:
        """Strip leading slash and normalize spacing."""
        cmd = command.strip()
        if cmd.startswith("/"):
            cmd = cmd[1:].strip()
        return cmd

    def check_command(self, server_name: str, raw_command: str) -> GuardResult:
        normalized = self.normalize_command(raw_command)
        if not normalized:
            return GuardResult(allowed=False, reason="Empty command")

        root_cmd = normalized.split()[0].lower()

        # 1. P0 Security Blacklist Check
        for bl in self.blacklist:
            bl_norm = self.normalize_command(bl).lower()
            if normalized.lower() == bl_norm or normalized.lower().startswith(bl_norm + " ") or root_cmd == bl_norm:
                return GuardResult(
                    allowed=False,
                    reason=f"Security violation: command '{raw_command}' is blacklisted (P0)",
                    is_blacklisted=True
                )

        # 2. Rate Limiting Check (ReadOnly gets 0.2 token cost, others 1.0)
        if self.enable_rate_limit:
            cost = 0.2 if root_cmd in self.READONLY_COMMANDS else 1.0
            limiter = self._get_limiter(server_name)
            if not limiter.acquire(cost):
                return GuardResult(
                    allowed=False,
                    reason=f"Rate limit exceeded for server '{server_name}' (max {self.rate_limit_per_sec} ops/s)",
                    is_rate_limited=True
                )

        return GuardResult(allowed=True, reason="Command authorized")
