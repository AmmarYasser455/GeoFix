"""Unit tests for the rule-based decision system."""

import pytest
from shapely.geometry import box

from geofix.core.models import (
    DetectedError,
    ErrorSeverity,
    FeatureMetadata,
    FixTier,
)
from geofix.decision.rules import (
    RuleSet,
    build_default_ruleset,
    rule_boundary_clip,
    rule_duplicate_diff_source,
    rule_duplicate_same_source,
    rule_exact_duplicate,
    rule_invalid_geometry,
    rule_sliver_overlap,
    rule_small_road_conflict,
    rule_tiny_building,
)


class TestRuleSet:
    def test_empty_ruleset(self, overlap_error, sample_metadata):
        rs = RuleSet()
        assert rs.evaluate(overlap_error, sample_metadata) is None

    def test_priority_ordering(self, overlap_error, sample_metadata):
        rs = RuleSet()
        called = []

        def rule_a(err, meta):
            called.append("a")
            return None

        def rule_b(err, meta):
            called.append("b")
            return None

        rs.add("rule_b", 20, rule_b)
        rs.add("rule_a", 10, rule_a)
        rs.evaluate(overlap_error, sample_metadata)
        assert called == ["a", "b"]

    def test_default_ruleset_has_rules(self):
        rs = build_default_ruleset()
        assert len(rs._rules) > 0


class TestDuplicateRules:
    def test_same_source_duplicate(self):
        geom = box(0, 0, 10, 10)
        error = DetectedError(
            error_id="e1",
            error_type="building_overlap",
            severity=ErrorSeverity.HIGH,
            geometry=geom,
            affected_features=["a", "b"],
            properties={"overlap_ratio": 0.99},
        )
        meta = {
            "a": FeatureMetadata(feature_id="a", source="osm", confidence=0.9),
            "b": FeatureMetadata(feature_id="b", source="osm", confidence=0.5),
        }
        result = rule_duplicate_same_source(error, meta)
        assert result is not None
        assert result.fix_type == "delete"
        assert result.tier == FixTier.RULE_BASED
        assert result.parameters["delete_feature"] == "b"

    def test_same_source_low_ratio_skips(self):
        geom = box(0, 0, 10, 10)
        error = DetectedError(
            error_id="e1",
            error_type="building_overlap",
            severity=ErrorSeverity.HIGH,
            geometry=geom,
            affected_features=["a", "b"],
            properties={"overlap_ratio": 0.5},
        )
        meta = {
            "a": FeatureMetadata(feature_id="a", source="osm"),
            "b": FeatureMetadata(feature_id="b", source="osm"),
        }
        assert rule_duplicate_same_source(error, meta) is None

    def test_diff_source_duplicate(self):
        geom = box(0, 0, 10, 10)
        error = DetectedError(
            error_id="e2",
            error_type="building_overlap",
            severity=ErrorSeverity.HIGH,
            geometry=geom,
            affected_features=["a", "b"],
            properties={"overlap_ratio": 0.99},
        )
        meta = {
            "a": FeatureMetadata(feature_id="a", source="osm", accuracy_m=2.0),
            "b": FeatureMetadata(feature_id="b", source="survey", accuracy_m=10.0),
        }
        result = rule_duplicate_diff_source(error, meta)
        assert result is not None
        assert result.fix_type == "delete"
        assert result.parameters["delete_feature"] == "b"


class TestExactDuplicate:
    def test_fires_on_duplicate(self):
        geom = box(0, 0, 5, 5)
        error = DetectedError(
            error_id="e3",
            error_type="duplicate_geometry",
            severity=ErrorSeverity.CRITICAL,
            geometry=geom,
            affected_features=["x", "y"],
        )
        result = rule_exact_duplicate(error, {})
        assert result is not None
        assert result.fix_type == "delete"
        assert result.confidence == 0.95

    def test_skips_non_duplicate(self):
        geom = box(0, 0, 5, 5)
        error = DetectedError(
            error_id="e4",
            error_type="building_overlap",
            severity=ErrorSeverity.HIGH,
            geometry=geom,
            affected_features=["x", "y"],
        )
        assert rule_exact_duplicate(error, {}) is None


class TestInvalidGeometry:
    def test_fires(self, invalid_geom_error):
        result = rule_invalid_geometry(invalid_geom_error, {})
        assert result is not None
        assert result.fix_type == "make_valid"
        assert result.confidence == 0.95

    def test_skips_other_types(self, overlap_error):
        assert rule_invalid_geometry(overlap_error, {}) is None


class TestSliverOverlap:
    def test_fires_on_sliver(self):
        geom = box(0, 0, 0.1, 0.1)
        error = DetectedError(
            error_id="e5",
            error_type="building_overlap",
            severity=ErrorSeverity.LOW,
            geometry=geom,
            properties={"overlap_type": "sliver", "inter_area_m2": 0.5},
        )
        result = rule_sliver_overlap(error, {})
        assert result is not None
        assert result.fix_type == "trim"

    def test_skips_large_sliver(self):
        geom = box(0, 0, 5, 5)
        error = DetectedError(
            error_id="e6",
            error_type="building_overlap",
            severity=ErrorSeverity.HIGH,
            geometry=geom,
            properties={"overlap_type": "sliver", "inter_area_m2": 5.0},
        )
        assert rule_sliver_overlap(error, {}) is None


class TestSmallRoadConflict:
    def test_fires(self):
        geom = box(0, 0, 1, 1)
        error = DetectedError(
            error_id="e7",
            error_type="building_on_road",
            severity=ErrorSeverity.HIGH,
            geometry=geom,
            properties={"inter_area_m2": 1.0},
        )
        result = rule_small_road_conflict(error, {})
        assert result is not None
        assert result.fix_type == "nudge"


class TestTinyBuilding:
    def test_fires(self):
        geom = box(0, 0, 0.1, 0.1)
        error = DetectedError(
            error_id="e8",
            error_type="unreasonable_area",
            severity=ErrorSeverity.MEDIUM,
            geometry=geom,
            properties={"area_m2": 0.5},
        )
        result = rule_tiny_building(error, {})
        assert result is not None
        assert result.fix_type == "delete"


class TestBoundaryClip:
    def test_fires(self):
        geom = box(0, 0, 10, 10)
        error = DetectedError(
            error_id="e9",
            error_type="building_boundary_overlap",
            severity=ErrorSeverity.MEDIUM,
            geometry=geom,
        )
        result = rule_boundary_clip(error, {})
        assert result is not None
        assert result.fix_type == "clip"
