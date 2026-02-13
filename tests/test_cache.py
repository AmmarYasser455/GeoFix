"""Unit tests for the response cache."""

import time

import pytest

from geofix.core.cache import ResponseCache


@pytest.fixture
def cache():
    return ResponseCache(max_size=5, ttl_seconds=2)


class TestResponseCache:
    def test_put_and_get(self, cache):
        cache.put("hello", "Hi there!")
        assert cache.get("hello") == "Hi there!"

    def test_cache_miss(self, cache):
        assert cache.get("unknown query") is None

    def test_normalization(self, cache):
        cache.put("Hello World!", "response")
        assert cache.get("  hello   world  ") == "response"
        assert cache.get("HELLO WORLD") == "response"

    def test_ttl_expiration(self, cache):
        cache.put("expire_me", "old response")
        assert cache.get("expire_me") == "old response"

        time.sleep(2.1)
        assert cache.get("expire_me") is None

    def test_max_size_eviction(self, cache):
        for i in range(6):
            cache.put(f"query_{i}", f"response_{i}")

        assert cache.size == 5

    def test_invalidate(self, cache):
        cache.put("a", "1")
        cache.put("b", "2")
        assert cache.size == 2

        cache.invalidate()
        assert cache.size == 0
        assert cache.get("a") is None

    def test_size_property(self, cache):
        assert cache.size == 0
        cache.put("q", "r")
        assert cache.size == 1
