# swisstopo-mcp v0.1.0

First public release of the MCP server for Swiss federal geodata via Swisstopo APIs.

## Features

**13 tools across 6 API families:**

- **REST API** (4 tools) — Layer search, feature identification, attribute search, feature details
- **Geocoding** (2 tools) — Address → coordinates and reverse
- **Height** (2 tools) — Elevation at a point, elevation profile along a line
- **STAC Catalog** (2 tools) — Search geodata collections, collection details
- **WMTS Maps** (1 tool) — Generate shareable map.geo.admin.ch URLs
- **ÖREB Cadastre** (2 tools) — Property ID lookup and public-law restrictions

## Highlights

- **WGS84-first API** — All tools accept lat/lon inputs; internal conversion to LV95 where required
- **272 tests passing** (264 unit + 8 live API tests)
- **No API key required** for 11 of 13 tools
- **German-localized output**, English codebase
- **Built for Python 3.11+**, following the same architecture as `zurich-opendata-mcp` and `swiss-transport-mcp`

## Use Cases

**Schulamt & Schulinfrastrukturplanung:**
Schuleinzugsgebiete mit Gemeindegrenzen und Gebäudedaten aus dem eidg. Gebäude-/Wohnungsregister (GWR) verknüpfen. Höhenprofile entlang von Schulwegen berechnen, um Barrierefreiheit und Steilheit zu analysieren. ÖREB-Auszüge für Schulliegenschaften abrufen, bevor Umbauprojekte gestartet werden — Bauzonen, Lärmbelastung und Altlasten auf einen Blick.

**Stadtverwaltung & Raumplanung:**
Bauzonen-Karten mit Bevölkerungsdaten verschneiden, um Standortentscheide für neue öffentliche Einrichtungen zu unterstützen. Amtliche Adressen geocodieren und in bestehende Verwaltungssysteme integrieren. Grundstücksinformationen via EGRID abrufen für Baubewilligungsverfahren.

**Interessierte Nutzer & Entwickler:**
Schweizweite Geodaten direkt in KI-gestützte Workflows einbinden — von der Immobilienanalyse über Wanderrouten-Planung (Höhenprofile) bis zur historischen Kartenrecherche via STAC-Katalog. In Kombination mit `zurich-opendata-mcp` und `swiss-transport-mcp` entsteht ein umfassendes Schweizer Open-Data-Ökosystem für Claude.

## Installation

```bash
pip install swisstopo-mcp
```

## Claude Desktop Config

```json
{
  "mcpServers": {
    "swisstopo": {
      "command": "swisstopo-mcp",
      "env": {
        "SWISSTOPO_OEREB_CANTONS": "ZH"
      }
    }
  }
}
```

## Links

- Repository: https://github.com/malkreide/swisstopo-mcp
- Documentation: see README.md
- Data source: https://api3.geo.admin.ch and https://data.geo.admin.ch/api/stac
