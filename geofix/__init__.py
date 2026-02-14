"""GeoFix — Autonomous geospatial data correction with conversational AI.

One-liner API::

    import geofix

    geofix.analyze("data.shp")
    geofix.analyze("data.shp", auto_fix=True, output="fixed.shp")
    geofix.validate("data.shp")
    geofix.fix("data.shp", "corrected.gpkg")
"""

__version__ = "2.1.0"
__author__ = "Ammar Yasser Abdalazim"

from geofix.api import AnalysisResult, analyze, fix, validate

__all__ = ["analyze", "validate", "fix", "AnalysisResult", "__version__"]
