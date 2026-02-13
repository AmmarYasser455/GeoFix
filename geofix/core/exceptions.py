"""GeoFix custom exceptions."""

from __future__ import annotations


class GeoFixError(Exception):
    """Base exception for all GeoFix errors."""


class DataLoadError(GeoFixError):
    """Raised when input data cannot be loaded or is invalid."""


class FixOperationError(GeoFixError):
    """Raised when a fix operation fails."""


class ValidationError(GeoFixError):
    """Raised when post-fix validation detects a regression."""


class DecisionError(GeoFixError):
    """Raised when the decision engine cannot determine a fix strategy."""


class LLMError(GeoFixError):
    """Raised when the LLM API call fails or returns unparseable output."""


class AuditError(GeoFixError):
    """Raised when audit logging fails."""
