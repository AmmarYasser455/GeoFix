"""One-liner API for GeoFix — ``import geofix; geofix.analyze("data.shp")``.

Provides three convenience functions that wrap the GeoFix validation
and fix pipeline for scripting, notebooks, and CLI usage.

Examples
--------
>>> import geofix
>>> results = geofix.analyze("data.shp")
>>> geofix.analyze("data.shp", auto_fix=True, output="fixed.shp")
>>> geofix.fix("data.shp", "corrected.gpkg")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import geopandas as gpd
from shapely.validation import explain_validity

logger = logging.getLogger("geofix.api")


# ── Result Container ────────────────────────────────────────────────────


class AnalysisResult(dict):
    """Quality analysis results with a nice ``__repr__``."""

    def __repr__(self) -> str:
        fc = self.get("feature_count", "?")
        ec = self.get("error_count", 0)
        qs = self.get("quality_score", "?")
        return f"<AnalysisResult features={fc} errors={ec} quality={qs}/100>"

    def summary(self) -> str:
        """Return a human-readable summary string."""
        lines = [
            f"📊 GeoFix Analysis Results",
            f"   Features:      {self.get('feature_count', '?')}",
            f"   Geometry type:  {self.get('geometry_type', '?')}",
            f"   CRS:            {self.get('crs', '?')}",
            f"   Quality score:  {self.get('quality_score', '?')}/100",
            f"   Total errors:   {self.get('error_count', 0)}",
        ]
        breakdown = self.get("error_breakdown", {})
        if breakdown:
            lines.append("   Error breakdown:")
            for etype, count in breakdown.items():
                lines.append(f"     • {etype}: {count}")
        return "\n".join(lines)


# ── Internal Helpers ────────────────────────────────────────────────────


def _read_file(file_path: str | Path) -> gpd.GeoDataFrame:
    """Read a geospatial file into a GeoDataFrame."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    supported = {".shp", ".geojson", ".json", ".gpkg", ".gml", ".kml"}
    if suffix not in supported:
        raise ValueError(
            f"Unsupported format '{suffix}'. Supported: {', '.join(sorted(supported))}"
        )

    gdf = gpd.read_file(str(path))
    logger.info("Loaded %d features from %s", len(gdf), path.name)
    return gdf


def _validate_geometries(gdf: gpd.GeoDataFrame) -> dict:
    """Run geometry validation checks and return error details."""
    errors: dict[str, list] = {
        "invalid_geometry": [],
        "null_geometry": [],
        "empty_geometry": [],
    }

    for idx, geom in enumerate(gdf.geometry):
        if geom is None:
            errors["null_geometry"].append(idx)
        elif geom.is_empty:
            errors["empty_geometry"].append(idx)
        elif not geom.is_valid:
            errors["invalid_geometry"].append(
                {"index": idx, "reason": explain_validity(geom)}
            )

    return errors


def _detect_overlaps(gdf: gpd.GeoDataFrame) -> list[dict]:
    """Detect pairwise polygon overlaps using spatial index."""
    if len(gdf) < 2:
        return []

    overlaps = []
    sindex = gdf.sindex

    for i, geom_a in enumerate(gdf.geometry):
        if geom_a is None or geom_a.is_empty:
            continue
        candidates = list(sindex.intersection(geom_a.bounds))
        for j in candidates:
            if j <= i:
                continue
            geom_b = gdf.geometry.iloc[j]
            if geom_b is None or geom_b.is_empty:
                continue
            if geom_a.intersects(geom_b):
                inter = geom_a.intersection(geom_b)
                if inter.area > 0:
                    overlaps.append({
                        "feature_a": i,
                        "feature_b": j,
                        "overlap_area": inter.area,
                    })

    return overlaps


def _compute_quality_score(
    feature_count: int,
    error_count: int,
    has_crs: bool,
) -> int:
    """Compute a 0-100 quality score."""
    if feature_count == 0:
        return 0

    error_rate = error_count / feature_count
    score = max(0, 100 - int(error_rate * 100))

    # Penalise missing CRS
    if not has_crs:
        score = max(0, score - 10)

    return score


# ── Public API ──────────────────────────────────────────────────────────


