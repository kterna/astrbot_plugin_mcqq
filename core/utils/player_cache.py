"""Thread-safe LRU & TTL cache for player list and server status queries."""

import time
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class PlayerListCache:
    """Thread-safe LRU Cache with TTL support for multi-server player queries."""
    def __init__(self, default_ttl: float = 15.0, max_capacity: int = 100):
        self.default_ttl = default_ttl
        self.max_capacity = max_capacity
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

    def get(self, server_name: str) -> Optional[List[str]]:
        now = time.monotonic()
        if server_name not in self._cache:
            return None
        entry = self._cache[server_name]
        if now >= entry.expires_at:
            # Expired: P0 no dirty reads
            del self._cache[server_name]
            return None
        self._cache.move_to_end(server_name)
        return list(entry.value)

    def set(self, server_name: str, players: List[str], ttl: Optional[float] = None):
        now = time.monotonic()
        effective_ttl = ttl if ttl is not None else self.default_ttl
        if server_name in self._cache:
            self._cache.move_to_end(server_name)
        elif len(self._cache) >= self.max_capacity:
            self._cache.popitem(last=False) # Evict oldest
        self._cache[server_name] = CacheEntry(
            value=list(players),
            expires_at=now + effective_ttl
        )

    def invalidate(self, server_name: str) -> bool:
        """Triggered upon player join/quit event to immediately purge stale cache."""
        if server_name in self._cache:
            del self._cache[server_name]
            return True
        return False

    def clear(self):
        self._cache.clear()
