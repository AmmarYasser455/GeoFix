"""Response cache for frequently asked queries.

Uses an LRU dict with TTL expiration to avoid re-processing
identical or near-identical queries.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Optional

logger = logging.getLogger("geofix.core.cache")


class ResponseCache:
    """In-memory LRU cache with TTL for AI responses."""

    def __init__(self, max_size: int = 256, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[str, float]] = {}

    @staticmethod
    def _normalize(query: str) -> str:
        """Normalize query for consistent cache keys."""
        text = query.lower().strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^\w\s]", "", text)
        return text

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def get(self, query: str) -> Optional[str]:
        """Look up a cached response. Returns None on miss."""
        key = self._hash(self._normalize(query))
        entry = self._cache.get(key)
        if entry is None:
            return None
        response, ts = entry
        if time.time() - ts > self.ttl:
            del self._cache[key]
            return None
        logger.debug("Cache hit for query: %s", query[:40])
        return response

    def put(self, query: str, response: str) -> None:
        """Store a response in the cache."""
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        key = self._hash(self._normalize(query))
        self._cache[key] = (response, time.time())

    def invalidate(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()
        logger.info("Response cache cleared")

    @property
    def size(self) -> int:
        return len(self._cache)
