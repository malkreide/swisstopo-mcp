# Merge-Plan: `swiss-geodata-mcp` → `swisstopo-mcp`

**Status:** Vorschlag / Review offen · **Stand:** 2026-07-27
**Basis-Server:** `swisstopo-mcp` (dieses Repo) · **Legacy-Kandidat:** `malkreide/swiss-geodata-mcp` v0.1.1

Dieses Dokument beschreibt die konkrete, PR-weise Zusammenführung der beiden
Server. Es ersetzt keine Audit-Runde (siehe Schritt 6) und enthält selbst keine
Code-Änderungen.

---

## 1. Ausgangslage in einem Absatz

Beide Server sprechen `api3.geo.admin.ch` und überlappen in fünf Kern-Tools
(Layer-Suche, Identify, Find, Höhe, Höhenprofil). `swisstopo-mcp` ist mit 19
Tools, 8 Upstreams, 19 Testdateien und einem Audit ohne offene Findings
funktional ein Superset — mit genau **einer** echten Ausnahme: der offiziellen
Koordinaten-Transformation via `geodesy.geo.admin.ch/reframe`. Der Merge läuft
daher in Richtung **B → A**.

## 2. Zwei Live-Befunde, die den Plan verändert haben

Beide wurden gegen die Produktiv-API verifiziert (2026-07-27), nicht aus dem
Code abgeleitet. Sie korrigieren zwei Annahmen der vorangegangenen Analyse.

### 2.1 Topic `ech` / `all` / `api` ist **kein** Migrationsthema

A fragt `/rest/services/ech/…`, B `/rest/services/all/…` bzw. `/api/…`. Das sah
nach unterschiedlicher Layer-Abdeckung aus. Gegenprobe:

| Aufruf | `ech` | `all` / `api` |
|---|---|---|
| `identify` auf `ch.are.bauzonen` (Zürich, LV95 2683531/1247914) | 1 Treffer | 1 Treffer |
| `identify` auf `…swissboundaries3d-gemeinde-flaeche.fill` | 177 | 177 |
| `SearchServer type=layers` q=`bauzonen` | `ch.are.bauzonen` | identisch |
| `SearchServer type=layers` q=`lawinen` | 4 Treffer | identisch |

→ **Ergebnis: identisch.** A's Endpunkt-Wahl ist gleichwertig. Es müssen **keine**
Pfade migriert werden, und A's Tools erreichen den vollen Layer-Bestand. Diese
Risikokategorie entfällt vollständig.

### 2.2 Die Transformations-Differenz ist ~1–2 dm, nicht ~1 m

