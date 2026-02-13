"""Bridge between GeoFix and GeoQA — wraps data profiling and pre-flight checks.

Provides a thin wrapper around ``geoqa.profile()`` so that:
  1. The chat agent can profile uploaded files before running QC.
  2. The decision engine can access quality scores when reasoning about fixes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import geopandas as gpd

logger = logging.getLogger("geofix.integration.geoqa")


@dataclass
class ProfileSummary:
    """Lightweight summary of a GeoQA profile for GeoFix consumption."""

    name: str
    feature_count: int = 0
    column_count: int = 0
    geometry_type: str = "Unknown"
    crs: str = "Unknown"
    quality_score: float = 0.0
    valid_pct: float = 0.0
    empty_count: int = 0
    duplicate_count: int = 0
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    report_path: Optional[Path] = None

    @property
    def is_ready(self) -> bool:
        """True if data passes pre-flight with no blockers."""
        return len(self.blockers) == 0


class GeoQABridge:
    """Wraps GeoQA profiling for GeoFix pre-flight checks.

    Usage::

        bridge = GeoQABridge()
        summary = bridge.profile(Path("buildings.shp"))
        if summary.is_ready:
            print("Data is ready for QC")
        else:
            print("Blockers:", summary.blockers)
    """

    def profile(
        self,
        data: Union[str, Path, gpd.GeoDataFrame],
        name: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ) -> ProfileSummary:
        """Profile a dataset and return a structured summary.

        Parameters
        ----------
        data : str, Path, or GeoDataFrame
            The geospatial data to profile.
        name : str, optional
            Human-readable name for the dataset.
        output_dir : Path, optional
            If provided, generate an HTML report here.

        Returns
        -------
        ProfileSummary
        """
        try:
            import geoqa
        except ImportError:
            logger.warning("GeoQA not installed — skipping profiling")
            return ProfileSummary(name=name or "unknown")

        if isinstance(data, (str, Path)):
            name = name or Path(data).stem

        logger.info("Profiling dataset: %s", name)

        try:
            profile = geoqa.profile(data, name=name)
        except Exception as exc:
            logger.error("GeoQA profiling failed: %s", exc)
            return ProfileSummary(
                name=name or "unknown",
                blockers=[f"Profiling failed: {exc}"],
            )

        # Extract structured results
        geom = profile.geometry_results
        summary = ProfileSummary(
            name=profile.name,
            feature_count=profile.feature_count,
            column_count=profile.column_count,
            geometry_type=profile.geometry_type,
            crs=profile.crs,
            quality_score=profile.quality_score,
            valid_pct=(
                geom.get("valid_count", 0) / max(profile.feature_count, 1) * 100
            ),
            empty_count=geom.get("empty_count", 0),
            duplicate_count=geom.get("duplicate_count", 0),
        )

        # Classify issues as warnings or blockers
        self._classify_issues(summary, profile)

        # Generate report if requested
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            report_path = output_dir / f"{name}_quality_report.html"
            try:
                profile.to_html(str(report_path))
                summary.report_path = report_path
            except Exception as exc:
                logger.warning("Report generation failed: %s", exc)

        return summary

    def _classify_issues(self, summary: ProfileSummary, profile) -> None:
        """Add warnings / blockers based on profile results."""
        # Blocker: no CRS
        if summary.crs in ("Unknown", "None", None):
            summary.blockers.append("No CRS defined — cannot perform spatial analysis")

        # Blocker: very low validity
        if summary.valid_pct < 50:
            summary.blockers.append(
                f"Only {summary.valid_pct:.0f}% of geometries are valid"
            )

        # Warning: moderate validity issues
        if 50 <= summary.valid_pct < 90:
            summary.warnings.append(
                f"{100 - summary.valid_pct:.0f}% of geometries are invalid"
            )

        # Warning: duplicates
        if summary.duplicate_count > 0:
            summary.warnings.append(
                f"{summary.duplicate_count} duplicate geometries detected"
            )

        # Warning: empty geometries
        if summary.empty_count > 0:
            summary.warnings.append(
                f"{summary.empty_count} empty geometries detected"
            )

        # Warning: low quality score
        if summary.quality_score < 50:
            summary.warnings.append(
                f"Low quality score: {summary.quality_score:.0f}/100"
            )
