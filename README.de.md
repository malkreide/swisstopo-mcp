> 🇨🇭 **Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide)**

# 🗺️ swisstopo-mcp

![Version](https://img.shields.io/badge/version-0.2.0-blue)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![Kein API-Schluessel](https://img.shields.io/badge/Auth-keiner%20erforderlich-brightgreen)](https://github.com/malkreide/swisstopo-mcp)
![CI](https://github.com/malkreide/swisstopo-mcp/actions/workflows/ci.yml/badge.svg)

> MCP-Server fuer schweizerische Bundesgeodaten -- Karten, Hoehenmodelle, Geocodierung, Katasterauszuege und herunterladbare Datensaetze via Swisstopo-APIs

[🇬🇧 English Version](README.md)

---

## Uebersicht

`swisstopo-mcp` gibt KI-Assistenten Zugriff auf die offizielle schweizerische Geodateninfrastruktur ueber 19 Tools, alle ohne Authentifizierung:

| Quelle | Daten | API |
|--------|-------|-----|
| **Swisstopo REST API** | 500+ Geodaten-Layer (Gebaeude, Grenzen, Landnutzung) | REST/JSON |
| **Geocoding** | Amtliche Adressen, Ortsnamen, PLZ | REST/JSON |
| **Hoehenservice** | Hoehe ueber Meer, Hoehenprofile | REST/JSON |
| **STAC-Katalog** | Orthophotos, Hoehenmodelle, 3D-Gebaeude | STAC 0.9 |
| **WMTS** | Landeskarten, Luftbilder, Bauzonen | URL-Builder |
| **OEREB-Kataster** | Eigentumsbeschraenkungen, Grundstuecke | REST/JSON (kantonal) |
| **geodienste.ch** | Interkantonale Basisgeodaten (amtliche Vermessung, belastete Standorte, Gefahrenkarten, …) | OGC API Features / WMS / WFS |
| **OpenStreetMap** | Points of Interest (Schulen, Spielplaetze, Apotheken, …) | Overpass API (ODbL) |
| **OpenPLZ API** | Administrative Adressebene: PLZ → Gemeinde (**BFS-Nummer**) → Bezirk → Kanton | REST/JSON (BFS + swisstopo OGD) |

**Anker-Demo-Abfrage:** *«Welche Gemeinden liegen im Bezirk Uster, und wie lauten ihre BFS-Nummern fuer die Verknuepfung mit BFS-Statistikdaten?»*
(Die BFS-Gemeindenummer ist der amtliche Join-Schluessel zu [`swiss-statistics-mcp`](https://github.com/malkreide) und [`zurich-opendata-mcp`](https://github.com/malkreide/zurich-opendata-mcp) — damit wird aus dem Geodaten-Wrapper ein semantischer Konnektor auf Gemeindeebene.)
[→ Weitere Anwendungsbeispiele nach Zielgruppe →](EXAMPLES.md)

---

## Funktionen

- 🗺️ **19 Tools** (REST, Geocoding, Hoehe, STAC, WMTS, OEREB, geodienste.ch, OpenStreetMap/Overpass, OpenPLZ)
- 🏛️ Administrative Adressebene aufloesen (PLZ → Gemeinde/**BFS-Nummer** → Bezirk → Kanton) via OpenPLZ
- 🔍 Schweizerische Adressen geocodieren und Koordinaten rueckwaerts geocodieren
- 🏔️ Hoehe ueber Meer abfragen und Hoehenprofile berechnen
- 📦 Geodatensaetze entdecken und herunterladen (Orthophotos, 3D-Gebaeude, historische Karten)
- 🏗️ Kartenobjekte an Koordinaten ueber 500+ Swisstopo-Layer identifizieren
- 🔗 Teilbare map.geo.admin.ch-Links generieren
- 📋 Grundstueck-IDs (EGRID) nachschlagen und OEREB-Auszuege abrufen
- 🔓 **Kein API-Schluessel erforderlich** fuer alle Tools (OEREB-Auszug benoetigt einen unterstuetzten Kanton)
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

### Konsolidierte Geodaten-Fassade

Eine Fassade ueber mehrere Karten-/Layer-Quellen, bewusst unter dem 18-Tool-Budget
(siehe [`docs/geodaten-erweiterung-phase1.md`](docs/geodaten-erweiterung-phase1.md)):

| Tool | Beschreibung |
|------|-------------|
| `list_available_layers` | Layer-Kennungen fuer `query_geodata` entdecken (`strassenverzeichnis`, `oereb-verfuegbarkeit`, `geodienste:<topic>:<KANTON>`); zeigt nur ohne Vertrag frei nutzbare geodienste-Datensaetze |
| `query_geodata` | Gewaehlten Layer per `point` / `bbox` / `commune` abfragen — amtliches Strassenverzeichnis, interkantonale geodienste.ch-Daten (OGC API Features) oder ÖREB-Verfuegbarkeit |
| `query_osm_features` | OpenStreetMap-POIs (Schulen, Spielplaetze, Apotheken, …) im Umkreis via Overpass — separate Quelle, ODbL (© OpenStreetMap contributors) |

### Administrative Adressebene (OpenPLZ)

Die amtliche Adresshierarchie **PLZ → Gemeinde → Bezirk → Kanton**, geliefert von
der [OpenPLZ API](https://openplzapi.org) (Daten: BFS-Gemeindeverzeichnis +
swisstopo-Strassenverzeichnis, Swiss OGD — eine **separate Quelle und Lizenz**
gegenueber den swisstopo-Geodaten oben). Jede Antwort mit Gemeinde exponiert
`bfs_commune_number` als benanntes Top-Level-Feld: den amtlichen **Join-Schluessel**
zu BFS-Statistikdaten (`swiss-statistics-mcp`) und zu `zurich-opendata-mcp`.

| Tool | Beschreibung |
|------|-------------|
| `lookup_postal_code` | Schweizer PLZ aufloesen → Ort, Gemeinde (+**BFS-Nummer**), Bezirk, Kanton |
| `find_commune` | Gemeinde in beide Richtungen aufloesen (`name` ↔ `bfs_number`) oder alle Gemeinden eines `canton` / `district` auflisten. Akzeptiert Kantonskuerzel (`ZH`) oder Schluessel (`1`); die Aufloesung erfolgt serverseitig |
| `search_address` | Volltextsuche ueber Schweizer Strassen und Ortschaften, je Treffer mit Gemeinde und BFS-Nummer |

### Beispiel-Abfragen

| Abfrage | Tool |
|---------|------|
| *"Wo ist die Bahnhofstrasse 1, Zuerich?"* | `swisstopo_geocode` |
| *"Welche Hoehe hat der Uetliberg-Gipfel?"* | `swisstopo_get_height` |
| *"Welche Gebaeude bei Koordinaten 2683500, 1247500?"* | `swisstopo_identify_features` |
| *"Finde Orthophoto-Datensaetze zum Download"* | `swisstopo_search_geodata` |
| *"Zeige mir eine Karte von Bern bei Zoomstufe 10"* | `swisstopo_map_url` |
| *"Welche Einschraenkungen gelten fuer Musterstrasse 5?"* | `swisstopo_get_egrid` + `swisstopo_get_oereb_extract` |
| *"Welche Schulhaeuser liegen im Umkreis von 500 m um Bederstrasse 109, 8002 Zuerich, und welche Strassen fuehren dorthin?"* | `query_osm_features` + `query_geodata` (`strassenverzeichnis`) |
| *"Welche Daten zu belasteten Standorten sind fuer den Kanton ZH frei?"* | `list_available_layers` + `query_geodata` (`geodienste:kataster_belasteter_standorte:ZH`) |
| *«Welche Gemeinden liegen im Bezirk Uster und wie lauten ihre BFS-Nummern?»* | `find_commune` (`district=109`) |
| *«Zu welcher Gemeinde und welchem Kanton gehoert die PLZ 8001?»* | `lookup_postal_code` |
| *«Wie lautet die BFS-Nummer von Winterthur (zur Verknuepfung mit BFS-Statistik)?»* | `find_commune` (`name=Winterthur`) |

---

## Architektur

```
┌─────────────────┐     ┌──────────────────────────────┐     ┌──────────────────────────┐
│   Claude / KI   │────▶│  swisstopo-mcp               │────▶│  Swisstopo REST API      │
│   (MCP Host)    │◀────│  (MCP Server)                │◀────│  api3.geo.admin.ch       │
└─────────────────┘     │                              │     ├──────────────────────────┤
                        │  19 Tools                    │────▶│  Geocoding               │
                        │  Stdio | Streamable HTTP     │◀────│  api3.geo.admin.ch       │
                        │                              │     ├──────────────────────────┤
                        │  Keine Authentifizierung     │────▶│  STAC-Katalog            │
                        │  (alle Tools; OEREB-Kanton)  │◀────│  data.geo.admin.ch       │
                        │                              │     ├──────────────────────────┤
                        │                              │────▶│  OEREB-Kataster          │
                        │                              │◀────│  (kantonale Endpunkte)   │
                        │                              │     ├──────────────────────────┤
                        │                              │────▶│  geodienste.ch (OGC API) │
                        │                              │◀────│  overpass.osm.ch (ODbL)  │
                        │                              │     ├──────────────────────────┤
                        │  BFS-Nr = Join-Schluessel zu │────▶│  OpenPLZ API             │
                        │  swiss-statistics-mcp        │◀────│  openplzapi.org (BFS/OGD)│
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
│   ├── oereb.py                 # swisstopo_get_egrid, swisstopo_get_oereb_extract
│   ├── geodata.py               # query_geodata + list_available_layers (Fassade)
│   ├── overpass.py              # query_osm_features (OpenStreetMap / Overpass)
│   └── openplz.py               # lookup_postal_code, find_commune, search_address (OpenPLZ)
├── tests/
│   ├── test_api_client.py
│   ├── test_geocoding.py
│   ├── test_height.py
│   ├── test_oereb.py
│   ├── test_openplz.py
│   ├── test_rest_api.py
│   ├── test_stac.py
│   └── test_wmts.py
├── .github/workflows/ci.yml     # GitHub Actions (Python 3.11/3.12/3.13)
├── pyproject.toml
├── CHANGELOG.md
├── CONTRIBUTING.md               # Mitwirken (Englisch)
├── CONTRIBUTING.de.md            # Mitwirken (Deutsch)
├── SECURITY.md                   # Sicherheitsrichtlinie (Englisch)
├── SECURITY.de.md                # Sicherheitsrichtlinie (Deutsch)
├── LICENSE
├── README.md                    # Englische Hauptversion
└── README.de.md                 # Diese Datei (Deutsch)
```

---

## Sicherheit & Compliance

Die vollständige Sicherheitsrichtlinie und Sicherheitslage ist in
[SECURITY.de.md](SECURITY.de.md) dokumentiert.

### Phase

Dieser Server ist in **Phase 1 — Read-only-Wrapper**. Alle 19 Tools sind
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

### Container-Deployment

Für containerisierte HTTP-Deployments stehen ein gehärtetes `Dockerfile` und
Kubernetes-Manifeste bereit (non-root, read-only Root-Dateisystem, gedroppte
Capabilities, Egress-NetworkPolicy) — siehe
[docs/deployment.md](docs/deployment.md).

### MCP-Protokollversion

Die MCP-Protokollversion wird vom `mcp`-SDK ausgehandelt; dieses ist in
`pyproject.toml` auf den `1.x`-Major gepinnt, damit ein Update die ausgehandelte
Version nicht stillschweigend ändert. SDK-Bumps werden monatlich via Dependabot
vorgeschlagen und in [CHANGELOG.md](CHANGELOG.md) dokumentiert.

### Sessions & Authentifizierung

Der Server ist bewusst nicht authentifiziert — er liefert ausschliesslich
öffentliche Open Data. Über HTTP werden Session-IDs vollständig vom FastMCP-
Framework verwaltet; es gibt keinen benutzerspezifischen Zustand, also nichts,
woran eine Session gebunden werden müsste. Würde später eine authentifizierte
Variante eingeführt, müssen Session-IDs an die validierte Benutzeridentität
gebunden werden (Audit-Finding SEC-009).

### Fehlerbehandlung

- **Ausführungsfehler** (Upstream-Fehler, ungültiger Wert) werden als
  `ToolResponse` mit `is_error: true` und menschenlesbarer `summary` zurückgegeben;
  rohe Exception-Texte erreichen den Client nie (sie landen stattdessen auf stderr).
- **Protokollfehler** (unbekanntes Tool, ungültige Argumente) gibt das MCP-SDK als
  JSON-RPC-Fehler mit Standardcodes aus (z.B. `-32602` invalid params). Die
  Eingabevalidierung erfolgt an der Pydantic-Grenze (SEC-018).

## MCP-Primitive

Dieser Server exponiert bewusst **nur Tools** (keine Resources/Prompts):
Er ist ein Phase-1-Read-only-Wrapper, und jedes Resultat ist eine
parametrisierte Live-API-Abfrage statt ein statisches, adressierbares Dokument.
Resources/Prompts können in einer späteren Phase ergänzt werden.

### Tool-Workflows

Die meisten Tools liefern ein gedanklich abgeschlossenes Resultat in einem
Aufruf. Zwei Domänen nutzen eine kurze, dokumentierte Discovery-Kette (jede
Tool-Beschreibung nennt den nächsten Schritt):

- **Feature-Abfrage:** `swisstopo_search_layers` (Layer-IDs finden) →
  `swisstopo_identify_features` / `swisstopo_find_features` →
  `swisstopo_get_feature` (Details).
- **Kataster:** `swisstopo_geocode` → `swisstopo_get_egrid` →
  `swisstopo_get_oereb_extract`.
- **Downloads:** `swisstopo_search_geodata` → `swisstopo_get_collection`.

---

## Antwortformat

Jedes Tool gibt ein strukturiertes `ToolResponse` zurück (FastMCP liefert es als
strukturierten Content mit Output-Schema plus JSON-Textblock):

| Feld | Bedeutung |
|---|---|
| `summary` | Menschenlesbare Markdown-Zusammenfassung |
| `results` | Maschinenlesbare strukturierte Datensätze |
| `count` | Anzahl `results` |
| `match_type` | `exact` / `fuzzy` / `none` (bei Such-Tools) |
| `source` / `license` | Datenquellen-Attribution (OGD-CH, CC/OGD-Bedingungen) |
| `provenance` / `retrieved_at` | Wie und wann die Daten bezogen wurden |
| `is_error` | `true` bei behandelten Fehlern |

---

## Bekannte Einschraenkungen

- **OEREB-Tools** erfordern einen Kantons-Parameter; nicht alle Kantone bieten dasselbe API-Format
- **STAC-Katalog** verwendet den Swisstopo-v0.9-Endpunkt; einige Collections haben ggf. unvollstaendige Metadaten
- **Geocoding** deckt nur Schweizer Adressen ab (kein Liechtenstein)
- **Rate Limits** werden von Swisstopo durchgesetzt; hochfrequente Nutzung kann gedrosselt werden

### Bekannte Befunde — OpenPLZ-Live-Probe (2026-07-20)

Die OpenPLZ-Endpoints wurden vor der Implementation live geprueft. In die Tools
eingeflossene Befunde:

| Endpoint / Verhalten | Ergebnis | Behandlung |
|---|---|---|
| `/Cantons` | 200, **26** Records, `key` = BFS-Kantonsnummer (ZH = `1`) | Kantonskuerzel wird aus dieser Liste aufgeloest |
| `/Cantons/{key}/Districts\|Communes` | 200 | Pfadparameter ist die **numerische `key`** |
| `/Cantons/ZH/Districts` (Kuerzel) | **200 + `[]`** — kein Fehler | `ZH`→`1` serverseitig aufgeloest; leere Antwort erhaelt erklaerende Note |
| `/Localities?postalCode=8001` | 200, `commune.key = 261` (BFS Zuerich) | `bfs_commune_number` als Top-Level-Feld ausgegeben |
| `/Localities?postalCode=9999` (unbekannt) | **200 + `[]`** | als Note gemeldet — leer ≠ nicht vorhanden |
| Pagination der Listen-Endpoints | Default `pageSize=10`, **hartes Maximum 50** (`100` → HTTP 400) | Tools iterieren die Seiten via `x-total-count` |
| roher Umlaut in Query (`?name=Zürich`) | **HTTP 400** | httpx encodiert `params` automatisch |
| Feld `historicalCode` | ≠ `key` bei Gemeinden (ID des historisierten Verzeichnisses) | nicht genutzt; Join-Schluessel ist die aktuelle `key` |
| Bulk-Dump | keiner bei OpenPLZ (nur `/swagger`) | Architektur A (Live-API-only) — fuer einen Lookup-Konnektor ausreichend |

**Die Kuerzel-vs-Key-Falle in einem Satz:** Eine leere OpenPLZ-Liste ist fast nie
ein Beweis, dass etwas *nicht existiert* — meistens ist es ein falscher
Pfadparameter (ein Kuerzel, wo eine numerische `key` erwartet wird). Die Tools
loesen Kuerzel serverseitig auf und annotieren jede leere Antwort.

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
