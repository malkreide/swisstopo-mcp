# Geodaten-Erweiterung — Phase 1: Live-Probe

**Datum der Probe:** 2026-07-19
**Methodik:** [`mcp-data-source-probe`](../README.de.md) — Schritt 1 (Live-Probe vor Design).
**Status:** Phase 1 abgeschlossen; **Phase 2 umgesetzt** (Freigabe: OEREB nur
Verfügbarkeits-Layer, geodienste in `query_geodata` integriert). Die 3 neuen
Tools (`query_geodata`, `list_available_layers`, `query_osm_features`) sind in
`geodata.py` / `overpass.py` implementiert — siehe CHANGELOG und READMEs.

Alle Ergebnisse unten sind empirisch (`curl` gegen die Live-Endpoints), nicht
aus der Dokumentation abgeleitet. *«Dokumentation ist ein Foto, Live-Probe ist
der aktuelle Zustand.»*

> **Egress-Hinweis (Session-Netzwerkpolitik):** Diese Probe lief hinter dem
> Agent-Egress-Proxy. Erreichbar: `api3.geo.admin.ch`, `geodienste.ch`,
> `overpass.osm.ch`, `overpass-api.de`. **Geblockt durch Organisations-Policy
> (502 policy denial):** `oereb.geo.zh.ch`, `oereb.cadastre.ch`, `oereb.ch`.
> Das betrifft nur *diese* Session — die Hosts sind produktiv erreichbar,
> stehen bereits auf der App-Allow-List (`api_client.py`) und werden vom
> bestehenden `swisstopo_get_oereb_extract`-Tool genutzt. Für die
> OEREB-Quelle wurde deshalb der erreichbare *bundesweite* Teil live geprüft
> und der cantonale Extract-Teil aus dem bestehenden Code + Doku dokumentiert.

---

## A) Amtliches Strassenverzeichnis — `ch.swisstopo.amtliches-strassenverzeichnis`

**Host:** `api3.geo.admin.ch` (bereits auf Allow-List, kein neuer Egress).
**Lizenz:** OGD Schweiz / swisstopo — freie Nutzung, Quellenangabe Pflicht.

### Befund-Tabelle

| Probe (Endpoint) | HTTP | Status | Records | Bemerkung |
|---|---|---|---|---|
| `SearchServer?type=locations&origins=address` (Adresssuche) | 200 | ✅ | 3 | Adress-Geocoding, liefert `featureId`, `lon/lat`, `x/y` |
| `SearchServer?type=featuresearch&features=ch.swisstopo.amtliches-strassenverzeichnis` (`Bederstrasse`) | 200 | ✅ | 1 | Suche nach Strassenname |
| dieselbe, Strassenname **+ Gemeinde** (`Bederstrasse Zürich`) | 200 | ✅ | 1 | Kombinierte Suche funktioniert |
| `MapServer/identify` (Punkt, `sr=2056`, `tolerance`) | 200 | ✅ | 1 | Geometrie (`paths`/Linien) + Attribute |
| `MapServer/{layer}/{featureId}?geometryFormat=geojson` | 200 | ✅ | 1 | Voll-Attribute + Geometrie |
| `MapServer/{layer}/999999999999` (Fehlerfall) | 404 | ✅ sauber | – | `{"detail":"No feature with id …","status":"error","code":404}` |

### Attribut-Schema (verifiziert, `str_esid=10098541`)

```
str_esid, stn_label (Bederstrasse), zip_label (8002 Zürich), com_name (Zürich),
com_fosnr (261 = BFS-Nr.), str_official (1), str_modified (2024-07-23),
str_type (Strasse), str_status (bestehend), str_children, str_parent, label
```

### Fundstücke / Fallstricke

- **Default-SR ist LV03 (CH1903, `sr=21781`), nicht LV95.** `SearchServer`
  liefert `x`=Nord (246137), `y`=Ost (682092). Für LV95 explizit `sr=2056`
  übergeben → 1246137 / 2682092. Ohne expliziten SR-Parameter kommen
  6-stellige LV03-Koordinaten zurück — leicht mit LV95 zu verwechseln.
