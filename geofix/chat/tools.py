"""LangChain tool definitions for the GeoFix chat agent.

These tools are exposed to the LLM so it can call them during
conversation. Each tool wraps a GeoFix subsystem.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger("geofix.chat.tools")

# These will be set by the agent on chat start
_state: dict = {}


def set_state(key: str, value) -> None:
    _state[key] = value


def get_state(key: str, default=None):
    return _state.get(key, default)


@tool
def profile_data() -> str:
    """Profile the currently uploaded geospatial dataset for quality assessment.

    Returns:
        A quality summary including score, feature count, and detected issues.
    """
    file_path = get_state("buildings_path")
    if not file_path:
        return "⚠️ No file uploaded. Please upload a geospatial file first."

    from geofix.integration.geoqa_bridge import GeoQABridge

    path = Path(file_path)
    if not path.exists():
        return "⚠️ File not found. Please upload a geospatial file first."
        
    bridge = GeoQABridge()
    summary = bridge.profile(path)
    set_state("last_profile", summary)

    lines = [
        f"**Dataset:** {summary.name}",
        f"**Features:** {summary.feature_count}",
        f"**Geometry type:** {summary.geometry_type}",
        f"**CRS:** {summary.crs}",
        f"**Quality score:** {summary.quality_score:.0f}/100",
        f"**Valid geometries:** {summary.valid_pct:.1f}%",
    ]
    if summary.warnings:
        lines.append(f"\n**Warnings:** " + "; ".join(summary.warnings))
    if summary.blockers:
        lines.append(f"\n**⚠️ Blockers:** " + "; ".join(summary.blockers))
    if summary.is_ready:
        lines.append("\n✅ Data is ready for error detection.")
    else:
        lines.append("\n❌ Data has blockers — fix before proceeding.")

    return "\n".join(lines)


@tool
def detect_errors() -> str:
    """Run the OVC pipeline to detect spatial errors in the uploaded data.

    ONLY use this if the user EXPLICITLY asks to "run a check", "detect errors", or "validate file".
    Do NOT use this for general questions about concepts.

    Returns:
        Summary of detected errors.
    """
    buildings_path = get_state("buildings_path")
    if not buildings_path:
        return "⚠️ No file uploaded. Please upload a geospatial file first."

    # Optional roads/boundary could be in state if we supported multiple uploads
    # For now, we assume None or handle via separate upload logic later
    roads_path = get_state("roads_path")
    boundary_path = get_state("boundary_path")

    from geofix.integration.ovc_bridge import OVCBridge
    
    bridge = OVCBridge()
    errors, outputs = bridge.detect_errors(
        buildings_path=Path(buildings_path),
        roads_path=Path(roads_path) if roads_path else None,
        boundary_path=Path(boundary_path) if boundary_path else None,
    )
    set_state("errors", errors)
    set_state("ovc_outputs", outputs)

    if not errors:
        return "✅ No spatial errors detected! Your data looks clean."

    # Summarise by error type
    from collections import Counter
    type_counts = Counter(e.error_type for e in errors)

    lines = [f"**Total errors detected:** {len(errors)}\n"]
    lines.append("| Error Type | Count |")
    lines.append("|---|---|")
    for etype, count in type_counts.most_common():
        lines.append(f"| {etype} | {count} |")

    lines.append(
        f"\nUse `fix_all_auto` to auto-fix high-confidence errors, "
        f"or `show_errors` to see details."
    )
    return "\n".join(lines)


@tool
def show_errors(error_type: Optional[str] = None, limit: int = 20) -> str:
    """Show detected errors, optionally filtered by type.

    Args:
        error_type: Filter by error type (e.g. "building_overlap"). Leave empty for all.
        limit: Maximum number of errors to show.

    Returns:
        Table of errors with details.
    """
    errors = get_state("errors", [])
    if not errors:
        return "No errors in memory. Run `detect_errors` first."

    if error_type:
        errors = [e for e in errors if e.error_type == error_type]

    errors = errors[:limit]

    lines = ["| # | Type | Severity | Features |"]
    lines.append("|---|---|---|---|")
    for i, e in enumerate(errors, 1):
        feats = ", ".join(e.affected_features[:3])
        lines.append(f"| {i} | {e.error_type} | {e.severity.value} | {feats} |")

    lines.append(f"\nShowing {len(errors)} errors.")
    return "\n".join(lines)


@tool
def fix_all_auto() -> str:
    """Automatically fix all errors using rule-based decisions (no LLM needed).

    Returns:
        Summary of applied, skipped, and pending-review fixes.
    """
    errors = get_state("errors", [])
    if not errors:
        return "No errors to fix. Run `detect_errors` first."

    from geofix.decision.engine import DecisionEngine
    from geofix.fixes.registry import build_default_registry
    from geofix.core.models import FixTier

    engine = DecisionEngine()
    registry = build_default_registry()

    applied = 0
    skipped = 0
    pending = 0
    fix_summary: dict[str, int] = {}
    fixed_results: dict[str, object] = {} # Map error_id -> fixed_geometry

    total = len(errors)
    logger.info("fix_all_auto: processing %d errors (rules-only mode)", total)

    for i, error in enumerate(errors):
        # rules_only=True → never calls LLM, instant decisions
        strategy = engine.decide(error, {}, rules_only=True)

        if strategy.tier == FixTier.HUMAN_REVIEW:
            pending += 1
            continue

        fix_op = registry.get(strategy.fix_type)
        if fix_op is None:
            skipped += 1
            continue

        result = fix_op.apply(strategy)
        if result.success:
            applied += 1
            fix_summary[strategy.fix_type] = fix_summary.get(strategy.fix_type, 0) + 1
            fixed_results[error.error_id] = result.fixed_geometry
        else:
            skipped += 1

    # Build detailed summary
    lines = [
        f"## Fix Results ({total} errors processed)\n",
        f"- ✅ **Applied:** {applied}",
        f"- ⏭️ **Skipped:** {skipped}",
        f"- 👁️ **Needs review:** {pending}",
    ]

    if fix_summary:
        lines.append("\n### Fixes Applied")
        lines.append("| Fix Type | Count |")
        lines.append("|---|---|")
        for ftype, count in sorted(fix_summary.items(), key=lambda x: -x[1]):
            lines.append(f"| {ftype} | {count} |")

    if pending > 0:
        lines.append(
            f"\n💡 {pending} errors need human review or LLM reasoning. "
            "Wait for API quota to reset, then ask about specific errors."
        )

    # --- SAVE RESULTS ---
    ovc_outputs = get_state("ovc_outputs")
    if ovc_outputs and ovc_outputs.gpkg_path.exists():
        try:
            import geopandas as gpd
            import pandas as pd
            from pathlib import Path

            gpkg_path = ovc_outputs.gpkg_path
            
            # 1. Load clean buildings
            try:
                clean_gdf = gpd.read_file(gpkg_path, layer="buildings_clean")
            except Exception:
                clean_gdf = gpd.GeoDataFrame()

            # 2. Reconstruct fixed/unfixed errors
            fixed_rows = []
            
            for error in errors:
                # Use fixed geometry if available, else original
                geom = fixed_results.get(error.error_id, error.geometry)
                
                # Check for deletion (None geometry)
                if geom is None or geom.is_empty:
                    continue

                # Use properties from error object + updated status
                props = error.properties.copy()
                props["geometry"] = geom
                props["fixed_status"] = "fixed" if error.error_id in fixed_results else "unfixed"
                
                # Restore ID columns if missing
                if "bldg_id" not in props and error.affected_features:
                     props["bldg_id"] = error.affected_features[0]

                fixed_rows.append(props)

            # 3. Create DataFrame from fixed data
            if fixed_rows:
                fixed_gdf = gpd.GeoDataFrame(fixed_rows, crs=clean_gdf.crs if not clean_gdf.empty else "EPSG:4326")
                
                # Align columns
                common_cols = list(set(clean_gdf.columns) & set(fixed_gdf.columns))
                if not clean_gdf.empty:
                    final_gdf = pd.concat([clean_gdf[common_cols], fixed_gdf[common_cols]], ignore_index=True)
                else:
                    final_gdf = fixed_gdf
            else:
                final_gdf = clean_gdf

            # 4. Save to new layer/file
            # We save as a NEW file to update the state properly
            out_dir = gpkg_path.parent
            fixed_path = out_dir / "buildings_fixed.gpkg"
            
            # Ensure it's a valid GeoDataFrame
            if not isinstance(final_gdf, gpd.GeoDataFrame):
                 final_gdf = gpd.GeoDataFrame(final_gdf, geometry="geometry")

            final_gdf.to_file(fixed_path, layer="buildings_fixed", driver="GPKG")
            
            # Update state so download_fixed() picks this up
            # We construct a new PipelineOutputs object or just monkey-patch the path?
            # PipelineOutputs is frozen. We must update the state directly.
            # But get_state returns a copy? Objects are ref?
            # We can't modify fixed dataclass.
            # We'll invoke set_state with a modified object if possible, or just hack "download_path"
            
            # Actually, `download_fixed` checks `ovc_outputs.gpkg_path`.
            # We can't change `ovc_outputs.gpkg_path` easily without re-creating the object.
            # AND `download_fixed` prefers `get_state("download_path")` if set?
            # Let's check download_fixed code...
            
            # Lines 257-259:
            # gpkg_path = ovc_outputs.gpkg_path
            # if gpkg_path... set_state("download_path", str(gpkg_path))
            
            # Use a state override!
            set_state("download_path", str(fixed_path))
            
            lines.append(f"\n💾 **Saved:** Corrected data saved to `{fixed_path.name}`")
            
        except Exception as e:
            logger.error("Failed to save fixed data: %s", e)
            lines.append(f"\n⚠️ Failed to save fixed data: {e}")

    # Oh wait, I need to capture the results in the loop above first!
    return "\n".join(lines)


@tool
def explain_fix(error_index: int) -> str:
    """Explain why a specific fix was chosen for an error.

    Args:
        error_index: 1-based index of the error (from show_errors).

    Returns:
        Detailed explanation of the fix strategy.
    """
    errors = get_state("errors", [])
    if not errors:
        return "No errors in memory. Run `detect_errors` first."

    idx = error_index - 1
    if idx < 0 or idx >= len(errors):
        return f"Invalid index. Valid range: 1–{len(errors)}"

    error = errors[idx]

    from geofix.decision.engine import DecisionEngine

    engine = DecisionEngine()
    strategy = engine.decide(error, {})

    return (
        f"**Error:** {error.error_type} ({error.severity.value})\n"
        f"**Fix type:** {strategy.fix_type}\n"
        f"**Tier:** {strategy.tier.value}\n"
        f"**Confidence:** {strategy.confidence:.0%}\n"
        f"**Reasoning:** {strategy.reasoning}\n"
    )


@tool
def download_fixed() -> str:
    """Export the corrected dataset as a downloadable file.

    Returns:
        Path to the corrected file or status message.
    """
    ovc_outputs = get_state("ovc_outputs")
    if ovc_outputs is None:
        return "No corrected data available. Run `detect_errors` and `fix_all_auto` first."

    gpkg_path = ovc_outputs.gpkg_path
    if gpkg_path and gpkg_path.exists():
        set_state("download_path", str(gpkg_path))
        return f"DOWNLOAD_READY:{gpkg_path}"

    return "Corrected data file not found. Try running `detect_errors` again."


@tool
def get_audit_log(limit: int = 10) -> str:
    """View recent audit log entries showing past fix actions.

    Args:
        limit: Maximum entries to show.

    Returns:
        Table of recent audit log entries.
    """
    audit = get_state("audit_logger")
    if audit is None:
        return "No audit log available for this session."

    rows = audit.get_history(limit=limit)
    if not rows:
        return "Audit log is empty."

    lines = ["| Time | Feature | Fix | Action | Conf |"]
    lines.append("|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['timestamp'][:19]} | {r['feature_id']} | "
            f"{r['fix_type']} | {r['action']} | {r['confidence']:.0%} |"
        )
    return "\n".join(lines)


@tool
def consult_encyclopedia(term: str) -> str:
    """Consult the internal GIS encyclopedia for definitions and solutions.

    Use this tool for specific technical terms like "topology", "OVC", "logic".
    For general questions (history, science), rely on your internal training.
    like "data control", "quality", "topology", "errors", "logic", "how do you work".

    Args:
        term: The term or concept to look up (e.g., 'sliver', 'topology', 'overlap').

    Returns:
        Definition and relevant info.
    """
    import json
    
    # Locate json in geofix/knowledge/gis_encyclopedia.json
    # tools.py is in geofix/chat/, so we go up one level
    base_dir = Path(__file__).resolve().parent.parent
    encyclopedia_path = base_dir / "knowledge" / "gis_encyclopedia.json"
    
    if not encyclopedia_path.exists():
        return "Encyclopedia database not found."
        
    try:
        with open(encyclopedia_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        term_lower = term.lower().strip()
        results = []
        
        # Search match in keys or values
        for section, items in data.items():
            for key, value in items.items():
                if term_lower in key.lower() or term_lower in value.lower(): 
                   # Priority match: exact key
                   prefix = "⭐ " if term_lower == key.lower() else ""
                   results.append(f"{prefix}**{key.replace('_', ' ').title()}** ({section}):\n{value}")

        if not results:
             return f"No exact entry found for '{term}'. Try simpler keywords."
             
        # Sort to put exact matches first
        results.sort(key=lambda x: "⭐" not in x)
        return "\n\n".join(results[:3])
        
    except Exception as e:
        return f"Error reading encyclopedia: {e}"


# All tools to register with the agent
ALL_TOOLS = [
    profile_data,
    detect_errors,
    show_errors,
    fix_all_auto,
    explain_fix,
    download_fixed,
    get_audit_log,
    consult_encyclopedia,
]
