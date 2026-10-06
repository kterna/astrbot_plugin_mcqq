"""Unit tests for RconSecurityGuard and TokenBucket."""

import pytest
import time
from core.adapters.rcon_guard import RconSecurityGuard, TokenBucket, GuardResult


def test_token_bucket_acquire():
    bucket = TokenBucket(capacity=2.0, refill_rate=10.0)
    assert bucket.acquire(1.0) is True
    assert bucket.acquire(1.0) is True
    assert bucket.acquire(1.0) is False # Depleted
    time.sleep(0.12)
    assert bucket.acquire(1.0) is True # Refilled


def test_rcon_guard_blacklisted_commands():
    guard = RconSecurityGuard()

    # Direct blacklist
    res = guard.check_command("srv1", "stop")
    assert res.allowed is False
    assert res.is_blacklisted is True

    # Leading slash bypass attempt
    res = guard.check_command("srv1", "/op notch")
    assert res.allowed is False
    assert res.is_blacklisted is True

    # Case insensitive bypass attempt
    res = guard.check_command("srv1", "/BAN player123")
    assert res.allowed is False
    assert res.is_blacklisted is True

    # Safe command
    res = guard.check_command("srv1", "say Hello Minecraft!")
    assert res.allowed is True
    assert res.is_blacklisted is False


def test_rcon_guard_rate_limiting():
    guard = RconSecurityGuard(rate_limit_per_sec=2.0)
    # Burst 2 allowed
    assert guard.check_command("srv1", "say 1").allowed is True
    assert guard.check_command("srv1", "say 2").allowed is True
    # 3rd should be rate limited
    res = guard.check_command("srv1", "say 3")
    assert res.allowed is False
    assert res.is_rate_limited is True
