"""Confidence scoring utilities for the decision engine."""

from __future__ import annotations

from geofix.core.models import DetectedError, FeatureMetadata


def accuracy_difference(
    meta_a: FeatureMetadata, meta_b: FeatureMetadata
) -> float:
    """Absolute difference in positional accuracy (meters)."""
    return abs(meta_a.accuracy_m - meta_b.accuracy_m)


def confidence_from_accuracy_gap(gap: float) -> float:
    """Higher gap → more confident we know which feature to keep.

    Returns a value in [0.5, 0.95].
    """
    if gap >= 10.0:
        return 0.95
    if gap >= 5.0:
        return 0.85
    if gap >= 2.0:
        return 0.75
    if gap >= 1.0:
        return 0.65
    return 0.55


def confidence_from_overlap_ratio(ratio: float) -> float:
    """Higher overlap ratio → more confident about the fix type.

    Returns a value in [0.5, 0.95].
    """
    if ratio >= 0.98:
        return 0.95
    if ratio >= 0.80:
        return 0.85
    if ratio >= 0.60:
        return 0.75
    if ratio >= 0.40:
        return 0.65
    return 0.55


def combined_confidence(*scores: float) -> float:
    """Combine multiple confidence scores as their geometric mean."""
    if not scores:
        return 0.0
    product = 1.0
    for s in scores:
        product *= max(s, 0.01)
    return product ** (1.0 / len(scores))
