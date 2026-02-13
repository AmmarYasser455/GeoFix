"""High-level audit logger — converts FixResult/AuditEntry to DB rows."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from geofix.audit.database import AuditDatabase
from geofix.core.models import AuditEntry, FixAction, FixResult

logger = logging.getLogger("geofix.audit.logger")


class AuditLogger:
    """Records every fix attempt in the audit database.

    Usage::

        audit = AuditLogger(Path("geofix_audit.db"))
        audit.log_fix(result, feature_id="42", action=FixAction.APPLIED)
        history = audit.get_history(feature_id="42")
    """

    def __init__(self, db_path: Path, session_id: str | None = None):
        self.db = AuditDatabase(db_path)
        self.session_id = session_id or str(uuid.uuid4())[:8]

    def log_fix(
        self,
        result: FixResult,
        feature_id: str,
        action: FixAction,
    ) -> int:
        """Write one fix result to the audit log. Returns the row ID."""
        strategy = result.strategy
        entry = {
            "timestamp": result.timestamp.isoformat(),
            "session_id": self.session_id,
            "feature_id": feature_id,
            "error_type": strategy.error.error_type,
            "error_id": strategy.error.error_id,
            "fix_type": strategy.fix_type,
            "tier": strategy.tier.value,
            "confidence": strategy.confidence,
            "reasoning": strategy.reasoning,
            "before_wkt": (
                result.original_geometry.wkt
                if result.original_geometry
                else None
            ),
            "after_wkt": (
                result.fixed_geometry.wkt if result.fixed_geometry else None
            ),
            "action": action.value,
            "validation_ok": 1 if result.validation_passed else 0,
            "new_errors": result.new_errors_introduced,
        }
        row_id = self.db.insert(entry)
        logger.info(
            "Audit logged: feature=%s action=%s fix=%s conf=%.2f",
            feature_id,
            action.value,
            strategy.fix_type,
            strategy.confidence,
        )
        return row_id

    def log_entry(self, entry: AuditEntry) -> int:
        """Log a full AuditEntry dataclass."""
        return self.log_fix(
            result=entry.fix_result,
            feature_id=entry.feature_id,
            action=entry.action,
        )

    def get_history(
        self,
        feature_id: str | None = None,
        error_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query audit history with optional filters."""
        return self.db.query(
            feature_id=feature_id,
            session_id=None,
            error_type=error_type,
            limit=limit,
        )

    def get_session_summary(self) -> dict:
        """Summary of the current session's activity."""
        rows = self.db.query(session_id=self.session_id, limit=10000)
        total = len(rows)
        applied = sum(1 for r in rows if r["action"] == "applied")
        rolled_back = sum(1 for r in rows if r["action"] == "rolled_back")
        skipped = sum(1 for r in rows if r["action"] == "skipped")
        pending = sum(1 for r in rows if r["action"] == "pending_review")
        return {
            "session_id": self.session_id,
            "total_actions": total,
            "applied": applied,
            "rolled_back": rolled_back,
            "skipped": skipped,
            "pending_review": pending,
        }

    def close(self) -> None:
        self.db.close()
