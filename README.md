# GeoFix 2.0: AI-Powered Geospatial Data Correction 🌍🤖

**GeoFix** is an autonomous AI agent that detects and fixes errors in geospatial data (Shapefiles, GeoJSON, GeoPackage). It runs **100% locally** using Ollama and Chainlit, providing a secure and free alternative to cloud-based solutions.

![GeoFix UI](public/avatars/GeoFix.png)

## Key Features

- **Local AI Intelligence**: Powered by **Llama 3.2** (via Ollama) for reasoning without data leaks.
- **Automated QC Pipeline**: Detects topology errors (overlaps, gaps, slivers) using OVC logic.
- **Conversational Interface**: Chat with your data ("Fix these errors", "Explain the logic").
- **Smart Model Switcher**: Toggle between **Speed** (Llama 3.2), **Smart** (Llama 3.1), and **Genius** (DeepSeek R1).
- **Professional UI**: Dark theme, CSS animations, and custom branding.
- **One-Click Export**: Download fixed datasets instantly.

## Quick Start

### Prerequisites
1.  **Python 3.10+**
2.  **[Ollama](https://ollama.com)** installed and running.
3.  Pull the required models:
    ```bash
    ollama run llama3.2
    ollama run llama3.1
    # Optional: ollama run deepseek-r1:14b
    ```

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/yourusername/geofix.git
    cd geofix
    ```

2.  Install dependencies:
    ```bash
    pip install -e .
    ```

3.  (Optional) Setup environment variables:
    Created a `.env` file if you want to use Google Gemini instead of Ollama.
    ```env
    GOOGLE_API_KEY=your_key_here
    ```

### Usage

Run the application:
```bash
geofix
# OR
chainlit run geofix/chat/app.py
```

Open your browser at **http://localhost:8080**.

## Logic & Tools

- **Profile Data**: Analyzes layer statistics and quality score.
- **Detect Errors**: Identifies OVC-standard errors (overlaps, invalid geometries).
- **Fix All**: Applies rule-based fixes first, then uses AI for complex cases.
- **Consult Encyclopedia**: Built-in knowledge base (RAG-lite) for GIS concepts.

## License

MIT License. Built by **Ammar Yasser Abdalazim**.
