# Installation

## Requirements

- Python 3.10+
- GDAL/GEOS libraries (included with `geopandas`)

## Install from PyPI

```bash
pip install geofix
```

## Install from source

```bash
git clone https://github.com/AmmarYasser455/GeoFix.git
cd GeoFix
pip install -e ".[dev]"
```

## Optional: Documentation tools

```bash
pip install -e ".[docs]"
mkdocs serve   # preview docs at http://localhost:8000
```

## Verify installation

```bash
geofix --version
python -c "import geofix; print(geofix.__version__)"
```

## LLM Setup (for chat mode)

GeoFix's chat interface uses LLMs via Ollama or Google Gemini.

### Option A: Ollama (local, free)

```bash
# Install Ollama from https://ollama.com
ollama pull llama3.2
```

### Option B: Google Gemini

Create a `.env` file:

```
GOOGLE_API_KEY=your_key_here
LLM_PROVIDER=gemini
```
