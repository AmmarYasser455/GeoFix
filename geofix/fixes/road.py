"""Road conflict fix operations: nudge buildings away from roads."""

from __future__ import annotations

import math

from shapely.affinity import translate
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

from geofix.fixes.base import FixOperation


class NudgeFix(FixOperation):
    """Move a building away from a road to resolve setback violations.

    Computes the direction from the road to the building centroid and
    translates the building geometry to achieve the minimum required
    distance.

    Parameters
    ----------
    params["road_geometry"] : BaseGeometry
        The road geometry (line or buffered polygon).
    params["min_distance_m"] : float
        Minimum required distance between building and road.
    """

    @property
    def name(self) -> str:
        return "nudge"

    def execute(
        self, geometry: BaseGeometry, params: dict
    ) -> BaseGeometry | None:
        road = params.get("road_geometry")
        min_dist = params.get("min_distance_m", 3.0)

        if road is None:
            return geometry

        current_dist = geometry.distance(road)
        if current_dist >= min_dist:
            return geometry  # already far enough

        # Find the nearest point on the road to the building
        nearest_on_road, nearest_on_bldg = nearest_points(road, geometry)

        # Direction vector from road to building
        dx = nearest_on_bldg.x - nearest_on_road.x
        dy = nearest_on_bldg.y - nearest_on_road.y
        length = math.sqrt(dx * dx + dy * dy)

        if length < 1e-10:
            # Points are essentially coincident — nudge north
            dx, dy, length = 0.0, 1.0, 1.0

        # Normalise and scale to the gap needed
        gap = min_dist - current_dist + 0.1  # small buffer
        nudge_x = (dx / length) * gap
        nudge_y = (dy / length) * gap

        return translate(geometry, xoff=nudge_x, yoff=nudge_y)

    def validate(
        self, original: BaseGeometry, fixed: BaseGeometry | None
    ) -> bool:
        if not super().validate(original, fixed):
            return False
        # Nudging should preserve area exactly
        if original.area > 0:
            ratio = fixed.area / original.area
            if abs(ratio - 1.0) > 0.01:
                return False
        return True
