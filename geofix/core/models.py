"""Core data models for the GeoFix pipeline.

Defines the data structures that flow through the system:
  Input files → DetectedError → FixStrategy → FixResult → AuditEntry
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from shapely.geometry.base import BaseGeometry

# ── Enums ───────────────────────────────────────────────────────────────


class FixTier(Enum):
    """Which decision tier produced the fix strategy."""

    RULE_BASED = "rule_based"
    LLM_REASONING = "llm_reasoning"
    HUMAN_REVIEW = "human_review"


class ErrorSeverity(Enum):
    """How urgent / impactful an error is."""

    CRITICAL = "critical"   # Must fix  (exact duplicates)
    HIGH = "high"           # Should fix (overlaps, road conflicts)
    MEDIUM = "medium"       # Review    (boundary touches)
    LOW = "low"             # Cosmetic  (slivers, low compactness)


class FixAction(Enum):
    """Outcome status recorded in the audit log."""

    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"
    PENDING_REVIEW = "pending_review"


# ── Feature Metadata ────────────────────────────────────────────────────


@dataclass
class FeatureMetadata:
    """Metadata attached to a single geospatial feature.

    Used by the decision engine to compare feature trustworthiness.
    All fields have sensible defaults so the system works even when
    users supply no metadata.
    """

    feature_id: str
    source: str = "unknown"
    source_date: Optional[str] = None
    accuracy_m: float = 10.0
    confidence: float = 0.5
    tags: dict[str, Any] = field(default_factory=dict)


# ── Error Model ─────────────────────────────────────────────────────────


@dataclass
class DetectedError:
    """A single error detected by OVC, enriched for GeoFix consumption.

    The ``error_type`` string matches OVC conventions:
    ``"building_overlap"``, ``"building_on_road"``,
    ``"building_boundary_overlap"``, ``"duplicate_geometry"``,
    ``"invalid_geometry"``, ``"unreasonable_area"``,
    ``"low_compactness"``, ``"road_setback"``.
    """

    error_id: str
    error_type: str
    severity: ErrorSeverity
    geometry: BaseGeometry
    affected_features: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    ovc_source: str = ""


# ── Fix Strategy & Result ───────────────────────────────────────────────


@dataclass
class FixStrategy:
    """What the decision engine recommends doing about an error."""

    error: DetectedError
    fix_type: str           # "snap", "trim", "merge", "delete", "make_valid", etc.
    tier: FixTier
    confidence: float       # 0.0–1.0
    parameters: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""


@dataclass
class FixResult:
    """Outcome of executing a FixStrategy."""

    strategy: FixStrategy
    success: bool
    original_geometry: BaseGeometry
    fixed_geometry: Optional[BaseGeometry]
    validation_passed: bool
    new_errors_introduced: int = 0
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Audit Entry ─────────────────────────────────────────────────────────


@dataclass
class AuditEntry:
    """Immutable record written to the audit database for every fix attempt."""

    fix_result: FixResult
    feature_id: str
    action: FixAction
    before_wkt: str
    after_wkt: Optional[str]
    confidence: float
    reasoning: str
    session_id: str = ""
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
