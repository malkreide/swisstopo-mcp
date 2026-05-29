[English Version](README.md)

> **Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide)**

# swisstopo-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![Kein API-Schluessel](https://img.shields.io/badge/Auth-keiner%20erforderlich-brightgreen)](https://github.com/malkreide/swisstopo-mcp)
![CI](https://github.com/malkreide/swisstopo-mcp/actions/workflows/ci.yml/badge.svg)

> MCP-Server fuer schweizerische Bundesgeodaten -- Karten, Hoehenmodelle, Geocodierung, Katasterauszuege und herunterladbare Datensaetze via Swisstopo-APIs

---

## Uebersicht

`swisstopo-mcp` gibt KI-Assistenten Zugriff auf die offizielle schweizerische Geodateninfrastruktur ueber 13 Tools aus 6 API-Familien, alle ohne Authentifizierung:

| Quelle | Daten | API |
|--------|-------|-----|
| **Swisstopo REST API** | 500+ Geodaten-Layer (Gebaeude, Grenzen, Landnutzung) | REST/JSON |
| **Geocoding** | Amtliche Adressen, Ortsnamen, PLZ | REST/JSON |
| **Hoehenservice** | Hoehe ueber Meer, Hoehenprofile | REST/JSON |
| **STAC-Katalog** | Orthophotos, Hoehenmodelle, 3D-Gebaeude | STAC 0.9 |
| **WMTS** | Landeskarten, Luftbilder, Bauzonen | URL-Builder |
| **OEREB-Kataster** | Eigentumsbeschraenkungen, Grundstuecke | REST/JSON (kantonal) |

**Anker-Demo-Abfrage:** *"Welche Nutzungseinschraenkungen gelten fuer das Grundstueck an der Musterstrasse 5, Zuerich? Zeige mir den Standort auf einer Karte."*
[→ Weitere Anwendungsbeispiele nach Zielgruppe →](EXAMPLES.md)

---

## Funktionen

- 🗺️ **13 Tools** aus **6 API-Familien** (REST, Geocoding, Hoehe, STAC, WMTS, OEREB)
- 🔍 Schweizerische Adressen geocodieren und Koordinaten rueckwaerts geocodieren
- 🏔️ Hoehe ueber Meer abfragen und Hoehenprofile berechnen
- 📦 Geodatensaetze entdecken und herunterladen (Orthophotos, 3D-Gebaeude, historische Karten)
- 🏗️ Kartenobjekte an Koordinaten ueber 500+ Swisstopo-Layer identifizieren
- 🔗 Teilbare map.geo.admin.ch-Links generieren
- 📋 Grundstueck-IDs (EGRID) nachschlagen und OEREB-Auszuege abrufen
- 🔓 **Kein API-Schluessel erforderlich** fuer 11 von 13 Tools
- ☁️ **Dualer Transport** -- stdio (Claude Desktop) + Streamable HTTP (Cloud)

---

## Voraussetzungen

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (empfohlen) oder pip

---

## Installation

```bash
# Repository klonen
git clone https://github.com/malkreide/swisstopo-mcp.git
cd swisstopo-mcp

# Installieren
pip install -e .
# oder mit uv:
uv pip install -e .
```

Oder mit `uvx` (ohne dauerhafte Installation):

```bash
uvx swisstopo-mcp
```

---

## Schnellstart

```bash
# stdio (fuer Claude Desktop)
python -m swisstopo_mcp.server

# Streamable HTTP (Port 8000)
python -m swisstopo_mcp.server --http --port 8000
```

Sofort in Claude Desktop ausprobieren:

> *"Wo befindet sich die Bahnhofstrasse 1, Zuerich? Gib mir die Koordinaten."*
> *"Welche Hoehe hat der Uetliberg-Gipfel?"*
> *"Welche Gebaeude befinden sich bei den Koordinaten 2683500, 1247500 (LV95)?"*

---

## Konfiguration

### Claude Desktop

Editiere `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) bzw. `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

Oder mit `uvx`:

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

**Pfad zur Konfigurationsdatei:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Cloud-Deployment (SSE fuer Browser-Zugriff)

Fuer den Einsatz via **claude.ai im Browser** (z.B. auf verwalteten Arbeitsplaetzen ohne lokale Software):

**Render.com (empfohlen):**
1. Repository auf GitHub pushen/forken
2. Auf [render.com](https://render.com): New Web Service -> GitHub-Repo verbinden
3. Start-Befehl setzen: `python -m swisstopo_mcp.server --http --port 8000`
4. In claude.ai unter Settings -> MCP Servers eintragen: `https://your-app.onrender.com/sse`

---

## Verfuegbare Tools

### REST API (Layer- & Feature-Abfragen)

| Tool | Beschreibung |
|------|-------------|
| `swisstopo_search_layers` | Swisstopo-Layerkatalog (500+ Layer) nach Stichwort durchsuchen |
| `swisstopo_identify_features` | Kartenobjekte an einer bestimmten Koordinate finden (raeumliche Abfrage) |
| `swisstopo_find_features` | Features anhand eines Attributwerts in einem Layer suchen (z.B. Gebaeude nach EGID) |
| `swisstopo_get_feature` | Vollstaendige Attribute und Geometrie eines Features per ID abrufen |

### Geocoding

| Tool | Beschreibung |
|------|-------------|
| `swisstopo_geocode` | Schweizerische Adressen, Ortsnamen oder PLZ in Koordinaten umwandeln |
| `swisstopo_reverse_geocode` | Naechstgelegene Adresse zu gegebenen Koordinaten finden |

### Hoehenservice

| Tool | Beschreibung |
|------|-------------|
| `swisstopo_get_height` | Hoehe ueber Meer (m ue. M.) an einer Koordinate abfragen |
| `swisstopo_elevation_profile` | Hoehenprofil entlang einer Linie berechnen |

### STAC-Katalog (Geodaten-Downloads)

| Tool | Beschreibung |
|------|-------------|
| `swisstopo_search_geodata` | STAC-Katalog nach herunterladbaren Geodatensaetzen durchsuchen |
| `swisstopo_get_collection` | Details und Download-Links einer STAC-Collection abrufen |

### WMTS (Karten-URLs)

| Tool | Beschreibung |
|------|-------------|
| `swisstopo_map_url` | map.geo.admin.ch-URL zum Oeffnen im Browser generieren |

### OEREB-Kataster

| Tool | Beschreibung |
|------|-------------|
| `swisstopo_get_egrid` | Kataster-Grundstueck-ID (EGRID) aus Koordinaten ermitteln |
| `swisstopo_get_oereb_extract` | Oeffentlich-rechtliche Eigentumsbeschraenkungen (OEREB) fuer ein Grundstueck abrufen |

### Beispiel-Abfragen

| Abfrage | Tool |
|---------|------|
| *"Wo ist die Bahnhofstrasse 1, Zuerich?"* | `swisstopo_geocode` |
| *"Welche Hoehe hat der Uetliberg-Gipfel?"* | `swisstopo_get_height` |
| *"Welche Gebaeude bei Koordinaten 2683500, 1247500?"* | `swisstopo_identify_features` |
| *"Finde Orthophoto-Datensaetze zum Download"* | `swisstopo_search_geodata` |
| *"Zeige mir eine Karte von Bern bei Zoomstufe 10"* | `swisstopo_map_url` |
| *"Welche Einschraenkungen gelten fuer Musterstrasse 5?"* | `swisstopo_get_egrid` + `swisstopo_get_oereb_extract` |

---

## Architektur

```
┌─────────────────┐     ┌──────────────────────────────┐     ┌──────────────────────────┐
│   Claude / KI   │────▶│  swisstopo-mcp               │────▶│  Swisstopo REST API      │
│   (MCP Host)    │◀────│  (MCP Server)                │◀────│  api3.geo.admin.ch       │
└─────────────────┘     │                              │     ├──────────────────────────┤
                        │  13 Tools                    │────▶│  Geocoding               │
                        │  Stdio | Streamable HTTP     │◀────│  api3.geo.admin.ch       │
                        │                              │     ├──────────────────────────┤
                        │  Keine Authentifizierung     │────▶│  STAC-Katalog            │
                        │  (11 von 13 Tools)           │◀────│  data.geo.admin.ch       │
                        │                              │     ├──────────────────────────┤
                        │                              │────▶│  OEREB-Kataster          │
                        │                              │◀────│  (kantonale Endpunkte)   │
                        └──────────────────────────────┘     └──────────────────────────┘
```

---

## Projektstruktur

```
swisstopo-mcp/
├── src/swisstopo_mcp/
│   ├── __init__.py              # Package-Version
│   ├── server.py                # MCP-Server (Tool-Registrierungen)
│   ├── api_client.py            # Gemeinsamer HTTP-Client (httpx + Fehlerbehandlung)
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
├── README.md                    # Englische Hauptversion
└── README.de.md                 # Diese Datei (Deutsch)
```

---

## Sicherheit & Compliance

### Phase

Dieser Server ist in **Phase 1 — Read-only-Wrapper**. Alle 13 Tools sind
`readOnlyHint: true` / `destructiveHint: false`; es gibt keine schreibenden
oder versendenden Funktionen. Spätere Phasen siehe
[docs/roadmap.md](docs/roadmap.md).

### Lethal-Trifecta-Bewertung

| Fähigkeit | Status | Begründung |
|---|---|---|
| Zugriff auf private Daten | ❌ Nein | Nur Public Open Data (Bundes-/Kantonsgeodaten) |
| Exposition gegenüber untrusted Content | ⚠️ Eingeschränkt | Liest nur von einer fixen Allow-List vertrauenswürdiger geo.admin-/OEREB-Hosts |
| Externe Kommunikation (write/send) | ❌ Nein | Read-only; keine Mail-/Webhook-/Schreib-Tools |

Trifecta-Score: höchstens 1 von 3 — sicher konzipiert.

### Egress

Ausgehende Requests sind auf eine explizite Code-Layer-Allow-List beschränkt,
Redirects sind deaktiviert — siehe
[docs/network-egress.md](docs/network-egress.md).

### MCP-Protokollversion

Die MCP-Protokollversion wird vom `mcp`-SDK ausgehandelt; dieses ist in
`pyproject.toml` auf den `1.x`-Major gepinnt, damit ein Update die ausgehandelte
Version nicht stillschweigend ändert. SDK-Bumps werden monatlich via Dependabot
vorgeschlagen und in [CHANGELOG.md](CHANGELOG.md) dokumentiert.

## MCP-Primitive

Dieser Server exponiert bewusst **nur Tools** (keine Resources/Prompts):
Er ist ein Phase-1-Read-only-Wrapper, und jedes Resultat ist eine
parametrisierte Live-API-Abfrage statt ein statisches, adressierbares Dokument.
Resources/Prompts können in einer späteren Phase ergänzt werden.

---

## Bekannte Einschraenkungen

- **OEREB-Tools** erfordern einen Kantons-Parameter; nicht alle Kantone bieten dasselbe API-Format
- **STAC-Katalog** verwendet den Swisstopo-v0.9-Endpunkt; einige Collections haben ggf. unvollstaendige Metadaten
- **Geocoding** deckt nur Schweizer Adressen ab (kein Liechtenstein)
- **Rate Limits** werden von Swisstopo durchgesetzt; hochfrequente Nutzung kann gedrosselt werden

---

## Tests

```bash
# Unit-Tests (kein Netzwerk erforderlich)
pytest tests/ -m "not live"

# Integrationstests (Live-API-Aufrufe)
pytest tests/ -m "live"
```

---

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

---

## Mitwirken

Siehe [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Lizenz

MIT-Lizenz -- siehe [LICENSE](LICENSE)

Daten bereitgestellt von [swisstopo](https://www.swisstopo.admin.ch/) unter den Bedingungen von [Open Government Data](https://opendata.swiss/).

---

## Autor

Hayal Oezkan · [malkreide](https://github.com/malkreide)

---

## Credits & Verwandte Projekte

- **Swisstopo:** [www.swisstopo.admin.ch](https://www.swisstopo.admin.ch/) -- Bundesamt fuer Landestopografie
- **Swisstopo APIs:** [api3.geo.admin.ch](https://api3.geo.admin.ch/) / [data.geo.admin.ch](https://data.geo.admin.ch/)
- **Protokoll:** [Model Context Protocol](https://modelcontextprotocol.io/) -- Anthropic / Linux Foundation
- **Verwandt:** [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) -- Zuercher Open Data
- **Verwandt:** [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp) -- Schweizer oeffentlicher Verkehr
- **Verwandt:** [swiss-cultural-heritage-mcp](https://github.com/malkreide/swiss-cultural-heritage-mcp) -- Schweizer Kulturerbe
- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)
