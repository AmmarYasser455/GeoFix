"""Unit tests for the audit database."""


import pytest

from geofix.audit.database import AuditDatabase


@pytest.fixture
def db(tmp_dir):
    """Create a temp audit database."""
    db = AuditDatabase(tmp_dir / "test_audit.db")
    yield db
    db.close()


def _sample_entry(**overrides):
    base = {
        "timestamp": "2026-01-01T00:00:00",
        "session_id": "test_session",
        "feature_id": "feat_1",
        "error_type": "building_overlap",
        "error_id": "err_1",
        "fix_type": "delete",
        "tier": "rule_based",
        "confidence": 0.95,
        "reasoning": "test reasoning",
        "before_wkt": "POLYGON((0 0,10 0,10 10,0 10,0 0))",
        "after_wkt": None,
        "action": "applied",
        "validation_ok": 1,
        "new_errors": 0,
    }
    base.update(overrides)
    return base


class TestAuditDatabase:
    def test_insert_and_query(self, db):
        row_id = db.insert(_sample_entry())
        assert row_id > 0

        rows = db.query(feature_id="feat_1")
        assert len(rows) == 1
        assert rows[0]["feature_id"] == "feat_1"

    def test_query_by_session(self, db):
        db.insert(_sample_entry(session_id="s1", feature_id="a"))
        db.insert(_sample_entry(session_id="s2", feature_id="b"))

        rows = db.query(session_id="s1")
        assert len(rows) == 1
        assert rows[0]["feature_id"] == "a"

    def test_query_by_error_type(self, db):
        db.insert(_sample_entry(error_type="building_overlap"))
        db.insert(_sample_entry(error_type="invalid_geometry", feature_id="f2"))

        rows = db.query(error_type="invalid_geometry")
        assert len(rows) == 1

    def test_query_limit(self, db):
        for i in range(10):
            db.insert(_sample_entry(feature_id=f"feat_{i}"))

        rows = db.query(limit=3)
        assert len(rows) == 3

    def test_count(self, db):
        assert db.count() == 0
        db.insert(_sample_entry())
        db.insert(_sample_entry(feature_id="f2"))
        assert db.count() == 2

    def test_count_by_session(self, db):
        db.insert(_sample_entry(session_id="s1"))
        db.insert(_sample_entry(session_id="s1", feature_id="f2"))
        db.insert(_sample_entry(session_id="s2", feature_id="f3"))

        assert db.count(session_id="s1") == 2
        assert db.count(session_id="s2") == 1

    def test_schema_idempotent(self, tmp_dir):
        """Opening the database twice should not fail."""
        path = tmp_dir / "schema_test.db"
        db1 = AuditDatabase(path)
        db1.insert(_sample_entry())
        db1.close()

        db2 = AuditDatabase(path)
        assert db2.count() == 1
        db2.close()