- `featuresearch` gibt bei Strassensuche nur die *aggregierte* Strasse zurück
  (`str_esid`), Adressen laufen über `type=locations&origins=address`.

### Architektur-Entscheid: **A (Live-API-only)**
Alle nötigen Endpoints funktionieren stabil (< 1.5 s). Kein Dump nötig — die
`api3`-Suchdienste sind der kanonische, gepflegte Zugang. Kein neuer Host.

---

## B) geodienste.ch — interkantonale Basisgeodaten

**Host:** `geodienste.ch` (**neu** → Egress-Allow-List erweitern).
**Katalog:** `https://geodienste.ch/info/services.json` (3.4 MB, **1137 Einträge**).

### Struktur

45 `base_topic`s × ~27 Kantone/Broker = 1137 Service-Einträge. Jeder Eintrag
trägt u. a.: `topic`, `canton`, `getcapabilities_wms`, `getcapabilities_wfs`,
`ogc_api_features`, `stac_item_url`, `contract_required_wms/_data`,
`opendata_terms_wms/_data`, `terms_of_use_*`, `updated_at`.

### Befund-Tabelle

| Probe | HTTP | Status | Records | Bemerkung |
|---|---|---|---|---|
| `info/services.json` (Katalog) | 200 | ✅ | 1137 | Voller interkantonaler Katalog als JSON-Dump |
| WMS `GetCapabilities` (ZH, Kataster belastete Standorte) | 200 | ✅ | 8 Layer | XML-Capabilities |
| WFS `GetCapabilities` (dito) | 200 | ✅ | – | vorhanden |
| OGC API Features `/ogcapi/collections?f=json` | 200 | ✅ | 2 Collections | GeoJSON-Discovery |
| OGC API Features `/collections/{id}/items?limit=2&f=json` | 200 | ✅ | 2 / **numberMatched 34553** | GeoJSON, sauberes Attribut-Schema |

### Frei nutzbar ohne Vertrag / ohne Login? — **Ja, breit.**

Kriterium *frei* = `contract_required_wms == false` **und**
`opendata_terms_wms` beginnt mit «Freie Nutzung».

- **~40 der 45 Topics** haben in der Mehrzahl der Kantone frei-nutzbare,
  ohne Vertrag zugängliche WMS-Dienste.
- **544 der freien Einträge bieten zusätzlich WFS *und* OGC API Features**
  (gleiche Anzahl → wo WFS existiert, existiert auch OGC API Features).
- Nur 7 Einträge haben `contract_required_wms=true`; nur 4 Topics haben
  *null* frei-nutzbare WMS-Kantone (`gewaesserzustand`,
  `naturereigniskataster_umfassend`, `rohrleitungsanlagen`,
  `thermische_netze`).

Top frei verfügbare Topics (frei/total Kantone):

```
fixpunkte 25/27, fruchtfolgeflaechen 21/27, gefahrenkarten 21/27,
kataster_belasteter_standorte 21/27, lwb_nutzungsflaechen 21/27,
naturereigniskataster 21/27, npl_waldgrenzen 21/27, waldreservate 21/27,
av (Amtliche Vermessung) 20/27, planungszonen 18/27, npl_nutzungsplanung 17/27, …
```

### Fundstücke / Fallstricke

- `opendata_terms_*` ist **Freitext**, kein Boolean — Werte:
  `"Freie Nutzung"`, `"Freie Nutzung. Quellenangabe ist Pflicht."`,
  `"keine Angabe"`, sowie Varianten mit «Kommerzielle Nutzung nur mit
  Bewilligung». Der Vertrags-Check muss beide Felder (`contract_required_*`
  **und** `opendata_terms_*`) prüfen.
- **OGC API Features ist der sauberste programmatische Zugang** (GeoJSON out,
  `numberMatched`, `limit`, `bbox`), deutlich handlicher als WFS-XML.
- URL-Muster: `https://geodienste.ch/db/{topic}_{version}/deu/ogcapi/…`.
  `?f=json` ist für JSON zwingend.
