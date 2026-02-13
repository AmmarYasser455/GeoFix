"""Bridge between GeoFix and OVC — wraps OVC error detection pipeline.

Converts OVC pipeline outputs (GeoPackage layers with error_type columns)
into GeoFix ``DetectedError`` objects for the decision engine.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

import geopandas as gpd

from geofix.core.config import GeoFixConfig, DEFAULT_CONFIG
from geofix.core.exceptions import DataLoadError
from geofix.core.models import DetectedError, ErrorSeverity

logger = logging.getLogger("geofix.integration.ovc")

# Maps OVC error_type strings to GeoFix severity levels.
_SEVERITY_MAP: dict[str, ErrorSeverity] = {
    "building_overlap": ErrorSeverity.HIGH,
    "building_on_road": ErrorSeverity.HIGH,
    "building_boundary_overlap": ErrorSeverity.MEDIUM,
    "outside_boundary": ErrorSeverity.MEDIUM,
    "duplicate_geometry": ErrorSeverity.CRITICAL,
    "invalid_geometry": ErrorSeverity.HIGH,
    "unreasonable_area": ErrorSeverity.MEDIUM,
    "low_compactness": ErrorSeverity.LOW,
    "road_setback": ErrorSeverity.MEDIUM,
}


class OVCBridge:
    """Wraps OVC's ``run_pipeline`` and converts results to GeoFix format.

    Usage::

        bridge = OVCBridge()
        errors, outputs = bridge.detect_errors(Path("buildings.shp"))
        for e in errors:
            print(e.error_type, e.severity)
    """

    def __init__(self, config: GeoFixConfig = DEFAULT_CONFIG):
        self.config = config

    # ── Public API ──────────────────────────────────────────────────

    def detect_errors(
        self,
        buildings_path: Path,
        roads_path: Optional[Path] = None,
        boundary_path: Optional[Path] = None,
        out_dir: Optional[Path] = None,
    ) -> tuple[list[DetectedError], object]:
        """Run the OVC pipeline and return normalised errors.

        Parameters
        ----------
        buildings_path : Path
            Required path to the buildings dataset.
        roads_path, boundary_path : Path, optional
            Optional supplementary datasets.
        out_dir : Path, optional
            Where to write OVC outputs (defaults to ``config.temp_dir``).

        Returns
        -------
        (errors, pipeline_outputs)
            A list of ``DetectedError`` and the raw OVC ``PipelineOutputs``.
        """
        from ovc.export.pipeline import run_pipeline
        from ovc.core.config import Config as OVCConfig

        out_dir = out_dir or self.config.temp_dir / "ovc_run"
        out_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Running OVC pipeline: buildings=%s roads=%s boundary=%s",
            buildings_path,
            roads_path,
            boundary_path,
        )

        try:
            outputs = run_pipeline(
                buildings_path=buildings_path,
                out_dir=out_dir,
                boundary_path=boundary_path,
                roads_path=roads_path,
                config=OVCConfig(),
            )
        except Exception as exc:
            raise DataLoadError(f"OVC pipeline failed: {exc}") from exc

        errors = self._read_errors_from_gpkg(outputs.gpkg_path)
        logger.info("OVC detected %d errors", len(errors))
        return errors, outputs

    # ── Internal helpers ────────────────────────────────────────────

    def _read_errors_from_gpkg(self, gpkg_path: Path) -> list[DetectedError]:
        """Read the 'errors' layer from the OVC GeoPackage and convert them.

        The OVC GeoPackage has four layers: boundary, roads, buildings_clean,
        and errors. Only the ``errors`` layer contains actual spatial errors
        with the ``error_type`` column (e.g. building_overlap, building_on_road).
        """
        if gpkg_path is None or not gpkg_path.exists():
            logger.warning("GeoPackage not found at %s", gpkg_path)
            return []

        import fiona

        errors: list[DetectedError] = []
        try:
            layer_names = fiona.listlayers(str(gpkg_path))
        except Exception:
            logger.warning("Cannot read layers from %s", gpkg_path)
            return []

        # Only process error-bearing layers — skip clean buildings, roads, etc.
        error_layers = {"errors", "overlaps", "road_conflicts", "boundary_overlaps"}
        target_layers = [n for n in layer_names if n in error_layers]

        if not target_layers:
            logger.warning(
                "No error layers found in %s (available: %s)",
                gpkg_path,
                layer_names,
            )
            return []

        for layer_name in target_layers:
            try:
                gdf = gpd.read_file(gpkg_path, layer=layer_name)
            except Exception:
                logger.warning("Skipping unreadable layer: %s", layer_name)
                continue

            if gdf.empty:
                continue

            errors.extend(self._convert_layer(gdf, layer_name))

        return errors

    def _convert_layer(
        self, gdf: gpd.GeoDataFrame, layer_name: str
    ) -> list[DetectedError]:
        """Convert a single OVC GeoDataFrame layer to DetectedError list."""
        results: list[DetectedError] = []

        for _, row in gdf.iterrows():
            error_type = row.get("error_type", layer_name)
            severity = _SEVERITY_MAP.get(error_type, ErrorSeverity.MEDIUM)

            # Collect affected feature IDs
            affected: list[str] = []
            for col in ("bldg_id", "bldg_a", "bldg_b", "osmid"):
                if col in row.index and row[col] is not None:
                    affected.append(str(row[col]))

            # Collect all non-geometry, non-ID properties
            props = {
                k: v
                for k, v in row.items()
                if k not in ("geometry", "bldg_id", "bldg_a", "bldg_b", "osmid")
                and v is not None
            }

            results.append(
                DetectedError(
                    error_id=str(uuid.uuid4()),
                    error_type=str(error_type),
                    severity=severity,
                    geometry=row.geometry,
                    affected_features=affected,
                    properties=props,
                    ovc_source=layer_name,
                )
            )

        return results
