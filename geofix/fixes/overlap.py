"""Overlap fix operations: delete, trim, merge, snap."""

from __future__ import annotations

from shapely.geometry import MultiPolygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import snap, unary_union

from geofix.fixes.base import FixOperation


class DeleteFix(FixOperation):
    """Mark a feature for deletion (returns None geometry).

    Used for exact duplicate removal. The decision engine chooses
    which duplicate to keep based on metadata comparison.
    """

    @property
    def name(self) -> str:
        return "delete"

    def execute(
        self, geometry: BaseGeometry, params: dict
    ) -> BaseGeometry | None:
        # Returning None signals that this feature should be removed
        return None

    def validate(
        self, original: BaseGeometry, fixed: BaseGeometry | None
    ) -> bool:
        # Deletion is always "valid" — the result is intentionally None
        return True


class TrimFix(FixOperation):
    """Remove the overlapping portion from the lower-priority feature.

    Uses ``difference()`` to subtract the overlap geometry from the
    feature being trimmed.

    Parameters
    ----------
    params["overlap_geometry"] : BaseGeometry
        The overlap region to subtract.
    """

    @property
    def name(self) -> str:
        return "trim"

    def execute(
        self, geometry: BaseGeometry, params: dict
    ) -> BaseGeometry | None:
        overlap = params.get("overlap_geometry")
        if overlap is None:
            return geometry

        result = geometry.difference(overlap)

        # Keep only the largest polygon if result is a collection
        if isinstance(result, MultiPolygon):
            polys = list(result.geoms)
            if not polys:
                return None
            result = max(polys, key=lambda p: p.area)

        return result

    def validate(
        self, original: BaseGeometry, fixed: BaseGeometry | None
    ) -> bool:
        if not super().validate(original, fixed):
            return False
        # Trimming shouldn't remove more than 70% of the area
        if original.area > 0:
            ratio = fixed.area / original.area
            if ratio < 0.3:
                return False
        return True


class MergeFix(FixOperation):
    """Merge two overlapping features into one combined geometry.

    Used when two features are near-duplicates (overlap_ratio ≥ 0.98)
    from the same source.

    Parameters
    ----------
    params["other_geometry"] : BaseGeometry
        The geometry to merge with.
    """

    @property
    def name(self) -> str:
        return "merge"

    def execute(
        self, geometry: BaseGeometry, params: dict
    ) -> BaseGeometry | None:
        other = params.get("other_geometry")
        if other is None:
            return geometry

        merged = unary_union([geometry, other])

        # Ensure result is a single polygon
        if isinstance(merged, MultiPolygon):
            polys = list(merged.geoms)
            if not polys:
                return None
            merged = max(polys, key=lambda p: p.area)

        return merged


class SnapFix(FixOperation):
    """Snap the lower-accuracy feature to the higher-accuracy feature.

    Adjusts the geometry of the less accurate feature so its boundary
    aligns with the more accurate neighbor, eliminating the overlap.

    Parameters
    ----------
    params["reference_geometry"] : BaseGeometry
        The higher-accuracy geometry to snap to.
    params["tolerance"] : float
        Maximum snap distance (meters in metric CRS).
    """

    @property
    def name(self) -> str:
        return "snap"

    def execute(
        self, geometry: BaseGeometry, params: dict
    ) -> BaseGeometry | None:
        reference = params.get("reference_geometry")
        tolerance = params.get("tolerance", 2.0)

        if reference is None:
            return geometry

        snapped = snap(geometry, reference, tolerance)

        # Remove any resulting overlap
        result = snapped.difference(reference)

        if isinstance(result, MultiPolygon):
            polys = list(result.geoms)
            if not polys:
                return None
            result = max(polys, key=lambda p: p.area)

        return result

    def validate(
        self, original: BaseGeometry, fixed: BaseGeometry | None
    ) -> bool:
        if not super().validate(original, fixed):
            return False
        # Snapping shouldn't change area by more than 50%
        if original.area > 0:
            ratio = fixed.area / original.area
            if ratio < 0.5 or ratio > 1.5:
                return False
        return True