- Attribut-Beispiel (belastete Standorte): `egrid, kanton, katastername,
  katasternummer, deponietypen, inbetrieb, nachsorge, ersteintrag, …`.

### Architektur-Entscheid: **B (Hybrid: Katalog-Dump zuerst, OGC-API live)**
Der `services.json`-Katalog wird als Discovery-Dump gecacht (TTL) — er ist die
Landkarte über Topics/Kantone/Frei-Status. Aktuelle Sachdaten kommen live über
OGC API Features. WMS `GetCapabilities` dient der Layer-Discovery, ist aber für
Datenabruf zweitrangig gegenüber OGC API Features.

---

## C) OEREB-Kataster — cadastre.ch

**Frage aus dem Auftrag:** Gibt es einen bundesweiten Einstieg oder nur
kantonale `pyramid_oereb`-Instanzen?

### Befund-Tabelle

| Probe | HTTP | Status | Bemerkung |
|---|---|---|---|
| `api3` Layer `ch.swisstopo-vd.stand-oerebkataster` (identify, Bederstr. 109) | 200 | ✅ | Bundesweite **Verfügbarkeits-/Zuständigkeitskarte** |
| ZH `pyramid_oereb` `oereb.geo.zh.ch/getegrid/json` | – | ⛔ geblockt | Org-Egress-Policy (502), nicht live prüfbar in dieser Session |
| Bundes-Dispatcher `oereb.cadastre.ch` | – | ⛔ geblockt | Org-Egress-Policy (502) |
| `oereb.ch` | – | ⛔ geblockt | Org-Egress-Policy (502) |

### Antwort: **Kantonal fragmentiert — kein bundesweiter Extract-API.**

- Der **einzige bundesweite Einstieg** ist die swisstopo-Layer
  `ch.swisstopo-vd.stand-oerebkataster` («Verfügbarkeit des ÖREB-Katasters»).
  Sie liefert pro Gemeinde: `oereb_status` («ÖREB-Kataster eingeführt»),
  `kanton`, `bfs_nr`, sowie **die zuständige Stelle** (Firmenname, Adresse,
  Telefon, E-Mail). Das ist ein **Discovery-/Dispatcher-Layer, kein
  Datenauszug.** ✅ live verifiziert an Bederstrasse 109 → Zürich, BFS 261,
  Status «eingeführt».
- Der **eigentliche Auszug** kommt ausschliesslich von kantonalen
  `pyramid_oereb`-Instanzen (`/getegrid/json/?EN=E,N` → `/extract/json/?EGRID=…`).
  Der Server unterstützt heute nur **ZH** (`oereb.geo.zh.ch`) und **BE**
  (`www.oereb2.apps.be.ch`), hart kodiert in `oereb.py`.
- `oereb.cadastre.ch` ist ein **Portal/Dispatcher**, kein einheitlicher
  Daten-Endpoint.

### Architektur-Entscheid: **Fragmentiert → Phase 1 auf Kanton Zürich beschränkt (explizit dokumentiert)**

- **Bundesweit** nutzbar (neu, live geprüft): Verfügbarkeits-Abfrage über
  `ch.swisstopo-vd.stand-oerebkataster` → «Ist ÖREB an diesem Punkt geführt,
  und wer ist zuständig?». Das ist ein **Live-API-only (A)**-Baustein auf dem
  bereits erlaubten `api3`-Host und fügt sich in die Fassade ein.
- **Extract** (EGRID → ÖREB-Auszug) bleibt auf **ZH** (und dem bereits
  vorhandenen BE) beschränkt. In dieser Session **nicht live verifizierbar**
  (Egress-Block), Vertrag = das bestehende, getestete `swisstopo_get_egrid` /
  `swisstopo_get_oereb_extract`. Kein neuer Host nötig — beide ZH/BE-Hosts
  stehen bereits auf der Allow-List.

> **Offener Punkt für Freigabe:** Der Extract-Teil kann in dieser Session
> nicht live geprüft werden. Empfehlung: Phase 2 baut nur den bundesweiten
> Verfügbarkeits-Baustein neu; der cantonale Extract bleibt beim bestehenden
> Tool. Kein «Ausbau auf alle Kantone» ohne separate Live-Probe je Kanton.

