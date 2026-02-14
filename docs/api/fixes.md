# Fix Operations

GeoFix includes a registry of geometry correction algorithms.

## Fix Registry

::: geofix.fixes.registry.FixRegistry

::: geofix.fixes.registry.build_default_registry

## Base Class

::: geofix.fixes.base.FixOperation

## Built-in Operations

| Fix Name | Description | Module |
|----------|-------------|--------|
| `make_valid` | Repairs invalid geometries via `buffer(0)` | `geometry.py` |
| `simplify` | Reduces vertex count while preserving topology | `geometry.py` |
| `delete` | Removes a feature entirely | `overlap.py` |
| `trim` | Trims overlapping areas | `overlap.py` |
| `merge` | Merges overlapping features | `overlap.py` |
| `snap` | Snaps vertices to nearby features | `overlap.py` |
| `clip` | Clips features to boundary | `boundary.py` |
| `nudge` | Nudges features away from roads | `road.py` |
| `flag` | Flags for human review (no-op) | `registry.py` |