A rechnet lokal mit der Swisstopo-Näherungsformel (Docstring: „~1m accuracy"),
B ruft den offiziellen REFRAME-Dienst. Gemessene Abweichung:

| Punkt | ΔE | ΔN | Distanz |
|---|---|---|---|
| Zürich (47.3769, 8.5417) | +0.148 m | −0.019 m | **≈ 0.15 m** |
| Genf (46.2044, 6.1432) | +0.160 m | −0.041 m | **≈ 0.17 m** |
| Davos (46.5197, 9.8355) | +0.026 m | −0.044 m | **≈ 0.05 m** |
| SW-Ecke (45.9, 7.0) | +0.120 m | +0.154 m | **≈ 0.20 m** |

→ **Konsequenz für den Plan:** Die ursprüngliche Empfehlung „A's Polynom durch
reframe ersetzen" wird **zurückgezogen**. Bei einer Abweichung von ≤ 0.2 m ist
ein Blanket-Replace nicht gerechtfertigt: das Polynom wird intern bei *jedem*
Höhen-, Profil- und Identify-Call benutzt: ein Ersatz würde einen synchronen
Netzwerk-Roundtrip in den heissesten Pfad des Servers einbauen — für Genauigkeit,
die unterhalb der Toleranz dieser Tools liegt (Identify arbeitet mit
`tolerance` 0–50 m).

**Stattdessen:** Polynom bleibt der interne Fast-Path; reframe kommt als
*exponiertes Tool* dazu (das ist der eigentliche Mehrwert von B) plus optional
ein `precise=True`-Flag für Fälle, in denen Zentimeter zählen (Katasterbezug).

## 3. Ein Nebenbefund: latenter Defekt in `HeightInput`

Aufgefallen beim Vergleich der Koordinaten-Konventionen, unabhängig vom Merge:

```python
# src/swisstopo_mcp/height.py
lat: float = Field(..., ge=45.8, le=47.9)   # WGS84-Bounds
lon: float = Field(..., ge=5.9,  le=10.5)
sr:  int   = Field(default=4326)
...
if params.sr == 4326:
    easting, northing = wgs84_to_lv95(params.lat, params.lon)
else:
    easting, northing = params.lon, params.lat   # erwartet LV95 in lat/lon
```

**Korrektur (PR 2, verifiziert):** Die ursprüngliche Beschreibung „unerreichbar"
war zu milde. Zwar ist der *beabsichtigte* Weg unerreichbar — LV95-Werte in
`lat`/`lon` werden von den Bounds (45.8–47.9 / 5.9–10.5) abgewiesen. Aber
`HeightInput(lat=46.9481, lon=7.4474, sr=2056)` **passiert die Validierung** und
schickt dann `easting=7.4474, northing=46.9481, sr=2056` upstream: Grad, als
Meter etikettiert. Das ist kein toter Code, sondern ein **still falsches
Resultat**.

Gleiches Muster in `ElevationProfileInput` und `IdentifyInput`. PR 2 schliesst
das, indem LV95 über explizite `easting`/`northing`-Felder läuft und `sr` für
Eingabekoordinaten nur noch `4326` akzeptiert — aus einer stillen Falschantwort
wird ein lauter Fehler.

---

## 4. Modul-Landkarte B → A

| B-Artefakt | Ziel in A | Vorgehen |
|---|---|---|
| `geoadmin.py::reframe()` + `REFRAME_BASE` | neu `coords.py` + `api_client.py` | **portieren** (PR 1) |
| `geoadmin.py::_to_float()` | `coords.py` (lokal) | portieren — reframe liefert Zahlen als **Strings** |
| `geoadmin.py::html_to_text()` | `rest_api.py` | portieren (PR 3, für Legende) |
| `geoadmin.py::legend_text()` / `layer_fields()` | `rest_api.py` | portieren (PR 3) |
| `server.py::geo_zoning_at` + `ZONING_LAYER` | `rest_api.py` | portieren inkl. **Rechtshinweis** (PR 3) |
| `server.py::geo_municipality_at` + `MUNICIPALITY_LAYER` | `rest_api.py` | portieren inkl. „current year"-Filter (PR 3) |
| `server.py::_lv95_error()` | `api_client.py` | portieren als Plausibilitäts-Gate (PR 2) |
| `geoadmin.py::search_layers/identify/find/height/profile` | — | **verwerfen** (Duplikat, A-Version ist reicher) |
| `models.py::GeoEnvelope` | — | **verwerfen** (A's `ToolResponse` ist das Zielformat) |
| `geoadmin.py::_get()` Retry | — | verwerfen (A's `request_with_retry` ist robuster: 2/4/8 s vs 0.5/1.0 s) |
| `tests/test_unit.py` Fixtures | `tests/test_coords.py`, `test_rest_api.py` | Fixtures übernehmen (live-verifizierte Payloads) |

---

## 5. PR-Sequenz

Sechs PRs, bewusst klein geschnitten. PR 1–3 in A sind unabhängig
reviewbar; PR 4–5 in B setzen PR 3 voraus.

### PR 0 — `fix: align server.json version with package` (A) · XS

Reines Housekeeping, aber **Release-Blocker**: `server.json` steht auf `0.1.3`,
`pyproject.toml` auf `0.2.0`. Registry-Publish würde eine falsche Version
ausweisen.

- `server.json`: `version` + `packages[0].version` → `0.2.0`
- Ohne Teständerung.

### PR 1 — `feat: official REFRAME coordinate conversion tool` (A) · M

Der Kern-Port. Bringt B's einzige echte Zusatzfähigkeit.

| Datei | Änderung |
|---|---|
| `src/swisstopo_mcp/api_client.py` | `REFRAME_BASE = "https://geodesy.geo.admin.ch/reframe"`; `"geodesy.geo.admin.ch"` in `ALLOWED_HOSTS`; `reframe_request()` analog `geo_admin_request()` (nutzt `request_with_retry`) |
| `src/swisstopo_mcp/coords.py` **(neu)** | `ConvertCoordinatesInput` (Pydantic, `strict=True`, `extra="forbid"`, `direction: Literal["wgs84_to_lv95","lv95_to_wgs84"]`); `convert_coordinates()` → `ToolResponse`; `_to_float()` für die String-Zahlen |
| `src/swisstopo_mcp/models.py` | Konstante `REFRAME_SOURCE = "swisstopo REFRAME (geodesy.geo.admin.ch)"` |
| `src/swisstopo_mcp/server.py` | Tool `swisstopo_convert_coordinates` registrieren; `instructions` ergänzen |
| `docs/network-egress.md` | Zeile für `geodesy.geo.admin.ch` (der Kommentar an `ALLOWED_HOSTS` verlangt diesen Sync explizit) |
| `tests/test_coords.py` **(neu)** | respx-mocked: beide Richtungen, **String→Float-Coercion**, unbekannte Direction, Fehlerpfad, Allow-List-Verletzung; `live`-Marker-Test gegen echte API |

**Achtung Achsen-Semantik:** bei `wgs84_to_lv95` trägt `easting` den *Längengrad*
und `northing` den *Breitengrad* — invertiert zur `lat/lon`-Konvention des
restlichen Servers. Muss im Docstring und Field-`description` explizit stehen,
sonst ist es eine Fehlerquelle für Modelle.

**Nicht** Teil dieses PRs: das Polynom anfassen (siehe 2.2).

### PR 2 — `feat: accept LV95 input on point-based tools` (A) · M

Schliesst den Defekt aus Abschnitt 3 und ist die Voraussetzung dafür, dass
B-Clients überhaupt migrieren können (B ist LV95-nativ).

- Einheitliches Eingabemuster für punktbasierte Tools: entweder `lat`/`lon`
  (WGS84, bestehende Bounds) **oder** `easting`/`northing` (LV95, Bounds
  ~2'480'000–2'840'000 / 1'070'000–1'300'000), validiert per
  `model_validator(mode="after")` als „genau eines von beiden".
- `_lv95_error()`-Gate aus B portieren: WGS84-aussehende Werte in
  LV95-Feldern → sofortiger, sprechender Fehler mit Verweis auf
  `swisstopo_convert_coordinates` (B's Ergonomie, die A fehlt).
- Betroffen: `height.py` (`HeightInput`, `ElevationProfileInput`),
  `rest_api.py` (`IdentifyInput`), `oereb.py` (`get_egrid`).
- `sr`-Feld: als deprecated markieren, Verhalten für `4326` unverändert.
- Tests: LV95-Pfad je Tool, Mischeingabe → `ValidationError`, WGS84-in-LV95-Gate.

**Risiko:** grösster Eingriff in bestehende Schemas. Rückwärtskompatibel, solange
`lat`/`lon` weiter akzeptiert werden — kein Breaking Change für A-Clients.

### PR 3 — `feat: port zoning, municipality and layer-info tools` (A) · M

Die drei Convenience-Tools, für die B in der Praxis benutzt wurde.

| Neues Tool | Ersetzt | Besonderheit |
|---|---|---|
| `swisstopo_zoning_at` | `geo_zoning_at` | Rechtshinweis („`ch.are.bauzonen` ist eine ARE-Synthese, **nicht** rechtsverbindlich") muss in **jede** Antwort — in `ToolResponse.summary` **und** als Feld |
| `swisstopo_municipality_at` | `geo_municipality_at` | Filter auf aktuellen Jahrgang (Layer liefert historische Stände; B's Test fängt das mit `bfs_number == 261` statt des 1950er-Records) |
| `swisstopo_layer_info` | `geo_layer_info` | braucht `html_to_text()` — Legende kommt als HTML |

- Implementierung als dünne Wrapper über bestehende A-Logik, **nicht** als neuer
  HTTP-Client.
- Quellen-/Lizenzkonstante für ARE in `models.py` ergänzen.
- **Tool-Budget:** 19 → 23. Das selbstgesetzte Limit von 20 (README/Audit
  ARCH-007) muss im selben PR bewusst auf 25 angehoben und begründet werden —
  sonst bricht der Merge eine dokumentierte Zusage.
- Tests: `test_rest_api.py` erweitern, Fixtures aus B's `test_unit.py`
  übernehmen (sind gegen die Live-API verifiziert).

### PR 4 — `docs: deprecate in favour of swisstopo-mcp` (B) · S

Erst wenn PR 1–3 gemerged sind — vorher gibt es kein vollwertiges Ziel.

- README(.de): Deprecation-Banner zuoberst, Tool-Mapping-Tabelle
  `geo_*` → `swisstopo_*`, Migrationshinweis zur Koordinaten-Konvention.
- `CHANGELOG.md`: `0.2.0 — Deprecated`.
- `server.json`: Description mit `[DEPRECATED — use swisstopo-mcp]` (Registry).
- `pyproject.toml`: `Development Status :: 7 - Inactive`.
- Code bleibt lauffähig — die 9 Tools funktionieren weiter.

### PR 5 — `chore: archive repository` (B) · XS

Nach Ablauf des Deprecation-Fensters (Vorschlag: **2 Releases oder 3 Monate**,
je nachdem was später eintritt). Repo auf GitHub archivieren, Registry-Eintrag
auf A zeigen lassen.

*Alternative, falls B nachweislich installierte Clients hat:* statt Archivierung
eine Alias-Schicht — die 9 `geo_*`-Tools bleiben registriert, delegieren aber an
importierte A-Handler. Kostet dauerhafte Wartung und lohnt sich nur bei echter
Nutzerbasis (siehe offene Frage 7.2).

### PR 6 — `docs: roadmap phase + audit re-run` (A) · S

- `docs/roadmap.md`: neuer Abschnitt „Phase 2.5 — Konsolidierung
  swiss-geodata-mcp" mit den obigen Punkten (das Phasenmodell ist per Audit-Check
  **OPS-003** verlangt).
- `mcp-audit` erneut laufen lassen: neue Egress-Hosts (SEC-021), neue
  Tool-Oberfläche (ARCH-007), neue Eingabevalidierung (SEC-018) sind alle
  audit-relevant. A steht aktuell bei **0 Findings** — dieser Stand ist zu halten.
- README(.de): Toolzahl 19 → 23 an allen Stellen (auch Modul-Docstring in
  `server.py`, der „19 Tools" nennt).

---

## 6. Breaking Changes für bestehende B-Clients

| # | Änderung | Wirkung | Abfederung |
|---|---|---|---|
| 1 | Tool-Namen `geo_*` → `swisstopo_*` | **hart** — alle 9 Tools | Mapping-Tabelle in PR 4; optional Alias-Schicht (PR 5) |
| 2 | Antwortformat `GeoEnvelope`-JSON-String → `ToolResponse` | **hart** — andere Feldnamen (`result` → `results`, `note` → in `summary`) | Feld-Mapping dokumentieren |
| 3 | Koordinaten-Konvention LV95 → WGS84-Default | **mittel** | PR 2 macht LV95 weiterhin gültig → in der Praxis entschärft |
| 4 | `direction`-Enum-Werte | keine | identisch übernommen |
| 5 | Server-Name/Registry-Eintrag | **hart** — Client-Config muss getauscht werden | unvermeidbar |

Für **A-Clients** entstehen bei korrekter Umsetzung **keine** Breaking Changes:
alle Ports sind additiv.

---

## 7. Risiken und offene Fragen

> **Entscheide (2026-07-27).** Alle drei offenen Fragen sind beantwortet:
> **§7.1 Tool-Budget → auf 25 angehoben.** **§7.2 Nutzerbasis → keine externen
> Nutzer, daher Archivierung ohne Alias-Shim.** **§7.3 Portfolio-Doktrin →
> Merge, mit `swisstopo-mcp` als Basis.** Die Absätze unten bleiben als
> Begründung stehen.

1. **Tool-Budget-Inflation.** 23 Tools in einem Server erhöhen die
   Auswahllast für das Modell. Falls die Tool-Beschreibungen nicht scharf
   getrennt sind, sinkt die Trefferquote — gerade weil dann *zwei* Wege zu
   Bauzonen führen (`swisstopo_zoning_at` und `query_geodata`). Gegenmassnahme:
   `<use_case>`-Tags konsequent, und in `instructions` eine klare
   Entscheidungsregel. **Vor** PR 3 zu klären.
2. **Nutzerbasis von B unbekannt.** Entscheidet zwischen PR 5 (Archiv) und der
   Alias-Variante. Vor PR 4 zu klären — PyPI-Downloadzahlen und
   Registry-Installationen prüfen.
3. **Portfolio-Doktrin.** Falls das Portfolio strikt dünne Single-Purpose-Server
   vorsieht, ist der konsequentere Weg nicht dieser Merge, sondern A zu
   *verschlanken* (OSM/OpenPLZ/geodienste ausgliedern) und B als schlanken
   geo.admin-Kern zu behalten. Dieser Plan setzt den Ist-Zustand voraus (A ist
   bereits ein Multi-Source-Aggregator). **Diese Frage kippt den Plan** und
   gehört vor PR 1 entschieden.
4. **`ch.are.bauzonen`-Haftung.** Der Nicht-Verbindlichkeits-Hinweis darf beim
   Port nicht verloren gehen — er ist in B bewusst in jeder Antwort. Als
   Testfall absichern, nicht nur als Docstring.
5. **REFRAME-Verfügbarkeit.** Neuer Single Point of Failure für ein Tool.
   Unkritisch, solange das Polynom der interne Fast-Path bleibt (2.2) — bei einem
   Blanket-Replace wäre es ein Verfügbarkeitsrisiko für den halben Server.

---

## 8. Reihenfolge auf einen Blick

```
PR 0 (A, XS)  version-fix          ─┐
PR 1 (A, M)   reframe-tool         ─┼─ unabhängig reviewbar
PR 2 (A, M)   LV95-input           ─┤
PR 3 (A, M)   zoning/municipality  ─┘   ← Budget-Entscheid nötig (7.1)
      │
      ▼
PR 4 (B, S)   deprecation           ← Nutzerbasis klären (7.2)
PR 5 (B, XS)  archiv | alias-shim
PR 6 (A, S)   roadmap + audit-rerun
```

Vorbedingung für den gesamten Plan: Entscheid zu offener Frage **7.3**
(Portfolio-Doktrin).
