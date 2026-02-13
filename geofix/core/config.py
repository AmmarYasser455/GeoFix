"""GeoFix configuration — extends OVC config with decision, LLM, cache, and router settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DecisionThresholds:
    """Confidence thresholds for the three-tier decision system."""

    auto_fix_min: float = 0.80
    llm_fix_min: float = 0.60
    human_review_below: float = 0.60


@dataclass(frozen=True)
class LLMConfig:
    """LLM provider settings."""

    provider: str = "ollama"
    model: str = "llama3.1:latest"
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
class CacheConfig:
    """Response cache settings."""

    max_size: int = 256
    ttl_seconds: int = 3600


@dataclass(frozen=True)
class ConversationConfig:
    """Conversation persistence settings."""

    db_path: Path = Path("geofix_conversations.db")
    max_history_messages: int = 50


@dataclass(frozen=True)
class RouterConfig:
    """Model router settings."""

    auto_route: bool = True
    simple_model: str = "llama3.2"
    medium_model: str = "llama3.2"
    complex_model: str = "llama3.1:latest"


@dataclass(frozen=True)
class GeoFixConfig:
    """Top-level GeoFix configuration."""

    decision: DecisionThresholds = field(default_factory=DecisionThresholds)
    llm: LLMConfig = field(default_factory=LLMConfig)
    geometry: GeometryThresholds = field(default_factory=GeometryThresholds)
    cache: CacheConfig = field(default_factory=CacheConfig)
    conversations: ConversationConfig = field(default_factory=ConversationConfig)
    router: RouterConfig = field(default_factory=RouterConfig)

    audit_db_path: Path = Path("geofix_audit.db")
    output_dir: Path = Path("geofix_output")
    temp_dir: Path = Path("_geofix_temp")


DEFAULT_CONFIG = GeoFixConfig()
