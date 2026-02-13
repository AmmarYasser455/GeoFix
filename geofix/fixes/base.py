"""Abstract base class for all geometry fix operations.

Every fix type (snap, trim, merge, delete, make_valid, …) inherits from
``FixOperation`` and implements ``name``, ``execute``, and optionally
overrides ``validate``.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from shapely.geometry.base import BaseGeometry

from geofix.core.models import FixResult, FixStrategy

logger = logging.getLogger("geofix.fixes")


class FixOperation(ABC):
    """Base class for geometry correction operations.

    Subclasses must implement:
    - ``name``    — unique string identifier
    - ``execute`` — apply the fix to a single geometry

    The ``apply`` method handles the full lifecycle:
    execute → validate → return FixResult.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this fix type (e.g. ``"make_valid"``)."""
        ...

    @abstractmethod
    def execute(
        self, geometry: BaseGeometry, params: dict
    ) -> BaseGeometry | None:
        """Apply the fix and return the corrected geometry.

        Parameters
        ----------
        geometry : BaseGeometry
            The geometry to fix.
        params : dict
            Fix-specific parameters from the ``FixStrategy``.

        Returns
        -------
        BaseGeometry or None
            The corrected geometry, or ``None`` if the fix cannot be applied.
        """
        ...

    def validate(
        self, original: BaseGeometry, fixed: BaseGeometry | None
    ) -> bool:
        """Check that the fix didn't introduce topology or area problems.

        Override in subclasses for fix-type-specific validation.
        """
        if fixed is None or fixed.is_empty:
            return False
        if not fixed.is_valid:
            return False
        # Ensure area didn't collapse to zero (unless original was already tiny)
        if original.area > 1.0 and fixed.area <= 0:
            return False
        return True

    def apply(self, strategy: FixStrategy) -> FixResult:
        """Full fix lifecycle: execute → validate → return result.

        This is the primary entry point called by the decision engine.
        """
        original = strategy.error.geometry
        try:
            fixed = self.execute(original, strategy.parameters)
            passed = self.validate(original, fixed)
            return FixResult(
                strategy=strategy,
                success=passed,
                original_geometry=original,
                fixed_geometry=fixed if passed else None,
                validation_passed=passed,
            )
        except Exception as exc:
            logger.warning(
                "Fix %s failed on error %s: %s",
                self.name,
                strategy.error.error_id,
                exc,
            )
            return FixResult(
                strategy=strategy,
                success=False,
                original_geometry=original,
                fixed_geometry=None,
                validation_passed=False,
            )
