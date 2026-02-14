# Quick Start

Get up and running with GeoFix in 5 minutes.

## 1. Analyse your data

```python
import geofix

result = geofix.analyze("buildings.shp")
print(result.summary())
```

Output:

```
📊 GeoFix Analysis Results
   Features:      1,247
   Geometry type:  Polygon
   CRS:            EPSG:4326
   Quality score:  87/100
   Total errors:   12
   Error breakdown:
     • invalid_geometry: 5
     • overlap: 7
```

## 2. Auto-fix errors

```python
result = geofix.analyze("buildings.shp", auto_fix=True, output="fixed.gpkg")
```

GeoFix repairs invalid geometries using `buffer(0)` — a standard technique that resolves self-intersections without changing the shape.

## 3. Generate a report

```python
geofix.analyze("buildings.shp", report="md")
# Creates buildings.report.md alongside your data
```

## 4. Use the CLI

```bash
# Analyse
geofix analyze buildings.shp

# Fix and save
geofix fix buildings.shp corrected.gpkg

# Generate report
geofix analyze buildings.shp --report md

# Launch chat assistant
geofix chat
```

## 5. Launch the AI assistant

```bash
geofix chat
```

Upload files directly in the chat interface for interactive analysis, error detection, and AI-powered fix recommendations.

## What's next?

- [API Reference](api/core.md) — full Python API
- [CLI Reference](cli.md) — all CLI commands and options
