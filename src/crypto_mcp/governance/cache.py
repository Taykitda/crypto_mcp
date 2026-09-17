"""Multi-tier in-memory cache with Fresh TTL and Stale Fallback buffer."""

import time
from typing import Any, Optional, Tuple


class CacheEntry:
    def __init__(self, value: Any, fresh_ttl: float, stale_ttl: float):
        self.value = value
        self.created_at = time.time()
        self.fresh_ttl = fresh_ttl
        self.stale_ttl = stale_ttl

    @property
    def age(self) -> float:
        return time.time() - self.created_at

    @property
    def is_fresh(self) -> bool:
        return self.age <= self.fresh_ttl

    @property
    def is_stale_valid(self) -> bool:
        return self.age <= self.stale_ttl


class MemoryCache:
    """Thread-safe and async-friendly in-memory cache with stale fallback support."""

    def __init__(self, default_fresh_ttl: float = 10.0, default_stale_ttl: float = 300.0):
        self.default_fresh_ttl = default_fresh_ttl
        self.default_stale_ttl = default_stale_ttl
        self._store: dict[str, CacheEntry] = {}

    def set(
        self,
        key: str,
        value: Any,
        fresh_ttl: Optional[float] = None,
        stale_ttl: Optional[float] = None,
    ) -> None:
        """Store an entry in cache."""
        f_ttl = fresh_ttl if fresh_ttl is not None else self.default_fresh_ttl
        s_ttl = stale_ttl if stale_ttl is not None else self.default_stale_ttl
        self._store[key] = CacheEntry(value=value, fresh_ttl=f_ttl, stale_ttl=s_ttl)

    def get(self, key: str, allow_stale: bool = False) -> Tuple[Optional[Any], bool, Optional[int]]:
        """Retrieve an entry.
        
        Returns:
            (value, is_stale, age_seconds)
            If not found or fully expired, returns (None, False, None).
        """
        entry = self._store.get(key)
        if entry is None:
            return None, False, None

        age_sec = int(entry.age)
        if entry.is_fresh:
            return entry.value, False, age_sec

        if allow_stale and entry.is_stale_valid:
            return entry.value, True, age_sec

        # Stale expired or stale not allowed
        return None, False, None

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
