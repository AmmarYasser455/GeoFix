# Core API

The main entry points for GeoFix — import directly from the package.

```python
import geofix

geofix.analyze("data.shp")
geofix.validate("data.shp")
geofix.fix("data.shp", "output.gpkg")
```

## Functions

::: geofix.api.analyze

::: geofix.api.validate

::: geofix.api.fix

## AnalysisResult

::: geofix.api.AnalysisResult

## Configuration

::: geofix.core.config.GeoFixConfig

::: geofix.core.config.LLMConfig

::: geofix.core.config.RouterConfig
