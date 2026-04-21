> **Part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide)**

# swisstopo-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![No Auth Required](https://img.shields.io/badge/auth-none%20required-brightgreen)](https://github.com/malkreide/swisstopo-mcp)
![CI](https://github.com/malkreide/swisstopo-mcp/actions/workflows/ci.yml/badge.svg)

> MCP server for Swiss federal geodata -- maps, elevation, geocoding, cadastral extracts, and downloadable datasets via Swisstopo APIs

[Deutsche Version](README.de.md)

---

## Overview

`swisstopo-mcp` gives AI assistants access to Switzerland's official geodata infrastructure through 13 tools across 6 API families, all without authentication:

| Source | Data | API |
|--------|------|-----|
| **Swisstopo REST API** | 500+ geodata layers (buildings, boundaries, land use) | REST/JSON |
| **Geocoding** | Official addresses, place names, postal codes | REST/JSON |
| **Height Service** | Elevation above sea level, elevation profiles | REST/JSON |
| **STAC Catalog** | Orthophotos, elevation models, 3D buildings | STAC 0.9 |
| **WMTS** | National maps, aerial images, zoning maps | URL builder |
| **OEREB Cadastre** | Public-law restrictions, parcels | REST/JSON (cantonal) |

**Anchor demo query:** *"What land-use restrictions apply to the parcel at Musterstrasse 5, Zurich? Show me the location on a map."*
[→ More use cases by audience →](EXAMPLES.md)

---

## Features

- 🗺️ **13 tools** across **6 API families** (REST, Geocoding, Height, STAC, WMTS, OEREB)
- 🔍 Geocode Swiss addresses and reverse-geocode coordinates
- 🏔️ Query elevation and compute elevation profiles
- 📦 Discover and download geodatasets (orthophotos, 3D buildings, historical maps)
- 🏗️ Identify map features at coordinates across 500+ Swisstopo layers
- 🔗 Generate shareable map.geo.admin.ch links
- 📋 Look up cadastral property IDs (EGRID) and retrieve OEREB extracts
- 🔓 **No API key required** for 11 of 13 tools
- ☁️ **Dual transport** -- stdio (Claude Desktop) + Streamable HTTP (cloud)

---

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

---

## Installation

```bash
# Clone the repository
git clone https://github.com/malkreide/swisstopo-mcp.git
cd swisstopo-mcp

# Install
pip install -e .
# or with uv:
uv pip install -e .
```

Or with `uvx` (no permanent installation):

```bash
uvx swisstopo-mcp
```

---

## Quickstart

```bash
# stdio (for Claude Desktop)
python -m swisstopo_mcp.server

# Streamable HTTP (port 8000)
python -m swisstopo_mcp.server --http --port 8000
```

Try it immediately in Claude Desktop:

> *"Where is Bahnhofstrasse 1, Zurich? Give me the coordinates."*
> *"What is the elevation at the Uetliberg summit?"*
> *"What buildings are at coordinates 2683500, 1247500 (LV95)?"*

---

## Configuration

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "swisstopo": {
      "command": "python",
      "args": ["-m", "swisstopo_mcp.server"]
    }
  }
}
```

Or with `uvx`:

```json
{
  "mcpServers": {
    "swisstopo": {
      "command": "uvx",
      "args": ["swisstopo-mcp"]
    }
  }
}
```

**Config file locations:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Cloud Deployment (SSE for browser access)

For use via **claude.ai in the browser** (e.g. on managed workstations without local software):

**Render.com (recommended):**
1. Push/fork the repository to GitHub
2. On [render.com](https://render.com): New Web Service -> connect GitHub repo
3. Set start command: `python -m swisstopo_mcp.server --http --port 8000`
4. In claude.ai under Settings -> MCP Servers, add: `https://your-app.onrender.com/sse`

---

## Available Tools

### REST API (Layer & Feature Queries)

| Tool | Description |
|------|-------------|
| `swisstopo_search_layers` | Search the Swisstopo layer catalog (500+ layers) by keyword |
| `swisstopo_identify_features` | Find map features at a specific coordinate (spatial query) |
| `swisstopo_find_features` | Search features by attribute value within a layer (e.g. buildings by EGID) |
| `swisstopo_get_feature` | Retrieve full attributes and geometry for a feature by ID |

### Geocoding

| Tool | Description |
|------|-------------|
| `swisstopo_geocode` | Convert Swiss addresses, place names, or postal codes to coordinates |
| `swisstopo_reverse_geocode` | Find the nearest address for given coordinates |

### Height Service

| Tool | Description |
|------|-------------|
| `swisstopo_get_height` | Get elevation above sea level (m a.s.l.) at a coordinate |
| `swisstopo_elevation_profile` | Compute an elevation profile along a line |

### STAC Catalog (Geodata Downloads)

