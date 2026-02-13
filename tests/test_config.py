"""Unit tests for configuration dataclasses."""

import pytest
from dataclasses import FrozenInstanceError
from pathlib import Path

from geofix.core.config import (
    CacheConfig,
    ConversationConfig,
    DecisionThresholds,
    DEFAULT_CONFIG,
    GeoFixConfig,
    GeometryThresholds,
    LLMConfig,
    RouterConfig,
)


class TestDecisionThresholds:
    def test_defaults(self):
        t = DecisionThresholds()
        assert t.auto_fix_min == 0.80
        assert t.llm_fix_min == 0.60
        assert t.human_review_below == 0.60

    def test_frozen(self):
        t = DecisionThresholds()
        with pytest.raises(FrozenInstanceError):
            t.auto_fix_min = 0.5


class TestLLMConfig:
    def test_defaults(self):
        c = LLMConfig()
        assert c.provider == "ollama"
        assert c.model == "llama3.2"
        assert c.temperature == 0.1
        assert c.max_tokens == 2048

    def test_frozen(self):
        c = LLMConfig()
        with pytest.raises(FrozenInstanceError):
            c.model = "other"


class TestGeometryThresholds:
    def test_defaults(self):
        g = GeometryThresholds()
        assert g.sliver_max_area_m2 == 1.0
        assert g.duplicate_ratio_min == 0.98


class TestCacheConfig:
    def test_defaults(self):
        c = CacheConfig()
        assert c.max_size == 256
        assert c.ttl_seconds == 3600


class TestConversationConfig:
    def test_defaults(self):
        c = ConversationConfig()
        assert c.db_path == Path("geofix_conversations.db")
        assert c.max_history_messages == 50


class TestRouterConfig:
    def test_defaults(self):
        r = RouterConfig()
        assert r.auto_route is True
        assert r.simple_model == "llama3.2"
        assert r.complex_model == "deepseek-r1:14b"


class TestGeoFixConfig:
    def test_default_config(self):
        c = DEFAULT_CONFIG
        assert isinstance(c.decision, DecisionThresholds)
        assert isinstance(c.llm, LLMConfig)
        assert isinstance(c.cache, CacheConfig)
        assert isinstance(c.conversations, ConversationConfig)
        assert isinstance(c.router, RouterConfig)
        assert c.audit_db_path == Path("geofix_audit.db")

    def test_frozen(self):
        with pytest.raises(FrozenInstanceError):
            DEFAULT_CONFIG.audit_db_path = Path("other.db")