---

## D) Overpass API (OpenStreetMap POIs) — die fragilste Quelle

**Instanzen geprüft:** `overpass.osm.ch` (Schweizer Instanz) und
`overpass-api.de` (Haupt-Instanz).
**Lizenz:** ODbL (OpenStreetMap) — Attribution «© OpenStreetMap contributors» Pflicht.

### Befund-Tabelle

| Probe | HTTP | Status | Records | Bemerkung |
|---|---|---|---|---|
| `overpass.osm.ch/api/interpreter` — Schulen ≤ 500 m um Bederstr. 109 | 200 | ✅ | **8** | Anchor-Query, 1.3 s |
| `overpass-api.de/api/interpreter` — gleiche Query | 406 | ⚠️ | – | Über diesen Egress-Proxy 406 (Header/UA-Interaktion) |
| `overpass.osm.ch/api/status` (Rate-Limit-Info) | 400 | ⚠️ | – | Diese CH-Instanz exponiert **kein** Standard-`/api/status` |
| `[timeout:1]` auf schwere Query (Gebäude 5 km) | 200 | ⚠️ | – | Server bricht **nicht** hart bei 1 s ab — Query lief 3.9 s durch |
| Syntaxfehler-Query | 200 | ⚠️ | – | Fehler als **XML/HTML**, nicht JSON (siehe unten) |

### Rate-Limits & Timeout-Verhalten (kritisch dokumentiert)

- **`overpass.osm.ch` ist die stabilere Wahl in dieser Umgebung.**
  `overpass-api.de` liefert über den Egress-Proxy konsistent **406 Not
  Acceptable** (Apache) — die Haupt-Instanz ist so nicht nutzbar. Empfehlung:
  **CH-Instanz als Primary, `.de` nur als optionaler Fallback mit
  Header-Anpassung.**
- **Kein `/api/status` auf der CH-Instanz** → das Slot-basierte Rate-Limit
  (`Rate-Limit`, `Slot available after …`) der `.de`-Instanz ist hier nicht
  abfragbar. Die CH-Instanz ist eine leichtere Community-Instanz; wir müssen
  client-seitig limitieren statt uns auf `/api/status` zu verlassen.
- **`[timeout:N]` ist ein Server-Hinweis, keine harte Garantie.** Bei
  Überschreitung antwortet Overpass i. d. R. mit HTTP 200 + eingebettetem
  `remark: "runtime error: Query timed out …"` (oder 429/504) — **nicht** mit
  einem sauberen HTTP-Fehler. Der Client muss den Body inspizieren.
- **Fehler kommen als XML/HTML, selbst bei `[out:json]`:**
  ```
  <p><strong>Error</strong>: line 1: parse error: ']' expected - ';' found.</p>
  ```
  → JSON-Parser darf nicht blind `response.json()` aufrufen; erst Content-Type
  / `remark` prüfen.

### Fundstück (kulturell)

*«Overpass ist wie ein Buffet ohne Türsteher: freundlich, aber wenn zu viele
gleichzeitig zugreifen, macht die Küche einfach zu — und der Fehlerzettel ist
in einer anderen Sprache (XML) als die Speisekarte (JSON), die du bestellt hast.»*

### Architektur-Entscheid: **A (Live-API-only) mit hartem Client-Timeout + Ergebnis-Limit**
Kein Dump (OSM-Planet wäre absurd gross). Stattdessen: eigenes, separates Tool
`query_osm_features` mit **hartem client-seitigem Timeout** (kürzer als der
Server-`[timeout:]`), **Ergebnis-Limit** (`out … ;` + Client-Cap), Retry mit
Backoff **nur** auf 429/5xx/Netzfehler, und Body-Inspektion vor JSON-Parse.

---

## Anchor Demo Query — Dekomposition (verifiziert)

> «Welche Schulhäuser liegen im Umkreis von 500 m um Bederstrasse 109, 8002
> Zürich, und welche Strassen führen dorthin?»

