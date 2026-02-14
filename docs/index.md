# GeoFix

<div align="center">

**AI-powered geospatial data quality and correction**

[![PyPI](https://img.shields.io/pypi/v/geofix)](https://pypi.org/project/geofix/)
[![Tests](https://github.com/AmmarYasser455/GeoFix/actions/workflows/ci.yml/badge.svg)](https://github.com/AmmarYasser455/GeoFix/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## What is GeoFix?

GeoFix is an **autonomous geospatial data quality assistant** that detects and fixes errors in spatial datasets. It combines deterministic geometry algorithms with AI-powered reasoning.

### Features

- **🔍 Detect** — overlaps, boundary violations, invalid geometries, duplicates
- **🔧 Fix** — auto-correct errors with audited, reversible operations
- **💬 Chat** — conversational AI interface for interactive data analysis
- **📊 Profile** — comprehensive data quality metrics and scoring

## Quick Start

```python
import geofix

# One-liner analysis
result = geofix.analyze("data.shp")
print(result.summary())

# Auto-fix and save
geofix.fix("data.shp", "corrected.gpkg")
```

Or from the command line:

```bash
geofix analyze data.shp --auto-fix --output fixed.gpkg
geofix chat   # launch AI assistant
```

## Installation

```bash
pip install geofix
```

## Next Steps

- [Installation Guide](installation.md) — detailed setup instructions
- [Quick Start Tutorial](quick-start.md) — 5-minute walkthrough
- [API Reference](api/core.md) — full Python API documentation
- [CLI Reference](cli.md) — command-line usage
