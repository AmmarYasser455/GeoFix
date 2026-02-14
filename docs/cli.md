# CLI Reference

GeoFix provides a command-line interface for quick data analysis.

## Usage

```bash
geofix [OPTIONS] COMMAND [ARGS]...
```

## Commands

### `analyze`

Analyse a geospatial file for quality issues.

```bash
geofix analyze FILE_PATH [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `FILE_PATH` | Path to a Shapefile, GeoJSON, or GeoPackage |

**Options:**

| Option | Description |
|--------|-------------|
| `--auto-fix` | Automatically fix invalid geometries |
| `-o, --output PATH` | Save result to this file |
| `--report [md\|html]` | Generate a quality report |

**Example:**

```bash
geofix analyze buildings.shp --auto-fix --output fixed.gpkg --report md
```

---

### `validate`

Validate a geospatial file without fixing anything.

```bash
geofix validate FILE_PATH
```

---

### `fix`

Auto-fix and save the corrected file.

```bash
geofix fix FILE_PATH OUTPUT
```

**Example:**

```bash
geofix fix buildings.shp corrected.gpkg
```

---

### `chat`

Launch the GeoFix AI chat interface.

```bash
geofix chat
```

This starts the Chainlit-powered conversational assistant where you can upload files and interact with GeoFix through natural language.

---

## Global Options

| Option | Description |
|--------|-------------|
| `--version` | Show version and exit |
| `--help` | Show help and exit |
