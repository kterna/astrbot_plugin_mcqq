"""Unit tests for PlayerListCache."""

import pytest
import time
from core.utils.player_cache import PlayerListCache


def test_player_cache_ttl_and_invalidation():
    cache = PlayerListCache(default_ttl=0.2, max_capacity=2)
    cache.set("srv1", ["Alice", "Bob"])

    # Immediate hit
    res = cache.get("srv1")
    assert res == ["Alice", "Bob"]

    # Invalidation on player join
    cache.invalidate("srv1")
    assert cache.get("srv1") is None

    # Expiry after TTL
    cache.set("srv2", ["Charlie"], ttl=0.1)
    time.sleep(0.12)
    assert cache.get("srv2") is None