| Schritt | Quelle | Live-Ergebnis |
|---|---|---|
| 1. Adresse → Koordinate | A / bestehendes Geocoding | Bederstr. 109 → LV95 2682092 / 1246137, WGS84 47.36097 / 8.52534 |
| 2. Schulen ≤ 500 m | **D** Overpass (`amenity=school`) | **8 Schulen** (u. a. Kantonsschule Enge/Freudenberg, Schule Gabler, Brunau-Stiftung) |
| 3. Strassen in der Umgebung | **A** Strassenverzeichnis (identify, tolerance) | 20 Strassen (Bederstrasse, Weberstrasse, Manessestrasse, Gutenbergstrasse …) |
| 4. (optional) ÖREB-Status am Punkt | **C** Verfügbarkeits-Layer | «ÖREB-Kataster eingeführt», Kanton Zürich |

Alle vier Quellen tragen zur selben Frage bei — die Komplementarität ist real.

---

## Phase-2-Vorschlag (wartet auf Freigabe)

### Tool-Inventar & Budget

Bestehend: **13 Tools**. Budget: **18**. Naive Erweiterung (je 1–2 Tools pro
Quelle) → 17–21 Tools = **Budget-Sprengung-Risiko**. Deshalb **Fassaden-Muster**
(wie im Auftrag verlangt):

| # | Neues Tool | Deckt ab | Begründung |
|---|---|---|---|
| 14 | `query_geodata(layer, bbox\|point\|commune, format)` | A (Strassenverz.), B (geodienste OGC API), C (ÖREB-Verfügbarkeit) | **Fassade** über alle karten-/layer-basierten Quellen |
| 15 | `list_available_layers(source?, canton?, free_only?)` | Discovery über A + B-Katalog + C | Discovery-Tool statt N Einzel-Tools |
| 16 | `query_osm_features(feature_type, area, radius_m)` | D (Overpass) | **Separat** (hartes Timeout/Limit, andere Fehler-Semantik, ODbL statt OGD) |

**Netto: 13 → 16 Tools. Unter Budget (18).** Die bestehenden ÖREB-Extract-Tools
(`swisstopo_get_egrid`, `swisstopo_get_oereb_extract`) bleiben unverändert.

### Weitere Phase-2-Aufgaben

1. **Egress-Allow-List** (`api_client.py` + `docs/network-egress.md`) erweitern:
   `geodienste.ch`, `overpass.osm.ch` (+ optional `overpass-api.de`).
2. **Retry mit Backoff** (2/4/8 s, 5xx+429+Netz) als gemeinsamer Wrapper —
   aktuell fehlt ein expliziter Retry im `api_client` (nur `raise_for_status`).
   Der Skill fordert ihn zwingend.
3. **Provenance-Werte** je Quelle in den `ToolResponse`-Envelope:
   `live_api` (A, C, D, geodienste OGC), `cached` (geodienste-Katalog-Dump).
4. **Attribution** je Quelle: swisstopo/OGD (A, C), geodienste + jeweiliger
   Kanton (B), «© OpenStreetMap contributors» / ODbL (D).
5. **Tests** (`respx`): Happy / Retry-bei-503 / Timeout — plus Overpass-spezifisch
   ein Test für **XML-Fehlerbody trotz `[out:json]`**.
6. **Graceful Degradation** für Overpass (Rate-Limit/Timeout → sprechende
   Meldung statt Stacktrace).

### Offene Freigabe-Fragen

- **C (ÖREB):** Nur bundesweiten Verfügbarkeits-Baustein neu bauen (empfohlen),
  oder auch cantonalen Extract ausbauen (bräuchte Egress-Freigabe + Live-Probe
  je Kanton, in dieser Session nicht möglich)?
- **Fassaden-Zuschnitt:** `query_geodata` als ein Tool über A+B+C — oder B
  (geodienste) wegen anderer Lizenz/Kanton-Semantik als eigenes Tool? (Der Skill
  favorisiert Konsolidierung; Budget erlaubt beides.)