def analyze(
    file_path: str | Path,
    *,
    auto_fix: bool = False,
    output: Optional[str | Path] = None,
    report: Optional[str] = None,
) -> AnalysisResult:
    """Analyse a geospatial file for quality issues.

    Parameters
    ----------
    file_path : str or Path
        Path to a Shapefile, GeoJSON, or GeoPackage.
    auto_fix : bool
        If ``True``, attempt to fix invalid geometries automatically.
    output : str or Path, optional
        Save the (optionally fixed) dataset to this path.
    report : str, optional
        Generate a report in the given format (``"md"``, ``"html"``).

    Returns
    -------
    AnalysisResult
        A dict-like object with quality metrics and error details.

    Examples
    --------
    >>> import geofix
    >>> r = geofix.analyze("data.shp")
    >>> r.summary()
    >>> geofix.analyze("data.shp", auto_fix=True, output="fixed.gpkg")
    """
    gdf = _read_file(file_path)

    # Basic metadata
    geometry_types = gdf.geometry.type.value_counts().to_dict() if len(gdf) else {}
    crs_str = str(gdf.crs) if gdf.crs else "No CRS"

    # Validation
    geom_errors = _validate_geometries(gdf)
    overlaps = _detect_overlaps(gdf)

    # Error breakdown
    error_breakdown: dict[str, int] = {}
    for etype, items in geom_errors.items():
        if items:
            error_breakdown[etype] = len(items)
    if overlaps:
        error_breakdown["overlap"] = len(overlaps)

    error_count = sum(error_breakdown.values())

    # Auto-fix invalid geometries
    if auto_fix and geom_errors["invalid_geometry"]:
        fixed_count = 0
        for entry in geom_errors["invalid_geometry"]:
            idx = entry["index"]
            geom = gdf.geometry.iloc[idx]
            repaired = geom.buffer(0)
            if repaired.is_valid and not repaired.is_empty:
                gdf.geometry.iloc[idx] = repaired
                fixed_count += 1

        if fixed_count > 0:
            logger.info("Auto-fixed %d invalid geometries via buffer(0)", fixed_count)
            # Re-validate
            geom_errors = _validate_geometries(gdf)
            error_breakdown = {}
            for etype, items in geom_errors.items():
                if items:
                    error_breakdown[etype] = len(items)
            if overlaps:
                error_breakdown["overlap"] = len(overlaps)
            error_count = sum(error_breakdown.values())

    quality_score = _compute_quality_score(
        len(gdf), error_count, gdf.crs is not None
    )

    # Save output
    if output:
        out_path = Path(output)
        gdf.to_file(str(out_path))
        logger.info("Saved to %s", out_path)

    result = AnalysisResult(
        feature_count=len(gdf),
        geometry_type=geometry_types,
        crs=crs_str,
        bounds=gdf.total_bounds.tolist() if len(gdf) else [],
        columns=gdf.columns.tolist(),
        error_count=error_count,
        error_breakdown=error_breakdown,
        quality_score=quality_score,
        invalid_geometries=geom_errors["invalid_geometry"],
        null_geometries=geom_errors["null_geometry"],
        empty_geometries=geom_errors["empty_geometry"],
        overlaps=overlaps,
        auto_fixed=auto_fix,
    )

    # Generate report
    if report:
        _generate_report(result, report, file_path)

    return result


def validate(file_path: str | Path) -> AnalysisResult:
    """Validate a geospatial file without fixing anything.

    Shorthand for ``analyze(file_path, auto_fix=False)``.
    """
    return analyze(file_path, auto_fix=False)


def fix(
    file_path: str | Path,
    output: str | Path,
) -> AnalysisResult:
    """Validate, auto-fix, and save the corrected file.

    Shorthand for ``analyze(file_path, auto_fix=True, output=output)``.
    """
    return analyze(file_path, auto_fix=True, output=output)


# ── Report Generation ───────────────────────────────────────────────────


def _generate_report(
    result: AnalysisResult,
    fmt: str,
    source_path: str | Path,
) -> str:
    """Generate a quality report in the specified format."""
    source = Path(source_path).name

    md = f"""# GeoFix Quality Report

**Source**: `{source}`
**Quality Score**: {result['quality_score']}/100

## Summary

| Metric | Value |
|---|---|
| Features | {result['feature_count']} |
| Geometry types | {result['geometry_type']} |
| CRS | {result['crs']} |
| Total errors | {result['error_count']} |

## Error Breakdown

"""
    for etype, count in result.get("error_breakdown", {}).items():
        md += f"- **{etype}**: {count}\n"

    if not result.get("error_breakdown"):
        md += "_No errors detected_ ✅\n"

    # Save report
    report_path = Path(source_path).with_suffix(f".report.{fmt}")
    if fmt == "md":
        report_path.write_text(md, encoding="utf-8")
    elif fmt == "html":
        try:
            import markdown

            html = markdown.markdown(md, extensions=["tables"])
            wrapped = f"<html><head><title>GeoFix Report</title></head><body>{html}</body></html>"
            report_path.write_text(wrapped, encoding="utf-8")
        except ImportError:
            # Fallback: write markdown if markdown package not installed
            report_path = report_path.with_suffix(".md")
            report_path.write_text(md, encoding="utf-8")

    logger.info("Report saved to %s", report_path)
    return str(report_path)
