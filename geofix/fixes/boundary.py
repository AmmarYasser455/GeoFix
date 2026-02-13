"""Boundary fix operations: clip features to study area boundary."""

from __future__ import annotations

from shapely.geometry.base import BaseGeometry
from shapely.geometry import MultiPolygon

from geofix.fixes.base import FixOperation


class ClipFix(FixOperation):
    """Clip a building geometry to the study area boundary.

    Uses ``intersection()`` to keep only the portion of the building
    that falls within the boundary polygon.

    Parameters
    ----------
    params["boundary_geometry"] : BaseGeometry
        The boundary polygon to clip to.
    """

    @property
    def name(self) -> str:
        return "clip"

    def execute(
        self, geometry: BaseGeometry, params: dict
    ) -> BaseGeometry | None:
        boundary = params.get("boundary_geometry")
        if boundary is None:
            return geometry

        clipped = geometry.intersection(boundary)

        if isinstance(clipped, MultiPolygon):
            polys = list(clipped.geoms)
            if not polys:
                return None
            clipped = max(polys, key=lambda p: p.area)

        return clipped

    def validate(
        self, original: BaseGeometry, fixed: BaseGeometry | None
    ) -> bool:
        if not super().validate(original, fixed):
            return False
        # Clipping should keep at least 10% of the original area
        if original.area > 0:
            ratio = fixed.area / original.area
            if ratio < 0.1:
                return False
        return True
