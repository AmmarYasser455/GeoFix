"""Rule-based decision logic — Tier 1 of the decision engine.

Each rule is a pure function:
    (error, metadata) → Optional[FixStrategy]

Rules are tried in priority order. The first rule that fires wins.
If no rule fires, the error is escalated to Tier 2 (LLM reasoning).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from geofix.core.models import (
    DetectedError,
    FeatureMetadata,
    FixStrategy,
    FixTier,
)
from geofix.decision.confidence import (
    accuracy_difference,
    combined_confidence,
    confidence_from_accuracy_gap,
    confidence_from_overlap_ratio,
)

logger = logging.getLogger("geofix.decision.rules")

# Type alias for a rule function
RuleFunc = Callable[
    [DetectedError, dict[str, FeatureMetadata]],
    Optional[FixStrategy],
]


@dataclass
class Rule:
    """A named rule with a priority."""

    name: str
    priority: int             # lower = higher priority
    func: RuleFunc


class RuleSet:
    """Ordered collection of deterministic rules.

    Usage::

        rules = RuleSet()
        rules.add("duplicate_same_source", 10, rule_duplicate_same_source)
        strategy = rules.evaluate(error, metadata)
    """

    def __init__(self) -> None:
        self._rules: list[Rule] = []

    def add(self, name: str, priority: int, func: RuleFunc) -> None:
        self._rules.append(Rule(name=name, priority=priority, func=func))
        self._rules.sort(key=lambda r: r.priority)

    def evaluate(
        self,
        error: DetectedError,
        metadata: dict[str, FeatureMetadata],
    ) -> Optional[FixStrategy]:
        """Try each rule; return the first strategy produced, or None."""
        for rule in self._rules:
            try:
                strategy = rule.func(error, metadata)
                if strategy is not None:
                    logger.info(
                        "Rule '%s' fired for error %s → %s (conf=%.2f)",
                        rule.name,
                        error.error_id,
                        strategy.fix_type,
                        strategy.confidence,
                    )
                    return strategy
            except Exception as exc:
                logger.warning("Rule '%s' raised: %s", rule.name, exc)
        return None


# ─── Built-in Rules ─────────────────────────────────────────────────────


def _get_meta(
    meta: dict[str, FeatureMetadata], fid: str
) -> FeatureMetadata:
    return meta.get(fid, FeatureMetadata(feature_id=fid))


# Rule 1: Exact/near duplicate from same source → delete lower confidence
def rule_duplicate_same_source(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    if error.error_type not in ("building_overlap", "duplicate_geometry"):
        return None
    ratio = error.properties.get("overlap_ratio", 0)
    if ratio < 0.98:
        return None
    if len(error.affected_features) < 2:
        return None
    a, b = error.affected_features[0], error.affected_features[1]
    ma, mb = _get_meta(meta, a), _get_meta(meta, b)
    if ma.source != mb.source:
        return None
    return FixStrategy(
        error=error,
        fix_type="delete",
        tier=FixTier.RULE_BASED,
        confidence=0.95,
        parameters={"delete_feature": b if ma.confidence >= mb.confidence else a},
        reasoning=f"Duplicate (ratio={ratio:.2f}) from same source '{ma.source}'",
    )


# Rule 2: Exact duplicate different source → keep higher accuracy
def rule_duplicate_diff_source(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    if error.error_type not in ("building_overlap", "duplicate_geometry"):
        return None
    ratio = error.properties.get("overlap_ratio", 0)
    if ratio < 0.98:
        return None
    if len(error.affected_features) < 2:
        return None
    a, b = error.affected_features[0], error.affected_features[1]
    ma, mb = _get_meta(meta, a), _get_meta(meta, b)
    if ma.source == mb.source:
        return None
    keep = a if ma.accuracy_m <= mb.accuracy_m else b
    delete = b if keep == a else a
    return FixStrategy(
        error=error,
        fix_type="delete",
        tier=FixTier.RULE_BASED,
        confidence=0.85,
        parameters={"delete_feature": delete, "keep_feature": keep},
        reasoning=(
            f"Duplicate from different sources "
            f"('{ma.source}' vs '{mb.source}'). "
            f"Keeping higher accuracy ({min(ma.accuracy_m, mb.accuracy_m):.1f}m)."
        ),
    )


# Rule 3: Partial overlap with large accuracy difference → snap
def rule_partial_overlap_accuracy(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    if error.error_type != "building_overlap":
        return None
    ratio = error.properties.get("overlap_ratio", 0)
    if ratio >= 0.98 or ratio < 0.30:
        return None
    if len(error.affected_features) < 2:
        return None
    a, b = error.affected_features[0], error.affected_features[1]
    ma, mb = _get_meta(meta, a), _get_meta(meta, b)
    gap = accuracy_difference(ma, mb)
    if gap <= 5.0:
        return None  # too close — escalate to LLM
    conf = combined_confidence(
        confidence_from_overlap_ratio(ratio),
        confidence_from_accuracy_gap(gap),
    )
    snap_target = a if ma.accuracy_m > mb.accuracy_m else b
    reference = b if snap_target == a else a
    return FixStrategy(
        error=error,
        fix_type="snap",
        tier=FixTier.RULE_BASED,
        confidence=conf,
        parameters={"snap_feature": snap_target, "reference_feature": reference},
        reasoning=(
            f"Partial overlap (ratio={ratio:.2f}) with accuracy gap "
            f"{gap:.1f}m. Snap less accurate feature."
        ),
    )


# Rule 5: Sliver overlap with tiny area → auto-trim
def rule_sliver_overlap(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    if error.error_type != "building_overlap":
        return None
    otype = error.properties.get("overlap_type", "")
    if otype != "sliver":
        return None
    area = error.properties.get("inter_area_m2", float("inf"))
    if area >= 1.0:
        return None
    return FixStrategy(
        error=error,
        fix_type="trim",
        tier=FixTier.RULE_BASED,
        confidence=0.90,
        reasoning=f"Sliver overlap ({area:.2f} m²) — auto-trimming.",
    )


# Rule 6: Small building-on-road conflict → snap off road
def rule_small_road_conflict(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    if error.error_type != "building_on_road":
        return None
    area = error.properties.get("inter_area_m2", float("inf"))
    if area >= 2.0:
        return None
    return FixStrategy(
        error=error,
        fix_type="nudge",
        tier=FixTier.RULE_BASED,
        confidence=0.85,
        parameters={"min_distance_m": 3.0},
        reasoning=f"Small road conflict ({area:.2f} m²) — nudging building off road.",
    )


# Rule 8: Invalid geometry → make_valid
def rule_invalid_geometry(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    if error.error_type != "invalid_geometry":
        return None
    return FixStrategy(
        error=error,
        fix_type="make_valid",
        tier=FixTier.RULE_BASED,
        confidence=0.95,
        reasoning="Self-intersecting / invalid geometry — applying make_valid().",
    )


# Rule 9: Unreasonably small building → flag for review
def rule_tiny_building(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    if error.error_type != "unreasonable_area":
        return None
    area = error.properties.get("area_m2", float("inf"))
    if area >= 1.0:
        return None
    return FixStrategy(
        error=error,
        fix_type="delete",
        tier=FixTier.RULE_BASED,
        confidence=0.70,
        reasoning=f"Unreasonably small building ({area:.2f} m²) — flagged for deletion.",
    )


# Rule 11: Very low compactness → simplify
def rule_low_compactness(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    if error.error_type != "low_compactness":
        return None
    compactness = error.properties.get("compactness", 1.0)
    if compactness >= 0.05:
        return None
    return FixStrategy(
        error=error,
        fix_type="simplify",
        tier=FixTier.RULE_BASED,
        confidence=0.75,
        parameters={"tolerance": 0.5, "preserve_topology": True},
        reasoning=f"Extremely low compactness ({compactness:.3f}) — simplifying.",
    )


# Rule 12: Boundary overlap with small encroachment → clip
def rule_boundary_clip(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    if error.error_type != "building_boundary_overlap":
        return None
    return FixStrategy(
        error=error,
        fix_type="clip",
        tier=FixTier.RULE_BASED,
        confidence=0.85,
        reasoning="Building extends beyond boundary — clipping to boundary.",
    )


# Rule 14: Exact duplicate geometry → delete
def rule_exact_duplicate(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    if error.error_type != "duplicate_geometry":
        return None
    if len(error.affected_features) < 2:
        return None
    return FixStrategy(
        error=error,
        fix_type="delete",
        tier=FixTier.RULE_BASED,
        confidence=0.95,
        parameters={"delete_feature": error.affected_features[1]},
        reasoning="Exact duplicate geometry (WKB match) — deleting duplicate.",
    )


# ─── Fallback rules for OVC per-building errors ─────────────────────────
# The OVC errors layer stores one building per row with error_type and
# error_class columns.  These rules handle that format when the more
# specific pairwise rules above don't match.


def rule_overlap_by_class(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    """Handle OVC building_overlap errors using the error_class field."""
    if error.error_type != "building_overlap":
        return None

    error_class = error.properties.get("error_class", "")

    if error_class == "duplicate":
        return FixStrategy(
            error=error,
            fix_type="delete",
            tier=FixTier.RULE_BASED,
            confidence=0.80,
            parameters={"delete_feature": error.affected_features[0] if error.affected_features else "unknown"},
            reasoning="Duplicate building (OVC class=duplicate) — flagged for deletion.",
        )
    elif error_class == "sliver":
        return FixStrategy(
            error=error,
            fix_type="trim",
            tier=FixTier.RULE_BASED,
            confidence=0.85,
            reasoning="Sliver overlap (OVC class=sliver) — auto-trimming overlap area.",
        )
    elif error_class == "partial":
        return FixStrategy(
            error=error,
            fix_type="snap",
            tier=FixTier.RULE_BASED,
            confidence=0.80,
            reasoning="Partial overlap (OVC class=partial) — snapping to reduce overlap.",
        )

    return None


def rule_road_conflict_fallback(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    """Handle OVC building_on_road errors."""
    if error.error_type != "building_on_road":
        return None
    return FixStrategy(
        error=error,
        fix_type="nudge",
        tier=FixTier.RULE_BASED,
        confidence=0.75,
        parameters={"min_distance_m": 3.0},
        reasoning="Building conflicts with road — nudging off road buffer.",
    )


def rule_outside_boundary(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    """Handle OVC outside_boundary errors."""
    if error.error_type != "outside_boundary":
        return None
    return FixStrategy(
        error=error,
        fix_type="flag",
        tier=FixTier.RULE_BASED,
        confidence=0.80,
        reasoning="Building is outside the study area boundary — flagged for review.",
    )


def rule_boundary_overlap_fallback(
    error: DetectedError, meta: dict[str, FeatureMetadata]
) -> Optional[FixStrategy]:
    """Handle OVC building_boundary_overlap errors."""
    if error.error_type != "building_boundary_overlap":
        return None
    return FixStrategy(
        error=error,
        fix_type="clip",
        tier=FixTier.RULE_BASED,
        confidence=0.80,
        reasoning="Building extends beyond boundary — clipping to boundary.",
    )


# ─── Factory ────────────────────────────────────────────────────────────


def build_default_ruleset() -> RuleSet:
    """Create a RuleSet pre-loaded with all built-in rules."""
    rs = RuleSet()
    rules = [
        # High-priority: specific pairwise rules (need full metadata)
        ("exact_duplicate", 10, rule_exact_duplicate),
        ("duplicate_same_source", 20, rule_duplicate_same_source),
        ("duplicate_diff_source", 30, rule_duplicate_diff_source),
        ("invalid_geometry", 40, rule_invalid_geometry),
        ("sliver_overlap", 50, rule_sliver_overlap),
        ("partial_overlap_accuracy", 60, rule_partial_overlap_accuracy),
        ("small_road_conflict", 70, rule_small_road_conflict),
        ("tiny_building", 80, rule_tiny_building),
        ("low_compactness", 90, rule_low_compactness),
        ("boundary_clip", 100, rule_boundary_clip),
        # Lower-priority: fallback rules for OVC per-building errors
        ("overlap_by_class", 200, rule_overlap_by_class),
        ("road_conflict_fallback", 210, rule_road_conflict_fallback),
        ("outside_boundary", 220, rule_outside_boundary),
        ("boundary_overlap_fallback", 230, rule_boundary_overlap_fallback),
    ]
    for name, priority, func in rules:
        rs.add(name, priority, func)
    return rs
