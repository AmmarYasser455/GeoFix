"""Shared test fixtures for GeoFix test suite."""

import tempfile
from pathlib import Path

import pytest

try:
    from shapely.geometry import box
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

from geofix.core.config import DEFAULT_CONFIG


@pytest.fixture
def tmp_dir():
    """Create a temporary directory, cleaned up after test."""
    with tempfile.TemporaryDirectory(prefix="geofix_test_") as d:
        yield Path(d)


@pytest.fixture
def config():
    return DEFAULT_CONFIG


@pytest.fixture
def sample_polygon():
    pytest.importorskip("shapely")
    return box(0, 0, 10, 10)


@pytest.fixture
def sample_polygon_b():
    pytest.importorskip("shapely")
    return box(5, 5, 15, 15)


@pytest.fixture
def sample_metadata():
    models = pytest.importorskip("geofix.core.models")
    return {
        "feat_a": models.FeatureMetadata(feature_id="feat_a", source="survey", accuracy_m=2.0),
        "feat_b": models.FeatureMetadata(feature_id="feat_b", source="survey", accuracy_m=10.0),
    }


@pytest.fixture
def overlap_error(sample_polygon):
    models = pytest.importorskip("geofix.core.models")
    return models.DetectedError(
        error_id="err_001",
        error_type="building_overlap",
        severity=models.ErrorSeverity.HIGH,
        geometry=sample_polygon,
        affected_features=["feat_a", "feat_b"],
        properties={"overlap_ratio": 0.99},
    )


@pytest.fixture
def invalid_geom_error():
    shapely = pytest.importorskip("shapely")
    models = pytest.importorskip("geofix.core.models")
    bowtie = shapely.geometry.Polygon([(0, 0), (10, 10), (10, 0), (0, 10)])
    return models.DetectedError(
        error_id="err_002",
        error_type="invalid_geometry",
        severity=models.ErrorSeverity.HIGH,
        geometry=bowtie,
        affected_features=["feat_c"],
    )
