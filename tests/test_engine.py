"""Unit tests for the three-tier decision engine."""


import pytest
from shapely.geometry import box

from geofix.core.config import DEFAULT_CONFIG
from geofix.core.models import (
    DetectedError,
    ErrorSeverity,
    FeatureMetadata,
    FixStrategy,
    FixTier,
)
from geofix.decision.engine import DecisionEngine


@pytest.fixture
def engine():
    return DecisionEngine(config=DEFAULT_CONFIG)


class TestDecisionEngine:
    def test_tier1_auto_fix(self, engine):
        """Exact duplicate should be auto-fixed by rules (Tier 1)."""
        error = DetectedError(
            error_id="t1",
            error_type="duplicate_geometry",
            severity=ErrorSeverity.CRITICAL,
            geometry=box(0, 0, 10, 10),
            affected_features=["a", "b"],
        )
        strategy = engine.decide(error, {})
        assert strategy.tier == FixTier.RULE_BASED
        assert strategy.fix_type == "delete"
        assert strategy.confidence >= DEFAULT_CONFIG.decision.auto_fix_min

    def test_rules_only_mode(self, engine):
        """rules_only=True should skip LLM tier entirely."""
        error = DetectedError(
            error_id="t2",
            error_type="building_overlap",
            severity=ErrorSeverity.HIGH,
            geometry=box(0, 0, 5, 5),
            affected_features=["a", "b"],
            properties={"overlap_ratio": 0.5},
        )
        meta = {
            "a": FeatureMetadata(feature_id="a", accuracy_m=5.0),
            "b": FeatureMetadata(feature_id="b", accuracy_m=5.0),
        }
        strategy = engine.decide(error, meta, rules_only=True)
        assert strategy.tier in (FixTier.RULE_BASED, FixTier.HUMAN_REVIEW)

    def test_fallback_to_human_review(self, engine):
        """An error with no matching rule and no LLM should fall through to Tier 3."""
        error = DetectedError(
            error_id="t3",
            error_type="unknown_error_type",
            severity=ErrorSeverity.MEDIUM,
            geometry=box(0, 0, 1, 1),
        )
        strategy = engine.decide(error, {}, rules_only=True)
        assert strategy.tier == FixTier.HUMAN_REVIEW
        assert strategy.fix_type == "human_review"

    def test_invalid_geometry_auto_fixed(self, engine, invalid_geom_error):
        """Invalid geometry should be auto-fixed with make_valid."""
        strategy = engine.decide(invalid_geom_error, {})
        assert strategy.fix_type == "make_valid"
        assert strategy.tier == FixTier.RULE_BASED

    def test_decide_batch(self, engine):
        """Batch decide should return one strategy per error."""
        errors = [
            DetectedError(
                error_id=f"b{i}",
                error_type="invalid_geometry",
                severity=ErrorSeverity.HIGH,
                geometry=box(0, 0, i + 1, i + 1),
            )
            for i in range(3)
        ]
        strategies = engine.decide_batch(errors, {})
        assert len(strategies) == 3
        for s in strategies:
            assert isinstance(s, FixStrategy)
