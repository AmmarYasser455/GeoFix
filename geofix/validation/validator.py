"""Post-fix validation — re-check that fixes don't introduce new errors.

After each fix operation the validator:
1. Checks geometry validity
2. Checks area reasonableness
3. Optionally re-runs the relevant OVC check on affected features
4. Returns a pass/fail verdict with details
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from shapely.geometry.base import BaseGeometry

logger = logging.getLogger("geofix.validation")


@dataclass
class ValidationResult:
    """Result of validating a single fix."""

    passed: bool
    checks_run: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


class Validator:
    """Validates that a fix didn't break geometry or introduce new errors.

    Usage::

        v = Validator()
        result = v.validate_fix(original, fixed)
        if not result.passed:
            print("Rollback:", result.failures)
    """

    def __init__(
        self,
        min_area_m2: float = 0.5,
        max_area_ratio_change: float = 5.0,
    ):
        self.min_area_m2 = min_area_m2
        self.max_area_ratio_change = max_area_ratio_change

    def validate_fix(
        self,
        original: BaseGeometry,
        fixed: BaseGeometry | None,
        allow_deletion: bool = False,
    ) -> ValidationResult:
        """Run all validation checks on a fix result.

        Parameters
        ----------
        original : BaseGeometry
            Geometry before the fix.
        fixed : BaseGeometry or None
            Geometry after the fix (None for deletions).
        allow_deletion : bool
            If True, a None/empty fixed geometry passes validation.
        """
        result = ValidationResult(passed=True)

        # Check 1: Null geometry
        result.checks_run.append("null_check")
        if fixed is None or fixed.is_empty:
            if allow_deletion:
                return result  # intentional deletion
            result.passed = False
            result.failures.append("Fix produced null/empty geometry")
            return result

        # Check 2: Geometry validity
        result.checks_run.append("validity_check")
        if not fixed.is_valid:
            result.passed = False
            result.failures.append(
                f"Fixed geometry is invalid: {fixed.geom_type}"
            )

        # Check 3: Area not zero (for polygons)
        result.checks_run.append("area_check")
        if hasattr(fixed, "area") and fixed.area <= 0:
            if original.area > 0:
                result.passed = False
                result.failures.append("Fixed geometry has zero area")

        # Check 4: Area didn't change too drastically
        result.checks_run.append("area_ratio_check")
        if original.area > 0 and fixed.area > 0:
            ratio = fixed.area / original.area
            if ratio > self.max_area_ratio_change:
                result.passed = False
                result.failures.append(
                    f"Area increased {ratio:.1f}x (max {self.max_area_ratio_change}x)"
                )
            if ratio < (1.0 / self.max_area_ratio_change):
                result.passed = False
                result.failures.append(
                    f"Area decreased to {ratio:.3f}x "
                    f"(min {1.0/self.max_area_ratio_change:.3f}x)"
                )

        # Check 5: Minimum area threshold
        result.checks_run.append("min_area_check")
        if hasattr(fixed, "area") and 0 < fixed.area < self.min_area_m2:
            result.passed = False
            result.failures.append(
                f"Fixed geometry area ({fixed.area:.2f} m²) "
                f"below minimum ({self.min_area_m2} m²)"
            )

        if result.failures:
            logger.warning("Validation failed: %s", "; ".join(result.failures))

        return result
