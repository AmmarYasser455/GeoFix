"""Tests for the one-liner API (geofix.analyze, geofix.validate, geofix.fix)."""


import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from geofix.api import AnalysisResult, analyze, fix, validate


@pytest.fixture
def sample_polygons(tmp_path):
    """Create a valid polygon shapefile for testing."""
    polys = [
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        Polygon([(2, 2), (3, 2), (3, 3), (2, 3)]),
    ]
    gdf = gpd.GeoDataFrame(
        {"name": ["A", "B"]},
        geometry=polys,
        crs="EPSG:4326",
    )
    path = tmp_path / "polygons.shp"
    gdf.to_file(path)
    return path


@pytest.fixture
def overlapping_polygons(tmp_path):
    """Create polygons with a deliberate overlap."""
    polys = [
        Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),
        Polygon([(1, 1), (3, 1), (3, 3), (1, 3)]),  # overlaps
    ]
    gdf = gpd.GeoDataFrame(
        {"name": ["A", "B"]},
        geometry=polys,
        crs="EPSG:4326",
    )
    path = tmp_path / "overlapping.shp"
    gdf.to_file(path)
    return path


class TestAnalyze:
    def test_basic_analysis(self, sample_polygons):
        result = analyze(sample_polygons)
        assert isinstance(result, AnalysisResult)
        assert result["feature_count"] == 2
        assert result["quality_score"] > 0
        assert result["error_count"] == 0

    def test_detects_overlaps(self, overlapping_polygons):
        result = analyze(overlapping_polygons)
        assert result["error_count"] > 0
        assert len(result["overlaps"]) > 0

    def test_repr(self, sample_polygons):
        result = analyze(sample_polygons)
        r = repr(result)
        assert "AnalysisResult" in r
        assert "features=2" in r

    def test_summary(self, sample_polygons):
        result = analyze(sample_polygons)
        s = result.summary()
        assert "GeoFix" in s
        assert "Quality score" in s

    def test_output_saves_file(self, sample_polygons, tmp_path):
        out = tmp_path / "output.shp"
        analyze(sample_polygons, output=out)
        assert out.exists()

    def test_auto_fix(self, sample_polygons):
        result = analyze(sample_polygons, auto_fix=True)
        assert result["auto_fixed"] is True

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            analyze("nonexistent.shp")

    def test_unsupported_format(self, tmp_path):
        bad = tmp_path / "data.xyz"
        bad.write_text("not a geo file")
        with pytest.raises(ValueError, match="Unsupported format"):
            analyze(bad)

    def test_report_md(self, sample_polygons, tmp_path):
        # Copy shapefile to tmp to keep report next to it
        import shutil

        dest = tmp_path / "data.shp"
        for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
            src = sample_polygons.with_suffix(ext)
            if src.exists():
                shutil.copy(src, tmp_path / f"data{ext}")

        analyze(dest, report="md")
        report = dest.with_suffix(".report.md")
        assert report.exists()
        content = report.read_text()
        assert "GeoFix Quality Report" in content


class TestValidate:
    def test_returns_result(self, sample_polygons):
        result = validate(sample_polygons)
        assert isinstance(result, AnalysisResult)
        assert result["auto_fixed"] is False


class TestFix:
    def test_fix_and_save(self, sample_polygons, tmp_path):
        out = tmp_path / "fixed.shp"
        result = fix(sample_polygons, out)
        assert out.exists()
        assert isinstance(result, AnalysisResult)
