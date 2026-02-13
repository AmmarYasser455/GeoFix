"""Geometry quality fix operations: make_valid, simplify."""

from __future__ import annotations

from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid

from geofix.fixes.base import FixOperation


class MakeValidFix(FixOperation):
    """Repair self-intersecting or otherwise invalid geometries.

    Uses ``shapely.validation.make_valid`` which follows the OGC
    approach of constructing valid geometry from the original coordinates.
    """

    @property
    def name(self) -> str:
        return "make_valid"

    def execute(
        self, geometry: BaseGeometry, params: dict
    ) -> BaseGeometry | None:
        if geometry is None:
            return None
        if geometry.is_valid:
            return geometry  # nothing to fix
        return make_valid(geometry)

    def validate(
        self, original: BaseGeometry, fixed: BaseGeometry | None
    ) -> bool:
        if not super().validate(original, fixed):
            return False
        # make_valid should always produce a valid result
        return fixed.is_valid


class SimplifyFix(FixOperation):
    """Simplify overly complex or jagged polygon boundaries.

    Uses Douglas-Peucker simplification. The ``tolerance`` parameter
    controls how aggressively to simplify (in CRS units).
    """

    @property
    def name(self) -> str:
        return "simplify"

    def execute(
        self, geometry: BaseGeometry, params: dict
    ) -> BaseGeometry | None:
        if geometry is None:
            return None
        tolerance = params.get("tolerance", 0.5)
        preserve_topology = params.get("preserve_topology", True)
        return geometry.simplify(tolerance, preserve_topology=preserve_topology)

    def validate(
        self, original: BaseGeometry, fixed: BaseGeometry | None
    ) -> bool:
        if not super().validate(original, fixed):
            return False
        # Ensure simplification didn't remove too much area
        if original.area > 0:
            area_ratio = fixed.area / original.area
            if area_ratio < 0.5:  # lost more than half the area
                return False
        return True
