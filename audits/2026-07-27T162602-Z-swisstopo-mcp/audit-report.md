# MCP-Server Audit-Report — `swisstopo-mcp`

**Audit-Datum:** 2026-07-27
**Skill-Version:** 1.0.0
**Catalog-Version:** 091f446b2796

---

## 1. Executive Summary

Server `swisstopo-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 24 bestanden, 20 Findings dokumentiert (2 critical, 11 high, 7 medium, 0 low). Production-Readiness: erreicht.

**Production-Readiness:** YES

> **Einordnung des YES.** Das Flag ist mechanisch: `aggregate_results.py` setzt
> `production_ready = False` nur bei **Status `fail`** in einer blockierenden
> Severity. Dieser Lauf hat null `fail`, also YES — bei zwei `partial` in
> **critical** (SEC-004, SEC-009) und elf in **high**. Der Vorlauf hatte zwei
> `fail` und war deshalb NO. Der Unterschied zwischen den beiden Läufen ist
> damit *nicht* «jetzt produktionsreif», sondern «kein Check mehr vollständig
> gerissen». Ich lese das Ergebnis nicht als Freigabe.

---

## 1a. Vergleich mit Lauf `2026-07-27T125314-Z`

Gleicher Katalog, gleiche 44 anwendbaren Checks, damit direkt vergleichbar.

| | Vorlauf | Dieser Lauf |
|---|---|---|
| pass | 22 | **24** |
| partial | 20 | **20** |
| fail | 2 | **0** |

Die Zahl bewegt sich, aber weniger als die Remediation-Notizen behaupteten.
Dieser Lauf war bewusst adversarial angelegt: die Agenten hatten den Auftrag,
meine eigenen Abschluss-Behauptungen zu widerlegen statt zu bestätigen. Das
hat funktioniert — in sechs Fällen gegen mich.

### Abschlüsse, die diesem Lauf nicht standgehalten haben

| Check | Was ich behauptet hatte | Was der Lauf gemessen hat |
|---|---|---|
| SEC-021 | Egress-ACL wird generiert und in CI geprüft | Generierung stimmt, **Output ist unbrauchbar**: falsche Einrückung ⇒ `services[0].allowed_domains == null`. Das CI-Gate vergleicht gegen denselben fehlerhaften Renderer und ist dafür strukturell blind. |
| ARCH-007 | `get_egrid` bewirbt sich nicht mehr als Vorstufe; Präzedenzregel ist aus den konkurrierenden Beschreibungen verlinkt | Zur Laufzeit falsifiziert (`server.py:496` stand weiter auf «Vorstufe»). Eine Ersetzung war stillschweigend fehlgeschlagen. Ich habe das nachgeprüft und behoben — die README-Workflows und die fehlende Parallelisierung sind offen. |
| OBS-006 | Tool-Argumente landen nie in Span-Attributen | Für den Parent-Span wahr, **für das System falsch**: die von `observability.py:79` eingeschaltete httpx-Instrumentierung exportiert `http.url` samt Query-String. Der Test aktiviert genau diese Instrumentierung nie. |
| CH-004 | Jede Quelle trägt ihre eigene Lizenz | Parameter existiert, wird an **14 Error-Call-Sites nicht übergeben**. ODbL-Daten werden als Swiss OGD etikettiert — eine Lizenz-Falschangabe, kein fehlendes Feld. |
| SEC-018 | Längengrenzen ergänzt | Für drei String-Felder nicht (`stac.py:34`, `geocoding.py:32`, `wmts.py:34`); `collection_id` landet direkt in einem URL-Pfad. |
| ARCH-003 | Bare-Negative-Sites tragen jetzt Hinweise | 5 von ~25. Die ÖREB-Gruppe — die Tools, die am häufigsten legitim leer zurückkommen — gehört nicht dazu. |

### Neu in diesem Lauf, im Vorlauf nicht gesehen

- **SDK-001 (high).** Unter `--http` läuft der Lifespan **pro MCP-Session**, nicht
  pro Prozess (gemessen: 3 `initialize` ⇒ 3 `server_started`). `DELETE /mcp` einer
  Session setzt den geteilten Client global auf `None` und fährt das Tracing
  herunter — die überlebenden Sessions fallen auf einen Client pro Aufruf zurück.
- **OBS-001 (high).** Das Protokoll-Flag `isError` wird nie gesetzt; der Server
  hat stattdessen ein eigenes Payload-Feld erfunden. Ein spec-konformer Client
  sieht bei jedem behandelten Fehler «Erfolg».
- **OBS-002 (high).** `overpass.py:146` reicht bis zu 300 Zeichen fremden
  Response-Body an den Nutzer durch — im Test inklusive Serverpfad und
  echoter Query. `PermissionError` gibt die komplette Egress-Allow-List heraus.
- **SCALE-003.** Die HAProxy-Datei ist real, aber funktionslos: `stick on`
  speichert aus dem *Request*, die Session-ID entsteht in der *Response*. Ohne
  `stick store-response` wird die Tabelle nie befüllt.

### Methodische Einschränkung

Ich habe während des Laufs Quellcode geändert (ARCH-007-Beschreibungen,
Tool-Zähler, `pin_dns` über `Settings`, `note=` in `oereb.py`), während drei
Agenten dieselben Dateien lasen. Zeilenangaben in den Findings können dadurch um
wenige Zeilen verschoben sein; der SDK/SCALE-Agent hat seine Zitate deshalb
nachverifiziert. Für einen sauberen Vergleich hätte der Baum eingefroren gehört.

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swisstopo-mcp` |
| Audit-Datum | 2026-07-27 |
| Skill-Version | 1.0.0 |
| Catalog-Version | 091f446b2796 |
| transport | `dual` |
| auth_model | `none` |
| data_class | `Public Open Data` |
| write_capable | `False` |
| deployment | `['local-stdio', 'andere']` |
| uses_sampling | `False` |
| tools_make_external_requests | `True` |
| stadt_zuerich_context | `False` |
| schulamt_context | `False` |
| data_source.is_swiss_open_data | `True` |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 8 | 0 | 3 | 0 | 0 |
| CH | 0 | 0 | 1 | 0 | 0 |
| OBS | 2 | 0 | 3 | 0 | 0 |
| OPS | 1 | 0 | 2 | 0 | 0 |
| SCALE | 3 | 0 | 2 | 0 | 0 |
| SDK | 2 | 0 | 2 | 0 | 0 |
| SEC | 8 | 0 | 7 | 0 | 0 |
| **Total** | **24** | **0** | **20** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| SEC-004 | SEC | critical | partial |
| SEC-009 | SEC | critical | partial |
| ARCH-006 | ARCH | high | partial |
| OBS-001 | OBS | high | partial |
| OBS-002 | OBS | high | partial |
| OPS-001 | OPS | high | partial |
| OPS-003 | OPS | high | partial |
| SCALE-002 | SCALE | high | partial |
| SCALE-003 | SCALE | high | partial |
| SDK-001 | SDK | high | partial |
| SEC-005 | SEC | high | partial |
| SEC-018 | SEC | high | partial |
| SEC-021 | SEC | high | partial |
| ARCH-003 | ARCH | medium | partial |
| ARCH-007 | ARCH | medium | partial |
| CH-004 | CH | medium | partial |
| OBS-006 | OBS | medium | partial |
| SDK-003 | SDK | medium | partial |
| SEC-014 | SEC | medium | partial |
| SEC-015 | SEC | medium | partial |

**Gesamt:** 20 Findings

---

## 5. Detail-Findings

### ARCH-003

## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

**Severity:** medium
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-003
**PDF-Reference:** Sec 2.2
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
`ToolResponse.note` was added (`src/swisstopo_mcp/models.py:78-85`, threaded through
`ok()` at `models.py:109`) and is populated at 5 call sites: `rest_api.py:325`, `:360`,
`:390`, `stac.py:158`, `oereb.py:339`. Against that, `match_type` can be `"none"` at
roughly 25 sites. The previous run recorded this as closed on the strength of the five.

The OpenPLZ hints credited earlier live in the summary markdown
(`openplz.py:326-331`, `:347`), not in the structured `note` field — the model reads
them either way, but the contract is inconsistent across modules. No fuzzy or
suggestion mechanism exists: `"fuzzy"` appears only as a `Literal` member
(`models.py:16`) with zero producing call sites, and the repo's own roadmap entry
(`docs/roadmap.md:28`) is still unticked.

### Expected Behavior
- Empty results trigger a fuzzy match or a suggestion mechanism
- Every `match_type == "none"` path carries an actionable next step
- A test enforces the invariant so coverage cannot regress silently