| Tool | Description |
|------|-------------|
| `swisstopo_search_geodata` | Search the STAC catalog for downloadable geodatasets |
| `swisstopo_get_collection` | Get details and download links for a STAC collection |

### WMTS (Map URLs)

| Tool | Description |
|------|-------------|
| `swisstopo_map_url` | Generate a map.geo.admin.ch URL for browser display |

### OEREB Cadastre

| Tool | Description |
|------|-------------|
| `swisstopo_get_egrid` | Resolve a cadastral property ID (EGRID) from coordinates |
| `swisstopo_get_oereb_extract` | Retrieve public-law land-use restrictions (OEREB) for a parcel |

### Example Use Cases

| Query | Tool |
|-------|------|
| *"Where is Bahnhofstrasse 1, Zurich?"* | `swisstopo_geocode` |
| *"What is the elevation at the Uetliberg summit?"* | `swisstopo_get_height` |
| *"What buildings are at coordinates 2683500, 1247500?"* | `swisstopo_identify_features` |
| *"Find orthophoto datasets for download"* | `swisstopo_search_geodata` |
| *"Show me a map of Bern at zoom level 10"* | `swisstopo_map_url` |
| *"What restrictions apply to parcel at Musterstrasse 5?"* | `swisstopo_get_egrid` + `swisstopo_get_oereb_extract` |

---

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────┐     ┌──────────────────────────┐
│   Claude / AI   │────▶│  swisstopo-mcp               │────▶│  Swisstopo REST API      │
│   (MCP Host)    │◀────│  (MCP Server)                │◀────│  api3.geo.admin.ch       │
└─────────────────┘     │                              │     ├──────────────────────────┤
                        │  13 Tools                    │────▶│  Geocoding               │
                        │  Stdio | Streamable HTTP     │◀────│  api3.geo.admin.ch       │
                        │                              │     ├──────────────────────────┤
                        │  No authentication required  │────▶│  STAC Catalog            │
                        │  (11 of 13 tools)            │◀────│  data.geo.admin.ch       │
                        │                              │     ├──────────────────────────┤
                        │                              │────▶│  OEREB Cadastre          │
                        │                              │◀────│  (cantonal endpoints)    │
                        └──────────────────────────────┘     └──────────────────────────┘
```

---

## Project Structure

```
swisstopo-mcp/
├── src/swisstopo_mcp/
│   ├── __init__.py              # Package version
│   ├── server.py                # MCP server wiring (tool registrations)
│   ├── api_client.py            # Shared HTTP client (httpx + error handling)
│   ├── geocoding.py             # swisstopo_geocode, swisstopo_reverse_geocode
│   ├── rest_api.py              # swisstopo_search_layers, identify, find, get_feature
│   ├── height.py                # swisstopo_get_height, swisstopo_elevation_profile
│   ├── stac.py                  # swisstopo_search_geodata, swisstopo_get_collection
│   ├── wmts.py                  # swisstopo_map_url
│   └── oereb.py                 # swisstopo_get_egrid, swisstopo_get_oereb_extract
├── tests/
│   ├── test_api_client.py
│   ├── test_geocoding.py
│   ├── test_height.py
│   ├── test_oereb.py
│   ├── test_rest_api.py
│   ├── test_stac.py
│   └── test_wmts.py
├── .github/workflows/ci.yml     # GitHub Actions (Python 3.11/3.12/3.13)
├── pyproject.toml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md                    # This file (English)
└── README.de.md                 # German version
```

---

## Known Limitations

- **OEREB tools** require a canton parameter; not all cantons expose the same API format
- **STAC catalog** uses Swisstopo's v0.9 endpoint; some collections may lack complete metadata
- **Geocoding** covers Swiss addresses only (no Liechtenstein)
- **Rate limits** are enforced by Swisstopo; high-frequency usage may be throttled

---

## Testing

```bash
# Unit tests (no network required)
pytest tests/ -m "not live"

# Integration tests (live API calls)
pytest tests/ -m "live"
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## License

MIT License -- see [LICENSE](LICENSE)

Data provided by [swisstopo](https://www.swisstopo.admin.ch/) under [Open Government Data](https://opendata.swiss/) terms.

---

## Author

Hayal Oezkan · [malkreide](https://github.com/malkreide)

---

## Credits & Related Projects

- **Swisstopo:** [www.swisstopo.admin.ch](https://www.swisstopo.admin.ch/) -- Swiss Federal Office of Topography
- **Swisstopo APIs:** [api3.geo.admin.ch](https://api3.geo.admin.ch/) / [data.geo.admin.ch](https://data.geo.admin.ch/)
- **Protocol:** [Model Context Protocol](https://modelcontextprotocol.io/) -- Anthropic / Linux Foundation
- **Related:** [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) -- Zurich city open data
- **Related:** [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp) -- Swiss public transport
- **Related:** [swiss-cultural-heritage-mcp](https://github.com/malkreide/swiss-cultural-heritage-mcp) -- Swiss cultural heritage
- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)
