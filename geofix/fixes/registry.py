"""Fix operation registry — maps fix type names to FixOperation instances."""

from __future__ import annotations

import logging
from typing import Optional

from geofix.fixes.base import FixOperation

logger = logging.getLogger("geofix.fixes.registry")


class FixRegistry:
    """Registry that maps fix type names to FixOperation instances.

    Usage::

        registry = FixRegistry()
        registry.register(MakeValidFix())
        registry.register(DeleteFix())

        fix_op = registry.get("make_valid")
        result = fix_op.apply(strategy)
    """

    def __init__(self) -> None:
        self._ops: dict[str, FixOperation] = {}

    def register(self, op: FixOperation) -> None:
        """Register a fix operation by its name."""
        if op.name in self._ops:
            logger.warning("Overwriting fix operation: %s", op.name)
        self._ops[op.name] = op
        logger.debug("Registered fix operation: %s", op.name)

    def get(self, name: str) -> Optional[FixOperation]:
        """Look up a fix operation by name."""
        return self._ops.get(name)

    def list_operations(self) -> list[str]:
        """Return all registered fix type names."""
        return list(self._ops.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._ops


def build_default_registry() -> FixRegistry:
    """Create a registry pre-loaded with all built-in fix operations."""
    from geofix.fixes.geometry import MakeValidFix, SimplifyFix
    from geofix.fixes.overlap import DeleteFix, TrimFix, MergeFix, SnapFix
    from geofix.fixes.boundary import ClipFix
    from geofix.fixes.road import NudgeFix

    registry = FixRegistry()
    for op in (
        MakeValidFix(),
        SimplifyFix(),
        DeleteFix(),
        TrimFix(),
        MergeFix(),
        SnapFix(),
        ClipFix(),
        NudgeFix(),
        FlagFix(),
    ):
        registry.register(op)

    return registry


class FlagFix(FixOperation):
    """No-op fix that marks a feature as flagged for review.

    Used for errors like 'outside_boundary' where the feature itself
    isn't broken — it just needs human attention.
    """

    @property
    def name(self) -> str:
        return "flag"

    def execute(self, geometry, params: dict):
        # Return geometry unchanged — flagging is metadata-only
        return geometry

    def validate(self, original, fixed) -> bool:
        return True  # always succeeds