### Evidence
- The `note` field was added as claimed — src/swisstopo_mcp/models.py:78-85 declares it and models.py:109 threads it through `ToolResponse.ok()`. But it is populated at only 5 call sites in all of src/: rest_api.py:325, rest_api.py:360, rest_api.py:390 (all three are `note=None if results else (...)`), stac.py:158, and oereb.py:339. Grep for `note=` across src/*.py returns exactly those plus the models.py definition.
- Against that, `match_type` can be "none" at 26 call sites. Enumerated: coords.py:311(always exact), geocoding.py:131,161; geodata.py:281,334,384,455,490,532; height.py:208; oereb.py:132,190,209,336; openplz.py:405,437,454,473,495,516,554; overpass.py:210; rest_api.py:324,359,389,415,468,504; stac.py:157,179. So structured `note` covers 5 of ~25 bare-negative-capable sites — roughly 20% coverage, not the «bare-negative sites» wholesale the remediation note implies.
- Sites that still return a bare negative with no next step in either the note field or the summary: src/swisstopo_mcp/oereb.py:132 («Kein EGRID gefunden für Koordinaten (lat, lon) in Kanton X.»), oereb.py:190 («EGRID '...' nicht gefunden in Kanton X.»), oereb.py:209 («Keine Eigentumsbeschränkungen gefunden.»), stac.py:179 (get_collection), rest_api.py:415 (get_feature), geodata.py:615 (`_format_records`: «{title}: keine Treffer.») which backs geodata.py:281/334/490/532, and overpass.py:232-236.
- Two sites carry an explanatory but non-actionable summary and no note: src/swisstopo_mcp/rest_api.py:164 («Keine Bauzone an dieser Position (ausserhalb Bauzone oder ausserhalb CH).») feeding rest_api.py:468, and rest_api.py:178 feeding rest_api.py:504. These state a cause, not a next tool or a refinement.
- The OpenPLZ hints the previous run credited are in the *summary markdown*, not the structured field: src/swisstopo_mcp/openplz.py:347 `_format_communes(title, records, note="")` appends the hint to the summary text (openplz.py:471, :493, :514), and openplz.py:326-331 does the same in `_format_localities`. The `ToolResponse.note` field is never set anywhere in openplz.py. The model reads it either way, so this is not a failure, but it does mean the structured contract is inconsistent across modules.
- No fuzzy or suggestion mechanism exists. `"fuzzy"` appears in src/ only at models.py:16 (the Literal) and models.py:73 (its description) — zero producing call sites, unchanged from the previous run. The maintainer's own record still says so: docs/roadmap.md:28 «[ ] Suggestion mechanism for empty results — still open (ARCH-003)» is still unticked.

Gaps:
- Pass criterion 1 (empty results trigger a fuzzy match or suggestion mechanism) is unmet — neither exists; `match_type: "fuzzy"` remains a dead branch of the type.
- Pass criterion 3 (at match_type == "none", an actionable hint) is met for 5 of ~25 sites. The ÖREB cluster in particular — the tools most likely to legitimately return nothing, since only ZH is enabled by default — has actionable hints on the new aggregate (oereb.py:339) but not on the three older paths (oereb.py:132, :190, :209).
- No test asserts the invariant «match_type == 'none' implies a non-empty hint», so the coverage that does exist can regress silently. The previous finding's remediation item 4 asked for exactly this test and it was not added — tests/ contains no such assertion.

### Risk Description
A bare negative is the point at which an LLM either gives up or invents. The sites
still uncovered are the ones where an empty answer is most often *correct but
narrowable*: the three older ÖREB paths (`oereb.py:132`, `:190`, `:209`) return
nothing whenever the parcel is outside the enabled cantons, which by default is all
of Switzerland except ZH — and they say so without naming
`swisstopo_municipality_at` as the way to find out which canton applies. The model is
left to conclude that no restrictions exist, which is a materially wrong answer about
a legally binding cadastre.

### Remediation
1. Add `note=` at the remaining bare-negative sites, starting with the ÖREB cluster
   (`oereb.py:132`, `:190`, `:209`), then `stac.py:179`, `rest_api.py:415`,
   `geodata.py:615` (`_format_records`, which backs four call sites) and
   `overpass.py:232-236`.
2. Move the OpenPLZ summary hints into the structured field so one contract holds.
3. Add the invariant test the previous remediation plan promised and did not deliver:
   for every handler, `match_type == "none"` implies a non-empty `note`.
4. Either implement the fuzzy fallback or remove `"fuzzy"` from the `Literal` — a
   type member no code can produce is a false promise in the schema.

### Effort Estimate
M (1-3d)

### Relation to run `2026-07-27T125314-Z`
Recorded as closed in run `2026-07-27T125314-Z`. That closure was too generous: about four fifths of the none-capable sites were never touched.

### Auditor Notes
Not a pass. The remediation status claims the bare-negative sites «in
rest_api.py (layer search, identify, find) and stac.py» now populate the
note — which is literally accurate and also the whole extent of the work.
The check's criterion is not «some sites», and the previous finding's own
remediation text said «Add a hint at every bare-negative site». Roughly
four fifths of the none-capable sites were not touched, and the fuzzy
fallback (criterion 1, and item 2 of the prior remediation plan) was not
implemented at all — confirmed by the repo's own unticked roadmap entry.
Real progress was made on the highest-traffic discovery entry points, which
is why this is partial rather than fail.


### ARCH-006

## Finding: ARCH-006 — Tool-Budget: High-Level-Use-Cases statt API-Mapping 1:1

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-006
**PDF-Reference:** Sec 2.3
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
24 tools, verified at runtime via `mcp.list_tools()` and matching `tool-hashes.json`.
The check's heuristic puts 16–25 in the "serious doubt whether all are needed" band,
twice the stated ideal of ≤12.

The documented justification is real, substantive and bilingual
(`README.md:334-364`, `README.de.md:324-354`) — it argues per cluster rather than
restating the number, which satisfies the check's documentation criterion. But it
concedes the criterion it is meant to discharge: `README.md:347-348` says the api3
five "remains a merge candidate for a future major release, not a settled question."
The five are still one tool per REST endpoint (`rest_api.py:311`, `:339`, `:373`,
`:404`, `:549`), and `swisstopo_geocode` / `swisstopo_reverse_geocode` hit the same
SearchServer endpoint with different parameters.

### Expected Behavior
- No obvious 1:1 API mappings, or a documented argument that aggregation is impossible
- Tool count justified against the budget

### Evidence
- Count verified at runtime: 24 tools (`mcp.list_tools()`), matching tool-hashes.json (24 entries, `scripts/snapshot_tool_hashes.py --check` reports «up to date (24 tools)»). Against the check's heuristic bands that is squarely in «16–25: ernste Zweifel, ob alle nötig sind», twice the stated ideal of <=12.
- The documented justification does exist and is substantive, in both READMEs as claimed: README.md:334-364 «Tool budget and aggregation» and README.de.md:324-354 «Tool-Budget und Aggregation». It argues per cluster (api3 five, search→detail pairs, existing aggregation) rather than restating the number, and it is section-parallel across the two languages.
- The api3 five are still a textbook one-tool-per-REST-endpoint mapping, which is the check's second pass criterion and it is unmet: swisstopo_search_layers → /rest/services/ech/SearchServer (rest_api.py:311), swisstopo_identify_features → /rest/services/ech/MapServer/identify (rest_api.py:339), swisstopo_find_features → /rest/services/ech/MapServer/find (rest_api.py:373), swisstopo_get_feature → /rest/services/ech/MapServer/{layer}/{id} (rest_api.py:404), swisstopo_layer_info → /rest/services/api/MapServer/{layer} (rest_api.py:549). A sixth pair, swisstopo_geocode and swisstopo_reverse_geocode, both call the same SearchServer endpoint with different params (rest_api.py:311-330 vs :339-360 region).
- The README's own text concedes the criterion rather than satisfying it. README.md:347-348: «This remains a merge candidate for a future major release, not a settled question.» The check's escape clause is «dokumentierte Begründung im README warum keine Aggregation möglich» — the README argues that merging would relocate the decision rather than that aggregation is impossible, and then defers it. That is a roadmap entry dressed as a justification.
- Real aggregation did land and is not merely argued: swisstopo_oereb_at (src/swisstopo_mcp/oereb.py:305) collapses one of the two search→detail pairs the previous finding named, and swisstopo_query_geodata (src/swisstopo_mcp/geodata.py) fronts three sources behind one tool. The count went 23 → 24 in the same batch, so the net movement toward the budget is negative.

Gaps:
- Pass criterion «keine offensichtlichen 1:1-API-Mappings» is unmet and acknowledged as unmet by the repo itself.
- The disjoint-argument-shapes argument is genuinely strong for identify/find/get_feature (a geometry vs an attribute pair vs an opaque ID) but is not made at all for the weaker cases it silently sweeps in: search_layers + layer_info are a discovery pair over the same catalogue, and geocode + reverse_geocode differ only in whether a bbox or a searchText is sent to one endpoint.
- The self-imposed budget of 25 is a README assertion with no CI gate — nothing fails if tool 26 is registered, unlike the tool-hash and egress-ACL snapshots which are gated in .github/workflows/ci.yml:40-48.

### Risk Description
Tool-selection accuracy degrades with surface size, and the degradation is worst
exactly where this surface is densest: five tools over one MapServer that differ in
argument shape rather than in what the user is asking for. The count moved 23 → 24 in
the consolidation batch, so net movement toward the budget is negative. The 25-tool
ceiling is a README assertion with no CI gate, unlike the tool-hash and egress-ACL
snapshots — nothing fails when tool 26 is registered.

### Remediation
1. Accept the debt explicitly or discharge it. The honest framing is that the api3
   five are a deferred breaking change, not a justified design — say that in the
   README instead of presenting the deferral as the justification.
2. The weak pairs the README sweeps in without arguing them deserve separate
   treatment: `search_layers` + `layer_info` are a discovery pair over one catalogue,
   and `geocode` + `reverse_geocode` differ only in which parameter is sent.
   Merging either is a small, self-contained breaking change.
3. Gate the budget in CI. `scripts/snapshot_tool_hashes.py` already enumerates the
   tools; assert `len(tools) <= 25` there so the ceiling is enforced, not asserted.

### Effort Estimate
M (1-3d) for the gate and the README correction; L for the api3 merge

### Relation to run `2026-07-27T125314-Z`
Left open by the previous run with the README justification as the mitigation. The justification is good but does not satisfy the criterion it is offered against.

### Auditor Notes
Judged on the parent's specific question: does the README argument satisfy
the criterion about documented justification, or is it special pleading? It
is partly each. The section is real, bilingual, per-cluster and honest — it
is not the hand-wave the check's escape clause was written to exclude, and
it satisfies criterion 5. But the check is a checklist, and criterion 2
(«keine offensichtlichen 1:1-API-Mappings») fails on the api3 five by the
repo's own admission. A justification that concludes «this remains a merge
candidate» documents the debt; it does not discharge it. One of the two
named search→detail pairs was genuinely collapsed, and the argument quality
is high, so partial rather than fail — but not the «Closed» the previous
batch recorded.


### ARCH-007

## Finding: ARCH-007 — Capability-Aggregation: Composability intern, Atomarität extern

**Severity:** medium
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-007
**PDF-Reference:** Sec 2.3
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
`swisstopo_oereb_at` (`src/swisstopo_mcp/oereb.py:305`) is a genuine aggregate: it
calls `_fetch_egrid_features()` and then `get_oereb_extract(...)` as an in-process
coroutine (`oereb.py:347-351`), returns no intermediate EGRID, and its empty path
carries an actionable note. One tool call in, a complete answer out. Verified in
source — it does not re-enter the MCP tool layer.

The surrounding steering work claimed alongside it was not all done. The precedence
rule is in the `instructions` string (`server.py:70-76`), but the cross-reference from
the competing descriptions is absent for the ÖREB pair, which is the exact pair the
aggregate supersedes. Both READMEs still document the superseded chain as current
(`README.md:470-471`, `README.de.md:464-465`), contradicting the tool-budget section
100 lines earlier. And `asyncio.gather` appears nowhere in `src/`: `geodata.py:460-478`
issues one request per discovered collection sequentially.

### Expected Behavior
- Tool descriptions state the aggregated character and point away from superseded chains
- Tools return self-contained results, not IDs to feed back
- Aggregation tools parallelise their internal fan-out

### Evidence
- The aggregate is real and genuinely avoids a second round trip. src/swisstopo_mcp/oereb.py:305 `oereb_at()` calls `_fetch_egrid_features()` (oereb.py:325) and `_first_egrid()` internally, then at oereb.py:347-351 calls `get_oereb_extract(...)` as a plain Python coroutine with a constructed `GetOerebExtractInput`. It does not re-enter the MCP tool layer and it returns no intermediate EGRID for the model to feed back. One tool call in, a complete answer out.
- Its empty path is also correct: oereb.py:331-345 returns match_type="none" with an actionable `note` naming swisstopo_municipality_at as the next step — the ARCH-003 pattern applied at the site that most needs it.
- The precedence rule is in the instructions string as claimed: src/swisstopo_mcp/server.py:70-76 — «PRECEDENCE for point questions — prefer the direct tool over the generic one: Bauzone → swisstopo_zoning_at ... Gemeinde/BFS-Nummer → swisstopo_municipality_at. ÖREB-Beschränkungen → swisstopo_oereb_at (swisstopo_get_egrid only when the parcel ID itself is wanted).»
- CROSS-REFERENCE CLAIM IS FALSE FOR THE ÖREB PAIR. The remediation asserts the rule «is cross-referenced from the competing tool descriptions» and that get_egrid's «description no longer bills it as a precursor». Runtime introspection contradicts both: src/swisstopo_mcp/server.py:496 still reads `<use_case>Vorstufe zu swisstopo_get_oereb_extract: Koordinaten → EGRID.</use_case>` — «Vorstufe» is precisely «precursor» — and src/swisstopo_mcp/server.py:516 still reads «EGRID via swisstopo_get_egrid ermitteln». Neither description mentions swisstopo_oereb_at at all. A model reading only those two descriptions is still steered into the two-call chain.
- The cross-reference IS present for the other two clusters, so the claim is half-true rather than wholly wrong: swisstopo_identify_features (server.py, runtime description) states «Für Bauzone bzw. Gemeinde gibt es direkte Tools (swisstopo_zoning_at, swisstopo_municipality_at) — dieses Tool nur nutzen, wenn zusätzliche Rohattribute gebraucht werden».
- Both READMEs still document the superseded chain as current. README.md:470-471 «Cadastre: `swisstopo_geocode` → `swisstopo_get_egrid` → `swisstopo_get_oereb_extract`» and README.de.md:464-465 (identical). Neither «Tool workflows» section mentions swisstopo_oereb_at, so the README contradicts the README's own tool-budget section 100 lines earlier (README.md:351-355), which says the pair «has been collapsed».
- Criterion 2 (parallelisation where aggregation happens) is unmet: `asyncio.gather` appears nowhere in src/ — the only asyncio call is `asyncio.sleep` at src/swisstopo_mcp/api_client.py:274. The concrete miss is src/swisstopo_mcp/geodata.py:460-478, where `swisstopo_query_geodata` loops over discovered geodienste collections issuing one `request_with_retry` per collection sequentially. That is the check's named anti-pattern «Aggregations-Tools intern sequentiell statt parallel».

Gaps:
- Criterion «Tool-Beschreibungen erwähnen explizit den aggregierten Charakter» holds for swisstopo_oereb_at and swisstopo_query_geodata but the competing older tools do not point at them (server.py:496, :516).
- Criterion «Tools liefern gedanklich abgeschlossene Resultate (nicht nur IDs/Pointer)» still fails for swisstopo_get_egrid (returns an EGRID only, oereb.py:145-152) and swisstopo_search_layers (returns layer IDs only). Both are deliberate and both are now shadowed by an aggregate, which is the right shape — but the pointer-only tools remain exposed and, per the previous item, still self-describe as chain steps.
- No parallelisation anywhere; the one place it would pay (geodata.py:460) is sequential.

### Risk Description
A model choosing between `swisstopo_get_egrid` and `swisstopo_oereb_at` reads the two
descriptions, not the server instructions — the remediation's own reasoning says
instructions are not reliably consulted per selection decision. If the older
description still bills itself as a precursor, the aggregate is invisible at the
moment of choice and the two-call chain survives. Separately, the sequential fan-out
in `geodata.py:460` is the check's named anti-pattern: an aggregation tool whose
latency is the sum of its parts.

**Correction to my own record:** I claimed in the previous batch that
`swisstopo_get_egrid`'s description no longer bills it as a precursor. That was false
when I wrote it — a targeted replacement had silently failed. I have since verified
the agent's contradiction at runtime and fixed both descriptions; the README
workflow sections and the parallelisation gap remain open.

### Remediation
1. Update `README.md:470-471` and `README.de.md:464-465` to name `swisstopo_oereb_at`
   as the current cadastre workflow, so the README stops contradicting itself.
2. Parallelise `geodata.py:460-478` with `asyncio.gather` and a bounded semaphore.
3. Add a test that asserts the description of every superseded tool mentions its
   aggregate — the class of silent-replacement failure that produced the false claim
   above is only catchable mechanically.

### Effort Estimate
S (<1d) for 1 and 3; M for the parallelisation

### Relation to run `2026-07-27T125314-Z`
Recorded as closed. The aggregate itself was real; two of the three supporting claims were not. See the correction above.

### Auditor Notes
The parent asked two things. First: does the aggregate really avoid a second
round trip? Yes — verified in source, it is an in-process coroutine call,
not a tool re-entry. Second: is the precedence rule cross-referenced from
the competing tool descriptions? No, not for the ÖREB pair, which is the
exact pair the aggregate was built to supersede. The remediation note makes
a specific factual claim («its description no longer bills it as a
precursor») that the runtime tool manifest falsifies — server.py:496 still
says «Vorstufe». Since instructions strings are, by the remediation's own
reasoning, «not reliably consulted per selection decision», the description
layer is where the rule has to live, and there it is missing. Add the stale
README workflow sections and the absent parallelisation, and this is
partial: genuine, well-built progress on the aggregate itself, with the
surrounding steering work claimed but not done.


### CH-004

## Finding: CH-004 — OGD-CH Lizenz-Compliance: CC BY 4.0 Attribution

**Severity:** medium
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** CH-004
**PDF-Reference:** Custom (OGD-CH-Richtlinien)
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
The source and licence constants exist and are correct (`models.py:24-55`), and
`ToolResponse.error()` gained a `license` parameter (`models.py:112-129`). But an AST
scan of all envelope call sites found 14 error sites that pass `source=` without
`license=` — `overpass.py:167,175,181,188,214`, `openplz.py:410,534,559`,
`oereb.py:117,157,171,280,316,328` — each falling back to `SWISSTOPO_LICENSE` via the
default at `models.py:118`.

Runtime-confirmed: `ToolResponse.error(..., source=OSM_SOURCE)` returns OpenStreetMap
data labelled `Swiss Open Government Data (opendata.swiss)`. The success paths are
clean, and both README source tables are complete.

### Expected Behavior
- Every source a tool can emit carries its own licence, error path included

### Evidence
- The claimed constants exist and are correct: src/swisstopo_mcp/models.py:24-25 REFRAME_SOURCE/REFRAME_LICENSE, models.py:26-29 ARE_SOURCE/ARE_LICENSE (asserted separately with the ARE naming, not inherited), models.py:30-31 SWISSBOUNDARIES_SOURCE/SWISSBOUNDARIES_LICENSE, plus OEREB (39-40), GEODIENSTE (41-42), OSM/ODbL (43-44) and OPENPLZ (51-55).
- ToolResponse.error() did gain the parameter: src/swisstopo_mcp/models.py:112-129 accepts `license` alongside `source`, defaulting both to the swisstopo values.
- DEFECT — the parameter is unused at 14 of the 19 error call sites, so the error envelope attributes third-party data under the swisstopo licence. AST scan of all ToolResponse.ok/error calls found 14 that pass `source=` without `license=`: src/swisstopo_mcp/overpass.py:167,175,181,188,214 (OSM); src/swisstopo_mcp/openplz.py:410,534,559 (OpenPLZ); src/swisstopo_mcp/oereb.py:117,157,171,280,316,328 (cantonal ÖREB). Every one silently falls back to SWISSTOPO_LICENSE via the models.py:118 default.
- RUNTIME CONFIRMED — reproducing the exact call shapes: ToolResponse.error(..., source=OSM_SOURCE) yields source='OpenStreetMap — Overpass API (overpass.osm.ch)' with license='Swiss Open Government Data (opendata.swiss)'. ODbL data is emitted under a Swiss OGD licence label — the share-alike obligation disappears. Same for OpenPLZ and for the cantonal ÖREB terms, which are the most restrictive licence in the server.
- The success paths are clean by contrast: every ToolResponse.ok() call that sets a non-default source also sets the matching licence — rest_api.py:465,501 (ARE, swissBOUNDARIES3D), coords.py:308 (REFRAME), overpass.py:209-211 (OSM/ODbL), openplz.py:402,434,446,470,492,513,551 (OpenPLZ), oereb.py:128,148,187,206,271,333 and geodata.py:280,333,382,399,453,489 (ÖREB, geodienste).
- The README source-and-licence table was added to both files and is complete: README.md:366-384 and README.de.md:355-373 list all eight sources with the serving tools and the licence, including OpenStreetMap → "ODbL — © OpenStreetMap contributors" and OpenPLZ → "Free use — attribution required", plus the non-binding caveat for ch.are.bauzonen.

Gaps:
- 14 error call sites need `license=` added (overpass.py 5×, openplz.py 3×, oereb.py 6×). Better: make source and licence a single argument — a paired constant or a source enum — so they cannot drift apart again, since a defaulted licence is exactly the failure this finding produced twice.
- No test asserts the source/licence pairing. tests/test_responses.py covers the envelope but nothing checks that a given source always travels with its own licence, so the regression was invisible.
- README table row for the cantonal ÖREB cadastre lists only swisstopo_get_egrid and swisstopo_get_oereb_extract; swisstopo_oereb_at (oereb.py:333) and swisstopo_query_geodata (geodata.py:399) also emit OEREB_SOURCE.
- geodata.py:531-533 (list_available_layers) emits a composite source with license='gemischt — siehe je Layer'. Acceptable for a discovery tool, but the per-record provenance the check asks for on aggregation is not present in the result records.

### Risk Description
ODbL is share-alike. Relabelling it as Swiss OGD is not a missing field but a licence
misstatement: a downstream consumer acting on the envelope's own attribution would
conclude no share-alike obligation attaches. The cantonal ÖREB terms — the most
restrictive licence in the server — are misattributed the same way, and ÖREB errors
are common by construction, since only ZH is enabled by default.

### Remediation
1. Make source and licence a single argument. A `SourceRef` pair (or a small enum
   keyed on source) removes the possibility of drift; a defaulted licence is exactly
   the failure this finding has now produced twice.
2. Until then, add `license=` at the 14 sites.
3. Add the test that would have caught it: for every constructed envelope, a
   non-default `source` implies the matching `license`.
4. Add `swisstopo_oereb_at` and `swisstopo_query_geodata` to the README's ÖREB row.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Recorded as closed. The constants, the parameter and the README tables were delivered; passing the parameter was not.

### Auditor Notes
Three of the four claims check out: the ARE / swissBOUNDARIES3D / REFRAME
constants exist, ToolResponse.error() has the licence parameter, and both
READMEs carry a complete and accurate eight-source table. The fourth —
that every source a tool can emit carries correct attribution, error path
included — does not. The parameter was added but almost never passed: 14
error sites hand back a non-swisstopo source under the swisstopo licence,
confirmed by executing the exact call shapes. The OSM case is the sharp
one, since ODbL is share-alike and relabelling it as Swiss OGD is a
licence misstatement rather than a missing field. Partial.


### OBS-001

## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** OBS-001
**PDF-Reference:** Sec 6.1
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
Execution errors are handled rather than raised — every handler wraps its body and
returns `ToolResponse.error(...)`, so no upstream failure escapes as a JSON-RPC error.
That is the half of the check that matters most, and it holds across all 24 tools.

The other half does not. The error flag never reaches the protocol layer: a runtime
`tools/call` probe returns a JSON payload containing `"is_error": true` and a tool
result with **no** protocol-level `isError` field. Nothing maps `models.py:86` onto
`mcp.types.CallToolResult.isError`.

Both READMEs (`README.md:450-452`, `README.de.md:444-446`) claim protocol errors are
emitted as JSON-RPC errors with standard codes such as `-32602`. A runtime probe
contradicts this for mcp 1.28.1: unknown tools and missing arguments both come back
as `isError` tool results, not JSON-RPC error objects.

### Expected Behavior
- Execution errors returned as tool results with `isError: true`
- Protocol errors as JSON-RPC errors
- Documented behaviour matches actual behaviour

### Evidence
- Execution errors are handled, not raised: every tool handler wraps its body in try/except and returns ToolResponse.error(...) — e.g. src/swisstopo_mcp/height.py:167-168, src/swisstopo_mcp/rest_api.py:334, src/swisstopo_mcp/stac.py:167. No handler lets an upstream failure escape as a JSON-RPC error.
- But the error flag never reaches the MCP protocol layer. Runtime probe (stdio, tools/call swisstopo_elevation_profile with a single coordinate pair) returns result.content[0].text = a JSON blob containing "is_error": true, and the tool result carries NO protocol-level isError field. The envelope field is defined at src/swisstopo_mcp/models.py:86 and set at models.py:126; nothing maps it onto mcp.types.CallToolResult.isError.
- README.md:450-452 and README.de.md:444-446 claim protocol errors are emitted as JSON-RPC errors with standard codes ("e.g. -32602 invalid params"). Runtime probe contradicts this: an unknown tool returns {"result":{"content":[{"text":"Unknown tool: does_not_exist"}],"isError":true}} and a missing required argument returns an isError tool result carrying the raw Pydantic message — neither is a JSON-RPC error object.
- Error-path test coverage exists for the execution side (tests/test_api_client.py:67-86 asserts the 404/timeout/connect/unexpected classifications) and per-tool error tests exist (e.g. tests/test_openplz.py, tests/test_overpass.py), but no test asserts the shape of the tool result at the protocol boundary — the mismatch between documented and actual protocol behaviour was invisible to the suite.

Gaps:
- ToolResponse.is_error is a payload convention only; a client that reads CallToolResult.isError (the spec mechanism) sees success for every handled error.
- No test exercises tools/call end-to-end and asserts the isError flag, so the documented-vs-actual divergence is uncaught.
- The READMEs' JSON-RPC error-code claim is factually wrong for this SDK version (mcp 1.28.1) and should be corrected or the behaviour changed.

### Risk Description
A spec-conformant client reads `CallToolResult.isError`. Here it reads `false` for
every handled error, because the server invented a payload-level convention instead.
Any consumer that branches on the protocol flag — retry logic, error dashboards, an
orchestrating agent — treats every upstream failure as a success and passes a German
error string downstream as though it were geodata.

### Remediation
1. Set the protocol flag. Return a `CallToolResult` with `isError=True` (or use the
   SDK mechanism that maps onto it) when `ToolResponse.is_error` is true, keeping the
   payload field for backward compatibility.
2. Add an end-to-end test that issues `tools/call` over a real session and asserts the
   flag — no current test crosses the protocol boundary, which is why the
   documentation could drift this far.
3. Correct the JSON-RPC error-code claim in both READMEs to describe what this SDK
   version actually does.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
New in this run. Not raised by `2026-07-27T125314-Z`, which recorded OBS-001 as passing.

### Auditor Notes
The separation the check cares about most — execution errors must not
become JSON-RPC errors — holds cleanly across all 24 tools. What is
missing is the other half: the spec's isError flag on the tool result.
The server invented its own payload field instead, and then documented
protocol behaviour (-32602) that a runtime probe shows the SDK does not
produce. Partial rather than pass because a spec-conformant client cannot
distinguish a handled error from a success without parsing the JSON body.


### OBS-002

## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** OBS-002
**PDF-Reference:** Sec 6.2
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
Central masking is correct for the generic path: `api_client.py:384-414` classifies
HTTP/timeout/connect errors into fixed messages and returns only "Unerwarteter
interner Fehler…" for anything unexpected, logging the detail to stderr. No
`traceback.format_exc()` anywhere in `src/`. Regression-tested at
`tests/test_api_client.py:80-86`.

Two paths bypass it. `overpass.py:145-146` returns `text.strip()[:300]` of any body
containing the substring "error", interpolated into the tool summary at
`overpass.py:176`; executed against a realistic Overpass error page, the summary came
back containing the server path `/opt/osm/db/overpass_db` and the echoed query.
Separately, `api_client.py:133-136` raises `PermissionError` embedding
`sorted(ALLOWED_HOSTS)`, and `handle_api_error` returns it verbatim
(`api_client.py:407-409`), handing the LLM the full ten-host egress allow-list;
`api_client.py:115-118` similarly returns a resolved internal IP.

### Expected Behavior
- No upstream body, URL or internal configuration in a user-facing message

### Evidence
- Central masking exists and is correct for the generic path: src/swisstopo_mcp/api_client.py:384-414 classifies HTTP status / timeout / connect errors into fixed German messages and, for anything unexpected, logs the detail to stderr (api_client.py:413) and returns only "Unerwarteter interner Fehler. Bitte später erneut versuchen." (api_client.py:414). No traceback.format_exc()/sys.exc_info() anywhere in src/.
- LEAK — raw upstream body reaches the user: src/swisstopo_mcp/overpass.py:145-146 falls back to `return text.strip()[:300]` on any body containing the substring "error", and that string is interpolated straight into the tool summary at overpass.py:176 (`f"Overpass-Fehler: {err}"`). Executed against a realistic Overpass error page, the tool summary came back containing the server-side filesystem path `/opt/osm/db/overpass_db`, the RAM figure and the full submitted Overpass query with the user's coordinates.
- LEAK — internal egress configuration reaches the user: src/swisstopo_mcp/api_client.py:133-136 raises PermissionError whose message embeds `sorted(ALLOWED_HOSTS)`; handle_api_error treats PermissionError as a user-facing validation error (api_client.py:407-409, `return f"{prefix}{e}"`), so a blocked request hands the LLM the server's complete ten-host egress allow-list. api_client.py:115-118 similarly returns the resolved internal IP address.
- Argument validation errors are returned verbatim by the SDK: runtime probe of tools/call swisstopo_geocode with an empty params object returned "Error executing tool swisstopo_geocode: 1 validation error for swisstopo_geocodeArguments … https://errors.pydantic.dev/2.13/v/missing" — internal model name and dependency version disclosed. Not the server's code, but `mask_error_details` is not available to mitigate it (see gaps).
- Masking is regression-tested: tests/test_api_client.py:80-82 asserts a RuntimeError produces "Unerwarteter interner Fehler" and tests/test_api_client.py:86 asserts intentional ValueError guidance survives.

Gaps:
- overpass.py:146 must not return the raw body; the 300-char fallback should be dropped or replaced with a fixed message, with the body logged to stderr only.
- PermissionError messages should not travel to the LLM verbatim — the allow-list and resolved IP belong in the log, not the tool result.
- mask_error_details=True is not set on the FastMCP init (src/swisstopo_mcp/server.py:49-62). Verified against the installed SDK: mcp.server.fastmcp.FastMCP.__init__ has no such parameter (mcp 1.28.1), so this pass criterion is not achievable without switching to the standalone fastmcp package. Handled defence-in-depth by the try/except-everything pattern instead.

### Risk Description
The Overpass path is an unconditional passthrough of up to 300 characters of a
third-party HTML body into text the model will read and may quote. Two things follow:
infrastructure disclosure (a filesystem path, tuning figures), and a prompt-injection
channel — a hostile or compromised Overpass instance controls text that lands in the
model's context. The allow-list disclosure is lower impact, since the hosts are public
federal endpoints, but it is internal configuration crossing the trust boundary on a
provokable error.

### Remediation
1. Drop the 300-char fallback at `overpass.py:146`. Log the body to stderr, return a
   fixed message.
2. Split `PermissionError` messages: full detail to the log, a bare "Ziel nicht auf
   der Egress-Allow-List" to the caller. Same for the resolved IP at
   `api_client.py:115-118`.
3. `mask_error_details=True` is **not** available — verified against the installed
   SDK, `mcp.server.fastmcp.FastMCP.__init__` has no such parameter in mcp 1.28.1.
   The try/except-everything pattern is the substitute; note that in `SECURITY.md`
   rather than leaving the criterion looking merely unimplemented.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
New in this run. `2026-07-27T125314-Z` recorded OBS-002 as passing on the strength of the central masking, without checking the module-level paths.

### Auditor Notes
The remediation's core claim — unexpected exceptions are masked — is real
and tested. But the check asks whether ANY upstream body or URL can reach
a user-facing message, and two paths do. The Overpass one is the serious
one: it is an unconditional passthrough of up to 300 characters of a
third-party HTML body, and a realistic Overpass error page contains a
server filesystem path plus the echoed query. The egress-allow-list
disclosure is lower impact (the hosts are public federal endpoints) but is
still internal configuration leaving the trust boundary on a provokable
error. Partial.


### OBS-006

## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

**Severity:** medium
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** OBS-006
**PDF-Reference:** Anhang B10
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
Two of the three claims survive a running interpreter. The no-op behaviour is exactly
as advertised, verified four ways: with `OTEL_EXPORTER_OTLP_ENDPOINT` unset,
`setup_tracing()` returns `False`, `httpx.AsyncClient.send` is not patched, the global
provider stays `ProxyTracerProvider`, and the real stdio server logs
`{"reason": "OTEL_EXPORTER_OTLP_ENDPOINT unset", "event": "tracing_disabled"}`. The
tool span carries exactly `{'mcp.tool.name', 'mcp.tool.result.is_error'}` — no
arguments.

The third is refuted. With tracing enabled, the httpx auto-instrumentation that
`observability.py:79` switches on emits a child span with
`http.url = https://api3.geo.admin.ch/...?searchText=Seilergraben+76%2C+Z%C3%BCrich&lat=47.3769`.
Every tool argument that becomes a query parameter is exported verbatim. The test at
`tests/test_observability.py:104` never enables the instrumentation, so it passes
while the leak path is untested.

### Expected Behavior
- Tool arguments never become span attributes
- Per-call spans with tool name and outcome

### Evidence
- SDK present and wired: pyproject.toml:38-41 declares opentelemetry-api/sdk/exporter-otlp/instrumentation-httpx as runtime (not optional) dependencies; src/swisstopo_mcp/observability.py:58-84 builds a TracerProvider with a Resource carrying service.name, adds BatchSpanProcessor(OTLPSpanExporter()) and calls HTTPXClientInstrumentor().instrument(). setup_tracing() runs first in the lifespan at src/swisstopo_mcp/server.py:36, before create_shared_client() at server.py:37 — the ordering the httpx patching requires.
- RUNTIME VERIFIED — the no-op claim holds. With OTEL_EXPORTER_OTLP_ENDPOINT unset: setup_tracing() → False, tracing_enabled() → False, get_tracer() → None, httpx.AsyncClient.send is NOT patched, and the global provider stays the inert ProxyTracerProvider. A @log_tool_call-decorated handler still returned its result unchanged. Driving the real stdio server with SWISSTOPO_LOG_LEVEL=DEBUG produced {"reason": "OTEL_EXPORTER_OTLP_ENDPOINT unset", "event": "tracing_disabled"} and nothing else tracing-related. Guard at observability.py:53-56; an all-whitespace value also counts as unset (.strip()).
- RUNTIME VERIFIED — the tool span itself excludes arguments. With a real TracerProvider + InMemorySpanExporter and a handler invoked as handler(search_text="Seilergraben 76, Zürich", lat=47.3769), the emitted span `mcp.tool/swisstopo_geocode` carried exactly {'mcp.tool.name': 'swisstopo_geocode', 'mcp.tool.result.is_error': False} — no argument values, no extra keys. Implementation at src/swisstopo_mcp/logging_config.py:88-115.
- RUNTIME REFUTED — the argument-exclusion claim fails end to end. Set OTEL_EXPORTER_OTLP_ENDPOINT, ran setup_tracing() (which returned True and instrumented httpx), then issued a real geo_admin_request through the respx-mocked client. The httpx auto-instrumentation emitted a child span `GET` with http.url = `https://api3.geo.admin.ch/rest/services/ech/SearchServer?searchText=Seilergraben+76%2C+Z%C3%BCrich&lat=47.3769`. The user's address and coordinates land in the observability backend verbatim as a span attribute — via the very instrumentation observability.py:79 enables. The exclusion is enforced on the parent span only; the child span defeats it.
- Handled errors are read from the envelope rather than inferred: logging_config.py:110-115 sets mcp.tool.result.is_error from getattr(result, 'is_error', False), and exceptions are recorded at logging_config.py:99-101. Both covered by tests/test_observability.py:81-102.
- OTLP configuration is env-driven and documented, not hardcoded: deploy/kubernetes.yaml:51-56 sets OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT (empty = off) and OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production; docs/deployment.md:58-60 documents all three.

Gaps:
- The httpx child spans carry full request URLs including query strings. Every tool argument that becomes a query parameter — geocoding search text, coordinates, canton, PLZ, layer and feature IDs, the Overpass area — is exported to the tracing backend. Needs a span processor or an httpx-instrumentation url-sanitising hook that strips or hashes the query string before export.
- tests/test_observability.py:104-117 asserts argument exclusion on the tool span only. It never enables the httpx instrumentation, so the test passes while the actual leak path is untested — the test's own claim ("must not land in a tracing backend") is broader than what it verifies.
- No mcp.user.id attribute. Defensible here (auth_model=none, no identity exists), but the check lists it as a per-call span requirement, so the user-behaviour-analysis workflow the check motivates is unavailable.

### Risk Description
"Arguments are excluded" is true of the span the module writes and false of the system
the module configures. The leak only bites when tracing is switched on — that is,
precisely in the cloud deployment this check applies to. Addresses, coordinates,
canton, PLZ and the Overpass area land in the observability backend, which typically
has a different retention policy and a wider access list than the server itself. The
test's stated claim ("must not land in a tracing backend") is broader than what it
verifies, so the gap is invisible to CI.

### Remediation
1. Sanitise the URL before export — either an httpx-instrumentation hook that strips
   or hashes the query string, or a span processor that rewrites `http.url` and
   `url.query` on child spans.
2. Extend `tests/test_observability.py` to enable the httpx instrumentation and assert
   no argument value appears in any exported span, parent or child. Testing only the
   span you wrote is what let this through.
3. Document the residual: even with query strings stripped, the request path can carry
   identifiers (`collection_id`, feature IDs).

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Implemented and recorded as closed in the same batch. The no-op and tool-span claims hold; the exclusion claim does not survive end to end.

### Auditor Notes
Two of the three claims survive contact with a running interpreter: the
no-op behaviour is exactly as advertised (verified four ways, including
against the real stdio server), and the tool span carries only the tool
name and the error flag. The third does not. "Tool arguments never become
span attributes" is true of the span the module writes and false of the
system the module configures: enabling httpx auto-instrumentation is what
puts `?searchText=Seilergraben+76,+Zürich&lat=47.3769` into an exported
span attribute. Since this only bites when tracing is switched on — i.e.
precisely in the cloud deployment this check applies to — it is a real
defect rather than a documentation nit. Partial.


### OPS-001

## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** OPS-001
**PDF-Reference:** Anhang C1
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
The nightly workflow is real and correct: `.github/workflows/live-test.yml` parses,
triggers on `cron "0 4 * * *"` plus `workflow_dispatch`, runs `pytest tests/ -m live`,
and files a deduplicated issue on failure. The marker is registered
(`pyproject.toml:69-71`) so `-m live` is not a silent no-op, and PR CI runs
`-m "not live"` across 3.11/3.12/3.13. 545 test functions across 27 files.

Coverage is not per-tool. The 17 tool-level live tests leave roughly ten tools with
none: `find_features`, `get_feature`, `layer_info`, `municipality_at`,
`get_collection`, `map_url`, `get_egrid`, `get_oereb_extract`, `oereb_at`,
`search_address`.

### Expected Behavior
- ≥1 live test per tool
- Separated from PR CI so an upstream outage cannot fail an unrelated PR

### Evidence
- The nightly workflow exists and is structurally valid: .github/workflows/live-test.yml parses cleanly (yaml.safe_load → job `live-tests`), triggers on `schedule: cron "0 4 * * *"` plus workflow_dispatch, runs `pytest tests/ -m live -v`, and on failure creates a deduplicated issue labelled `live-test-failure` via actions/github-script (it lists open issues with that label first and only creates one when none exist).
- `live`-marked tests really exist — 19 occurrences of @pytest.mark.live across 10 files, 17 of them tool-level: tests/test_geocoding.py:349,355,362; tests/test_height.py:393,399; tests/test_rest_api.py:361,367; tests/test_openplz.py:371,378,384; tests/test_geodata.py:246,255,268; tests/test_overpass.py:154; tests/test_coords.py:205; tests/test_stac.py:386; tests/test_places.py:282. Two more (tests/test_dns_pinning.py:138,171) cover the SEC-005 TLS/SNI handshake.
- The marker is registered so `-m live` is not a silent no-op: pyproject.toml:69-71 `markers = ["live: live API tests (skipped in CI by default)"]`.
- PR CI excludes them: .github/workflows/ci.yml runs `pytest tests/ -m "not live"` across Python 3.11/3.12/3.13, so an upstream outage cannot fail an unrelated PR — the separation the check asks for.
- Unit-test volume far exceeds the ≥5-per-tool bar: 545 test functions across 27 files for 24 tools.
- GAP — live coverage is not per-tool. Mapping the 17 tool-level live tests to the 24 tools leaves roughly ten with no live test at all: swisstopo_find_features, swisstopo_get_feature, swisstopo_layer_info, swisstopo_municipality_at, swisstopo_get_collection, swisstopo_map_url, swisstopo_get_egrid, swisstopo_get_oereb_extract, swisstopo_oereb_at and swisstopo_search_address. The ÖREB group is the notable one: it is the only cantonal, per-canton-format dependency in the server and therefore the most schema-drift-prone, and nothing nightly touches it.

Gaps:
- ≥1 live test per tool is not met — about ten tools, including the three ÖREB tools, have none.
- respx is used in only 6 of 27 test files (test_coords, test_lv95_input, test_oereb, test_openplz, test_places, test_retry); the rest mock by monkeypatching the api_client helpers, which does not exercise the URL/params/response-parsing layer the check wants respx for.
- Unverifiable in this environment: the workflow pins actions/checkout@v7, actions/setup-python@v6 and actions/github-script@v8. Outbound access to the GitHub API for actions/* is blocked here, so tag existence could not be confirmed. If any tag does not resolve, the nightly run — or specifically the failure-reporting step, which only executes `if: failure()` — fails silently for the reader.

### Risk Description
The point of the nightly job is detecting upstream contract drift. The three ÖREB
tools are the only cantonal, per-canton-format dependency in the server — the most
drift-prone upstream by a wide margin — and nothing nightly touches them. A ZH schema
change would surface as a user-visible failure rather than as a 04:00 issue.

### Remediation
1. Add live tests for the ÖREB cluster first; a known ZH parcel with a stable EGRID is
   enough to detect a schema change.
2. Then the remaining seven, at the same shallow depth — the job is drift detection,
   not correctness.
3. Widen respx use beyond the six files that have it, so the URL/params/parsing layer
   is exercised rather than monkeypatched over.
4. Unverifiable here: the workflow pins `actions/checkout@v7`, `setup-python@v6`,
   `github-script@v8` and outbound access to the GitHub API is blocked in this
   sandbox. If any tag does not resolve, the failure-reporting step — which only runs
   `if: failure()` — fails silently. Confirm the tags resolve.

### Effort Estimate
M (1-3d)

### Relation to run `2026-07-27T125314-Z`
Raised and remediated in the previous run. The workflow claim holds in full; the per-tool criterion was never met.

### Auditor Notes
The specific remediation claim holds: the workflow is real, valid, nightly,
dispatchable, runs only the live marker, and files a deduplicated issue on
failure; the marker is registered and PR CI excludes it. What keeps this
off a pass is the check's per-tool live-coverage criterion. Ten tools have
no live test, so the nightly job cannot detect contract drift for them —
and the ÖREB cluster, the most fragile upstream in the server, is among
them. Unit-side depth is excellent; the respx criterion is met in spirit
for six modules only.


### OPS-003

## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** OPS-003
**PDF-Reference:** Anhang C4
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
The headline contradiction from the previous run is closed: `README.md:319` and
`README.de.md:317` both declare Phase 2.5, matching `docs/roadmap.md`. Tool
annotations match the declared phase — all 24 registrations carry `readOnlyHint=True`
and `destructiveHint=False`, verified mechanically.

Three things claimed were not fully delivered. The status table and advance criteria
went into `README.md:322-332` only; `README.de.md:317-322` has neither — the same
bilingual-drift failure mode as the original finding. Both READMEs still assert
"Phase-1 read-only wrapper" 138 lines further down (`README.md:457`,
`README.de.md:451`). And the two documents name each other as authoritative:
`README.md:320` calls the roadmap "the single authority for phase state", while
`docs/roadmap.md:3-4` points back at the README.

### Expected Behavior
- One authoritative phase declaration, consistent across all documents
- Explicit advance criteria per phase

### Evidence
- The headline contradiction from run 2026-07-27T125314-Z is closed: README.md:319 and README.de.md:317 both declare "Phase 2.5 — Consolidation of `swiss-geodata-mcp`", which matches the docs/roadmap.md heading "## Phase 2.5 — Consolidation of `swiss-geodata-mcp` (✅ done)".
- A phase status table and explicit advance criteria were added — but to the ENGLISH README only. README.md:322-332 carries the table (Read tools / Write tools / Transport / Last audit) plus the three advance conditions. README.de.md:317-322 is three sentences of prose with neither table nor criteria. The remediation is half-applied, which is the same bilingual-drift failure mode as the original finding.
- Residual Phase-1 claims survive inside both READMEs: README.md:457 ("it is a Phase-1 read-only wrapper") and README.de.md:451 ("Er ist ein Phase-1-Read-only-Wrapper"), 138 lines below the section that declares Phase 2.5. A reader landing on the MCP-Primitives section still gets the old answer.
- The two documents each name the other as authoritative: README.md:320 calls docs/roadmap.md "the single authority for phase state", while docs/roadmap.md:3-4 says "The current phase is declared in the README (\"Security & Compliance\" section)". The circular reference means neither is authoritative.
- Phase matches the tool annotations, verified mechanically: all 24 @mcp.tool declarations in src/swisstopo_mcp/server.py carry readOnlyHint=True (24 occurrences) and destructiveHint=False (24 occurrences); `grep -rn 'destructiveHint=True' src/` returns nothing.
- The phase correction is recorded in the CHANGELOG under Unreleased (CHANGELOG.md:65-67), satisfying the ARCH-012 synergy requirement.

Gaps:
- README.de.md needs the same status table and advance criteria as README.md:322-332, or the two documents are not synchronised.
- README.md:457 / README.de.md:451 still assert Phase 1 and must be reworded.
- Circular authority claim between README.md:320 and docs/roadmap.md:3-4 must be resolved to one document.
- The check's Phase-1→2 gate requires an ISDS classification and a DSG Verarbeitungsverzeichnis; neither exists in docs/ (only deployment.md, geodaten-erweiterung-phase1.md, merge-plan-swiss-geodata-mcp.md, network-egress.md, roadmap.md), and the roadmap's Phase-1 checklist does not list them. Arguably reducible for federal open data with no personal data, but the gate is not documented as waived.
- README.md:327 lists the Last audit as `audits/2026-07-27T162602-Z-swisstopo-mcp/` — this run, which is still in progress and has no report yet. The claim precedes the evidence.

### Risk Description
The circular authority claim means neither document is authoritative, so the next
contradiction has nothing to be resolved against. A reader landing on the
MCP-Primitives section still gets the Phase-1 answer, which understates the current
surface. This is documentation risk rather than runtime risk, but the phase
declaration is what gates the write-tool review — it needs to be unambiguous.

### Remediation
1. Port the status table and advance criteria into `README.de.md`.
2. Reword `README.md:457` and `README.de.md:451`.
3. Break the circle: make `docs/roadmap.md` the single authority and have both READMEs
   link to it without restating.
4. The check's Phase-1→2 gate wants an ISDS classification and a DSG
   Verarbeitungsverzeichnis. Neither exists. For federal open data with no personal
   data the case for waiving them is strong — but document the waiver rather than
   leaving the gate silently unmet.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Remediated in the previous run; half-applied. Note `README.md:327` cites this run as the last audit — a claim that preceded its evidence, and is only made true by this report.

### Auditor Notes
The specific defect the previous run named — READMEs saying Phase 1 while
the roadmap said 2.5 — is genuinely fixed in the phase sections. But three
checkable things the remediation claimed are not fully there: the German
README got neither the table nor the criteria, both READMEs still contain
a literal "Phase-1 read-only wrapper" sentence further down, and the two
documents point at each other for authority. Tool annotations do match the
declared phase, which is the substantive half of the check. Partial.


### SCALE-002

## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SCALE-002
**PDF-Reference:** Sec 5.2
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
The default deployment sidesteps the problem deliberately and with documentation:
`replicas: 1` (`deploy/kubernetes.yaml:18`) with a comment explaining that
Streamable-HTTP sessions are per-pod, repeated in `docs/deployment.md:98-110`. That is
an honest choice and makes the problem moot today.

Neither escape hatch works. The HAProxy option (called "preferred") does not achieve
header affinity — see SCALE-003. The NGINX cookie option
(`deploy/ingress-sticky-sessions.yaml:28`) scopes itself to "browser clients that
carry cookies", and MCP hosts are not cookie-persisting browsers; the file's own
comment concedes NGINX cannot stick on an arbitrary request header. Neither artefact
is wired into the shipped manifests, and the Service sets no `sessionAffinity` at
all.

### Expected Behavior
- At least one affinity or shared-state pattern demonstrably implemented
- Explicit session TTL

### Evidence
- The default deployment sidesteps the problem rather than solving it, deliberately and with documentation: `replicas: 1` at deploy/kubernetes.yaml:18 with a comment at :13-17 explaining that Streamable-HTTP sessions are per-pod and that scaling out requires affinity or a shared store first. docs/deployment.md:98-110 repeats it under 'Scaling out (SCALE-002)'.
- Two opt-in affinity artefacts exist with explicit TTLs: deploy/haproxy.cfg:36-37 (`stick-table type string len 64 size 100k expire 1h` + `stick on req.hdr(Mcp-Session-Id)`) and deploy/ingress-sticky-sessions.yaml:30-52 (NGINX cookie affinity, `affinity-mode: persistent`, `session-cookie-max-age: "3600"`).
- Neither is wired into the shipped deployment: the Service at deploy/kubernetes.yaml:89-98 has no `sessionAffinity`, no Ingress is applied by deploy/kubernetes.yaml, and deploy/haproxy.cfg is a standalone file no manifest references.
- Option A (HAProxy, called 'preferred' at deploy/ingress-sticky-sessions.yaml:14 and docs/deployment.md:104-106) does not actually achieve header affinity — see SCALE-003. `stick on` is shorthand for `stick match` + `stick store-request`; the initialize request carries no Mcp-Session-Id (the server MINTS it in the response, confirmed at runtime: the 200 response carried `mcp-session-id: dc67841a766944d0927c20a291deb6e3` and the request had no such header), so nothing is stored. The first request that does carry the header misses the table and is round-robined to a possibly-wrong replica, then pinned there for the full 1h.
- Option B (NGINX cookie affinity) is inapplicable to the actual client population: deploy/ingress-sticky-sessions.yaml:28 itself scopes it to 'browser clients that carry cookies', while MCP hosts (Claude Desktop, mcp-remote and similar) are not cookie-persisting browsers. The file's own comment at :26-27 concedes NGINX cannot stick on an arbitrary request header.
- No shared-state alternative is implemented: no redis/memcached/SessionStore anywhere in src/, and Option C at deploy/ingress-sticky-sessions.yaml:54-58 is explicitly declared out of scope.

Gaps:
- No failover test and no test of any kind covering session affinity — Modus 3 of the check is not satisfied by tests either.
- Both offered patterns have a correctness or applicability defect, so a reader who follows docs/deployment.md:102-110 and raises `replicas` will get broken sessions in the majority of cases.
- The Service does not even set `sessionAffinity: ClientIP` as a crude fallback for the raise-replicas case.

### Risk Description
The single-replica default is safe. The danger is the documented upgrade path: a
reader who follows `docs/deployment.md:102-110` and raises `replicas` gets broken
sessions in the majority of cases, and gets them intermittently rather than
immediately — the failure looks like flaky clients, not like a misconfiguration.

### Remediation
1. Fix the HAProxy config (SCALE-003) or stop calling it preferred.
2. Set `sessionAffinity: ClientIP` on the Service as a crude fallback, so raising
   replicas degrades rather than breaks.
3. State plainly in `docs/deployment.md` that no verified multi-replica path exists
   yet — the current text implies two working options.

### Effort Estimate
M (1-3d)

### Relation to run `2026-07-27T125314-Z`
Left open by the previous run. The new information is that both offered patterns are defective, not merely unwired.

### Auditor Notes
The check asks for at least one affinity or shared-state pattern to be
demonstrably implemented. Nothing is implemented in the applied path — the
single-replica default makes the problem moot today, which is an honest and
documented choice, so this is not a fail. But the two escape hatches offered for
the moment someone scales out do not hold up under scrutiny: the HAProxy config
never learns the session-to-backend mapping (it only reads the header, never
stores it from the response), and cookie affinity does not apply to non-browser
MCP clients. TTLs are set on both, which satisfies one criterion. Partial.


### SCALE-003

## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SCALE-003
**PDF-Reference:** Sec 5.2
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
`deploy/haproxy.cfg` is a complete, parseable config with transport-aware timeouts
(`timeout tunnel 1h`), a 100k stick-table with `expire 1h`, an explicit
`stick on req.hdr(Mcp-Session-Id)` and a wired health check. The nominal checklist
items are met.

It would not work. `stick on` is shorthand for `stick match` + `stick store-REQUEST`.
The session id is minted by the server in the **response** — verified at runtime, an
`initialize` POST carrying no `Mcp-Session-Id` returned 200 with
`mcp-session-id: dc67841a766944d0927c20a291deb6e3`. On that request the pattern is
empty, so nothing is stored. The client's next request is the first to carry the
header, misses the empty table, is round-robined to a replica that with two servers is
wrong half the time, and is then pinned there for the full hour.

Second defect: `server mcp1 swisstopo-mcp-1:8000` / `mcp2 swisstopo-mcp-2:8000`
(`haproxy.cfg:45-46`) name hosts nothing in `deploy/` creates — there is a Deployment
and one ClusterIP Service, not a StatefulSet or a headless Service — and with no
`resolvers` section HAProxy resolves once at startup and refuses to start on
unresolvable names. The same defective snippet is duplicated at
`deploy/ingress-sticky-sessions.yaml:17-22` and pointed at from
`docs/deployment.md:104-106`.

### Expected Behavior
- Load balancer routes on `Mcp-Session-Id`
- Stick-table sized ≥100k with an explicit TTL
- Failover behaviour tested

### Evidence
- The claim that the comment-only sketch was replaced by a real file is TRUE as far as it goes: deploy/haproxy.cfg is a complete, syntactically plausible config with global/defaults/frontend/backend sections (deploy/haproxy.cfg:12-46), mountable at /usr/local/etc/haproxy/haproxy.cfg as its header states (:8-10). Timeouts are transport-aware (`timeout server 120s`, `timeout tunnel 1h` at :24-25), which matters for a long-lived response stream.
- The header-routing criteria are nominally met: the LB reads Mcp-Session-Id explicitly (`stick on req.hdr(Mcp-Session-Id)`, deploy/haproxy.cfg:37), stick-table capacity is 100k which meets the check's >=100k floor, and TTL is explicit (`expire 1h`, :36). Health check is wired (`option httpchk GET /healthz` + `http-check expect status 200`, :42-43).
- CORRECTNESS DEFECT — the config does not actually deliver affinity. HAProxy's `stick on <pattern>` is shorthand for `stick match` + `stick store-REQUEST`. The session id is minted by the server and returned in the RESPONSE header: verified at runtime, an initialize POST carrying no Mcp-Session-Id returned 200 with `mcp-session-id: dc67841a766944d0927c20a291deb6e3`. On that request the pattern is empty, so nothing is matched and nothing is stored. The client's NEXT request is the first to carry the header — it misses the empty table, gets round-robined (deploy/haproxy.cfg:32) to a replica that with 2 servers is the wrong one 50% of the time, and `stick store-request` then pins the session to that wrong replica for the full hour.
- The missing line is `stick store-response res.hdr(Mcp-Session-Id)` — the canonical HAProxy pattern for a server-generated identifier. Without it the whole stick-table block at deploy/haproxy.cfg:36-37 is inert on the only request that could populate it.
- DEPLOYABILITY DEFECT — the backend addresses correspond to nothing this repo ships: `server mcp1 swisstopo-mcp-1:8000` / `server mcp2 swisstopo-mcp-2:8000` (deploy/haproxy.cfg:45-46). deploy/kubernetes.yaml provides a Deployment (:6-87) and a single ClusterIP Service named `swisstopo-mcp` (:89-98) — not a StatefulSet and not a headless Service, so no per-pod DNS names of that shape exist. There is also no `resolvers` section, so HAProxy resolves server names once at startup and refuses to start on unresolvable names.
- The same defective snippet is duplicated as the 'preferred' option at deploy/ingress-sticky-sessions.yaml:17-22 and pointed to as preferred in docs/deployment.md:104-106, so the error is reproduced in three places.
- No failover test exists (no test references haproxy, stick, or affinity), so the check's Modus 2 / fourth pass criterion is unmet.

Gaps:
- `stick store-response res.hdr(Mcp-Session-Id)` missing — affinity is never learned from the initialize response.
- Backend server names/addresses do not match any manifest in deploy/; no StatefulSet, no headless Service, no `resolvers` section.
- No failover behaviour test, and no documented manual verification of the routing.
- docs/deployment.md:98-110 links only to deploy/ingress-sticky-sessions.yaml and never mentions deploy/haproxy.cfg, so the 'real' config is unreferenced from the deployment docs.

### Risk Description
This is worse than having no config: it looks correct, it parses, it satisfies every
checklist item a reviewer would grep for, and it silently pins half of all sessions to
the wrong replica for an hour. The symptom at the client is a session that works for
one call and then returns "session not found" — indistinguishable from a client bug.

### Remediation
1. Add `stick store-response res.hdr(Mcp-Session-Id)` — the canonical HAProxy pattern
   for a server-generated identifier. Without it the whole stick-table block is inert
   on the only request that could populate it.
2. Either ship a StatefulSet plus a headless Service so `swisstopo-mcp-{0,1}` resolve,
   or replace the static `server` lines with a `resolvers` section against the cluster
   DNS and `server-template`.
3. Fix the duplicated snippet in `ingress-sticky-sessions.yaml` and reference
   `deploy/haproxy.cfg` from `docs/deployment.md`, which currently never mentions it.
4. Add a failover test, or document a manual verification procedure — nothing in
   `tests/` references haproxy, stick or affinity.

### Effort Estimate
M (1-3d)

### Relation to run `2026-07-27T125314-Z`
The previous run's finding was that this existed only as a comment. It is now a real file — and the real file does not work.

### Auditor Notes
Judged on whether it is genuinely deployable, the honest answer is: it is a real
file rather than a comment, and it would parse — but it would not work. Two
independent problems. First, the stick-table is never populated: `stick on`
stores from the request, and the request that establishes the session has no
session header yet, so the mapping is learned only on a later request that has
already been round-robined, pinning half the sessions to the wrong replica.
Second, the server lines name hosts no manifest in this repo creates, and with no
resolvers block HAProxy would fail to start against them. The nominal checklist
items (reads the header, 100k table, explicit TTL) are satisfied, so this is not
a fail — but calling it a deployable session-affinity config is not supportable.
Partial.


### SDK-001

## Finding: SDK-001 — FastMCP Lifespan via @asynccontextmanager + AsyncExitStack

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SDK-001
**PDF-Reference:** Sec 3.1
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
The structural criteria all pass: `@asynccontextmanager` lifespan at `server.py:30-46`,
passed via `lifespan=` at `server.py:51`, cleanup in `finally`, and no per-call client
construction on the happy path.

The claimed invariant does not hold on the HTTP transport, measured rather than read.
A freshly started `--http` server logged 0 `server_started` events at boot; after
three `initialize` POSTs it had logged exactly 3 `server_started` and 0
`server_stopped`. The lifespan runs **once per MCP session**, not once per process,
so the docstring at `server.py:32-33` ("one shared httpx.AsyncClient for the server's
lifetime") is false under `--http`.

Because `_shared_client` is a module global (`api_client.py:209`), each new session's
`set_shared_client()` clobbers the previous one. Worse, session teardown is
destructive: `DELETE /mcp` for one of three open sessions returned 200 and ran
`set_shared_client(None)` (`server.py:44`) plus `shutdown_tracing()` (`server.py:45`).
The two surviving sessions then fall through to the ephemeral per-call branch at
`api_client.py:258` — the exact anti-pattern this check forbids — with tracing torn
down underneath them.

### Expected Behavior
- One shared client for the process lifetime
- No client constructed per tool call

### Evidence
- Lifespan is present and correctly shaped: `@asynccontextmanager async def lifespan(server: FastMCP)` at src/swisstopo_mcp/server.py:30-46, passed to the constructor at src/swisstopo_mcp/server.py:51 (`lifespan=lifespan`), with cleanup in a `finally` block (`await client.aclose()` at src/swisstopo_mcp/server.py:43).
- Tool handlers do not create a client per call: the shared instance is registered via set_shared_client() (src/swisstopo_mcp/server.py:38) and returned wrapped in a non-closing adapter by _get_client() (src/swisstopo_mcp/api_client.py:239-258), so `async with await _get_client()` reuses the pool instead of closing it. follow_redirects=False and a 30s timeout are set on the client at src/swisstopo_mcp/api_client.py:220-225.
- RUNTIME DEFECT (measured, not read): under streamable-http the lifespan runs once per MCP SESSION, not once per process. A freshly started `python -m swisstopo_mcp.server --http --port 8770` logged 0 `server_started` events at boot; after three `initialize` POSTs it had logged exactly 3 `server_started` and 0 `server_stopped`. The docstring at src/swisstopo_mcp/server.py:32-33 ('one shared httpx.AsyncClient for the server's lifetime') does not hold on the HTTP transport.
- Because `_shared_client` is a module-level global (src/swisstopo_mcp/api_client.py:209), each new session's `set_shared_client(client)` (src/swisstopo_mcp/server.py:38) clobbers the previous session's client. With N concurrent sessions, N clients exist but only the newest is ever used; the older ones sit idle holding their pools until their own session ends.
- Session teardown is destructive to surviving sessions: DELETE /mcp for one of three open sessions returned HTTP 200 and produced exactly 1 `server_stopped` while 2 sessions stayed open. That path runs `set_shared_client(None)` (src/swisstopo_mcp/server.py:44) — the two live sessions then fall through to the ephemeral per-call branch at src/swisstopo_mcp/api_client.py:258, i.e. exactly the anti-pattern this check forbids — and `shutdown_tracing()` (src/swisstopo_mcp/server.py:45), which calls `provider.shutdown()` and sets `_tracer = None` (src/swisstopo_mcp/observability.py:87-102), killing tracing process-wide for the surviving sessions.

Gaps:
- No test asserts the lifespan runs once per process; tests/test_shared_client.py:33-44 only exercises set/get in isolation and cannot see the per-session re-entry.
- No guard against concurrent sessions clobbering the global — a refcount, an AsyncExitStack owned by the ASGI app lifespan, or storing the client on the app/server state instead of a module global would all fix it.
- setup_tracing()/shutdown_tracing() are not idempotent across overlapping sessions; `_instrumented` is guarded (observability.py:78) but `_tracer` and the TracerProvider are not.

### Risk Description
Reachable with two concurrent clients, which is the normal case for any deployment
that is not one desktop app. When one client disconnects, every other live session
silently degrades to a fresh `httpx.AsyncClient` per tool call: no connection reuse, a
new TLS handshake per request, and — since `_build_client` is where the pinned
transport and `follow_redirects=False` are set — the security posture is at least
reconstructed each time rather than inherited, but at a latency cost that grows with
load. Tracing stops process-wide for the survivors.

### Remediation
1. Move client ownership out of the per-session lifespan. Either an `AsyncExitStack`
   owned by the ASGI app lifespan, or store the client on the app/server state rather
   than a module global.
2. Failing that, refcount: `set_shared_client` increments, teardown decrements and
   only closes at zero. Same for `setup_tracing`/`shutdown_tracing`, which are not
   idempotent across overlapping sessions (`_instrumented` is guarded,
   `_tracer` and the provider are not).
3. Add the test that would have caught it: start the HTTP app, open two sessions,
   close one, assert the other still resolves the shared client.
4. Correct the docstring at `server.py:32-33` — it states a per-process invariant the
   HTTP transport does not provide.

### Effort Estimate
M (1-3d)

### Relation to run `2026-07-27T125314-Z`
New in this run. `2026-07-27T125314-Z` recorded SDK-001 as passing on the structural criteria without driving a running HTTP server.

### Auditor Notes
The structural pass criteria are all met (asynccontextmanager, lifespan= in the
constructor, cleanup in finally, no per-call client construction on the happy
path), so this is not a fail. But the claimed invariant was verified against a
running server rather than read, and it does not hold for the transport this
server ships in its container: the lifespan is per-session. The consequence is
concrete and reachable with two concurrent clients — ending one session nulls
the shared client for the others, degrading them to a fresh httpx.AsyncClient
per tool call, and tears down the tracer provider underneath them. Correct for
stdio, broken under --http, hence partial.


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SDK-003
**PDF-Reference:** Sec 3.1
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
3 of 24 tools take a `Context`: `elevation_profile`, `get_oereb_extract` and the new
`oereb_at`. They do use it (`ctx.info()` at `height.py:179`, `oereb.py:167`;
`ctx.report_progress()` at `height.py:204`) rather than merely accept it.

The two tools the previous run named as the actually-slow ones still have none.
`swisstopo_query_osm_features` (`server.py:615`) has a 30s client / 25s server timeout
(`overpass.py:39-40`). `swisstopo_find_commune` (`server.py:672`) drives
`_fetch_all_pages` (`openplz.py:153-185`), a `while True` page loop bounded by
`OPENPLZ_MAX_RECORDS=2000` at pageSize 50 — up to 40 sequential upstream requests with
no signal. The one `report_progress` call fires `progress=1, total=1` *after*
`geo_admin_request` has already returned: a completion marker, not a cadence. The
swallowed legend failure at `rest_api.py:546-547` is unchanged.

Positive: no `print()` anywhere in `src/`; structlog is bound to stderr, so stdout
stays reserved for the protocol.

### Expected Behavior
- `Context` on every tool with expected runtime > 2s
- Progress at a 1–2s cadence
- Swallowed upstream errors surfaced via `ctx.warning()`

### Evidence
- Only 3 of 24 tools take a Context: swisstopo_elevation_profile (src/swisstopo_mcp/server.py:363), swisstopo_get_oereb_extract (src/swisstopo_mcp/server.py:514) and swisstopo_oereb_at (src/swisstopo_mcp/server.py:535). The third is new since the previous run; the two tools the previous run named as the actually-slow ones still have none.
- Those three do use the context rather than merely accept it: `ctx.info()` at src/swisstopo_mcp/height.py:179 and src/swisstopo_mcp/oereb.py:167, `ctx.report_progress()` at src/swisstopo_mcp/height.py:204. Inner helpers keep `ctx: Context | None = None` so direct calls still work (src/swisstopo_mcp/height.py:173, src/swisstopo_mcp/oereb.py:162, :305).
- The single report_progress call is still a post-hoc completion marker, not a cadence: src/swisstopo_mcp/height.py:204 fires `progress=1, total=1` AFTER `geo_admin_request` at :189-196 has already returned. The actual wait is unreported. This is item 2 of the previous run's remediation list and it was not applied.
- swisstopo_query_osm_features — the slowest tool in the surface — still takes no ctx (src/swisstopo_mcp/server.py:615) despite a 30s client / 25s server timeout (src/swisstopo_mcp/overpass.py:39-40).
- swisstopo_find_commune still takes no ctx (src/swisstopo_mcp/server.py:672) while `_list_by_canton`/`_list_by_district` (src/swisstopo_mcp/openplz.py:458, :481, :502) drive `_fetch_all_pages` (src/swisstopo_mcp/openplz.py:153-185), a `while True` page loop bounded by OPENPLZ_MAX_RECORDS=2000 at pageSize 50 (src/swisstopo_mcp/openplz.py:49, :163) — up to 40 sequential upstream requests with no progress signal.
- The swallowed legend failure is unchanged: bare `except Exception: meta["legend"] = None` at src/swisstopo_mcp/rest_api.py:546-547, with no ctx threaded into layer_info (src/swisstopo_mcp/server.py:429), so a client cannot tell 'no legend exists' from 'legend fetch failed'. Item 3 of the previous remediation list, not applied.
- Positive on the stdio-safety criterion: no `print()` anywhere in src/; structlog is bound to stderr so stdout stays reserved for the protocol (src/swisstopo_mcp/logging_config.py, WriteLoggerFactory(file=sys.stderr)).
- Retry backoff compounds the gap: every upstream call can add 2s+4s+8s of silent waiting (src/swisstopo_mcp/api_client.py:268 RETRY_BACKOFFS), and no ctx is threaded into api_client at all, so even the three ctx-aware tools report nothing during a retry storm.

Gaps:
- No ctx on the two tools with expected runtime > 2s (query_osm_features, find_commune).
- No progress reporting at a 1-2s cadence anywhere; the one call that exists fires after the wait.
- Silently swallowed upstream errors are not surfaced via ctx.warning()/ctx.error() (rest_api.py:546-547).
- tests/test_context.py:11-32 asserts only that elevation_profile awaits ctx.info and ctx.report_progress at all — it cannot distinguish a completion marker from a cadence, so it would keep passing under every gap above.

### Risk Description
Retry backoff compounds this: every upstream call can add 2s+4s+8s of silent waiting
(`api_client.py:268`), and no `ctx` is threaded into `api_client` at all, so even the
three context-aware tools report nothing during a retry storm. From the client's side
a 45-second Overpass query is indistinguishable from a hang, and the usual response is
to cancel and retry — multiplying the load on the upstream that was already slow.

### Remediation
1. Thread `ctx` into `swisstopo_query_osm_features` and `swisstopo_find_commune`;
   report per page in `_fetch_all_pages`, which has a natural cadence.
2. Move the `height.py:204` call before the await, or report per chunk.
3. Thread an optional `ctx` into `api_client.request_with_retry` so a retry emits
   `ctx.warning()` — the silent 14 seconds is the worst of it.
4. Replace the bare `except Exception` at `rest_api.py:546-547` with a
   `ctx.warning()`, so "no legend exists" is distinguishable from "legend fetch
   failed".
5. `tests/test_context.py:11-32` asserts only that the calls happen at all; it cannot
   distinguish a completion marker from a cadence and would keep passing under every
   gap above.

### Effort Estimate
M (1-3d)

### Relation to run `2026-07-27T125314-Z`
Left open by the previous run; no remediation was claimed. Three of the four prior remediation items remain unapplied.

### Auditor Notes
This check was left open by the previous run and no remediation was claimed for
it, which matches what the source shows: three of the four remediation items are
unapplied. One tool (oereb_at) gained a ctx parameter, and the stdio-safety half
of the check (no print, stderr-bound logging) is solid, so it is not a fail. But
the substantive criteria — ctx on tools >2s, progress every 1-2s, warnings for
swallowed errors — are all still unmet on the tools that actually keep a client
waiting. Partial.


### SEC-004

## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

**Severity:** critical
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-004
**PDF-Reference:** Sec 4.4
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
Both claimed additions are real and fire on every outbound path. HTTPS enforcement
runs first (`api_client.py:126`, covered by `tests/test_egress_allowlist.py:58-71` for
`http://`, `file://`, `ftp://`, `gopher://`). The resolved-IP guard
(`api_client.py:74-87`) blocks every range the check names including
`169.254.169.254`, `::1/128`, `fe80::/10` and `fc00::/7`, and hangs off
`assert_host_allowed` (`api_client.py:137`) so the two direct-client sites in
`oereb.py` inherit it. `check_host=False` is never passed anywhere in `src/`. The
strongest real case is covered: `geodata.py:426` takes `ogc_base` from the *remote*
geodienste.ch catalogue and still cannot escape the frozenset.

TOCTOU is not closed by default. `assert_resolved_ip_public` resolves
(`api_client.py:109`) and httpx resolves again at connect time; the pinning transport
that closes the window is off unless `SWISSTOPO_PIN_DNS` is set. The `lru_cache` on
`_resolve` does not help — httpx never consults it. The guard also fails open on
`socket.gaierror` (`api_client.py:110-111`).

### Expected Behavior
- HTTPS enforced, resolved IP checked, DNS resolved once and that IP used
- Egress proxy as defence in depth

### Evidence
- HTTPS scheme enforcement is real and runs first: src/swisstopo_mcp/api_client.py:126 rejects any scheme != 'https' before the host is even looked at; tests/test_egress_allowlist.py:58-71 cover http://, file://, ftp://, gopher://.
- Resolved-IP guard exists and covers every range the check names: src/swisstopo_mcp/api_client.py:74-87 blocks 10/8, 172.16/12, 192.168/16, 127/8, 169.254/16 (incl. 169.254.169.254), 0.0.0.0/8, ::1/128, fe80::/10, fc00::/7; enforced at src/swisstopo_mcp/api_client.py:101-118 and invoked from assert_host_allowed at src/swisstopo_mcp/api_client.py:137.
- Both guards do run on every outbound path. The single retry wrapper calls assert_host_allowed unconditionally (src/swisstopo_mcp/api_client.py:293-294), and grep confirms `check_host=False` is never passed anywhere in src/ — the parameter exists only at its definition (src/swisstopo_mcp/api_client.py:285). The two direct-client sites in oereb.py both call it first: src/swisstopo_mcp/oereb.py:91 before src/swisstopo_mcp/oereb.py:92, and src/swisstopo_mcp/oereb.py:183 before src/swisstopo_mcp/oereb.py:184.
- The strongest real-world case is covered: src/swisstopo_mcp/geodata.py:426 takes `ogc_base` out of the *remote* geodienste.ch catalogue and interpolates it into request URLs at src/swisstopo_mcp/geodata.py:449 and :464 — a remotely-controlled base URL that is nonetheless forced through assert_host_allowed by request_with_retry. Redirect-based bypass is closed by follow_redirects=False at src/swisstopo_mcp/api_client.py:223.
- TOCTOU is NOT closed on the default path. assert_resolved_ip_public resolves the name (src/swisstopo_mcp/api_client.py:109) and then httpx resolves it again at connect time; the pinning transport that would close the window is off unless SWISSTOPO_PIN_DNS is set (src/swisstopo_mcp/api_client.py:214-215, wired at src/swisstopo_mcp/api_client.py:224). The lru_cache on _resolve (src/swisstopo_mcp/api_client.py:90) does not help — httpx never consults it. The check's pass criterion 'DNS-Resolution erfolgt einmal, resolved IP wird für den eigentlichen Request verwendet' is therefore unmet by default.
- The guard fails open on resolution error: src/swisstopo_mcp/api_client.py:110-111 swallows socket.gaierror and returns without raising, so a host that cannot be resolved is treated as vetted. Deliberate and documented, and low-impact given the frozenset host list, but it is a documented weakening rather than a closed criterion.

Gaps:
- DNS pinning is opt-in and off by default, so the shipped default configuration retains the rebinding window between the IP check and the connection (SEC-005 detail).
- The Defense-in-Depth egress proxy exists on paper (deploy/egress-proxy.yaml) but the ACL it consumes is structurally broken — see SEC-021. So the 'Egress-Proxy als Defense-in-Depth' criterion is not actually satisfied by the shipped artefacts.
- assert_resolved_ip_public fails open on socket.gaierror (src/swisstopo_mcp/api_client.py:110-111).
- No runtime SSRF probe was executed against a running HTTP server; verification was code-level plus the unit suite (570 tests pass).

### Risk Description
Between the guard's lookup and httpx's, a resolver that answers differently on the
second query places an arbitrary address behind an allow-listed name. The exposure is
bounded — a fixed frozenset of ten federal and cantonal hosts, no credentials, no
secrets, public data only — so the realistic attacker is a hostile or compromised
resolver rather than a remote input. The defence-in-depth layer that would compensate
is nominally shipped but non-functional: see SEC-021.

### Remediation
1. Consider defaulting `SWISSTOPO_PIN_DNS` to on for the stdio path, which has no
   network-layer compensation at all. It is inert behind a proxy anyway, so the
   cluster path is unaffected.
2. Decide deliberately about the fail-open on `gaierror`. It is documented and
   low-impact, but it is a weakening, not a closed criterion.
3. Fix the egress ACL (SEC-021) so the defence-in-depth criterion is satisfied by an
   artefact that works.

### Effort Estimate
S (<1d) for 1 and 2

### Relation to run `2026-07-27T125314-Z`
Recorded as closed. The two additions are genuine; the no-TOCTOU criterion is explicit in the check and is unmet in the default configuration.

### Auditor Notes
The two claimed additions are real, not cosmetic: the scheme check and the
resolved-IP guard are both in assert_host_allowed and both fire on every
outbound path, including the two direct-client call sites in oereb.py that
the brief flagged. I verified there is no bypass — check_host=False is never
used, and the one place a URL base comes from remote data (geodata.py
ogc_base) still goes through the retry wrapper.
Not a pass, because the check lists no-TOCTOU as an explicit pass criterion
and the default configuration still does two independent lookups. The
mitigations are genuine (fixed frozenset of ten federal/cantonal hosts, no
auth, no secrets, public data only), which is why this is partial rather
than fail.


### SEC-005

## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-005
**PDF-Reference:** Sec 4.4
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
`PinnedTransport` (`api_client.py:167-190`) is real and wired into `_build_client`
(`api_client.py:224`), the single constructor behind both the shared client and the
ephemeral fallback, so the `oereb.py` direct-client sites inherit it. The ordering is
correct: Host header (`:187`) and `sni_hostname` (`:188`) are set *before* the URL is
rewritten (`:189`), and it re-asserts the SEC-004 IP guard on the pinned address
(`:184`) rather than trusting the resolver twice.

It is off by default, and `SECURITY.md:27` still says "DNS pinning | **Not
implemented** (SEC-005)" — the exact opposite of what the code does.
`docs/network-egress.md` describes it correctly as available and off by default.

### Expected Behavior
- The resolved IP is used for the TCP connection
- Certificate validation unaffected

### Evidence
- PinnedTransport exists and is genuinely wired into the client factory, not orphaned: defined at src/swisstopo_mcp/api_client.py:167-190 and passed as the transport in _build_client at src/swisstopo_mcp/api_client.py:224, which is the single constructor behind both create_shared_client (src/swisstopo_mcp/api_client.py:228-230) and the ephemeral fallback (src/swisstopo_mcp/api_client.py:253-258). The oereb.py direct-client sites use the same _get_client, so they inherit it.
- The claimed SNI/Host preservation is in the code, not just the docstring: src/swisstopo_mcp/api_client.py:187 sets the Host header to the original hostname, src/swisstopo_mcp/api_client.py:188 sets extensions['sni_hostname'], and only then does src/swisstopo_mcp/api_client.py:189 rewrite request.url to the resolved address. Unit tests assert each of the three separately (tests/test_dns_pinning.py:78-101).
- The pin reuses the vetted address rather than trusting the resolver a second time: src/swisstopo_mcp/api_client.py:177 resolves via the shared cached _resolve and src/swisstopo_mcp/api_client.py:184 re-asserts the SEC-004 IP guard before connecting; tests/test_dns_pinning.py:103-107 proves a 127.0.0.1 answer raises PermissionError.
- It is off by default: src/swisstopo_mcp/api_client.py:212-215 requires SWISSTOPO_PIN_DNS in {1,true,yes} AND no proxy env var. tests/test_dns_pinning.py:47-49 asserts the default is False. So the shipped default deployment — including the local stdio path, which has no network-layer compensation — runs without pinning and keeps the rebinding window open.
- The security policy contradicts the code. SECURITY.md:27 still states 'DNS pinning | **Not implemented** (SEC-005) ... a rebinding window exists between the guard's lookup and the connection'. docs/network-egress.md describes it correctly as 'available, off by default'. A reader of SECURITY.md — the document the audit trail points at — would conclude the control does not exist.

Gaps:
- Default-off means the criterion 'Resolved IP wird für die TCP-Connection verwendet' holds only for operators who explicitly opt in and who are not behind a proxy.
- Pinning and the shipped egress proxy are mutually exclusive by design (src/swisstopo_mcp/api_client.py:158-164, deploy/egress-proxy.yaml:51-53), so a Kubernetes deployment following the shipped manifests gets neither pinning nor — given the broken ACL, see SEC-021 — a working per-host proxy.
- SECURITY.md:27 is stale and states the opposite of what the code does.
- End-to-end TLS-with-pinned-IP is only covered by @pytest.mark.live tests (tests/test_dns_pinning.py:138-168), which are deselected in CI (.github/workflows/ci.yml runs `pytest -m "not live"`). The non-live suite proves request rewriting, not that a handshake succeeds.
- Only addresses[0] is used (src/swisstopo_mcp/api_client.py:185); if getaddrinfo returns an IPv6 address first in an IPv4-only environment the request fails rather than falling back.

### Risk Description
The control is inert in the shipped default, so the rebinding window SEC-004 leaves
open stays open. On the cluster path, pinning and the egress proxy are mutually
exclusive by design (`api_client.py:158-164`) — and given the broken ACL (SEC-021), a
deployment following the shipped manifests gets neither. `SECURITY.md` is the document
the audit trail points at; a reader would conclude the control does not exist.

### Remediation
1. Correct `SECURITY.md:27`. This is drift in the safe direction, but it is drift.
2. Reconsider the default (see SEC-004 item 1).
3. Only `addresses[0]` is used (`api_client.py:185`); if `getaddrinfo` returns an IPv6
   address first in an IPv4-only environment the request fails with no fallback. Walk
   the list.
4. The end-to-end TLS proof is `@pytest.mark.live` only, deselected in PR CI. That is
   the right split, but it means the non-live suite proves request rewriting, not that
   a handshake succeeds — worth stating in the test module docstring.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Recorded as closed on the strength of a live TLS verification. The transport is sound; default-off and the stale SECURITY.md line keep it partial.

### Auditor Notes
The remediation is substantive — the transport is real, correctly ordered
(Host + SNI set before the URL is rewritten), reuses the SEC-004 guard, and
is properly plumbed through the one client factory. That answers the two
things the brief asked me to check.
It is not a pass because the control is inert in the default configuration
and, on the cluster path, is deliberately mutually exclusive with an egress
proxy whose ACL does not work. The doc contradiction at SECURITY.md:27 is
the mirror image of overclaiming, but it is still drift and should be fixed.


### SEC-009

## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

**Severity:** critical
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-009
**PDF-Reference:** Sec 4.6
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
Session-ID generation is cryptographically sound but is the SDK's, not the server's —
`uuid4().hex`, 128 bits from `os.urandom`, with the SDK major pinned at
`pyproject.toml:33` so it cannot change under a minor bump. The SDK's owner-binding
mechanism exists but is inert: with no auth configured the requestor is `None` for
every caller, so the mismatch check compares `None` to `None` and always passes.

Two criteria that are independent of auth are unmet. No session TTL:
`server.py:725` calls `mcp.streamable_http_app()` with defaults and the SDK's
`session_idle_timeout` default is `None`, so sessions live until the process restarts.
No server-side invalidation: `server.py:708-734` adds only `/healthz`.

### Expected Behavior
- Explicit session TTL
- Server-side invalidation path
- Session bound to the authenticated principal

### Evidence
- Session-ID generation is cryptographically sound, but it is the SDK's, not the server's. The server never generates a session id; mcp.server.streamable_http_manager creates `new_session_id = uuid4().hex` (128 bits from os.urandom). The SDK major is pinned at pyproject.toml:33 (`mcp[cli]>=1.28.1,<2.0.0`), so the generator cannot change under a minor bump without a deliberate constraint change.
- The SDK does implement owner binding — `self._session_owners: dict[str, AuthorizationContext]` with a mismatch check on every request — but it is inert here. The requestor is derived from an AuthenticatedUser; with no auth configured (FastMCP is constructed without an auth/token verifier at src/swisstopo_mcp/server.py:49-99) the requestor is None for every caller, so the comparison `requestor != self._session_owners.get(...)` compares None to None and always passes. Anyone presenting a valid Mcp-Session-Id is that session.
- No session TTL is configured. src/swisstopo_mcp/server.py:725 calls mcp.streamable_http_app() with defaults, and FastMCP.streamable_http_app constructs StreamableHTTPSessionManager without a session_idle_timeout; the SDK's default for that parameter is None, i.e. sessions live until the process restarts. The check's criterion 'Session-TTL ist explizit gesetzt' is unmet.
- There is no server-side logout/invalidation endpoint. src/swisstopo_mcp/server.py:708-734 adds only /healthz alongside the MCP mount.
- The residual risk is genuinely low and the deferral is documented honestly: SECURITY.md:45-51 states the server is unauthenticated by design, that there is no per-user state to bind to, and names SEC-009 as the trigger if an authenticated deployment is introduced. All 24 tools are stateless reads against public open data (verified via mcp.list_tools()), so a hijacked session confers no privilege the caller did not already have. Transport-level DNS-rebinding protection with explicit host/origin lists is on at src/swisstopo_mcp/server.py:58-62.

Gaps:
- No session TTL / idle timeout — sessions are unbounded for the process lifetime.
- No server-side session invalidation path (no logout).
- The SDK's user-binding mechanism is present but a no-op because auth_model=none; no compensating binding (e.g. client-IP or a signed token) exists.
- No runtime hijack probe was run against a live HTTP instance; verification is code- and SDK-source-level.

### Risk Description
All 24 tools are stateless reads against public open data, so a hijacked session
confers no privilege the caller did not already have — the exploit value is close to
zero and the deferral in `SECURITY.md:45-51` is honest. What remains is unbounded
session accumulation: with no idle timeout, every session that is never explicitly
deleted is retained for the process lifetime, which is a memory-growth and
resource-exhaustion property rather than a confidentiality one.

### Remediation
1. Set an explicit `session_idle_timeout` when constructing the app. This is a
   one-line change with no auth prerequisite and closes the unbounded-growth
   behaviour.
2. Document the absence of a logout route as deliberate (there is no session-scoped
   state to invalidate) rather than leaving the criterion unaddressed.
3. Keep the SEC-009 trigger in `SECURITY.md` — if an authenticated deployment is ever
   introduced, the inert owner binding becomes load-bearing.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Recorded as a documented deferral. Two of the six criteria are independent of auth and were not examined; neither is met.

### Auditor Notes
I deliberately did not inherit the prior 'documented deferral' framing. Two
of the six pass criteria (TTL, server-side invalidation) are independent of
whether auth exists, and neither is met — the server takes the SDK default
of no idle timeout and adds no logout route. The user-binding criteria are
genuinely inapplicable rather than skipped, and the ID entropy criterion is
met via the SDK's uuid4.
Partial rather than pass on the two unmet criteria; partial rather than
fail because the server holds no session-scoped state and serves only
public data, so the exploit value of a stolen session id is close to zero.


### SEC-014

## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway-Pattern

**Severity:** medium
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-014
**PDF-Reference:** Sec 5.3
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
No tool allow-list exists in any form, and none is possible without an auth layer —
the server is unauthenticated by design (`SECURITY.md:45-51`), so there are no claims
to check. All 24 tools are returned to any caller.

The deferral's premises are enforced in CI, which is more than prose:
`tests/test_tool_hygiene.py:60-72` fails the build if any tool lacks `readOnlyHint` or
sets `destructiveHint`, and `tests/test_egress_allowlist.py:113-143` fails in both
directions if the code frozenset and `docs/network-egress.md` drift apart. Both run on
every push across three Python versions.

The read-only gate enforces a *declaration*, not a *property*: it reads
`t.annotations.readOnlyHint`, a self-asserted hint. A future tool that writes while
still carrying `readOnlyHint=True` passes. The claim happens to hold today — the only
non-GET in `src/` is the Overpass query POST (`overpass.py:159-165`), a read expressed
as POST — but that was verified by the auditor, not by the test.

### Expected Behavior
- Default-deny tool allow-list per team/role
- Server-side group/role check for sensitive tools
- Audit logging for denied calls

### Evidence
- No tool allow-list exists in any form: no gateway config, no allowed_tools/tool_allowlist/denied_tools key anywhere in deploy/ or the repo, and no per-role or per-group filtering of the tools/list response. src/swisstopo_mcp/server.py registers all 24 tools unconditionally; mcp.list_tools() at runtime returns all 24 to any caller. Server-side defence-in-depth via group/role claims is impossible by construction — the server is unauthenticated (SECURITY.md:45-51), so there are no claims to check.
- The deferral is documented and its premise IS enforced in CI, which is more than prose: SECURITY.md:60-69 states the deferral, and tests/test_tool_hygiene.py:60-66 fails the build if any tool lacks readOnlyHint, tests/test_tool_hygiene.py:68-72 fails if any tool sets destructiveHint. .github/workflows/ci.yml:29-31 runs the suite on every push and PR across three Python versions, so the premise cannot quietly become false. Verified: 570 tests pass.
- The test enforces a *declaration*, not a *property*. It reads t.annotations.readOnlyHint — a self-asserted hint on the tool registration (e.g. src/swisstopo_mcp/server.py:112-118). A future tool that performs a write while still carrying readOnlyHint=True would pass the gate. The substantive read-only claim happens to hold today — no POST/PUT/DELETE to a mutating endpoint exists in src/, the only non-GET is the Overpass query POST at src/swisstopo_mcp/overpass.py:159-165, which is a read expressed as POST — but that is verified by me, not by the test.
- The second CI-enforced premise is real and stronger: egress is a frozenset at src/swisstopo_mcp/api_client.py:55, and tests/test_egress_allowlist.py:113-143 fails in both directions if code and docs/network-egress.md drift apart. That genuinely bounds what a compromised or mis-specified tool can reach.

Gaps:
- No default-deny tool allow-list per team/role — the check's primary criterion — and none is possible without an auth layer.
- No server-side group/role check for sensitive tools (no auth model).
- No audit logging or alerting for denied tool calls, because nothing is ever denied.
- The read-only premise is enforced at the annotation level only; a write-capable tool that lies in its annotations would slip past tests/test_tool_hygiene.py:60-72.

### Risk Description
Architecturally correct to defer for a single unauthenticated read-only server, and
the risk-bounding argument is backed by real gates. The residual is that "enforced in
CI" carries more weight in `SECURITY.md` than it earns: the gate stands one
indirection away from the premise it substitutes for.

### Remediation
1. Add a test that asserts the property, not the annotation: no handler issues a
   non-GET request except the known Overpass POST. That converts the premise from
   auditor-verified to CI-verified.
2. Reword `SECURITY.md:60-69` to say the annotation contract is gated, not that
   read-only-ness is.
3. Revisit if auth is ever introduced — the whole check becomes applicable at that
   point.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Recorded as a documented deferral. Sustained, with the caveat above made explicit.

### Auditor Notes
I was asked to judge whether the tests enforce the deferral's premises or
merely look like they do. Verdict: they enforce a real, load-bearing thing
(the annotation contract and the egress frozenset/doc sync), and they will
actually fail — I ran them. But the read-only gate checks what a tool
*declares*, not what it *does*, so it is one indirection away from the
premise it is standing in for. Worth stating plainly rather than letting
'enforced in CI' carry more weight than it earns.
Partial: the check's actual criteria (default-deny allow-list, role scoping,
denied-call auditing) are entirely absent. Not fail, because the deferral is
architecturally correct for a single unauthenticated read-only server and
the risk-bounding argument is backed by real gates.


### SEC-015

## Finding: SEC-015 — Pre-Flight Tool-Poisoning Detection

**Severity:** medium
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-015
**PDF-Reference:** Sec 5.3
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
A real self-scan exists and runs in CI: `tests/test_tool_hygiene.py` rejects
zero-width and bidi characters (written as escapes, not literals — a deliberate and
correct choice), six override phrases across German, French and English, non-ASCII
tool names, and descriptions under 40 characters. All 11 tests pass on every push. The
pattern list is genuinely better than an off-the-shelf English one for a German-language
surface. `tool-hashes.json` pins name + description + inputSchema per tool and CI
fails on drift.

It scans the wrong surface only partially. Every assertion reads `t.name` or
`t.description`. Nothing scans `t.inputSchema`, whose per-field `description` strings
reach the model's context identically — nor the 36-line `instructions` block at
`server.py:63-98`, which is sent to every client. An injection in a
`Field(description=...)` passes every test in the file.

Two named pattern classes are missing: system-prompt tag markers (`<SYSTEM>`,
`[INST]`, `### Instructions:` — the file matches the literal phrase "system prompt"
only) and an over-length ceiling. Homoglyph detection is `name.isascii()` rather than
an NFKC comparison, and covers names only.

### Expected Behavior
- Scan for invisible characters, override phrases, system-prompt markers, over-length
  descriptions — across all text shipped to the model

### Evidence
- A real self-scan exists and runs in CI: tests/test_tool_hygiene.py:78-80 rejects zero-width/bidi/word-joiner characters (range at tests/test_tool_hygiene.py:32-34), tests/test_tool_hygiene.py:82-85 parametrises six override-phrase patterns in German, French and English (tests/test_tool_hygiene.py:36-49), tests/test_tool_hygiene.py:87-90 rejects non-ASCII tool names (the homoglyph vector), and tests/test_tool_hygiene.py:92-95 rejects descriptions under 40 chars. Executed: all 11 tests in the file pass, and .github/workflows/ci.yml:29-31 runs them on every push/PR.
- The pattern list is genuinely better than an off-the-shelf English one for this repo — the descriptions are German (e.g. src/swisstopo_mcp/server.py:121-126) and tests/test_tool_hygiene.py:38-43 covers ignoriere/missachte/vergiss + vorherigen/bisherigen/obigen and 'du bist jetzt'. Writing the invisible-character class as escapes (tests/test_tool_hygiene.py:32-34) rather than literals is a deliberate, correct choice.
- It scans the wrong surface only partially. The fixture returns mcp.list_tools() and every assertion reads `t.name` or `t.description`. Nothing scans `t.inputSchema`, whose per-field `description` strings are shipped to the model in exactly the same context window — e.g. the free-text descriptions at src/swisstopo_mcp/coords.py:193-204 and src/swisstopo_mcp/server.py:63-98's `instructions` block (a 36-line prose payload sent to every client). An injection placed in a Field(description=...) or in the server instructions passes every test in this file.
- Two of the check's named pattern classes are missing: there is no match for embedded system-prompt markers `<SYSTEM>`, `[INST]` or `### Instructions:` (tests/test_tool_hygiene.py:43 matches the literal phrase 'system prompt' only, not the tag form), and there is no description-length ceiling (the check names ~4000 chars as a smuggling signal; tests/test_tool_hygiene.py:92-95 only enforces a floor of 40). No suspicious-URL-host check either.
- The complementary control is real: tool-hashes.json pins name+description+inputSchema per tool (scripts/snapshot_tool_hashes.py:44-58) and .github/workflows/ci.yml:43-44 fails the build on drift — verified by running `--check`, which reports 'up to date (24 tools)'. That does cover the input-schema surface for *change detection*, though not for *content* detection. SECURITY.md:73-84 states plainly that this is a self-scan and cannot see across servers.

Gaps:
- Input-schema field descriptions and the server-level `instructions` string (src/swisstopo_mcp/server.py:63-98) are not scanned at all, despite reaching the model's context identically to tool descriptions.
- Missing pattern classes: system-prompt tag markers (<SYSTEM>, [INST], ### Instructions:) and an over-length description ceiling.
- No gateway-level pre-flight filter, no default-deny on high-risk definitions, no audit events and no SIEM alerting — the check's central mechanism is absent, as the deferral states.
- Homoglyph detection is `name.isascii()` (tests/test_tool_hygiene.py:89) rather than an NFKC-normalisation comparison; it catches Cyrillic-in-name but not a non-canonical ASCII-compatible form, and it does not cover descriptions.

### Risk Description
Parameter descriptions and the server `instructions` block are prime injection real
estate precisely because reviewers read tool descriptions and skip schemas. The
file's own docstring frames itself as scanning "this server's own descriptions",
which is what makes the gap dangerous: the control looks complete. The hash snapshot
catches *change* to the schema surface but not *content*, so a poisoned description
committed alongside a regenerated snapshot passes both gates.

### Remediation
1. Extend the fixture to walk `t.inputSchema` recursively and apply every existing
   assertion to each `description` it finds, plus `mcp.instructions`.
2. Add the missing pattern classes: `<SYSTEM>`, `[INST]`, `### Instructions:`, and a
   ceiling of ~4000 characters.
3. Replace `name.isascii()` with an NFKC-normalisation comparison and apply it to
   descriptions too.
4. Narrow the claim in `SECURITY.md:73-84` to what is actually scanned, or widen the
   scan to match the claim.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Recorded as closed. The scan is real and runs; its surface is narrower than the security policy implies.

### Auditor Notes
Asked to judge whether the tests enforce the deferral's premises or merely
look like they do: they do enforce something real and they do run — but the
scan is narrower than SECURITY.md:73-84 implies. The most valuable finding
here is the surface gap: parameter descriptions and the 36-line server
`instructions` block are prime injection real estate and are not covered by
a single assertion, even though the file's own docstring frames itself as
scanning 'this server's own descriptions'.
Partial. The gateway-level control the check is actually about does not
exist (legitimately deferred), the self-scan covers 2.5 of the 4 required
pattern classes, and it misses a whole category of shipped text.


### SEC-018

## Finding: SEC-018 — Input-Validation an Tool-Boundaries (Pydantic strict / Zod)

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-018
**PDF-Reference:** Sec 3 / Sec 4 (Defense-in-Depth)
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
Verified by runtime introspection of all 24 input models rather than by sampling.
Every model carries `ConfigDict(str_strip_whitespace=True, extra="forbid",
strict=True)`, including the `SwissPointInput` base (`coords.py:90`) so a future
subclass cannot regress. Every integer field has both bounds. `validate_sr()` is wired
at three sites and the other three `sr` fields are guarded by something stricter
(`check_deprecated_sr`, which rejects anything but 4326). `easting`/`northing` look
unbounded but are not — the model validator at `coords.py:140-156` enforces the LV95
Swiss extent. Patterns are whitelist-based throughout.

One claim overreaches. Three string fields have no `max_length`: `stac.py:34-39`
`collection_id` (min_length and a pattern, but no ceiling — and it is interpolated
straight into a URL path at `stac.py:174`), `geocoding.py:32-39` `origins`, and
`wmts.py:34-38` `layers`. A pattern constrains the charset, not the size.

### Expected Behavior
- Length bounds on every string field

### Evidence
- Checked every input model by runtime introspection, not by sampling: all 24 Pydantic models across geocoding/rest_api/stac/wmts/height/coords/oereb/geodata/overpass/openplz carry `model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)`. Not one is permissive. The base SwissPointInput declares it too (src/swisstopo_mcp/coords.py:90) so a future subclass that forgets cannot regress.
- Every integer field has both bounds. Enumerated: limit ge=1/le=50 (src/swisstopo_mcp/geocoding.py:50), le=10, le=30, le=100; tolerance ge=0/le=200 (src/swisstopo_mcp/rest_api.py:66); nb_points ge=2/le=1000 (src/swisstopo_mcp/height.py:58-63); radius_m ge=10/le=5000; zoom ge=1/le=13; bfs_number ge=1/le=9999. No unbounded int.
- validate_sr() is genuinely wired up now, at three sites: src/swisstopo_mcp/geocoding.py:43-48, src/swisstopo_mcp/geocoding.py:61-66 and src/swisstopo_mcp/rest_api.py:102-105. The remaining three `sr` fields are guarded by something stricter — check_deprecated_sr (src/swisstopo_mcp/coords.py:57-74) rejects anything but 4326 — at src/swisstopo_mcp/rest_api.py:72-75, src/swisstopo_mcp/height.py:35-38 and src/swisstopo_mcp/height.py:69-72. No `sr` reaches an upstream unvalidated.
- easting/northing look unbounded at field level but are not: the model validator at src/swisstopo_mcp/coords.py:140-156 rejects degree-magnitude values and enforces the LV95 Swiss extent (2 480 000–2 840 000 / 1 070 000–1 300 000), and src/swisstopo_mcp/coords.py:210-235 does the direction-aware equivalent for ConvertCoordinatesInput. The omission is deliberate and documented at src/swisstopo_mcp/coords.py:104-106.
- Patterns are whitelist-based throughout, defined centrally at src/swisstopo_mcp/api_client.py:43-47 (TEXT/ID/COORDS/LANG/CANTON) — all `^[...]+$` allow-lists, no negative lookahead. tests/test_input_validation.py:14-40 proves rejection of NUL bytes, angle brackets, quotes, backticks and `../../etc/passwd`; tests/test_input_validation.py:44-60 proves strict mode rejects "10" for an int and rejects extra fields.
- THE GAP the remediation overclaims: three string fields still have no max_length, so 'length bounds added' is not true across the board. src/swisstopo_mcp/stac.py:34-39 collection_id has min_length=2 and a pattern but no ceiling — and it is interpolated straight into a URL path at src/swisstopo_mcp/stac.py:174. src/swisstopo_mcp/geocoding.py:32-39 `origins` has a pattern but no length bound. src/swisstopo_mcp/wmts.py:34-38 `layers` has a pattern but no length bound. A pattern constrains the charset, not the size, so a multi-kilobyte value of legal characters passes validation and is forwarded upstream.

Gaps:
- src/swisstopo_mcp/stac.py:34-39 — collection_id: no max_length; value is interpolated into an upstream URL path.
- src/swisstopo_mcp/geocoding.py:32-39 — origins: no max_length.
- src/swisstopo_mcp/wmts.py:34-38 — layers: no max_length.
- TEXT_PATTERN (src/swisstopo_mcp/api_client.py:43) permits ';' '&' '/' '%'. Harmless here — no shell, no SQL, and values go through httpx param encoding — but it is a broader charset than the check's whitelist ideal implies.
- origins is documented as an enum of seven values (address/zipcode/gg25/...) but is validated only as a lowercase-alphanumeric-comma string; a Literal or explicit member check would be exact.

### Risk Description
A multi-kilobyte value of legal characters passes validation and is forwarded upstream.
`collection_id` is the sharp one because it lands in a URL path rather than a query
parameter — the failure mode is a malformed upstream request or an oversized URL
rejected at the edge, not injection, since the charset is already restricted. Low
severity, but the remediation note currently claims more than the code does.

### Remediation
1. Add `max_length` to the three fields: `collection_id` (say 128), `origins` (128),
   `layers` (512 — it is a comma-separated list).
2. Make `origins` a `Literal` over its seven documented values; it is documented as an
   enum but validated as a lowercase-alphanumeric-comma string.
3. `TEXT_PATTERN` (`api_client.py:43`) permits `;` `&` `/` `%`. Harmless here — no
   shell, no SQL, httpx encodes params — but worth a comment saying so deliberately.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Recorded as closed. Strict mode, extra-forbid, int bounds and sr validation all hold universally; the length-bounds claim does not.

### Auditor Notes
The brief asked me to check every input model rather than a sample, so I
introspected all 24 at runtime and enumerated every field's constraints.
The strict/extra-forbid claim holds universally, the int-bounds claim holds
universally, the validate_sr wiring claim holds (three direct sites plus a
stricter guard on the other three), and the easting/northing 'no bounds'
appearance is a false alarm — a model validator enforces the Swiss extent.
Downgraded to partial on one concrete, reproducible point: the claim that
length bounds were added does not hold for three string fields, one of
which (collection_id) lands directly in an upstream URL path. Small fix,
but the claim currently says more than the code does.


### SEC-021

## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-021
**PDF-Reference:** Anhang B5 + B12
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
The code-layer allow-list is correct and non-mutable: a frozenset of ten hosts built
from literals (`api_client.py:55-68`), enforced before every request, with
`check_host=False` never passed anywhere in `src/`. Documentation and the update
procedure exist and are test-enforced in both directions
(`tests/test_egress_allowlist.py:122-143`). The generation claim is true —
`scripts/render_egress_acl.py` renders the ACL from `ALLOWED_HOSTS` and CI runs
`--check` on every push; executed, it reports "up to date (10 hosts)".

**The generated ACL does not work.** `render_egress_acl.py:25` emits host entries at
two-space indent while the `allowed_domains:` key sits at four. Parsing
`deploy/smokescreen-acl.yaml` with `yaml.safe_load` yields
`services[0].allowed_domains == null`, with the ten hostnames promoted to bare strings
as *siblings of the service object*. The per-host network-layer allow-list therefore
does not exist in any loadable form.

The CI gate cannot see this: `render_egress_acl.py:44` compares the committed file
byte-for-byte against the output of the same buggy renderer. It gates staleness, not
validity, and no test parses the file. A second defect: `deploy/egress-proxy.yaml:30`
passes `--config-file=/etc/smokescreen/config.yaml`, but the ConfigMap
(`egress-proxy.yaml:13`) is created from `smokescreen-acl.yaml` only, so the sidecar
would fail to start.

### Expected Behavior
- Per-host egress allow-list at the network layer
- Documented and enforced

### Evidence
- Code-layer allow-list is correct and non-mutable: src/swisstopo_mcp/api_client.py:55-68 declares ALLOWED_HOSTS as a frozenset of ten hosts, built from literals with an explicit comment that it is not loaded from env. No wildcards. Enforced by assert_host_allowed at src/swisstopo_mcp/api_client.py:121-137.
- The pre-request check runs on every outbound path — verified, not assumed. request_with_retry calls it before the first attempt (src/swisstopo_mcp/api_client.py:293-294) and `check_host=False` is never passed anywhere in src/; the two direct-client sites in oereb.py call it explicitly (src/swisstopo_mcp/oereb.py:91 and :183). The strongest case: src/swisstopo_mcp/geodata.py:426 takes a base URL out of the remote geodienste.ch catalogue and it still cannot escape the frozenset.
- Documentation and update procedure exist and are test-enforced in both directions: docs/network-egress.md tabulates all ten hosts with purpose and consuming tools, and lists a five-step update procedure. tests/test_egress_allowlist.py:122-127 fails if a code host is undocumented; tests/test_egress_allowlist.py:129-143 fails if a documented host left the code.
- The generation claim is TRUE: scripts/render_egress_acl.py:22-31 renders deploy/smokescreen-acl.yaml from ALLOWED_HOSTS, and .github/workflows/ci.yml:48-49 runs `--check` on every push and PR. I executed it — exit 0, 'smokescreen-acl.yaml is up to date (10 hosts)'. deploy/egress-proxy.yaml is shipped as claimed, with the Smokescreen sidecar (deploy/egress-proxy.yaml:27-45) and a replacement NetworkPolicy permitting DNS plus proxied HTTPS only (deploy/egress-proxy.yaml:64-95).
- BUT THE GENERATED ACL IS STRUCTURALLY BROKEN. scripts/render_egress_acl.py:25 emits the host entries at two-space indent (`f"  - {h}"`) while the `allowed_domains:` key it attaches them to sits at four-space indent (scripts/render_egress_acl.py:28, matching deploy/smokescreen-acl.yaml:22). Parsing deploy/smokescreen-acl.yaml with yaml.safe_load yields `services[0].allowed_domains == null` and the ten hostnames promoted to bare strings *as siblings of the service object* inside the `services` list. The per-host network-layer allow-list the check requires therefore does not exist in any loadable form — the file either fails Smokescreen's unmarshal or enforces an empty domain list.
- The CI gate cannot catch this: scripts/render_egress_acl.py:44 compares the committed file byte-for-byte against the output of the same buggy renderer. It gates staleness, not validity. There is no test anywhere that parses deploy/smokescreen-acl.yaml.
- A second defect in the same artefact: deploy/egress-proxy.yaml:30 passes `--config-file=/etc/smokescreen/config.yaml`, but the documented ConfigMap (deploy/egress-proxy.yaml:13) is created from smokescreen-acl.yaml only, so config.yaml would be absent from the mount at deploy/egress-proxy.yaml:38 and the sidecar would fail to start.

Gaps:
- deploy/smokescreen-acl.yaml is invalid as a Smokescreen ACL — allowed_domains parses as null and the ten hosts land as stray strings in `services`. Fix: emit the rules at six-space indent in scripts/render_egress_acl.py:25 (`f"      - {h}"`).
- No test parses the generated ACL; the CI gate only compares bytes against the same renderer, so the defect is invisible to the pipeline.
- deploy/egress-proxy.yaml:30 references a config.yaml the documented ConfigMap does not contain.
- The NetworkPolicy actually shipped in deploy/kubernetes.yaml:100-131 is CIDR+port only (443 out, private ranges excepted, DNS to kube-system) — correctly and explicitly described as such in docs/network-egress.md, but it means that until the proxy manifest is applied AND fixed, the network layer has no per-host control at all.
- docs/network-egress.md states the shipped NetworkPolicy 'permits DNS, ports 80/443'; deploy/kubernetes.yaml:112-115 permits TCP/443 only. Minor doc inaccuracy.

### Risk Description
This is the defence-in-depth layer that SEC-004 and SEC-005 both point at when their
own criteria fall short. It is shipped, generated, CI-gated and non-functional — the
worst combination, because every signal a reviewer would check says it works. An
operator applying `deploy/egress-proxy.yaml` gets a sidecar that either fails to
unmarshal the ACL or enforces an empty domain list, and in the meantime pinning is
disabled precisely because a proxy is configured (`api_client.py:158-164`). The net
effect of following the shipped manifests is *less* egress control than not following
them.

The shipped `deploy/kubernetes.yaml` NetworkPolicy is CIDR+port only, which is
correctly described as such in `docs/network-egress.md` — but it means that until the
proxy manifest is applied *and* fixed, the network layer has no per-host control at
all.

### Remediation
1. Fix the indentation at `render_egress_acl.py:25` — six spaces, so the entries nest
   under `allowed_domains`. Regenerate and commit.
2. Add a test that `yaml.safe_load`s the committed ACL and asserts
   `services[0]["allowed_domains"] == sorted(ALLOWED_HOSTS)`. A byte-comparison gate
   against the generator can only catch staleness; this is the class of bug it is
   structurally blind to.
3. Add the missing `config.yaml` to the ConfigMap, or drop the `--config-file` flag.
4. Correct `docs/network-egress.md`: it says the shipped NetworkPolicy permits ports
   80/443; `deploy/kubernetes.yaml:112-115` permits TCP/443 only.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Recorded as closed. The generation pipeline is real; its output is invalid, and the gate is blind to that by construction.

### Auditor Notes
The brief asked me to verify the generation is real and the CI step exists.
Both are real — I ran the script and read the workflow. That is where a
surface reading would stop, and it is exactly what the file-level claim in
the previous remediation asserts.
Parsing the output tells a different story: the renderer emits the host list
at the wrong indent level, so the ACL that is supposed to carry the ten-host
network-layer allow-list parses with allowed_domains: null. The generation
pipeline is genuine but produces a non-functional artefact, and the CI gate
is structurally incapable of noticing because it diffs against its own
output. Combined with the missing config.yaml in the sidecar args, the
network-layer half of SEC-021 is not actually deliverable as shipped.
Code layer: solid pass. Network layer: present in intent, broken in fact.
Partial, with a one-line fix available.


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **SEC-004** (critical, partial)
2. **SEC-009** (critical, partial)
3. **ARCH-006** (high, partial)
4. **OBS-001** (high, partial)
5. **OBS-002** (high, partial)
6. **OPS-001** (high, partial)
7. **OPS-003** (high, partial)
8. **SCALE-002** (high, partial)
9. **SCALE-003** (high, partial)
10. **SDK-001** (high, partial)
11. **SEC-005** (high, partial)
12. **SEC-018** (high, partial)
13. **SEC-021** (high, partial)
14. **ARCH-003** (medium, partial)
15. **ARCH-007** (medium, partial)
16. **CH-004** (medium, partial)
17. **OBS-006** (medium, partial)
18. **SDK-003** (medium, partial)
19. **SEC-014** (medium, partial)
20. **SEC-015** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| catalog_version | `091f446b2796` |
| audit_date | `2026-07-27` |


_Generated by tools/build_report.py — do not edit by hand._
