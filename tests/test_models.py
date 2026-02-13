"""Unit tests for core data models."""

from datetime import datetime, timezone

from shapely.geometry import box

from geofix.core.models import (
    AuditEntry,
    DetectedError,
    ErrorSeverity,
    FeatureMetadata,
    FixAction,
    FixResult,
    FixStrategy,
    FixTier,
)


class TestEnums:
    def test_fix_tier_values(self):
        assert FixTier.RULE_BASED.value == "rule_based"
        assert FixTier.LLM_REASONING.value == "llm_reasoning"
        assert FixTier.HUMAN_REVIEW.value == "human_review"

    def test_error_severity_values(self):
        assert ErrorSeverity.CRITICAL.value == "critical"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.LOW.value == "low"

    def test_fix_action_values(self):
        assert FixAction.APPLIED.value == "applied"
        assert FixAction.ROLLED_BACK.value == "rolled_back"
        assert FixAction.SKIPPED.value == "skipped"
        assert FixAction.PENDING_REVIEW.value == "pending_review"


class TestFeatureMetadata:
    def test_defaults(self):
        meta = FeatureMetadata(feature_id="feat_1")
        assert meta.source == "unknown"
        assert meta.accuracy_m == 10.0
        assert meta.confidence == 0.5
        assert meta.tags == {}

    def test_custom_values(self):
        meta = FeatureMetadata(
            feature_id="f1",
            source="survey",
            accuracy_m=1.5,
            confidence=0.9,
        )
        assert meta.source == "survey"
        assert meta.accuracy_m == 1.5


class TestDetectedError:
    def test_creation(self):
        geom = box(0, 0, 1, 1)
        error = DetectedError(
            error_id="e1",
            error_type="building_overlap",
            severity=ErrorSeverity.HIGH,
            geometry=geom,
        )
        assert error.error_id == "e1"
        assert error.error_type == "building_overlap"
        assert error.affected_features == []
        assert error.ovc_source == ""

    def test_with_affected_features(self):
        geom = box(0, 0, 1, 1)
        error = DetectedError(
            error_id="e2",
            error_type="duplicate_geometry",
            severity=ErrorSeverity.CRITICAL,
            geometry=geom,
            affected_features=["a", "b"],
        )
        assert len(error.affected_features) == 2


class TestFixStrategy:
    def test_creation(self, overlap_error):
        strategy = FixStrategy(
            error=overlap_error,
            fix_type="delete",
            tier=FixTier.RULE_BASED,
            confidence=0.95,
        )
        assert strategy.fix_type == "delete"
        assert strategy.confidence == 0.95
        assert strategy.reasoning == ""

    def test_with_reasoning(self, overlap_error):
        strategy = FixStrategy(
            error=overlap_error,
            fix_type="snap",
            tier=FixTier.LLM_REASONING,
            confidence=0.75,
            reasoning="LLM recommends snapping.",
        )
        assert "LLM" in strategy.reasoning


class TestFixResult:
    def test_successful_fix(self, overlap_error, sample_polygon):
        strategy = FixStrategy(
            error=overlap_error,
            fix_type="trim",
            tier=FixTier.RULE_BASED,
            confidence=0.90,
        )
        result = FixResult(
            strategy=strategy,
            success=True,
            original_geometry=sample_polygon,
            fixed_geometry=box(0, 0, 9, 9),
            validation_passed=True,
        )
        assert result.success
        assert result.validation_passed
        assert result.new_errors_introduced == 0
        assert isinstance(result.timestamp, datetime)

    def test_failed_fix(self, overlap_error, sample_polygon):
        strategy = FixStrategy(
            error=overlap_error,
            fix_type="merge",
            tier=FixTier.RULE_BASED,
            confidence=0.50,
        )
        result = FixResult(
            strategy=strategy,
            success=False,
            original_geometry=sample_polygon,
            fixed_geometry=None,
            validation_passed=False,
        )
        assert not result.success
        assert result.fixed_geometry is None
