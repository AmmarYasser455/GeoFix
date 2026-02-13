"""GeoFix configuration — extends OVC config with decision and LLM settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DecisionThresholds:
    """Confidence thresholds for the three-tier decision system."""

    auto_fix_min: float = 0.80        # Tier 1 — rule-based auto-fix
    llm_fix_min: float = 0.60         # Tier 2 — LLM-recommended fix
    human_review_below: float = 0.60  # Tier 3 — escalate to human


@dataclass(frozen=True)
class LLMConfig:
    """LLM provider settings."""

    provider: str = "ollama"            # "ollama" or "google"
    model: str = "llama3.2"
    temperature: float = 0.1
    max_tokens: int = 2048
    fallback_model: str = "mistral"
    ollama_base_url: str = "http://localhost:11434"


@dataclass(frozen=True)
class GeometryThresholds:
    """Thresholds for geometry quality and fix decisions."""

    sliver_max_area_m2: float = 1.0
    min_building_area_m2: float = 4.0
    max_building_area_m2: float = 50_000.0
    road_snap_distance_m: float = 2.0
    boundary_clip_buffer_m: float = 0.5
    duplicate_ratio_min: float = 0.98
    partial_ratio_min: float = 0.30


@dataclass(frozen=True)
class GeoFixConfig:
    """Top-level GeoFix configuration."""

    decision: DecisionThresholds = field(default_factory=DecisionThresholds)
    llm: LLMConfig = field(default_factory=LLMConfig)
    geometry: GeometryThresholds = field(default_factory=GeometryThresholds)

    # Paths
    audit_db_path: Path = Path("geofix_audit.db")
    output_dir: Path = Path("geofix_output")
    temp_dir: Path = Path("_geofix_temp")


DEFAULT_CONFIG = GeoFixConfig()
