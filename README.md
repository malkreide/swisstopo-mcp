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

## Security & Compliance

### Phase

This server is in **Phase 1 — Read-only wrapper**. All 13 tools are
`readOnlyHint: true` / `destructiveHint: false`; there are no write or send
capabilities. See [docs/roadmap.md](docs/roadmap.md) for later phases.

### Lethal Trifecta assessment

| Capability | Status | Rationale |
|---|---|---|
| Access to private data | ❌ No | Public Open Data only (federal/cantonal geodata) |
| Exposure to untrusted content | ⚠️ Limited | Reads only from a fixed allow-list of trusted geo.admin / OEREB hosts |
| External communication (write/send) | ❌ No | Read-only; no mail/webhook/write tools |

Trifecta score: at most 1 of 3 — safe by design.

### Egress

Outbound requests are restricted to an explicit code-layer allow-list and
redirects are disabled — see [docs/network-egress.md](docs/network-egress.md).

### Container deployment

For containerised HTTP deployments, a hardened `Dockerfile` and Kubernetes
manifests (non-root, read-only root filesystem, dropped capabilities, egress
NetworkPolicy) are provided — see [docs/deployment.md](docs/deployment.md).

### MCP Protocol Version

The MCP protocol version is negotiated by the `mcp` SDK, which is pinned to the
`1.x` major in `pyproject.toml` so an update cannot silently change the
negotiated version. SDK bumps are proposed monthly via Dependabot and tracked
in [CHANGELOG.md](CHANGELOG.md).

### Sessions & Authentication

The server is unauthenticated by design — it serves only public open data. Over
HTTP, session IDs are managed entirely by the FastMCP framework; there is no
per-user state, so there is nothing user-specific to bind a session to. If an
authenticated deployment is ever introduced, session IDs must be bound to the
validated user identity (audit finding SEC-009).

### Error handling

- **Execution errors** (upstream failure, invalid value) are returned as a
  `ToolResponse` with `is_error: true` and a user-friendly `summary`; raw
  exception text is never leaked to the client (it is logged to stderr instead).
- **Protocol errors** (unknown tool, malformed/invalid arguments) are emitted by
  the MCP SDK as JSON-RPC errors with standard codes (e.g. `-32602` invalid
  params). Input validation happens at the Pydantic boundary (SEC-018).

## MCP Primitives

This server intentionally exposes **Tools only** (no Resources or Prompts):
it is a Phase-1 read-only wrapper, and every result is a live, parameterised
API query rather than a static addressable document. Resources/Prompts may be
added in a later phase if stable URI schemes emerge.

### Tool workflows

Most tools return a thought-complete result in a single call. Two domains use a
short, documented discovery chain (each tool's description states the next step):

- **Feature query:** `swisstopo_search_layers` (find layer IDs) →
  `swisstopo_identify_features` / `swisstopo_find_features` →
  `swisstopo_get_feature` (full detail).
- **Cadastre:** `swisstopo_geocode` → `swisstopo_get_egrid` →
  `swisstopo_get_oereb_extract`.
- **Downloads:** `swisstopo_search_geodata` → `swisstopo_get_collection`.

---

## Response Format

Every tool returns a structured `ToolResponse` (FastMCP emits it as structured
content with an output schema, plus a JSON text block):

| Field | Meaning |
|---|---|
| `summary` | Human-readable Markdown summary |
| `results` | Machine-readable structured records |
| `count` | Number of `results` |
| `match_type` | `exact` / `fuzzy` / `none` (search-style tools) |
| `source` / `license` | Data attribution (OGD-CH, CC/OGD terms) |
| `provenance` / `retrieved_at` | How and when the data was obtained |
| `is_error` | `true` for handled errors |

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
