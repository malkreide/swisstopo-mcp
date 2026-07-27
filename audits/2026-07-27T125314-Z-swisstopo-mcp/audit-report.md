# MCP-Server Audit-Report — `swisstopo-mcp`

**Audit-Datum:** 2026-07-27
**Skill-Version:** 1.0.0
**Catalog-Version:** sha256:091f446b2796

---

## 1. Executive Summary

Server `swisstopo-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 22 bestanden, 22 Findings dokumentiert (1 critical, 11 high, 10 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: SEC-022.

**Production-Readiness:** NO

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swisstopo-mcp` |
| Audit-Datum | 2026-07-27 |
| Skill-Version | 1.0.0 |
| Catalog-Version | sha256:091f446b2796 |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 5 | 0 | 6 | 0 | 0 |
| CH | 0 | 0 | 1 | 0 | 0 |
| OBS | 4 | 1 | 0 | 0 | 0 |
| OPS | 1 | 0 | 2 | 0 | 0 |
| SCALE | 3 | 0 | 2 | 0 | 0 |
| SDK | 1 | 0 | 3 | 0 | 0 |
| SEC | 8 | 1 | 6 | 0 | 0 |
| **Total** | **22** | **2** | **20** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| SEC-004 | SEC | critical | partial |
| ARCH-004 | ARCH | high | partial |
| ARCH-006 | ARCH | high | partial |
| OPS-001 | OPS | high | partial |
| OPS-003 | OPS | high | partial |
| SCALE-001 | SCALE | high | partial |
| SCALE-003 | SCALE | high | partial |
| SDK-004 | SDK | high | partial |
| SEC-005 | SEC | high | partial |
| SEC-018 | SEC | high | partial |
| SEC-021 | SEC | high | partial |
| SEC-022 | SEC | high | fail |
| ARCH-003 | ARCH | medium | partial |
| ARCH-007 | ARCH | medium | partial |
| ARCH-011 | ARCH | medium | partial |
| ARCH-012 | ARCH | medium | partial |
| CH-004 | CH | medium | partial |
| OBS-006 | OBS | medium | fail |
| SDK-002 | SDK | medium | partial |
| SDK-003 | SDK | medium | partial |
| SEC-014 | SEC | medium | partial |
| SEC-015 | SEC | medium | partial |

**Gesamt:** 22 Findings

---

## 5. Detail-Findings

### ARCH-003

## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-003
**PDF-Reference:** Sec 2.2

### Observed Behavior
The structural half of the check is in place. The response envelope carries a machine-readable `match_type` field (`exact | fuzzy | none`) — `src/swisstopo_mcp/models.py:16` and `models.py:67-69` — set at 39 call sites across the tool modules, so empty results are reported as `match_type: none` rather than as an error. No tool returns a bare "No results found" string as its error channel.

The behavioural half is not. No fuzzy or suggestion mechanism exists anywhere in the codebase: the literal `"fuzzy"` appears only in the type definition at `src/swisstopo_mcp/models.py:16` and is never emitted by any handler — grep over `src/` finds zero producing call sites.

Two tools do show the intended pattern. `src/swisstopo_mcp/geocoding.py:56-62` returns an actionable hint on empty ("Versuche einen kürzeren oder allgemeineren Suchbegriff, prüfe die Schreibweise, oder grenze mit dem Parameter `origins` ein"), and `src/swisstopo_mcp/openplz.py:327-329` / `openplz.py:486-487` / `openplz.py:507-509` explain that OpenPLZ answers an unknown key with HTTP 200 plus `[]` and name the likely cause.

Several core search tools return a bare negative with no follow-up path: `src/swisstopo_mcp/rest_api.py:196` ("Keine Layer gefunden für {query}."), `rest_api.py:215`, `rest_api.py:240`, `src/swisstopo_mcp/stac.py:154-156` and `src/swisstopo_mcp/geodata.py:637`. These are the primary discovery entry points, so an empty answer there ends the chain without offering a refinement.

The repository records this as open: `docs/roadmap.md:33` lists "[ ] Suggestion mechanism for empty results — still open (ARCH-003)" under Phase 2, directly beneath the completed `match_type` item.

### Expected Behavior
- For non-sensitive search tools: empty results trigger a fuzzy match or a suggestion mechanism
- The response carries a `match_type` field (exact / fuzzy / none)
- At `match_type == "none"`: an actionable hint (suggestions, other tools, term refinement)
- For sensitive tools: exact lookups only, no fuzzy fallback, documented as such

The sensitive-tool exception does not apply here — all data served are public Swiss OGD.

### Evidence
- `match_type` in the envelope: `src/swisstopo_mcp/models.py:16`, `models.py:67-69`; set at 39 call sites across the tool modules
- Intended pattern, implemented: `src/swisstopo_mcp/geocoding.py:56-62`; `src/swisstopo_mcp/openplz.py:327-329`, `:486-487`, `:507-509`
- `"fuzzy"` never emitted: literal appears only at `src/swisstopo_mcp/models.py:16`; zero producing call sites in `src/`
- Bare negatives on the discovery entry points: `src/swisstopo_mcp/rest_api.py:196`, `rest_api.py:215`, `rest_api.py:240`, `src/swisstopo_mcp/stac.py:154-156`, `src/swisstopo_mcp/geodata.py:637`
- Maintainer's own record: `docs/roadmap.md:33`

Gaps:
- No fuzzy fallback or suggestion generator for any non-sensitive search tool (`swisstopo_search_layers`, `swisstopo_find_features`, `swisstopo_search_geodata`, `list_available_layers`)
- For those tools the `match_type: none` response carries no actionable note — only a statement that nothing was found

### Risk Description
The tools that return a bare negative are exactly the ones the LLM reaches first. `swisstopo_search_layers` is the entry point to the whole api3 layer surface; if a user asks about "Lärmbelastung" and the layer is indexed as "Strassenlärm", the tool returns "Keine Layer gefunden für Lärmbelastung." and the chain stops there. The LLM has three options at that point, two of which are bad: report a false negative to the user ("swisstopo has no noise data" — untrue), or invent a plausible layer ID and call `swisstopo_layer_info` with it, producing a second failure and a hallucinated intermediate. The correct third option — retry with a different term — requires the LLM to guess that retrying is worthwhile, which the current response gives it no reason to believe.

This matters more on this server than on most because the layer namespace is dense, German, and uses federal naming conventions no user will guess (`ch.are.bauzonen`, `ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill`). Term mismatch on the first attempt is the normal case, not the exception. The two tools that already do this right (`geocoding.py:56-62`, the OpenPLZ trio) demonstrate the fix costs a few lines and shows what the model needs.

No data-confidentiality risk arises from adding fuzzy matching here: everything served is public OGD, so the check's sensitive-lookup exception does not constrain the remediation.

### Remediation
1. **Add a hint at every bare-negative site**, mirroring the pattern already used at `src/swisstopo_mcp/geocoding.py:56-62`. In `src/swisstopo_mcp/rest_api.py:196`, `:215`, `:240`, `src/swisstopo_mcp/stac.py:154-156` and `src/swisstopo_mcp/geodata.py:637`, populate a `note` alongside `match_type: none`:

```python
return SearchResult(
    results=[],
    match_type="none",
    note=(
        f"Keine Layer für «{query}» gefunden. Versuche einen kürzeren oder "
        f"allgemeineren Begriff, oder rufe swisstopo_search_layers ohne "
        f"Themenfilter auf, um die verfügbaren Themen zu sehen."
    ),
)
```

   This alone closes Pass-Criterion 3 and is the higher-value half of the fix.

2. **Add a fuzzy fallback for layer search**, which is the one place it is genuinely worth the effort. `swisstopo_search_layers` already retrieves the layer catalogue; on an empty exact match, run `difflib.get_close_matches` over the catalogue's titles and IDs and return the top 3–5 with `match_type: "fuzzy"`:

```python
if not results:
    candidates = difflib.get_close_matches(query, _layer_titles(), n=5, cutoff=0.6)
    if candidates:
        return SearchResult(
            results=[_layer_for_title(c) for c in candidates],
            match_type="fuzzy",
            note="Keine exakte Übereinstimmung — die folgenden Layer sind ähnlich benannt.",
        )
```

   This makes `match_type: "fuzzy"` a value the server actually emits rather than a dead branch of the type at `models.py:16`.

3. For `swisstopo_search_geodata` and `list_available_layers`, where the key space is a fixed enumerated set (`src/swisstopo_mcp/geodata.py`), the cheaper fix is to include the available keys directly in the empty response instead of fuzzy-matching — the set is small enough to enumerate.
4. Add tests asserting each search tool returns a non-empty `note` when `match_type == "none"`, and one asserting a near-miss query against the layer catalogue yields `match_type == "fuzzy"`.
5. Tick `docs/roadmap.md:33` once items 1–2 land.

### Effort Estimate
M (1-3d)


### ARCH-004

## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-004
**PDF-Reference:** Sec 2.1

### Observed Behavior
The substance of Inversion of Control holds. No tool handler touches transport internals — a grep for `request.headers` / `remote_addr` / `websocket` / `stdin` / `stdout` across `src/` returns zero hits inside handlers, and the only starlette imports are function-local inside `build_http_app` (`src/swisstopo_mcp/server.py:667-669`), i.e. in transport wiring rather than tool code. Where a handler needs session context it takes the transport-agnostic MCP `Context` (`src/swisstopo_mcp/server.py:337` for `swisstopo_elevation_profile`, `server.py:484` for `swisstopo_get_oereb_extract`), which is the documented pass pattern. Both transports are served from one entrypoint and one FastMCP instance (`src/swisstopo_mcp/server.py:686-701`, with `build_http_app` at `server.py:674` deriving from the same `mcp` object), so tool outputs cannot diverge by construction, and the lifespan is shared — one `httpx.AsyncClient` created at `src/swisstopo_mcp/server.py:27-39` and attached at construction time (`server.py:44`).

A pydantic-settings `Settings` object exists and is used for transport config (`src/swisstopo_mcp/config.py:12-33`, env prefix `SWISSTOPO_`, `.env` support), consumed at `src/swisstopo_mcp/server.py:23`, `694`, `696`, `697` and covered by `tests/test_config.py:8-30`. Container and Kubernetes override it by environment only (`Dockerfile:22-27`, `deploy/kubernetes.yaml:39-42`), never by a code fork.

Two criteria are unmet:

1. **Transport is selected by CLI flag, not by env var.** `src/swisstopo_mcp/server.py:689-694` reads `sys.argv` for `--http`; `Settings` has no `transport` field (`src/swisstopo_mcp/config.py:22-26`).
2. **Configuration does not run exclusively through `Settings`.** `src/swisstopo_mcp/oereb.py:33` reads `os.environ.get("SWISSTOPO_OEREB_CANTONS", "ZH")` at every call of `get_active_cantons()`, and `src/swisstopo_mcp/logging_config.py:32` falls back to `os.environ.get("SWISSTOPO_LOG_LEVEL")`. Both contradict the module docstring at `src/swisstopo_mcp/config.py:3-5` ("come from a single Settings object instead of ad-hoc sys.argv / os.environ reads"), and `SWISSTOPO_OEREB_CANTONS` is documented in `.env.example:7` but has no field in `Settings` at all.

### Expected Behavior
- Tool handlers use only `ctx: Context` for client/session information, never direct request access
- Server code supports at least stdio plus SSE/Streamable HTTP, selectable via env var
- Configuration runs through a settings object (pydantic-settings or equivalent), not global module vars or ad-hoc env reads
- Tools produce identical outputs regardless of transport
- Lifespan / setup code is shared across all transports

### Evidence
- Handlers are transport-clean: grep for `request.headers` / `remote_addr` / `websocket` / `stdin` / `stdout` across `src/` returns zero hits inside handlers; starlette imports are function-local at `src/swisstopo_mcp/server.py:667-669`; the single `httpx.RequestError` reference at `src/swisstopo_mcp/api_client.py:176` is the outbound client, not the inbound transport
- Transport-agnostic Context usage: `src/swisstopo_mcp/server.py:337`, `server.py:484`
- One entrypoint, one FastMCP instance: `src/swisstopo_mcp/server.py:686-701`; `build_http_app` at `server.py:674`
- Shared lifespan: `src/swisstopo_mcp/server.py:27-39`, attached at `server.py:44`
- Settings object: `src/swisstopo_mcp/config.py:12-33`; consumed at `src/swisstopo_mcp/server.py:23`, `694`, `696`, `697`; tested at `tests/test_config.py:8-30`; env-only overrides at `Dockerfile:22-27`, `deploy/kubernetes.yaml:39-42`
- Ad-hoc config reads: `src/swisstopo_mcp/oereb.py:33`, `src/swisstopo_mcp/logging_config.py:32`; contradicted docstring at `src/swisstopo_mcp/config.py:3-5`; undeclared knob documented at `.env.example:7`

Gaps:
- Transport is selected by CLI flag (`sys.argv`, `src/swisstopo_mcp/server.py:689-694`), not by env var / Settings field — `Settings` has no `transport` field (`src/swisstopo_mcp/config.py:22-26`)
- `src/swisstopo_mcp/oereb.py:33` reads `os.environ` at call time, so the enabled-canton set is a hidden global re-read per invocation, making the OEREB tool surface dependent on ambient process state rather than injected config

### Risk Description
Neither gap is a security issue, which is why the impact is operational rather than exploitable — but the second one is more than cosmetic.

`src/swisstopo_mcp/oereb.py:33` re-reads `SWISSTOPO_OEREB_CANTONS` on every call to `get_active_cantons()`. That makes the set of cantons the OEREB tools will serve a function of ambient process state at call time, not of configuration captured at startup. Practical consequences: the value cannot be validated (a typo'd canton code fails silently per call rather than at startup, where `Settings` would reject it), it cannot be logged at startup as part of the effective configuration, and a test or a caller that mutates `os.environ` changes tool behaviour mid-process. Because `SWISSTOPO_OEREB_CANTONS` is documented in `.env.example:7` but absent from `Settings`, an operator reading `config.py` to learn what is configurable will not find it — and `config.py:3-5` actively tells them there is nothing else to look for.

The transport gap bites in container orchestration. `Dockerfile:22-27` and `deploy/kubernetes.yaml:39-42` configure everything else by environment; transport alone requires an argv change, which means switching a deployment from stdio to HTTP is a container-command edit rather than an env-var edit. That is a different change-management path for one setting than for all the others, and it is the one setting most likely to differ between local and deployed runs.

### Remediation
1. **Add a `transport` field to `Settings`** in `src/swisstopo_mcp/config.py:22-26` and let the CLI flag override it rather than be the only path:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SWISSTOPO_", env_file=".env")
    transport: Literal["stdio", "streamable-http"] = "stdio"
    oereb_cantons: str = "ZH"
    log_level: str = "INFO"
    ...
```

Then in `src/swisstopo_mcp/server.py:689-694`:

```python
transport = "streamable-http" if "--http" in sys.argv else settings.transport
```

This keeps `--http` working for existing users while making `SWISSTOPO_TRANSPORT=streamable-http` the deployment path, and it aligns transport with every other setting in `Dockerfile:22-27` and `deploy/kubernetes.yaml:39-42`.

2. **Route the OEREB cantons through `Settings`.** Replace the call-time read at `src/swisstopo_mcp/oereb.py:33` with a lookup on the injected settings object, and validate it at startup:

```python
# config.py
oereb_cantons: str = "ZH"

@field_validator("oereb_cantons")
@classmethod
def _known_cantons(cls, v: str) -> str:
    unknown = {c.strip().upper() for c in v.split(",")} - set(OEREB_ENDPOINTS)
    if unknown:
        raise ValueError(f"Unknown canton codes: {sorted(unknown)}")
    return v

# oereb.py:33
def get_active_cantons(settings: Settings) -> set[str]:
    return {c.strip().upper() for c in settings.oereb_cantons.split(",")}
```

A typo'd canton then fails at startup with a clear message instead of producing an empty result set at call time.

3. **Fold the logging fallback in.** `src/swisstopo_mcp/logging_config.py:32` should take `settings.log_level` rather than reading `os.environ` — `Settings` already carries the field, so this is a signature change, not a new knob.
4. **Extend `tests/test_config.py:8-30`** with cases for `SWISSTOPO_TRANSPORT` and `SWISSTOPO_OEREB_CANTONS`, including the invalid-canton rejection. That is what makes `config.py:3-5`'s claim true rather than aspirational.

### Effort Estimate
S (<1d)


### ARCH-006

## Finding: ARCH-006 — Tool-Budget: High-Level-Use-Cases statt API-Mapping 1:1

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-006
**PDF-Reference:** Sec 2.3

### Observed Behavior
23 tools are exposed, confirmed at runtime via `mcp.list_tools()` against the instance built at `src/swisstopo_mcp/server.py:42`. That falls in the check's "16–25: serious doubt whether all are needed" band and is roughly double the ideal of ≤ 12.

The budget is an explicit, documented decision rather than drift. `CHANGELOG.md:24-28` records "Tool budget raised from 20 to 25 to accommodate the consolidation", `docs/roadmap.md:46` records the same under Phase 2.5, `docs/merge-plan-swiss-geodata-mcp.md:182` and `:241` record the decision and its date, and `README.md:198` states the façade is "kept under the 25-tool budget".

Real aggregation exists and is documented. `query_geodata` fronts three distinct sources behind one tool (`src/swisstopo_mcp/geodata.py:236-248` routes `strassenverzeichnis` / `oereb-verfuegbarkeit` / `geodienste:<topic>:<canton>`), explicitly to avoid one tool per source (`src/swisstopo_mcp/geodata.py:4-13`). Two new convenience tools collapse previously multi-call questions into one call (`src/swisstopo_mcp/rest_api.py:405` `zoning_at`, `rest_api.py:435` `municipality_at`), and the anchor demo queries at `README.md:222-238` are answerable in 1–2 calls.

Two shortfalls remain:

1. **Endpoint-shaped clusters persist and are not argued for.** Five tools sit on the single api3 MapServer/SearchServer API — `swisstopo_search_layers` (`rest_api.py:288`, `/SearchServer`), `swisstopo_layer_info` (`rest_api.py:470`, `/MapServer/{layer}`), `swisstopo_identify_features` (`rest_api.py:311`, `/identify`), `swisstopo_find_features` (`rest_api.py:339`, `/find`), `swisstopo_get_feature` (`rest_api.py:362`, `/{layer}/{id}`) — a close 1:1 mapping of upstream endpoints. Two further search→detail pairs exist: `swisstopo_search_geodata` → `swisstopo_get_collection` and `swisstopo_get_egrid` → `swisstopo_get_oereb_extract`. The README documents the budget *number* but not why these clusters cannot be aggregated further.
2. **Budget figures have drifted out of sync across the repo.** `src/swisstopo_mcp/geodata.py:5` still says the façade keeps the server "well under its 18-tool budget" and `docs/geodaten-erweiterung-phase1.md:253` still states "Budget: 18", while README, CHANGELOG and roadmap now say 25.

### Expected Behavior
- The tool count is justified (ideally ≤ 12 tools)
- No obvious 1:1 API mappings (e.g. one tool per REST endpoint)
- The server's anchor demo query is answerable in 1–2 tool calls
- Where aggregation happens, performance is acceptable (typically < 5s)
- With many tools: a documented justification in the README explaining why no further aggregation is possible

### Evidence
- 23 tools, confirmed at runtime via `mcp.list_tools()` against `src/swisstopo_mcp/server.py:42`
- Documented budget decision: `CHANGELOG.md:24-28`, `docs/roadmap.md:46`, `docs/merge-plan-swiss-geodata-mcp.md:182` and `:241`, `README.md:198`
- Genuine aggregation: `src/swisstopo_mcp/geodata.py:236-248` (three sources behind `query_geodata`), rationale at `src/swisstopo_mcp/geodata.py:4-13`; one-call convenience tools at `src/swisstopo_mcp/rest_api.py:405` and `rest_api.py:435`
- Anchor demo queries answerable in 1–2 calls: `README.md:222-238`
- Endpoint-shaped cluster on one upstream API: `rest_api.py:288`, `rest_api.py:470`, `rest_api.py:311`, `rest_api.py:339`, `rest_api.py:362`
- Stale budget numbers: `src/swisstopo_mcp/geodata.py:5` and `docs/geodaten-erweiterung-phase1.md:253` (both "18") vs 25 in README/CHANGELOG/roadmap
- The repo's own risk register names this: `docs/merge-plan-swiss-geodata-mcp.md:246-251` lists "Tool-Budget-Inflation" as risk #1 of the expansion

Gaps:
- Tool count (23) is nearly double the check's ideal of ≤ 12, and the README documents the budget number without arguing why the remaining endpoint-shaped clusters (`search_layers`/`layer_info`/`identify`/`find`/`get_feature`; `search_geodata`→`get_collection`; `get_egrid`→`get_oereb_extract`) cannot be aggregated further
- Stale budget numbers at `src/swisstopo_mcp/geodata.py:5` and `docs/geodaten-erweiterung-phase1.md:253` contradict the current documented budget of 25

### Risk Description
A 23-tool manifest costs context on every request and, more importantly, degrades tool selection. The five api3 tools are the acute case: `swisstopo_identify_features`, `swisstopo_find_features` and `swisstopo_get_feature` all retrieve features from the same layers and differ mainly in how the caller addresses them (by geometry, by attribute search, by ID). An LLM choosing between them is making an upstream-API decision, not a user-intent decision — which is exactly the coupling the check exists to prevent. Wrong picks here do not error loudly; `find` with a geometry-shaped question returns an empty result, which then interacts with the missing suggestion mechanism (ARCH-003) to produce a false negative rather than a retry.

The growth direction is the part worth watching. The count rose through two feature releases, and the repo's own merge plan named tool-budget inflation as risk #1 of that expansion (`docs/merge-plan-swiss-geodata-mcp.md:246-251`). The offsetting consolidation was real — `query_geodata` genuinely collapsed three sources, and `zoning_at` / `municipality_at` genuinely removed discovery chains — so the trajectory is not simply upward. But at 23 of a 25 budget there are two slots left, and the next data source added will force either a raise or a consolidation. Deciding which now, in the README, is cheaper than deciding it under pressure.

The stale "18" figures are a minor but real hazard: a contributor reading `src/swisstopo_mcp/geodata.py:5` concludes there is far more headroom than exists.

### Remediation
1. **Fix the stale numbers first** — one-line edits at `src/swisstopo_mcp/geodata.py:5` and `docs/geodaten-erweiterung-phase1.md:253`, changing 18 to 25. Better still, remove the number from the code comment entirely and point at `README.md:198` as the single source, so the next raise does not need a code change.
2. **Add a "Tool Budget and Aggregation" subsection to `README.md`** near line 198 that argues the clusters rather than just stating the count. It needs to answer, per cluster, why aggregation was rejected:
   - *api3 five* — state whether `identify` / `find` / `get_feature` are kept separate because their argument shapes are genuinely disjoint (geometry vs attribute vs ID), or whether they are a merge candidate for a future release. If the former, say so explicitly; that is a legitimate justification and it satisfies the criterion.
   - *`search_geodata` → `get_collection`* and *`get_egrid` → `get_oereb_extract`* — these are search→detail pairs, i.e. the shape the check's fail pattern describes. See ARCH-007, which tracks the ÖREB pair specifically; the README entry should reference the planned one-call aggregate rather than defending the split.
3. **Consider merging the three feature-retrieval tools** behind one `swisstopo_get_features` with a discriminated-union input (`by_point` / `by_attribute` / `by_id`). This turns an LLM tool-selection decision into a parameter decision validated by Pydantic, which the models in `rest_api.py` are already strict enough to support. It also frees two budget slots. This is the substantive fix; item 2 is the minimum that satisfies the check.
4. Add the aggregation rationale to `docs/roadmap.md:46` alongside the budget entry so the decision has a durable record, not just a README paragraph.

Items 1 and 2 are the ones required to move this check; item 3 is the one that reduces the count.

### Effort Estimate
M (1-3d) for items 1, 2 and 4. Item 3 (merging the three feature-retrieval tools) is a breaking tool-surface change and should ride the same major release as the SEC-022 renames — L (1-2w) if taken together.


### ARCH-007

## Finding: ARCH-007 — Capability-Aggregation: Composability intern, Atomarität extern

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-007
**PDF-Reference:** Sec 2.3

### Observed Behavior
The remediation from the 2026-05-29 audit ("add a higher-level tool that resolves a common case in one call instead of a discovery chain") is genuinely satisfied for point questions. `swisstopo_zoning_at` (`src/swisstopo_mcp/rest_api.py:405-432`) and `swisstopo_municipality_at` (`rest_api.py:435-467`) each answer a complete user question from a bare coordinate: they hardcode the layer (`rest_api.py:30-32`), run the identify internally via the shared helper `_identify_lv95` (`rest_api.py:381-402`) and return a thought-complete record — zone type, code, municipality, BFS number and canton, or municipality, BFS number and canton. No layer-discovery call is required, and the descriptions say so (`src/swisstopo_mcp/server.py:361-362`). Both encapsulate non-trivial internal logic rather than exposing it: `municipality_at` filters the swissBOUNDARIES3D layer's one-polygon-per-historical-year records down to the current year (`rest_api.py:442-447`), and `_as_bfs_number` (`rest_api.py:126-139`) normalises the BFS join key across two upstream layers that disagree on its type. Provenance travels with the aggregate — zoning results carry the ARE non-binding legal caveat on every record, not only in the prose summary (`rest_api.py:419-421`, constant at `src/swisstopo_mcp/models.py:30-33`), and both tools set an explicit source (`rest_api.py:429`, `rest_api.py:462`).

Three criteria remain unmet on the wider surface:

1. **Pointer-only tools remain**, which is the check's named fail pattern. `swisstopo_get_egrid` returns nothing but a parcel ID whose only use is the follow-up call to `swisstopo_get_oereb_extract` — the description is literally "Vorstufe zu swisstopo_get_oereb_extract" (`src/swisstopo_mcp/server.py:465-471`). Likewise `swisstopo_search_layers` returns layer IDs only (`src/swisstopo_mcp/rest_api.py:159`, "<important_notes>Liefert Layer-IDs, keine Feature-Daten"), `swisstopo_search_geodata` requires `swisstopo_get_collection` for the actual download links (`server.py:249-250`), and `list_available_layers` returns only keys for `query_geodata` (`server.py:514`).
2. **No internal parallelisation anywhere.** `asyncio.gather` / `TaskGroup` appear zero times in `src/`. The clearest missed case is the newly added `swisstopo_layer_info`, which makes two independent upstream calls sequentially — layer metadata at `src/swisstopo_mcp/rest_api.py:474` and the legend at `rest_api.py:495-498`.
3. **The larger surface created a tool-selection ambiguity that is only half-mitigated.** Zoning at a point is now reachable three ways: `swisstopo_zoning_at`, `swisstopo_identify_features` with `layers='ch.are.bauzonen'` (the same layer, `src/swisstopo_mcp/rest_api.py:32`), and `query_geodata` with a `geodienste:<nutzungsplanung>:<canton>` key (`src/swisstopo_mcp/geodata.py:406-415`). The repo's own merge plan flagged this as a pre-merge blocker requiring "in `instructions` eine klare Entscheidungsregel" (`docs/merge-plan-swiss-geodata-mcp.md:246-251`). What landed is a mention, not a rule: `src/swisstopo_mcp/server.py:50-52` says the direct tools exist but states no precedence, and neither `swisstopo_identify_features` (`server.py:174-182`) nor `query_geodata` (`server.py:534-544`) cross-references `swisstopo_zoning_at`.

### Expected Behavior
- Tools deliver thought-complete results, not just IDs/pointers for follow-up calls
- Where aggregation makes sense: tools use `asyncio.gather` / `Promise.all` for parallelisation
- Tool descriptions explicitly mention their aggregated character
- The server's anchor demo query is answerable in ≤ 2 tool calls

### Evidence
- One-call aggregates that meet the pattern: `src/swisstopo_mcp/rest_api.py:405-432` (`zoning_at`), `rest_api.py:435-467` (`municipality_at`), hardcoded layers at `rest_api.py:30-32`, shared helper at `rest_api.py:381-402`, descriptions at `src/swisstopo_mcp/server.py:361-362`
- Encapsulated internal logic: `rest_api.py:442-447` (historical-year filter), `rest_api.py:126-139` (`_as_bfs_number`)
- Provenance on the aggregate: `rest_api.py:419-421` with `src/swisstopo_mcp/models.py:30-33`; explicit source at `rest_api.py:429`, `rest_api.py:462`
- Pointer-only tools: `src/swisstopo_mcp/server.py:465-471` (`get_egrid`), `src/swisstopo_mcp/rest_api.py:159` (`search_layers`), `server.py:249-250` (`search_geodata` → `get_collection`), `server.py:514` (`list_available_layers`)
- No parallelisation: `asyncio.gather` appears zero times in `src/`; sequential independent calls at `src/swisstopo_mcp/rest_api.py:474` and `rest_api.py:495-498`
- Three routes to zoning: `src/swisstopo_mcp/rest_api.py:32`, `src/swisstopo_mcp/geodata.py:406-415`, plus `zoning_at` itself
- Predicted countermeasure not implemented as specified: `docs/merge-plan-swiss-geodata-mcp.md:246-251` vs what landed at `src/swisstopo_mcp/server.py:50-52`; no cross-references at `server.py:174-182` or `server.py:534-544`

Gaps:
- Three paths to zoning data with no stated precedence rule — the countermeasure the merge plan itself required (`docs/merge-plan-swiss-geodata-mcp.md:250-251`) was implemented only as a mention in the instructions string (`src/swisstopo_mcp/server.py:50-52`), not as an explicit routing rule, and not mirrored into the competing tools' descriptions
- `swisstopo_get_egrid` still returns a bare ID that is useless without a second call (`src/swisstopo_mcp/server.py:465-471`); the ÖREB pair is the one remaining chain where a one-call aggregate (coordinate → ÖREB extract) would be a direct analogue of what `zoning_at` / `municipality_at` did for the layer chain
- No `asyncio.gather` in the codebase; `swisstopo_layer_info`'s two independent upstream requests (`rest_api.py:474` and `:495`) run sequentially

### Risk Description
The ambiguity is the primary open item and it is the one with a behavioural cost today. An LLM asked "welche Bauzone gilt an dieser Koordinate?" has three defensible answers in the manifest and no rule to pick between them. The three are not equivalent: `zoning_at` returns a thought-complete record with the ARE legal caveat attached to every record (`rest_api.py:419-421`), while `identify_features` on `ch.are.bauzonen` returns raw feature attributes with no caveat, and `query_geodata` routes to cantonal geodienste data with different coverage and currency. So the choice the LLM makes silently determines whether the user sees the non-binding-legal-status disclaimer — a compliance-relevant difference presented as an implementation detail. The repo predicted this exact failure and specified the countermeasure; what shipped advertises the new tools without stating which wins.

`swisstopo_get_egrid` is the check's fail pattern verbatim: a tool whose result answers no user question and whose description names the tool that must be called next. Every ÖREB lookup therefore costs two calls, with a chance of a chaining hallucination in between — the LLM inventing or mistranscribing an EGRID rather than passing through the one it received.

The missing parallelisation is the mildest of the three: `swisstopo_layer_info` doubles its own latency by awaiting metadata and legend in sequence when they are independent. On a tool that exists to make discovery more usable, that is a self-inflicted cost, but it is user-visible only as slowness.

### Remediation
1. **State a precedence rule and mirror it into the competing tools.** In `src/swisstopo_mcp/server.py:50-52`, replace the mention with an explicit rule, e.g.: "Für Bauzonen an einer Koordinate immer `swisstopo_zoning_at` verwenden. `swisstopo_identify_features` mit `ch.are.bauzonen` nur, wenn zusätzliche Rohattribute gebraucht werden. `query_geodata` mit `geodienste:nutzungsplanung:<kanton>` nur für kantonale Nutzungsplanung, die über die ARE-Bauzonen hinausgeht." Then add a one-line cross-reference to the descriptions at `server.py:174-182` and `server.py:534-544` — the instructions string alone is not reliably consulted per tool-selection decision, which is why the merge plan asked for the rule and not a mention.
2. **Add a one-call ÖREB aggregate.** Introduce `swisstopo_oereb_at(lat, lon)` in `src/swisstopo_mcp/oereb.py` that resolves the EGRID internally and returns the extract, exactly as `zoning_at` collapsed the layer chain:

```python
async def oereb_at(params: OerebAtInput) -> OerebExtract:
    egrid = await _resolve_egrid(params.lat, params.lon)   # internal, not a tool result
    if egrid is None:
        return OerebExtract(results=[], match_type="none", note="...")   # ARCH-003
    return await get_oereb_extract(GetOerebExtractInput(egrid=egrid))
```

Keep `swisstopo_get_egrid` for callers who genuinely need the parcel ID, but drop "Vorstufe zu swisstopo_get_oereb_extract" from its description (`server.py:465-471`) once it is no longer the only path. Note this adds a tool against the budget tracked in ARCH-006 — the offsetting consolidation proposed there (merging the three feature-retrieval tools) should be sequenced with it.

3. **Parallelise `swisstopo_layer_info`.** In `src/swisstopo_mcp/rest_api.py:474` and `:495-498`:

```python
meta, legend = await asyncio.gather(
    geo_admin_request(f"/MapServer/{layer}"),
    geo_admin_request_text(f"/MapServer/{layer}/legend"),
)
```

Handle the legend failing independently — a missing legend should degrade the result, not fail the call, so use `return_exceptions=True` and fall back to `legend=None`.

4. Add a test asserting `swisstopo_layer_info` issues both upstream requests concurrently (respx call ordering, or a timing assertion against two delayed mocks), so the sequential form does not return in a later refactor.

### Effort Estimate
M (1-3d)


### ARCH-011

## Finding: ARCH-011 — Standardisierte Repo-Struktur (src-Layout, tests, README.de.md)

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-011
**PDF-Reference:** Anhang A8

### Observed Behavior
Five of the seven criteria are met cleanly. All five mandatory top-level files are present at the repo root — `README.md`, `README.de.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml` — plus the bilingual extras `CONTRIBUTING.md` / `CONTRIBUTING.de.md` and `SECURITY.md` / `SECURITY.de.md`. All three mandatory directories exist: `src/`, `tests/` (22 test modules, correctly outside `src/`) and `.github/workflows/`. The src-layout is correct — `src/` contains the package directory `src/swisstopo_mcp/` rather than loose `.py` files, and `pyproject.toml` declares it explicitly (hatchling build backend at `pyproject.toml` lines 1-3, `[tool.hatch.build.targets.wheel] packages = ["src/swisstopo_mcp"]` at lines 56-57). CI coverage exceeds the minimum: `.github/workflows/ci.yml:29-37` runs `pytest -m "not live"` plus ruff across Python 3.11/3.12/3.13, `.github/workflows/publish.yml` publishes on release, and `.github/workflows/security.yml` runs gitleaks. `README.de.md` is a genuine parallel document rather than a stub — 20 top-level sections in `README.md` against 19 in `README.de.md`, mapping 1:1 semantically (Overview/Übersicht, Available Tools/Verfügbare Tools, Security & Compliance, MCP Primitives/MCP-Primitive, …).

Two criteria are unmet:

1. **No `tools/` sub-package despite 23 tools.** Tool bodies are split by domain module — `geocoding.py`, `rest_api.py`, `height.py`, `stac.py`, `wmts.py`, `oereb.py`, `geodata.py`, `overpass.py`, `openplz.py`, `coords.py` — and `src/swisstopo_mcp/server.py` contains only registrations that delegate (e.g. `server.py:358`, `return await zoning_at(params)`). But those modules sit flat under `src/swisstopo_mcp/` rather than in `src/swisstopo_mcp/tools/`, and `server.py` is 701 lines against the check's <200-line guidance for a registry file. The bulk of those 701 lines is decorator blocks and docstrings, not logic.
2. **The deviation is not justified anywhere.** `README.md:266-305` and `README.de.md:266-303` render the layout as a tree but give no rationale, and the check explicitly conditions deviations on being argued in the README.

A third, minor discrepancy: `README.de.md` lacks the generated uvx `## Installation` section present at `README.md:484` (between the `BEGIN/END GENERATED: install` markers), which accounts for the 20 vs 19 section count.

### Expected Behavior
- Mandatory top-level files present: `README.md`, `README.de.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml`
- Directories present: `src/`, `tests/`, `.github/workflows/`
- Correct src-layout, no flat package
- CI workflows: at minimum a test workflow (without live tests) and a publish workflow
- `README.de.md` parallel to `README.md` (same top-level sections)
- With > 5 tools: a `tools/` directory with one file per group
- Deviations from the standard are justified in the README

### Evidence
- Mandatory files at the repo root: `README.md`, `README.de.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml`, plus `CONTRIBUTING.md` / `CONTRIBUTING.de.md` and `SECURITY.md` / `SECURITY.de.md`
- Mandatory directories: `src/`, `tests/` (22 modules, outside `src/`), `.github/workflows/`
- src-layout declared: `pyproject.toml` lines 1-3 (hatchling) and 56-57 (`packages = ["src/swisstopo_mcp"]`)
- CI: `.github/workflows/ci.yml:29-37` (pytest `-m "not live"` + ruff, Python 3.11/3.12/3.13), `.github/workflows/publish.yml`, `.github/workflows/security.yml`; the `not live` marker is declared under `[tool.pytest.ini_options]` in `pyproject.toml`
- README parity: 20 top-level sections in `README.md` vs 19 in `README.de.md`, semantically 1:1; the single difference is the generated uvx install block at `README.md:484`
- Domain-module split with a delegating registry: `geocoding.py`, `rest_api.py`, `height.py`, `stac.py`, `wmts.py`, `oereb.py`, `geodata.py`, `overpass.py`, `openplz.py`, `coords.py`; delegation example at `src/swisstopo_mcp/server.py:358`
- Layout documented without rationale: `README.md:266-305`, `README.de.md:266-303`

Gaps:
- No `tools/` sub-package despite 23 tools; the equivalent split lives as flat per-domain modules under `src/swisstopo_mcp/`, and `src/swisstopo_mcp/server.py` is 701 lines (check guidance: <200 for a registry-only file)
- This deviation is not justified anywhere: `README.md:266-305` and `README.de.md:266-303` show the tree but give no rationale
- `README.de.md` lacks the generated uvx `## Installation` section present at `README.md:484`, so the section inventory is 20 vs 19

### Risk Description
Substantively the intent of the layout rule is honoured, so the impact here is low and documentation-shaped rather than structural. There is no 800-line god-file: tool logic sits in per-domain modules that mirror the upstream API families, `server.py` holds only wiring, and every criterion the rule exists to protect — test isolation, reviewable diffs, findable code — is satisfied by the flat-module arrangement.

What the deviation costs is portfolio consistency, which is the stated reason the rule exists. The audit skill, CI templates and dependency tooling are meant to run identically across 29 servers; a tool-file path that is `src/<pkg>/tools/*.py` on other servers and `src/<pkg>/*.py` here means any portfolio-wide script that globs for tool modules either misses this repo or needs a special case. The same applies to a new maintainer arriving from a sibling server: `src/swisstopo_mcp/` holds tool modules, client code and config side by side with no directory-level signal about which is which.

`server.py` at 701 lines is worth noting but not alarming — it is decorator blocks and docstrings, and splitting it would move the volume rather than reduce it. The real gap the check identifies is that none of this reasoning is written down: a reviewer comparing this repo to the standard sees a deviation with no explanation and cannot tell whether it was considered or overlooked.

### Remediation
Two options; the second is sufficient to pass the check and is the better trade here.

**Option A — conform.** `git mv` the ten domain modules into `src/swisstopo_mcp/tools/` with an `__init__.py` re-exporting the handlers, update imports in `server.py`, and leave `server.py` as the registry. This aligns the path with the portfolio standard but touches every import in the repo and every test module, for no functional gain.

**Option B — justify the deviation (recommended).** Add a short "Project Structure" rationale to `README.md:266-305` and its counterpart at `README.de.md:266-303`, e.g.:

> The tool modules sit flat under `src/swisstopo_mcp/` rather than in a `tools/` sub-package. Each module maps to one upstream API family (`rest_api.py` → api3 MapServer, `stac.py` → STAC, `oereb.py` → cantonal ÖREB, …), which is the axis along which this server's code actually varies; a `tools/` level would add a directory without adding a distinction. `server.py` contains registrations only and delegates every tool body to its domain module.

The check permits deviations that are argued, so two paragraphs close criterion 7. If `server.py`'s length is a concern independent of the directory question, split the registrations by family into `server.py` plus per-family registration modules — but that is a readability call, not a check requirement.

Independently of the option chosen:

1. Add the missing `## Installation` section to `README.de.md` so the section inventory reaches parity, or extend the generator that writes the `BEGIN/END GENERATED: install` block at `README.md:484` to emit the German file too — the latter prevents the drift from recurring at the next regeneration.
2. Consider a CI check comparing `grep -E '^## ' README.md | wc -l` against `README.de.md`, which turns bilingual drift into a test failure. That is cheap and serves ARCH-011 across the whole portfolio.

### Effort Estimate
S (<1d) for Option B plus the README parity fix. Option A is also S but touches far more files for less benefit.


### ARCH-012

## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-012
**PDF-Reference:** Anhang A9

### Observed Behavior
There is no explicit `protocolVersion` pin in the server code — a case-insensitive grep for `protocol.?version` over `src/` returns zero hits. The FastMCP instance is constructed with `name`, `lifespan` and `instructions` only (`src/swisstopo_mcp/server.py:42-76`), so the negotiated version is whatever the SDK default is.

That gap is largely structural rather than an omission. The pin is not expressible through the SDK's public API: inspecting mcp 1.28.1 in a clean venv, neither `FastMCP.__init__` nor the lowlevel `Server.__init__` accepts a `protocol_version` parameter, and `mcp.types.LATEST_PROTOCOL_VERSION` is `"2025-11-25"`. The version is negotiated during `initialize` and is not author-settable.

A compensating control is in place and deliberate: `pyproject.toml:31-33` pins the SDK to the 1.x major with the inline rationale "Pinned to the 1.x major so an SDK update cannot silently change the negotiated MCP protocol version (ARCH-012). Dependabot proposes bumps." — `mcp[cli]>=1.28.1,<2.0.0`.

Two of the three gaps from the 2026-05-29 run are genuinely closed. Both READMEs now carry the required section (`README.md:340-345` "MCP Protocol Version", `README.de.md:341-347` "MCP-Protokollversion"), each explaining the negotiate-plus-major-pin approach and pointing at Dependabot and `CHANGELOG.md`. Automated SDK update PRs are configured: `.github/dependabot.yml` sets a monthly pip schedule with a dedicated `mcp-sdk` group matching the mcp package, separated from a catch-all `python-deps` group, plus a monthly github-actions entry. `CHANGELOG.md` is in Keep-a-Changelog format with a SemVer reference (`CHANGELOG.md:1-6`), an `[Unreleased]` section and dated releases (`[0.2.0] - 2026-07-20`, `[0.1.0] - 2026-04-02`), and is actively maintained — the three new tools and the 20→25 budget raise are at `CHANGELOG.md:11-28`, and the SDK pin decision itself is logged at `CHANGELOG.md:206`.

What remains is that no concrete spec version is recorded anywhere in the repo, and there is no breaking-change policy.

### Expected Behavior
- `protocolVersion` explicitly pinned in the server code (not "latest", not the default)
- `CHANGELOG.md` present, in Keep-a-Changelog format
- CHANGELOG entries explicitly name spec-version bumps
- README has an "MCP Protocol Version" section naming the currently supported version
- Update policy documented in the README
- Dependabot or Renovate active for monthly SDK update PRs

### Evidence
- No pin in code: case-insensitive grep for `protocol.?version` over `src/` returns zero hits; instance constructed with name/lifespan/instructions only at `src/swisstopo_mcp/server.py:42-76`
- Not expressible via the SDK: inspected mcp 1.28.1 — neither `FastMCP.__init__` nor lowlevel `Server.__init__` accepts a `protocol_version` parameter; `mcp.types.LATEST_PROTOCOL_VERSION` is `"2025-11-25"`
- Compensating major pin with rationale: `pyproject.toml:31-33` (`mcp[cli]>=1.28.1,<2.0.0`)
- CHANGELOG format and maintenance: `CHANGELOG.md:1-6`, `CHANGELOG.md:11-28`, SDK pin decision at `CHANGELOG.md:206`
- README sections in both languages: `README.md:340-345`, `README.de.md:341-347`
- Dependabot config: `.github/dependabot.yml` (monthly pip, `mcp-sdk` group for the mcp package, separate `python-deps` group, monthly github-actions)

Gaps:
- The README "MCP Protocol Version" section names no concrete spec version — neither `README.md:340-345` nor `README.de.md:341-347` states which protocol version is actually negotiated (2025-11-25 under the pinned mcp 1.28.1), so the criterion "README section with the currently supported version" is unmet and there is no baseline against which a future silent change could be detected
- No CHANGELOG entry references a spec version at all: a grep for `2024-11` / `2025-03` / `2025-06` / `2025-11` across `CHANGELOG.md` returns zero hits. The SDK pin is recorded (`CHANGELOG.md:206`) but not the protocol version it currently yields, leaving the audit-trail criterion unmet
- No breaking-change / compatibility-window policy is documented: the README section covers how updates are proposed (Dependabot, monthly) but not what happens when a spec change breaks compatibility — no semver-major trigger rule and no support window for older spec versions

### Risk Description
The missing pin in code is not actionable — the Python SDK does not expose it, and the 1.x major pin at `pyproject.toml:31-33` is the best available substitute, documented as such. Marking it as an open defect would be marking the SDK's design as this server's defect.

The gap that does matter is cheap and self-defeating in a specific way: the major pin exists to prevent a silent protocol-version change, but because no file in the repo records which version is currently negotiated, exactly the drift the pin is meant to prevent would be undetectable by reading the repo. If a patch-level mcp bump inside the 1.x range moves `LATEST_PROTOCOL_VERSION` — which is permitted by the constraint `>=1.28.1,<2.0.0` — nothing in the README, the CHANGELOG or the tests would show it. A maintainer investigating a client compatibility complaint six months from now has no baseline to diff against and must reconstruct the version by inspecting the installed SDK, which is precisely the reconstruction work the audit-trail criterion exists to eliminate.

Given how fast this spec moves (four major updates in 13 months, per the check's own framing), the absent breaking-change policy compounds it: Dependabot will open the PR, and there is no written rule saying whether a protocol change is a major bump for this server or what happens to clients still speaking the old version.

### Remediation
1. **Record the negotiated version in both READMEs.** Extend `README.md:340-345` and `README.de.md:341-347` with the concrete value and where it comes from:

```markdown
## MCP Protocol Version

This server negotiates the MCP protocol version during `initialize`; the
Python SDK does not expose an author-settable pin. As of `mcp` 1.28.1 the
negotiated version is **2025-11-25** (`mcp.types.LATEST_PROTOCOL_VERSION`).
The SDK is pinned to the 1.x major in `pyproject.toml` so an update cannot
silently move it; Dependabot proposes bumps monthly.

### Update Policy
- SDK updates are tested on a feature branch before merge.
- A change to the negotiated protocol version is recorded in CHANGELOG.md
  under `### Changed` with both the old and new version.
- A protocol change that breaks existing clients triggers a major release.
- Compatibility window: the previous spec version is supported for 6 months
  after a bump.
```

Adjust the window to whatever the portfolio actually commits to — the point is that a number exists, not that it is six months.

2. **Add a CHANGELOG entry now**, retroactively, under the release that introduced the current SDK pin: "MCP protocol version negotiated as 2025-11-25 (mcp 1.28.1)". Adopt the convention that every mcp bump PR notes the resulting protocol version, so `CHANGELOG.md` becomes the audit trail the criterion asks for.
3. **Make the drift detectable automatically.** A test is stronger than a documentation convention here, because Dependabot merges are routine:

```python
# tests/test_protocol_version.py
from mcp.types import LATEST_PROTOCOL_VERSION

EXPECTED = "2025-11-25"   # keep in sync with README + CHANGELOG

def test_negotiated_protocol_version_unchanged():
    assert LATEST_PROTOCOL_VERSION == EXPECTED, (
        "SDK protocol version changed — update README, CHANGELOG and this constant, "
        "and assess client compatibility per the update policy."
    )
```

This turns a silent SDK-side change into a red CI run on the Dependabot PR, which is the moment the maintainer can actually act on it.

4. Once items 1–3 land, this check passes. Re-check the pin criterion when an SDK version exposes `protocol_version` on the constructor; until then, `pyproject.toml:31-33` plus the test in item 3 is the complete available control.

### Effort Estimate
S (<1d)


### CH-004

## Finding: CH-004 — OGD-CH Lizenz-Compliance: CC BY 4.0 Attribution

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** CH-004
**PDF-Reference:** Custom (OGD-CH-Richtlinien)

### Observed Behavior

Every tool answer carries populated `source` and `license` fields, but the three sources added in this release set `source` only — so ARE data ships under the swisstopo licence constant inherited through an omitted keyword argument.

What is in place:

- The envelope carries both fields by construction: `src/swisstopo_mcp/models.py:70-71` defines `source` (default `SWISSTOPO_SOURCE`) and `license` (default `SWISSTOPO_LICENSE`) on every `ToolResponse`; `ToolResponse.ok()` takes both as keyword args (`src/swisstopo_mcp/models.py:83-84`).
- Per-record provenance for the ARE legal caveat is correctly implemented: `src/swisstopo_mcp/rest_api.py:421` attaches `legal_note: ARE_ZONING_CAVEAT` to every zoning record (`src/swisstopo_mcp/models.py:30-33`), not only to the prose summary (`src/swisstopo_mcp/rest_api.py:152`). Regression-tested at `tests/test_places.py:110-115` and verified empirically (`results[0]['legal_note']` present).
- Provenance survives aggregation: `src/swisstopo_mcp/geodata.py:532-533` marks mixed-source results "gemischt — siehe je Layer".

What fails:

- **New source ARE — attribution incomplete.** `src/swisstopo_mcp/rest_api.py:429` passes only `source=ARE_SOURCE` to `ToolResponse.ok()`; no `license=` is passed, so the `ch.are.bauzonen` response silently inherits `SWISSTOPO_LICENSE`. Confirmed empirically with a respx-mocked call: `source='ch.are.bauzonen (ARE) / geo.admin.ch'`, `license='Swiss Open Government Data (opendata.swiss)'` (== the `SWISSTOPO_LICENSE` default). `src/swisstopo_mcp/models.py:25` defines `ARE_SOURCE` but there is **no** `ARE_LICENSE` constant.
- **Same omission on the other two new sources:** `src/swisstopo_mcp/rest_api.py:462` (swissBOUNDARIES3D) and `src/swisstopo_mcp/coords.py:280,303,306,309` (REFRAME) pass `source=` only. `src/swisstopo_mcp/models.py:24,26` define `REFRAME_SOURCE` and `SWISSBOUNDARIES_SOURCE` with no matching `*_LICENSE` constants. For these two the swisstopo fallback is materially correct (both are swisstopo products); for ARE — the Bundesamt für Raumentwicklung, a different federal office — the licence statement is inherited rather than asserted.
- **This breaks the pattern every other non-swisstopo source in the repo follows:** ÖREB (`src/swisstopo_mcp/oereb.py:113-114,132-133,171-172,190-191,255-256`), geodienste (`src/swisstopo_mcp/geodata.py:454,490-491`), OSM/ODbL (`src/swisstopo_mcp/overpass.py:211`) and OpenPLZ (`src/swisstopo_mcp/openplz.py:406-407,438-439,455-456,474-475,496-497,517-518`) all pass `source=` **and** `license=` explicitly.
- **Error envelopes cannot carry a licence at all:** `src/swisstopo_mcp/models.py:99-100` — `ToolResponse.error()` accepts `source` but not `license`, so every handled error from ARE / ÖREB / OSM / OpenPLZ / geodienste reports `SWISSTOPO_LICENSE` (e.g. `src/swisstopo_mcp/rest_api.py:432`, `src/swisstopo_mcp/coords.py:306,309`, `src/swisstopo_mcp/overpass.py:214`, `src/swisstopo_mcp/openplz.py:411`).
- **README licence documentation is incomplete:** `README.md:461` / `README.de.md:462` name only "Data provided by swisstopo … under Open Government Data terms". There is no "Data sources & licences" table. The overview source table (`README.md:22-33`) lists 9 sources but has no licence column and does not list ARE / `ch.are.bauzonen`, swissBOUNDARIES3D or the REFRAME service (`geodesy.geo.admin.ch`) at all. `README.md:157-159` mentions `swisstopo_zoning_at` as "(not legally binding)" but never names ARE as the data producer.
- **No test asserts the licence field of the new sources:** `tests/test_places.py` (300 lines, covering zoning/municipality/layer_info) and `tests/test_coords.py` never assert `out.source` or `out.license`; `tests/test_responses.py:18-19,42,66` only assert `SWISSTOPO_SOURCE` and `OEREB_SOURCE`.
- The ARE non-binding caveat is on every record but not in the `ToolResponse`-level fields; the empty-result path (`src/swisstopo_mcp/rest_api.py:145`) returns no record and therefore no caveat.

### Expected Behavior

Per the check's Pass Criteria:

- Tool answers contain a `source` field with producer and licence
- The README documents all used data sources with their licences
- On aggregation, provenance is retained per record, not only globally
- No licence conflicts
- **Attribution text exactly per the licence requirement** — for CC BY: author, source, licence, and a modification note where applicable

### Evidence

- File: `src/swisstopo_mcp/rest_api.py:429` — `ToolResponse.ok(..., source=ARE_SOURCE)` with no `license=`; same at `:432` (error path) and `:462`/`:466` (swissBOUNDARIES3D).
- File: `src/swisstopo_mcp/coords.py:280,303,306,309` — REFRAME paths, `source=` only.
- File: `src/swisstopo_mcp/models.py:24,25,26` — `REFRAME_SOURCE`, `ARE_SOURCE`, `SWISSBOUNDARIES_SOURCE` defined; no `*_LICENSE` counterparts. `src/swisstopo_mcp/models.py:70-71,83-84` — envelope defaults and `ok()` signature. `src/swisstopo_mcp/models.py:99-100` — `error()` has no `license` parameter.
- Empirical (respx-mocked `zoning_at` call): `source='ch.are.bauzonen (ARE) / geo.admin.ch'`, `license='Swiss Open Government Data (opendata.swiss)'`.
- Counter-examples following the correct pattern: `src/swisstopo_mcp/oereb.py:113-114`, `src/swisstopo_mcp/geodata.py:454`, `src/swisstopo_mcp/overpass.py:211`, `src/swisstopo_mcp/openplz.py:406-407`.
- File: `README.md:461` / `README.de.md:462` (licence prose), `README.md:22-33` (source table without a licence column), `README.md:157-159`.
- File: `tests/test_places.py`, `tests/test_coords.py` — no `source` / `license` assertions; `tests/test_responses.py:18-19,42,66` — only swisstopo and ÖREB.
- Positive: `src/swisstopo_mcp/rest_api.py:421` + `tests/test_places.py:110-115` — per-record `legal_note`.

### Risk Description

The emitted text ("Swiss Open Government Data (opendata.swiss)") happens to be generically true for federal OGD, which is why this is a compliance weakness rather than an outright licence violation. The concrete problems:

- `ch.are.bauzonen` is published by the **ARE**, not swisstopo. The response tells a downstream consumer that the data comes from ARE but states a licence that was never asserted for it — it was inherited by an omitted keyword argument. An LLM client relaying the attribution to an end user therefore reproduces a licence statement nobody checked against the ARE's actual terms. If those terms ever diverge from the generic OGD wording, the server emits a wrong attribution with no code change and no signal.
- Because the inheritance is silent, the same trap applies to the next non-swisstopo source added: forgetting `license=` produces a plausible-looking, wrong attribution rather than an error. Six existing sources pass it explicitly, so a reviewer reading only those files would reasonably assume the argument is required.
- Every handled error from a non-swisstopo source mis-states the licence, because `ToolResponse.error()` (`src/swisstopo_mcp/models.py:99-100`) cannot carry one. An error envelope for an ÖREB or OSM failure claims swisstopo OGD terms.
- The READMEs document one source with one licence while the server actually draws on nine, including OSM under ODbL — a share-alike licence with materially different obligations from CC BY. A user reading `README.md:461` has no way to learn that ODbL applies to any part of the output.

### Remediation

1. `src/swisstopo_mcp/models.py`: add the missing licence constants next to the existing `*_SOURCE` constants (`:24-26`):

   ```python
   ARE_LICENSE = "..."               # per ARE / ch.are.bauzonen terms of use
   SWISSBOUNDARIES_LICENSE = SWISSTOPO_LICENSE
   REFRAME_LICENSE = SWISSTOPO_LICENSE
   ```

   Aliasing the two swisstopo products to `SWISSTOPO_LICENSE` keeps the emitted text identical while making the assertion explicit rather than accidental. Verify the ARE wording against the layer's terms on geo.admin.ch before filling it in.
2. Pass `license=` at every new-source call site: `src/swisstopo_mcp/rest_api.py:429` and `:432` (ARE), `:462` and `:466` (swissBOUNDARIES3D), `src/swisstopo_mcp/coords.py:280,303,306,309` (REFRAME).
3. `src/swisstopo_mcp/models.py:99-100`: give `ToolResponse.error()` a `license: str = SWISSTOPO_LICENSE` keyword mirroring `ok()`, and pass it at the error paths of every non-swisstopo source (`src/swisstopo_mcp/rest_api.py:432`, `src/swisstopo_mcp/coords.py:306,309`, `src/swisstopo_mcp/overpass.py:214`, `src/swisstopo_mcp/openplz.py:411`).
4. Add a "Data sources & licences" table to `README.md` and `README.de.md` (replacing the single licence line at `README.md:461` / `README.de.md:462`), with one row per source — swisstopo, ARE (`ch.are.bauzonen`), swissBOUNDARIES3D, REFRAME (`geodesy.geo.admin.ch`), ÖREB (cantonal), geodienste, OpenPLZ, OSM/ODbL — each with URL, licence and the exact attribution text. Name ARE as the producer where `swisstopo_zoning_at` is described (`README.md:157-159`).
5. Add regression tests asserting `out.source` and `out.license` for the three new sources in `tests/test_places.py` and `tests/test_coords.py`, mirroring the existing pattern at `tests/test_responses.py:18-19,42,66`. A test that fails when a licence is inherited by default is what prevents this from recurring.
6. Optional: also surface `ARE_ZONING_CAVEAT` on the empty-result path (`src/swisstopo_mcp/rest_api.py:145`), so a "no zoning found here" answer still carries the non-binding caveat in its summary.

### Effort Estimate

S (<1d) — three constants, eight call sites, one signature change, a README table and two test additions.


### OBS-006

## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OBS-006
**PDF-Reference:** Anhang B10

### Observed Behavior

The check applies (`is_cloud_deployed == true`, corroborated by `Dockerfile`, `deploy/kubernetes.yaml`, `deploy/ingress-sticky-sessions.yaml`, `docs/deployment.md` and a dual-transport HTTP app with `/healthz` at `src/swisstopo_mcp/server.py:657-683`), and nothing that satisfies it exists. This is an absence, not a partial implementation.

- **No OpenTelemetry SDK anywhere in the dependency tree:** `pyproject.toml:31-40` (`[project].dependencies` = `mcp[cli]`, `httpx`, `pydantic`, `pydantic-settings`, `structlog`) and `pyproject.toml:43-49` (`[project.optional-dependencies].dev` = `pytest`, `pytest-asyncio`, `pytest-cov`, `respx`, `ruff`). No `opentelemetry-api` / `-sdk` / `-exporter-otlp` / `-instrumentation-httpx`.
- **No tracing code in `src/`:** a case-insensitive grep for `opentelemetry | otel | tracer | start_as_current_span | set_attribute` over `src/` returns zero tracing hits (the only "span"-adjacent matches are the word `lifespan` at `src/swisstopo_mcp/api_client.py:80,82,98` and `src/swisstopo_mcp/server.py:28,44`). There is no observability module and no `traced_tool` decorator; the only cross-cutting instrumentation is the structlog decorator at `src/swisstopo_mcp/logging_config.py:63-91` (OBS-003).
- **No auto-instrumentation of the HTTP client, so upstream latency is untraced:** `src/swisstopo_mcp/api_client.py:88-99` builds the shared `httpx.AsyncClient` with no `HTTPXClientInstrumentor().instrument()` call, and the retry wrapper at `src/swisstopo_mcp/api_client.py:146-187` records nothing beyond a debug log line (`api_client.py:169`). Backend hop latency to `api3.geo.admin.ch`, `geodesy.geo.admin.ch`, `overpass.osm.ch` and `openplzapi.org` is therefore invisible as a child span.
- **No OTLP configuration in any deployment artifact:** a grep for `OTEL_EXPORTER_OTLP_ENDPOINT | OTEL_SERVICE_NAME | OTEL_RESOURCE_ATTRIBUTES` over `deploy/`, `Dockerfile` and `docs/` returns zero hits. `deploy/kubernetes.yaml:39-44` sets only `SWISSTOPO_HTTP_HOST` and `SWISSTOPO_ALLOWED_ORIGINS`; the container has liveness/readiness probes on `/healthz` (`deploy/kubernetes.yaml:50-60`) but no telemetry sidecar, collector reference or service-name tag.
- **No observability plan in the docs either:** a grep for `observab|metric|prometheus|trace|tracing|monitor` over `deploy/`, `docs/`, `README.md` and `SECURITY.md` returns a single unrelated hit (`docs/geodaten-erweiterung-phase1.md:280`, about error messages vs stacktraces). `docs/roadmap.md` lists no tracing item in any phase.

Note: this check was not part of the 2026-05-29 run (36 checks, OBS-006 absent from `verification-results.json`), so this is a first evaluation rather than a regression.

### Expected Behavior

Per the check's Pass Criteria:

- OpenTelemetry SDK installed and initialised
- TracerProvider configured with an OTLP exporter
- Auto-instrumentation active for the HTTP client (httpx)
- One span per tool call carrying `mcp.tool.name`, `mcp.user.id`, `mcp.tool.result.is_error`
- Backend API calls appear automatically as child spans
- No sensitive data in span attributes (no PII, no tokens, no raw argument contents)
- OTLP endpoint configurable via env var
- Service name and environment tag set explicitly

### Evidence

- File: `pyproject.toml:31-40`, `pyproject.toml:43-49` — dependency lists; no `opentelemetry-*` package.
- Grep over `src/`: zero hits for `opentelemetry|otel|tracer|start_as_current_span|set_attribute`.
- File: `src/swisstopo_mcp/api_client.py:88-99` — shared `httpx.AsyncClient` created without instrumentation; `src/swisstopo_mcp/api_client.py:146-187` — retry wrapper, only a debug log at `:169`.
- File: `deploy/kubernetes.yaml:39-44` (env vars: none OTEL), `deploy/kubernetes.yaml:50-60` (probes only).
- File: `src/swisstopo_mcp/logging_config.py:83` — per-call `duration_ms` in unaggregated stderr JSON logs, the only latency signal that exists.
- File: `src/swisstopo_mcp/server.py:657-683` — the HTTP app under audit; `docs/roadmap.md` — no tracing item in any phase.

### Risk Description

Two of the three workflows this check enables are weak for this server, and one is genuinely missing:

- **User-behaviour forensics (weak here).** The server is unauthenticated, read-only, public open data. There is no user identity to attach to a span and no read+exfiltrate pattern to detect. This mitigates severity but does not remove the finding.
- **P99 / slow-tool identification (partially covered).** structlog already emits per-call `duration_ms` (`src/swisstopo_mcp/logging_config.py:83`), but only as unaggregated JSON on stderr, so there is no way to compute a percentile or compare tools without shipping and parsing container logs by hand.
- **Backend-bottleneck attribution (missing, and this is the real gap).** The server fans out to four independent upstream APIs, three of which — `overpass.osm.ch`, `openplzapi.org`, `geodienste.ch` — are community or third-party endpoints with known transient 503s already handled in `src/swisstopo_mcp/api_client.py:130-138`. When a tool call is slow in production there is currently no way to tell whether the latency is in the server, in `api3.geo.admin.ch`, or in Overpass. The operator's only recourse is to reproduce the call by hand and hope the condition persists — which for transient upstream degradation it usually does not. Because the retry wrapper (`api_client.py:146-187`) silently absorbs retries, a request that took three attempts and 20 s is indistinguishable in the logs from one that took 20 s in a single attempt.

### Remediation

Given structlog already emits `duration_ms`, this is an increment rather than a rebuild.

1. `pyproject.toml:31-40`: add `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp` and `opentelemetry-instrumentation-httpx` to the dependencies (or to an `otel` extra if the stdio users should not pay for them).
2. Add `src/swisstopo_mcp/observability.py` with a `setup_tracing()` that builds a `Resource` from `OTEL_SERVICE_NAME` (default `swisstopo-mcp`) plus `deployment.environment`, installs a `TracerProvider` with a `BatchSpanProcessor(OTLPSpanExporter())`, and calls `HTTPXClientInstrumentor().instrument()`. Make it a no-op when `OTEL_EXPORTER_OTLP_ENDPOINT` is unset, so the local stdio path is unaffected.
3. Call `setup_tracing()` from the lifespan at `src/swisstopo_mcp/server.py:25-38`, before `create_shared_client()` — the shared client must be created after instrumentation for the httpx auto-instrumentation to attach, which is why the ordering matters here specifically.
4. Wrap the existing structlog tool decorator at `src/swisstopo_mcp/logging_config.py:63-91` in a span rather than adding a second decorator: it already knows the tool name, the duration and the `is_error` outcome, so set `mcp.tool.name` and `mcp.tool.result.is_error` from the values it already has. Do **not** add `mcp.user.id` — there is no authenticated identity (`auth_model=none`) — and do not put tool arguments into attributes; coordinates and addresses are user input and belong nowhere near an observability backend (SEC-023 synergy).
5. `deploy/kubernetes.yaml:39-44`: add `OTEL_SERVICE_NAME=swisstopo-mcp`, `OTEL_EXPORTER_OTLP_ENDPOINT` pointing at the cluster collector, and `OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production`. Document the variables in `.env.example` and `docs/deployment.md`.
6. Add a tracing item to `docs/roadmap.md` so the operational plan matches the deployment posture, and a unit test asserting that `setup_tracing()` is inert without an OTLP endpoint (so CI and stdio users see no behaviour change).

### Effort Estimate

M (1-3d) — SDK setup, one new module, decorator extension, deployment wiring and a collector endpoint to point at.


### OPS-001

## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OPS-001
**PDF-Reference:** Anhang C1

### Observed Behavior

The mocked/live split is implemented correctly, but the live half is never executed by automation and does not cover all tools.

What is in place:

- Marker registered and CI excludes live tests: `pyproject.toml:64-66` (`[tool.pytest.ini_options] markers = ['live: live API tests (skipped in CI by default)']`) and `.github/workflows/ci.yml:26-28` runs `pytest tests/ -m "not live"` across a Python 3.11/3.12/3.13 matrix.
- Large mocked unit suite: 22 test modules, ~464 test functions for 23 tools (`tests/test_oereb.py` 61, `tests/test_stac.py` 48, `tests/test_height.py` 47, `tests/test_rest_api.py` 40, `tests/test_geocoding.py` 38, `tests/test_places.py` 28, `tests/test_openplz.py` 27, `tests/test_wmts.py` 26, `tests/test_coords.py` 24, `tests/test_geodata.py` 23, plus regression suites `tests/test_responses.py`, `tests/test_logging.py`, `tests/test_egress_allowlist.py`, `tests/test_input_validation.py`, `tests/test_shared_client.py`, `tests/test_http_app.py`, `tests/test_retry.py`, `tests/test_context.py`). Well above the "5 unit tests per tool" bar.
- `respx` HTTP mocking is used where the transport matters: `tests/test_places.py:12,96,109,117,128,134,142` (all zoning/municipality/layer_info paths), `tests/test_coords.py`, `tests/test_openplz.py`, `tests/test_lv95_input.py`, `tests/test_retry.py`. Other modules mock at the function boundary with monkeypatch instead (e.g. `tests/test_responses.py:37,49,57`).
- The three new tools have proper three-way unit coverage: happy path (`tests/test_places.py:96-107`), error path (`tests/test_places.py:142-147`, upstream 500 → `is_error` with body suppressed), and edge cases (`tests/test_places.py:134-140` empty result as soft miss; `:149-151` missing coordinates → `ValidationError`; `:172-184` historical-only municipality record → soft miss).
- Live tests exist for the new tools and are correctly marked: `tests/test_places.py:282-299` (`@pytest.mark.live class TestPlacesLive` covering `zoning_at`, `municipality_at`, `layer_info` against Zurich LV95 2683531/1247914) and `tests/test_coords.py:205-238` (`@pytest.mark.live TestReframeLive` with a WGS84→LV95→WGS84 roundtrip and a drift guard asserting the local polynomial stays within 1 m of REFRAME).

What is missing:

- **No nightly or manual live-test workflow.** `.github/workflows/` contains only `ci.yml`, `publish.yml` and `security.yml`. None has a `schedule:` trigger or a `pytest -m live` step, so the 17 live tests are never executed by automation. This gap was already recorded in the 2026-05-29 run and is unchanged.
- **5 of 23 tools have no live test:** `swisstopo_find_features` and `swisstopo_get_feature` (`tests/test_rest_api.py:361-378` covers only `search_layers` and `identify_features`), `swisstopo_get_collection` (`tests/test_stac.py:386` covers only `search_geodata`), `swisstopo_get_egrid` and `swisstopo_get_oereb_extract` (`tests/test_oereb.py`: zero live markers despite 61 tests). `tests/test_wmts.py` also has zero live markers, but `swisstopo_map_url` is a pure URL builder with no network call, so that is correct by design.
- Layout note only, not counted against the status: `tests/test_unit.py` and `tests/test_live.py` as named files do not exist; the repo splits per source module and separates live tests by marker within each file, which is functionally equivalent to the check's intent.

### Expected Behavior

Per the check's Pass Criteria:

- At least 5 unit tests per tool, mocked with `respx`
- At least 1 live test per tool, marked `@pytest.mark.live`
- Marker registered in `pyproject.toml`
- CI workflow runs `pytest -m "not live"`
- **A separate nightly/manual live-test workflow** (`schedule:` + `workflow_dispatch` running `pytest -m live`)
- Live tests use test-specific credentials rather than production keys (vacuously satisfied — all upstream endpoints are key-less)

### Evidence

- File: `pyproject.toml:64-66` — live marker registered.
- File: `.github/workflows/ci.yml:26-28` — `pytest tests/ -m "not live"` on a 3.11/3.12/3.13 matrix.
- File: `tests/test_places.py:282-299`, `tests/test_coords.py:205-238` — live tests exist and are correctly marked.
- Directory: `.github/workflows/` — contains only `ci.yml`, `publish.yml`, `security.yml`; no `schedule:` trigger and no `pytest -m live` step anywhere.
- File: `tests/test_rest_api.py:361-378`, `tests/test_stac.py:386`, `tests/test_oereb.py` — live coverage gaps for `find_features`, `get_feature`, `get_collection`, `get_egrid`, `get_oereb_extract`.
- File: `README.md:404` — the README itself flags the cantonal ÖREB endpoint formats (`oereb.geo.zh.ch`, `www.oereb2.apps.be.ch`) as inconsistent.

### Risk Description

Schema drift in the upstream APIs goes undetected until someone runs the live suite by hand. This is not theoretical for the current release: the tool surface just grew onto two upstream layers whose attribute schemas the handlers depend on **by name** —

- `src/swisstopo_mcp/rest_api.py:412-422` reads `ch_bez_d` / `ch_bez_f` / `ch_code_hn` / `bfs_no` / `kt_kz`
- `src/swisstopo_mcp/rest_api.py:443-456` reads `is_current_jahr` / `gemname` / `gde_nr` / `kanton`

The unit fixtures pin those exact names. A rename upstream would leave CI fully green while every zoning and municipality result silently returns nulls — the worst class of failure for a data server, because it is indistinguishable from "no data at this location". The live tests that would catch it exist; nothing runs them.

The unlive-tested pair `swisstopo_get_egrid` / `swisstopo_get_oereb_extract` is the most exposed remainder, since those hit cantonal endpoints whose formats the README already describes as inconsistent — precisely the endpoints most likely to change without notice.

### Remediation

1. Add `.github/workflows/live-test.yml`:

   ```yaml
   on:
     schedule:
       - cron: "0 4 * * *"   # nightly 04:00 UTC
     workflow_dispatch:
   jobs:
     live-tests:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v5
         - uses: actions/setup-python@v6
           with:
             python-version: "3.12"
         - run: pip install -e ".[dev]"
         - run: pytest -m live -v
   ```

   No credentials are needed — all upstreams are key-less. Route failures to an issue or a notification so a red nightly is actually seen; a silently failing schedule reproduces the current situation.
2. Close the live-coverage holes with one live test per tool:
   - `tests/test_oereb.py`: add a `@pytest.mark.live` class covering `swisstopo_get_egrid` and `swisstopo_get_oereb_extract` against a known Zurich parcel, asserting only structural invariants (EGRID present, extract non-empty) so cantonal content changes do not cause false alarms.
   - `tests/test_rest_api.py:361-378`: extend the live class with `find_features` and `get_feature`.
   - `tests/test_stac.py:386`: add a live `get_collection` case.
3. Make schema drift explicit rather than incidental: in the new live tests for zoning and municipality, assert the presence of the attribute names the handlers read (`ch_bez_d`, `bfs_no`, `kt_kz`, `is_current_jahr`, `gemname`, `gde_nr`, `kanton`) so a rename fails loudly with a readable message instead of surfacing as an empty result.

### Effort Estimate

M (1-3d) — the workflow file is an hour; the five missing live tests plus the schema-drift assertions are the bulk of the work.


### OPS-003

## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OPS-003
**PDF-Reference:** Anhang C4

### Observed Behavior

A phase is declared and the code matches the read-only discipline, but the declaration contradicts the roadmap and the Phase 1 → 2 gate was crossed without its required artefacts.

What is in place:

- A phase is declared in the README: `README.md:313-317` ("### Phase — This server is in **Phase 1 — Read-only wrapper**. All 23 tools are `readOnlyHint: true` / `destructiveHint: false`; there are no write or send capabilities."), mirrored at `README.de.md:311-316`.
- The declared phase is consistent with the actual tool annotations: 23 of 23 `@mcp.tool` registrations in `src/swisstopo_mcp/server.py` carry `readOnlyHint: True` (e.g. `server.py:91, 148, 168, 352, 375, 397, 426`) and `grep -rn 'destructiveHint.*True' src/` returns zero hits. No write, send, mail or webhook tool exists.
- A roadmap file exists with phase-specific tasks: `docs/roadmap.md` — Phase 1 Read-only wrapper (`:6-19`, marked done, 7 checked items including the audit run against mcp-audit-skill), Phase 2 Semantic/richer responses (`:21-30`), Phase 2.5 Consolidation of swiss-geodata-mcp (`:32-49`), Phase 3 Write operations (`:51-55`, "not planned", with an explicit requirement to re-run the Lethal-Trifecta assessment and a security review before any write tool).

What fails:

- **Contradictory phase declaration.** `README.md:315` says the server is in Phase 1, but `docs/roadmap.md:6` marks Phase 1 "(✅ done)", `docs/roadmap.md:21` marks Phase 2 "(✅ largely done)" with structured returns, structlog and `match_type` checked off (`:23-27`), and `docs/roadmap.md:32` declares Phase 2.5 "(🔄 in progress)". The three tools audited in this run were delivered under Phase 2.5 (`docs/roadmap.md:45-47`) and `src/swisstopo_mcp/server.py:494` labels the geodata facade "(Phase-2 Geodaten-Erweiterung)". A reader consulting the README gets a different phase than a reader consulting the roadmap.
- **Missing Phase 1 → 2 prerequisites.** The check requires the transition to be gated on a completed audit run, an ISDS classification and a DSG-Verarbeitungsverzeichnis. Only the audit run exists (`docs/roadmap.md:18`, `audits/` with four run directories). A case-insensitive grep for `isds|verarbeitungsverzeichnis|dsg|datenschutz` over `README.md`, `README.de.md`, `docs/` and `SECURITY.md` returns **zero hits** — neither artefact exists, yet the roadmap already reports Phase 2 as largely done and Phase 2.5 in progress.
- **No phase transitions in the CHANGELOG.** `grep -in 'phase' CHANGELOG.md` returns only four incidental hits (`:133-134` and `:151` referencing `docs/geodaten-erweiterung-phase1.md` and its live probe; `:186` noting that a roadmap and a README security section were added). No entry records the Phase 1 → Phase 2 or Phase 2 → Phase 2.5 transition or its sign-off.
- `docs/roadmap.md:49` lists "Re-run the audit against the changed surface" as an open Phase-2.5 item — the roadmap itself acknowledges that the current run was still outstanding when the tools shipped.

### Expected Behavior

Per the check's Pass Criteria:

- The current phase is declared explicitly in the README (Phase 1 / 2 / 3), single-sourced
- The phase matches the actual tool annotations (no Phase-1 server with destructive tools)
- A roadmap file with phase-specific tasks exists
- Phase transitions require documented prerequisites — Phase 1 → 2: audit run, ISDS classification and DSG-Verarbeitungsverzeichnis complete
- Phase transitions are documented in the CHANGELOG

### Evidence

- File: `README.md:313-317` / `README.de.md:311-316` — "Phase 1 — Read-only wrapper".
- File: `docs/roadmap.md:6` (Phase 1 done), `:21-30` (Phase 2 largely done), `:32-49` (Phase 2.5 in progress, incl. `:45-47` for the tools audited here, `:49` audit re-run still open), `:51-55` (Phase 3 gated).
- File: `src/swisstopo_mcp/server.py:494` — geodata facade labelled "(Phase-2 Geodaten-Erweiterung)".
- File: `src/swisstopo_mcp/server.py:91, 148, 168, 352, 375, 397, 426` — `readOnlyHint: True`; zero `destructiveHint: True` in `src/`.
- Grep: `isds|verarbeitungsverzeichnis|dsg|datenschutz` over `README.md`, `README.de.md`, `docs/`, `SECURITY.md` → zero hits.
- File: `CHANGELOG.md:133-134, 151, 186` — the only `phase` hits, none recording a transition.

### Risk Description

The substantive risk this check guards against — "we built writes because we could" — has **not** materialised: 23/23 tools are read-only, and Phase 3 is explicitly gated behind a re-run of SEC-019 and a security review (`docs/roadmap.md:53-55`). The remaining risk is governance, and it is concrete:

- Two contradictory phase declarations produce exactly the uncertainty the check's anti-pattern table names ("Phase nicht deklariert → Maintainer und Reviewer unsicher, was zugelassen ist"). A reviewer who trusts `README.md:315` believes the server is still a Phase-1 wrapper and applies Phase-1 rules to a PR that is in fact a Phase-2.5 change; a reviewer who trusts the roadmap applies looser ones. Neither can point to an authoritative statement.
- The Phase 1 → 2 gate was crossed with no record that anyone considered the ISDS and DSG requirements. For a public-open-data, auth-none, read-only server the substantive compliance risk is low — no personal data is processed, so a Verarbeitungsverzeichnis would be near-empty — but "low risk" is a reason to write a short document, not a reason to skip the gate. As it stands, nothing in the repo shows the exemption was ever assessed, so the next server in the portfolio inherits the precedent that the gate is optional.
- Without CHANGELOG entries, no phase transition has an owner or a date. If a future contributor proposes a write tool, there is no recorded decision trail showing which prerequisites were met and by whom.

### Remediation

1. Make the README the single phase authority and correct it. In `README.md:313-317` and `README.de.md:311-316`, replace the prose Phase-1 statement with a status table stating the actual phase (Phase 2.5 per `docs/roadmap.md:32`) and listing each prerequisite with its status:

   ```markdown
   ## Phase

   This server is in **Phase 2.5 — Consolidation** (see [docs/roadmap.md](./docs/roadmap.md)).

   | Property | Status |
   |---|---|
   | Read tools | 23, all `readOnlyHint: true` |
   | Write tools | none (Phase 3, not planned) |
   | ISDS classification | see `docs/isds-klassifikation.md` |
   | DSG-Verarbeitungsverzeichnis | see `docs/dsg-processing-record.md` |
   | Audit run | 2026-07-27, `audits/2026-07-27T125314-Z-swisstopo-mcp/` |
   ```

   `docs/roadmap.md` then keeps the task lists and stops being a second source of truth for the current phase.
2. Add `docs/isds-klassifikation.md`. For this server it is short: public federal open data, no personal data, no authentication, read-only — classify accordingly and state the reasoning explicitly so the exemption is recorded rather than assumed.
3. Add `docs/dsg-processing-record.md` covering the same ground for DSG: which data categories are processed (none personal — coordinates and public geodata), which upstreams are contacted (`api3.geo.admin.ch`, `geodesy.geo.admin.ch`, cantonal ÖREB endpoints, `overpass.osm.ch`, `openplzapi.org`, `geodienste.ch`), and what is logged (per-call `duration_ms`, no request payloads).
4. Record phase transitions in `CHANGELOG.md`: one entry each for Phase 1 → 2 and Phase 2 → 2.5, naming the date, the prerequisites met and who signed off. Add a line to the contributing/release notes making a CHANGELOG entry mandatory for any future phase change.

### Effort Estimate

S (<1d) — four documentation edits; the two compliance documents are short for this data profile, and no code change is required.


### SCALE-001

## Finding: SCALE-001 — Streamable HTTP statt stdio für Cloud-Deployments

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SCALE-001
**PDF-Reference:** Sec 5.1

### Observed Behavior

The transport architecture is right, but the cloud endpoint does not answer `initialize` when reached under the hostname the deployment actually uses.

- Transport is selectable, not hardcoded to stdio: `--http` switches to Streamable HTTP served by uvicorn, otherwise `mcp.run()` (stdio) — `src/swisstopo_mcp/server.py:686-701`. Host and port come from pydantic-settings env vars `SWISSTOPO_HTTP_HOST` / `SWISSTOPO_HTTP_PORT` (`src/swisstopo_mcp/config.py:22-24`), with `--port` as an override (`src/swisstopo_mcp/server.py:693-694`).
- The container/cloud path selects HTTP explicitly in the image manifest: `CMD ["python", "-m", "swisstopo_mcp.server", "--http", "--port", "8000"]` (`Dockerfile:38`) with `SWISSTOPO_HTTP_HOST=0.0.0.0` set only in the container (`Dockerfile:24-26`); `deploy/kubernetes.yaml:38-45` exposes containerPort 8000 and re-sets the env var. No stdio in the cloud path.
- No legacy WebSocket transport anywhere: a grep for `websocket` / `ws://` / `wss://` across `src/` returns nothing; the app is built from `mcp.streamable_http_app()` (`src/swisstopo_mcp/server.py:674`).
- **Runtime (Modus 2), localhost:** the HTTP endpoint works when reached with a localhost `Host` header. `POST /mcp` initialize returns HTTP 200 with a full capabilities/serverInfo response (`serverInfo` `swisstopo_mcp`, `protocolVersion` `2025-06-18`) and an `mcp-session-id` header; `GET /healthz` returns 200 `{"status":"ok"}` (`src/swisstopo_mcp/server.py:671-675`).
- **Runtime defect (reproduced against a running instance):** started with `SWISSTOPO_HTTP_HOST=0.0.0.0` and called as `POST /mcp` with `Host: swisstopo-mcp.example.com` — the hostname `deploy/ingress-sticky-sessions.yaml` forwards — the server returns **HTTP 421 "Invalid Host header"**, while `GET /healthz` with the same `Host` still returns **HTTP 200**.

Root cause is identical to SDK-004: `transport_security` is never passed to `FastMCP(...)` (`src/swisstopo_mcp/server.py:42-44`; the identifier appears nowhere in the repository). mcp 1.28.1 therefore auto-pins `allowed_hosts` to `[127.0.0.1:*, localhost:*, [::1]:*]` because FastMCP's internal host stays `127.0.0.1` (`mcp/server/fastmcp/server.py:177-183`), regardless of the uvicorn bind address.

Secondary observations:

- Transport selection is by CLI flag (`--http`), not by an env var such as `MCP_TRANSPORT`. Acceptable, since the deployment manifest sets it explicitly (`Dockerfile:38`), but the transport cannot be switched by env alone in a K8s Deployment without overriding the command.
- No deployment-level smoke test asserts that `initialize` returns 200 through the public hostname.

### Expected Behavior

Per the check's Pass Criteria:

- Env-based transport selection covering stdio and streamable-http/sse
- The cloud deployment uses streamable-http or sse, not stdio
- No WebSocket implementation remains in the code
- **The cloud endpoint answers `initialize` with HTTP 200** — the criterion that fails here, since it must hold for requests carrying the deployment's real hostname, not only for `Host: 127.0.0.1`

### Evidence

- File: `src/swisstopo_mcp/server.py:42-44` — `FastMCP(...)` constructed without `transport_security=`.
- File: `src/swisstopo_mcp/server.py:686-701` — `--http` / uvicorn vs `mcp.run()` transport selection.
- File: `Dockerfile:38` and `Dockerfile:24-26` — cloud path pins `--http --port 8000` with `SWISSTOPO_HTTP_HOST=0.0.0.0`.
- File: `deploy/kubernetes.yaml:38-45` (containerPort/env), `deploy/kubernetes.yaml:49-60` (liveness/readiness probes on `/healthz`).
- File: `deploy/ingress-sticky-sessions.yaml` — routes MCP traffic with `Host: swisstopo-mcp.example.com`.
- Upstream: mcp 1.28.1 `mcp/server/fastmcp/server.py:177-183` — auto-derived localhost-only `allowed_hosts`.
- Runtime probe (auditor, Modus 2):
  ```
  POST /mcp     Host: 127.0.0.1:8000                -> HTTP 200 + mcp-session-id
  POST /mcp     Host: swisstopo-mcp.example.com     -> HTTP 421 "Invalid Host header"
  GET  /healthz Host: swisstopo-mcp.example.com     -> HTTP 200 {"status":"ok"}
  ```

### Risk Description

As shipped, `deploy/kubernetes.yaml` + `deploy/ingress-sticky-sessions.yaml` route MCP traffic with `Host: swisstopo-mcp.example.com`, so **every MCP request receives HTTP 421** — while liveness and readiness probes (`deploy/kubernetes.yaml:49-60`, path `/healthz`) stay green, because `/healthz` is mounted outside the MCP app (`src/swisstopo_mcp/server.py:671-675`) and is not host-validated.

That is a silent-failure deployment, precisely the failure mode SCALE-001 names: "Server startet, Health-Check grün, aber Client-Verbindungen schlagen fehl." Concretely:

- Kubernetes reports the Deployment as healthy and available; no alert fires, no restart happens, no pod is marked unready.
- 100 % of client traffic fails with a status code (421) that most MCP clients surface as an opaque connection error, not as a misconfiguration hint.
- Rollouts and autoscaling proceed normally on a service that answers nothing, so the outage can persist indefinitely until a human tries the endpoint by hand.

Together with the SDK-004 origin rejection, the HTTP transport as shipped is reachable only from localhost.

### Remediation

Same single fix as SDK-004 — pass `TransportSecuritySettings` to `FastMCP` with the deployment's hostnames and origins.

1. `src/swisstopo_mcp/config.py`: add `allowed_hosts: str = ""` plus an `allowed_hosts_list` property mirroring `origins_list`, driven by `SWISSTOPO_ALLOWED_HOSTS`.
2. `src/swisstopo_mcp/server.py:42-44`:

   ```diff
   + from mcp.server.transport_security import TransportSecuritySettings
   +
     mcp = FastMCP(
         "swisstopo_mcp",
         lifespan=lifespan,
   +     transport_security=TransportSecuritySettings(
   +         enable_dns_rebinding_protection=True,
   +         allowed_hosts=settings.allowed_hosts_list,
   +         allowed_origins=settings.origins_list,
   +     ),
         instructions=(...),
     )
   ```

   Keep the localhost defaults in the list so the local `--http` workflow is unaffected, and keep DNS-rebinding protection on (SEC-005).
3. `deploy/kubernetes.yaml:39-44`: add `SWISSTOPO_ALLOWED_HOSTS` with the ingress hostname from `deploy/ingress-sticky-sessions.yaml`; document the variable in `.env.example` and `docs/deployment.md` as a mandatory setting for any non-localhost deployment.
4. Make the health probe meaningful: either point the readiness probe at a path inside the MCP app, or add a startup smoke check (a script in `deploy/` or a CI job) that issues `POST /mcp` `initialize` with `Host: <public hostname>` and fails on anything other than HTTP 200. Without this, the next host-validation regression is again invisible.
5. Optional, addressing the secondary gap: honour a `SWISSTOPO_TRANSPORT` env var alongside `--http` in `src/swisstopo_mcp/server.py:686-701` so the transport can be switched in a Deployment without overriding `command`.

### Effort Estimate

S (<1d) — one constructor argument and one env var; the deployment smoke test adds a few hours.


### SCALE-003

## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SCALE-003
**PDF-Reference:** Sec 5.2

### Observed Behavior

The correct header-based routing pattern is documented in the repo, but only as a comment; the one manifest that can actually be applied routes by cookie instead of by `Mcp-Session-Id`.

- Header-based routing is specified with the right primitives: an HAProxy backend with `stick on req.hdr(Mcp-Session-Id)` over a `stick-table type string len 64 size 100k expire 1h` — `deploy/ingress-sticky-sessions.yaml:11-18`. Capacity (100k sessions) and TTL (1h) both meet the pass criteria.
- **That HAProxy block is a YAML comment, not deployable configuration:** lines `deploy/ingress-sticky-sessions.yaml:11-18` are all `#`-prefixed. No `haproxy.cfg` or `nginx.conf` exists in the repo (searched for `haproxy.cfg` / `nginx.conf` / `ingress*.yaml` — only `deploy/ingress-sticky-sessions.yaml` is present).
- **The only executable manifest in the file is Option B, NGINX Ingress cookie affinity** (`deploy/ingress-sticky-sessions.yaml:28-49`). It does not read `Mcp-Session-Id` at all; the file itself states "NGINX cannot stick on an arbitrary request header, so it pins clients with an affinity cookie instead" (`deploy/ingress-sticky-sessions.yaml:23-25`). It also omits `nginx.ingress.kubernetes.io/upstream-hash-by: "$http_mcp_session_id"`, which the check's own remediation snippet prescribes.
- **Nothing in the repo applies any of it by default:** `deploy/kubernetes.yaml:18` ships `replicas: 1` and `deploy/kubernetes.yaml:76-86` a plain ClusterIP Service with no `sessionAffinity`; the ingress file is explicitly conditional ("Apply ONE of these alongside deploy/kubernetes.yaml after raising replicas", `deploy/ingress-sticky-sessions.yaml:8`).
- No failover behaviour has been tested or documented — Modus 2 was not run, and nothing in `tests/` or `docs/deployment.md` covers it.

### Expected Behavior

Per the check's Pass Criteria:

- The edge load balancer reads the `Mcp-Session-Id` header explicitly
- Stick-table / hash mechanism with sufficient capacity (≥100k sessions)
- TTL set explicitly, correlated with the session TTL
- Failover behaviour tested: on backend failure a session is not routed to a new backend without shared state

### Evidence

- File: `deploy/ingress-sticky-sessions.yaml:11-18` — the correct HAProxy stick-table config, entirely `#`-commented.
- File: `deploy/ingress-sticky-sessions.yaml:23-25` — explicit statement that the NGINX path cannot stick on the header.
- File: `deploy/ingress-sticky-sessions.yaml:28-49` — the only applicable manifest; cookie affinity, no `upstream-hash-by: "$http_mcp_session_id"`.
- File: `deploy/ingress-sticky-sessions.yaml:8` — the whole file is conditional on raising replicas.
- File: `deploy/kubernetes.yaml:18` — `replicas: 1`.
- File: `deploy/kubernetes.yaml:76-86` — ClusterIP Service without `sessionAffinity`.
- Search: no `haproxy.cfg` and no `nginx.conf` anywhere in the repo.

### Risk Description

The exposure is latent while `replicas: 1`, which is why this is not urgent today. It becomes an outage the moment someone scales out — and scaling out is exactly the operation an operator performs under load, without touching the ingress file:

- MCP clients are predominantly non-browser (Claude Desktop, CLI agents, the stdio-to-HTTP bridges). They have no cookie jar, so the cookie affinity in `deploy/ingress-sticky-sessions.yaml:28-49` does not pin them at all. Requests round-robin across pods, each pod rejects the unknown `Mcp-Session-Id`, and every multi-request conversation breaks mid-flight with errors that look like random flakiness rather than a routing bug.
- The Service has no `sessionAffinity: ClientIP` fallback (`deploy/kubernetes.yaml:76-86`), so there is not even the weaker IP-based affinity behind it — and IP affinity would in any case break behind NAT, the caveat the check calls out.
- The operator's most likely reaction — "apply the sticky-sessions manifest" — installs the cookie variant and does not fix it, because the HAProxy variant that would fix it is a comment.
- Failover is untested, so even with correct sticking there is no evidence about what happens to an in-flight session when a pod is drained during a rolling update.

### Remediation

1. Ship deployable header-based routing, not a comment. In `deploy/`, add a real `haproxy.cfg` (or a HAProxy Ingress `ConfigMap` manifest) containing the block currently commented at `deploy/ingress-sticky-sessions.yaml:11-18`, uncommented and complete:

   ```
   backend mcp_backend
       mode http
       balance roundrobin
       stick-table type string len 64 size 100k expire 1h
       stick on req.hdr(Mcp-Session-Id)
       server mcp1 ... check
       server mcp2 ... check
   ```

   Keep the size/TTL values as they are — they already meet the criteria.
2. If NGINX Ingress must remain an option, fix it rather than leaving it as the only applicable path: add `nginx.ingress.kubernetes.io/upstream-hash-by: "$http_mcp_session_id"` to the annotations at `deploy/ingress-sticky-sessions.yaml:28-49`, and state in the surrounding comment that cookie affinity alone is insufficient for non-browser MCP clients.
3. Add a fallback at the Service layer: set `sessionAffinity: ClientIP` with an explicit `sessionAffinityConfig.clientIP.timeoutSeconds` in `deploy/kubernetes.yaml:76-86`, documented as a partial mitigation that does not survive NAT.
4. Gate scale-out on this: in `docs/deployment.md`, state that raising `replicas` above 1 requires the header-based routing manifest, and add the failover procedure — drain a pod while a session is active and record the observed client behaviour — as a documented pre-scale-out test.
5. Re-run the check's Modus 2 probe after step 1: hold one `Mcp-Session-Id` across five requests and assert all five reach the same pod.

### Effort Estimate

M (1-3d) — the config itself is small; the failover test and the deployment documentation are the bulk.


### SDK-002

## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SDK-002
**PDF-Reference:** Sec 3.1

### Observed Behavior

Every MCP-visible tool return is a structured, schema-exposed Pydantic v2 envelope, confirmed at runtime — but four inner handlers misstate their return type.

What is in place:

- All 23 registered tools annotate `-> ToolResponse`, including the three new REST tools (`src/swisstopo_mcp/server.py:358` `zoning_at`, `:381` `municipality_at`, `:403` `layer_info`) and the new coords tool (`src/swisstopo_mcp/server.py:432` `convert_coordinates`).
- Runtime verification against the live server object: `mcp.list_tools()` returns 23 tools and every one carries a non-null `outputSchema` — the `ToolResponse` envelope (`summary` / `results` / `count` / `match_type` / `source` / `license` / `provenance` / `retrieved_at` / `is_error`). No tool falls back to an unschema'd dict.
- The envelope satisfies the structural criteria: `Literal` types for enumerables (`Provenance` / `MatchType` at `src/swisstopo_mcp/models.py:15-16`), `Field(default_factory=list)` for `results` (`src/swisstopo_mcp/models.py:63-65`), `extra="forbid"` (`src/swisstopo_mcp/models.py:60`), and `ok()` / `error()` constructors that always set `count` consistently (`src/swisstopo_mcp/models.py:76-100`).
- Pydantic ≥ 2 is a hard dependency (`pyproject.toml:38` `"pydantic>=2.0.0"`) and v2-only APIs are used throughout (`ConfigDict`, `model_validator(mode="after")` — e.g. `src/swisstopo_mcp/coords.py:19, :110, :202`); no v1 syntax (`.parse_obj` / `class Config`) anywhere in `src/`.

What fails:

- **Four inner handlers in `src/swisstopo_mcp/rest_api.py` declare `-> str` but return `ToolResponse` objects on every path:** `search_layers` (`src/swisstopo_mcp/rest_api.py:289`, returns `ToolResponse` at `:302` and `:308`), `identify_features` (`:312`, returns at `:330` / `:336`), `find_features` (`:340`, returns at `:353` / `:359`), `get_feature` (`:363`, returns at `:372` / `:378`). The new handlers in the same file are correct (`zoning_at` `src/swisstopo_mcp/rest_api.py:406`, `municipality_at` `:436`, `layer_info` `:471`, all `-> ToolResponse`), so the file is internally inconsistent.
- **No static type checker is configured** to catch this class of drift: `pyproject.toml:65-78` enables ruff with `select = [E, F, W, I, UP]` only — no mypy or pyright in the dependencies or in `.github/workflows/ci.yml`.

### Expected Behavior

Per the check's Pass Criteria:

- Pydantic ≥ 2.0 in the dependencies
- Tools have explicit return annotations (BaseModel / TypedDict / dataclass) — and those annotations must state the type actually returned
- Search/list tools use a consistent response envelope with `source`, `provenance`, `results`, `count`
- Pydantic fields use `Field(default=...)` / `Field(default_factory=...)` for defaults
- `Literal` types for enumerable values instead of bare `str`

### Evidence

- File: `src/swisstopo_mcp/rest_api.py:289` — `async def search_layers(...) -> str:` while returning `ToolResponse` at `:302` and `:308`.
- File: `src/swisstopo_mcp/rest_api.py:312` (returns at `:330`, `:336`), `:340` (returns at `:353`, `:359`), `:363` (returns at `:372`, `:378`) — same defect.
- Counter-example in the same file: `src/swisstopo_mcp/rest_api.py:406`, `:436`, `:471` — correct `-> ToolResponse`.
- File: `src/swisstopo_mcp/models.py:15-16, 60, 63-65, 76-100` — envelope definition, `extra="forbid"`, constructors.
- File: `pyproject.toml:38` — `pydantic>=2.0.0`; `pyproject.toml:65-78` — ruff with `select = [E, F, W, I, UP]`, no type checker.
- Runtime: `mcp.list_tools()` → 23 tools, all with a non-null `outputSchema`.

### Risk Description

The client-facing schema is unaffected today, because FastMCP derives the `outputSchema` from the decorated wrappers in `src/swisstopo_mcp/server.py`, not from the inner handlers — this was verified at runtime. The damage is therefore to type-correctness and reviewability, and it is a live trap rather than an abstract one:

- The annotations are simply wrong and would fail any mypy or pyright gate, which is a blocker for adding one later — a first type-check run starts with four errors that look like real bugs.
- More concretely: a future contributor reading `-> str` on `src/swisstopo_mcp/rest_api.py:289` may add an early-return `return "no layers found"` on a new branch. That passes ruff, passes review (it matches the declared signature), and silently breaks the envelope contract for that one tool — the client receives a bare string where the schema promises `summary` / `results` / `count` / `source` / `license`, which for this server also means the CH-004 attribution disappears from that path.
- The inconsistency within a single file (`:289/:312/:340/:363` wrong, `:406/:436/:471` right) makes the correct pattern non-obvious to anyone extending `rest_api.py`.

### Remediation

1. Correct the four annotations in `src/swisstopo_mcp/rest_api.py` — a mechanical change on four lines:

   ```diff
   - async def search_layers(...) -> str:          # rest_api.py:289
   + async def search_layers(...) -> ToolResponse:
   - async def identify_features(...) -> str:      # rest_api.py:312
   + async def identify_features(...) -> ToolResponse:
   - async def find_features(...) -> str:          # rest_api.py:340
   + async def find_features(...) -> ToolResponse:
   - async def get_feature(...) -> str:            # rest_api.py:363
   + async def get_feature(...) -> ToolResponse:
   ```

2. Add a static type gate so the drift cannot recur. In `pyproject.toml`, add `mypy` to `[project.optional-dependencies].dev` and a `[tool.mypy]` section scoped to `src/` (start permissive — `check_untyped_defs = true`, `warn_return_any = true` — and tighten later); add a `mypy src/` step to `.github/workflows/ci.yml` next to the existing ruff step.
3. Optional hardening while in the file: a small unit test asserting `isinstance(result, ToolResponse)` for each of the four handlers makes the contract enforced at runtime as well, independent of the type checker.

### Effort Estimate

S (<1d) — four one-line edits; the mypy gate adds a few hours, mostly for the first clean run.


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SDK-003
**PDF-Reference:** Sec 3.1

### Observed Behavior

Context injection now exists for two tools, but the two genuinely slow tools in the surface are not among them, and the one progress call that exists fires after the wait rather than during it.

What is in place:

- Context injection is wired for two tools: `swisstopo_elevation_profile` (`src/swisstopo_mcp/server.py:337` declares `ctx: Context` and forwards it at `:345`) and `swisstopo_get_oereb_extract` (`src/swisstopo_mcp/server.py:484`, forwards at `:491`).
- Those handlers actually use the context rather than merely accepting it: `ctx.info()` at `src/swisstopo_mcp/height.py:179` and `src/swisstopo_mcp/oereb.py:147`, `ctx.report_progress()` at `src/swisstopo_mcp/height.py:204`. This closes the gap the 2026-05-29 audit recorded ("No tool injects `ctx: Context`").
- No `print()` anywhere in `src/`, and structlog is bound to stderr explicitly so stdout stays reserved for the stdio protocol: `src/swisstopo_mcp/logging_config.py:47-48` (`WriteLoggerFactory(file=sys.stderr)`).

What fails:

- **`find_commune` can issue up to 40 sequential upstream requests without any `ctx`:** `_list_by_canton` / `_list_by_district` (`src/swisstopo_mcp/openplz.py:479`, `:501`) call `_fetch_all_pages` (`src/swisstopo_mcp/openplz.py:152-185`), which loops with `pageSize=50` up to `OPENPLZ_MAX_RECORDS=2000` (`src/swisstopo_mcp/openplz.py:48-49`). The tool wrapper takes no `Context` (`src/swisstopo_mcp/server.py:618`), so a multi-second canton listing reports nothing to the client.
- **`query_osm_features` runs against Overpass with a 30 s client timeout and a 25 s server-side timeout hint** (`src/swisstopo_mcp/overpass.py:39-40`, request at `:164`) and also takes no `Context` (`src/swisstopo_mcp/server.py:561`). This is the single slowest tool in the surface and the most likely to hit a client-side timeout with no progress signal.
- **The one progress call fires after the wait:** `elevation_profile` reports progress only once, after the upstream call has already returned (`progress=1, total=1` at `src/swisstopo_mcp/height.py:204`). That is a completion marker, not the 1-2 s cadence the pass criteria ask for; the actual wait — the profile request — is unreported.
- **A swallowed upstream failure is not surfaced via `ctx.warning()`:** `layer_info` catches the legend fetch exception bare and sets `legend=None` (`src/swisstopo_mcp/rest_api.py:494-501`). The null is visible in the result, but the reason for it never reaches the client.
- Not counted against the status: the new tools added since the last audit (`convert_coordinates`, `zoning_at`, `municipality_at`) take no `ctx`, which is acceptable — each is a single fast upstream call (`src/swisstopo_mcp/coords.py:269`, `src/swisstopo_mcp/rest_api.py:387`).

### Expected Behavior

Per the check's Pass Criteria:

- Tools with an expected runtime > 2 s declare a `ctx: Context` parameter
- Long-running tools call `ctx.report_progress()` at least every 1-2 seconds
- Error cases that do not become the tool result are logged via `ctx.warning()` / `ctx.error()` instead of being swallowed silently
- Log statements in tool bodies use `ctx.info()` rather than `print()` or the stdlib logger (critical for stdio servers)

### Evidence

- File: `src/swisstopo_mcp/server.py:618` — `find_commune` wrapper, no `ctx` parameter.
- File: `src/swisstopo_mcp/openplz.py:479, :501` → `_fetch_all_pages` at `:152-185`, paging with `pageSize=50` up to `OPENPLZ_MAX_RECORDS=2000` (`:48-49`) — up to 40 sequential requests.
- File: `src/swisstopo_mcp/server.py:561` — `query_osm_features` wrapper, no `ctx`.
- File: `src/swisstopo_mcp/overpass.py:39-40` (30 s client / 25 s server timeout), request at `:164`.
- File: `src/swisstopo_mcp/height.py:204` — `report_progress(progress=1, total=1)` after the upstream call returned.
- File: `src/swisstopo_mcp/rest_api.py:494-501` — bare `except`, `legend=None`, no `ctx.warning()`.
- Positive: `src/swisstopo_mcp/server.py:337, :345, :484, :491`; `src/swisstopo_mcp/height.py:179`; `src/swisstopo_mcp/oereb.py:147`.
- File: `src/swisstopo_mcp/logging_config.py:47-48` — stderr-bound structlog, no `print()` in `src/`.

### Risk Description

The two tools without context are precisely the two that keep the client waiting:

- A canton-wide `find_commune` listing performs up to 40 sequential paged requests (`src/swisstopo_mcp/openplz.py:152-185`) against `openplzapi.org`, a third-party endpoint with known transient slowness. From the client's perspective the tool call is indistinguishable from a hang, so the model or the user cancels or retries — and a retry restarts the whole 40-request walk, doubling load on the upstream.
- `query_osm_features` can legitimately take close to its 30 s client timeout (`src/swisstopo_mcp/overpass.py:39-40`). Several MCP hosts apply their own shorter tool-call timeout; with no progress notification there is nothing to keep the call alive or to explain the wait, so a legitimate slow query is reported to the user as a failure.
- The swallowed legend error at `src/swisstopo_mcp/rest_api.py:494-501` is the more insidious case: `legend=None` is a valid-looking value, so the model will report to the user that the layer has no legend, when in fact the legend fetch failed. Nothing in the response or the client-visible log distinguishes "no legend exists" from "we could not retrieve it".

### Remediation

1. Add `ctx: Context` to the two slow tool wrappers and forward it:
   - `src/swisstopo_mcp/server.py:618` (`find_commune`) → forward to `_list_by_canton` / `_list_by_district` (`src/swisstopo_mcp/openplz.py:479, :501`), and report progress per page inside `_fetch_all_pages` (`src/swisstopo_mcp/openplz.py:152-185`):

     ```python
     if ctx is not None:
         await ctx.report_progress(
             progress=len(records), total=OPENPLZ_MAX_RECORDS,
             message=f"Fetched {len(records)} records (page {page})",
         )
     ```

     Keep `ctx` optional (`ctx: Context | None = None`) on the inner helpers so the existing unit tests continue to call them directly.
   - `src/swisstopo_mcp/server.py:561` (`query_osm_features`) → forward to `src/swisstopo_mcp/overpass.py`; emit `await ctx.info("Querying Overpass (may take up to 30s)…")` and a `report_progress` before the request at `:164`, since a single long request cannot be subdivided.
2. Move the elevation-profile progress signal in front of the wait: in `src/swisstopo_mcp/height.py`, call `ctx.report_progress(progress=0, total=1, message=...)` before the upstream request and keep the existing completion call at `:204`. That gives the client something during the wait rather than only after it.
3. Surface the swallowed legend failure: in `src/swisstopo_mcp/rest_api.py:494-501`, narrow the bare `except` to the expected HTTP/timeout exception types and add `await ctx.warning(f"Legend fetch failed for {layer_id}: {type(exc).__name__}")` (with `ctx` threaded from the `layer_info` wrapper at `src/swisstopo_mcp/server.py:403`), so the client can distinguish "no legend" from "legend unavailable". Keep the message free of upstream response bodies (OBS-002).
4. Extend `tests/test_context.py` with a fake `Context` recording `report_progress` / `warning` calls, asserting that a paged `find_commune` run emits more than one progress event and that a failing legend fetch emits exactly one warning.

### Effort Estimate

S (<1d) — two wrapper signatures, three call sites and one test module; no architectural change.


### SDK-004

## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SDK-004
**PDF-Reference:** Sec 3.1

### Observed Behavior

The CORS layer itself is correct and test-covered, but every cross-origin MCP request from a configured origin is rejected by the SDK's transport-security layer before it ever reaches the CORS-wrapped handler.

- CORS middleware is configured on the Streamable-HTTP app with the critical header exposed: `expose_headers=["Mcp-Session-Id"]` and `allow_headers` including `Mcp-Session-Id` — `src/swisstopo_mcp/server.py:676-682`.
- Origins are never wildcarded: `allow_origins=allowed_origins or []` (`src/swisstopo_mcp/server.py:678`), fed from `SWISSTOPO_ALLOWED_ORIGINS` via pydantic-settings (`src/swisstopo_mcp/config.py:25-31`, passed at `src/swisstopo_mcp/server.py:696`). The default is the empty list, i.e. no cross-origin access unless explicitly configured.
- `allow_credentials` is not enabled (absent at `src/swisstopo_mcp/server.py:676-682`), which is correct for `auth_model=none` and avoids the wildcard+credentials CORS violation.
- Regression tests assert the configuration: `tests/test_http_app.py:19-33` check `expose_headers`, `allow_headers`, the explicit origin list and the no-origins default.
- **Runtime defect (reproduced against a running instance):** `POST /mcp` with `Origin: https://client.example.com` — an origin explicitly configured via `SWISSTOPO_ALLOWED_ORIGINS` — returns **HTTP 403 "Invalid Origin header"**. The response still carries `access-control-expose-headers: Mcp-Session-Id`, so CORS is fine; the request is killed one layer earlier. The preflight is also fine: `OPTIONS /mcp` with the same Origin returns HTTP 200 with `access-control-allow-origin: https://client.example.com`, `access-control-allow-methods: GET, POST, OPTIONS` and `access-control-allow-headers` including `Mcp-Session-Id`. A `POST` without any `Origin` header returns HTTP 200 plus an `mcp-session-id` header, so the session mechanism itself works.

Root cause: `transport_security` is never passed to `FastMCP(...)` at `src/swisstopo_mcp/server.py:42-44`. A grep for `transport_security` / `TransportSecuritySettings` across `src/`, `tests/` and `docs/` returns nothing — the identifier does not appear anywhere in the repository. mcp 1.28.1 therefore auto-enables DNS-rebinding protection with a localhost-only allow-list derived from the server's internal host, which stays `127.0.0.1` (`mcp/server/fastmcp/server.py:177-183`): `allowed_origins = [http://127.0.0.1:*, http://localhost:*, http://[::1]:*]`.

`SWISSTOPO_ALLOWED_ORIGINS` therefore reaches `CORSMiddleware` only. This is the exact "CORS looks right, browser client still breaks" symptom SDK-004 exists to prevent, only moved one layer down. See SCALE-001 for the matching `Host`-header failure — both share this single root cause.

### Expected Behavior

Per the check's Pass Criteria:

- CORS middleware configured while HTTP/SSE transport is active
- `expose_headers` contains `Mcp-Session-Id`
- `allow_headers` contains `Mcp-Session-Id` for follow-up requests
- `allow_origins` is an explicit list in production, never a wildcard
- Runtime (Modus 2): a cross-origin `POST /mcp` carrying `Origin: <configured origin>` returns `Access-Control-Allow-Origin`, `Access-Control-Expose-Headers: Mcp-Session-Id` **and a usable `Mcp-Session-Id`** — i.e. a browser client can complete a session, not merely pass the preflight.

### Evidence

- File: `src/swisstopo_mcp/server.py:42-44` — `FastMCP("swisstopo_mcp", lifespan=lifespan, instructions=...)`; no `transport_security=` argument.
- File: `src/swisstopo_mcp/server.py:676-682` — CORS middleware with `expose_headers=["Mcp-Session-Id"]` (correct).
- File: `src/swisstopo_mcp/config.py:25-31` — `allowed_origins` / `origins_list`, consumed only by `CORSMiddleware` at `src/swisstopo_mcp/server.py:696`.
- File: `tests/test_http_app.py:19-33` — asserts middleware kwargs only; no test issues a real cross-origin `POST`, which is why the 403 was invisible to CI.
- Upstream: mcp 1.28.1 `mcp/server/fastmcp/server.py:177-183` — auto-derived localhost-only origin allow-list when the internal host is `127.0.0.1`.
- Runtime probe (auditor, Modus 2):
  ```
  OPTIONS /mcp  Origin: https://client.example.com  -> HTTP 200
                access-control-allow-origin: https://client.example.com
                access-control-allow-headers: ... Mcp-Session-Id
  POST    /mcp  Origin: https://client.example.com  -> HTTP 403 "Invalid Origin header"
  POST    /mcp  (no Origin)                         -> HTTP 200 + mcp-session-id
  ```

### Risk Description

Any browser-based MCP client hosted on a domain other than the server's is unusable, in **every configuration a deployment can reach** — there is no value of `SWISSTOPO_ALLOWED_ORIGINS` that fixes it, because that variable never reaches the layer doing the rejecting. The failure is maximally hard to diagnose:

- Local stdio tests pass, server-side curl without `Origin` passes, the CORS preflight passes and the unit tests pass. Only the real browser request fails.
- The 403 body says "Invalid Origin header" while the response headers say the origin *is* allowed, so the operator's first move — widening `SWISSTOPO_ALLOWED_ORIGINS` — has no effect and will be repeated for a long time before the SDK layer is suspected.
- Combined with SCALE-001 (HTTP 421 on the deployment's real `Host`), the HTTP transport as shipped serves no client other than one on localhost, while `/healthz` stays green.

### Remediation

Pass an explicit `TransportSecuritySettings` into `FastMCP` so the deployment's origins and hostnames are honoured by the SDK's `TransportSecurityMiddleware`, not just by CORS. Single fix, shared with SCALE-001.

1. `src/swisstopo_mcp/config.py`: add an `allowed_hosts: str = ""` setting with an `allowed_hosts_list` property mirroring `origins_list`, so the deployment hostname is configurable (`SWISSTOPO_ALLOWED_HOSTS`).
2. `src/swisstopo_mcp/server.py:42-44`: construct `FastMCP` with the transport-security settings.

   ```diff
   + from mcp.server.transport_security import TransportSecuritySettings
   +
     mcp = FastMCP(
         "swisstopo_mcp",
         lifespan=lifespan,
   +     transport_security=TransportSecuritySettings(
   +         enable_dns_rebinding_protection=True,
   +         allowed_origins=settings.origins_list,
   +         allowed_hosts=settings.allowed_hosts_list,
   +     ),
         instructions=(...),
     )
   ```

   Keep DNS-rebinding protection enabled (SEC-005 depends on it) — the fix is to feed it the right lists, never to disable it. Retain the localhost entries as defaults so the local `--http` workflow keeps working.
3. `deploy/kubernetes.yaml`: add `SWISSTOPO_ALLOWED_HOSTS=swisstopo-mcp.example.com` next to the existing `SWISSTOPO_ALLOWED_ORIGINS` env var, and document both in `.env.example` and `docs/deployment.md`.
4. `tests/test_http_app.py`: replace the kwargs-inspection-only coverage with an end-to-end test using `httpx.ASGITransport` that issues a real `POST /mcp` initialize with `Origin: https://client.example.com` against an app built with that origin configured, asserting HTTP 200 and a returned `mcp-session-id`. Add the negative case (an unconfigured origin still yields 403).

### Effort Estimate

S (<1d) — one constructor argument, one settings field, one deployment env var, plus the end-to-end regression test that would have caught it.


### SEC-004

## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

**Severity:** critical
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-004
**PDF-Reference:** Sec 4.4

### Observed Behavior
The structural SSRF surface is closed: no tool accepts a user-supplied URL, every upstream base is a module constant (`src/swisstopo_mcp/api_client.py:16-22`) or a fixed cantonal registry entry (`src/swisstopo_mcp/oereb.py:25-28`), the host allow-list is a frozenset of 10 hosts checked before every request (`src/swisstopo_mcp/api_client.py:51-64`, `api_client.py:67-74`, called at `api_client.py:162-163`), and redirects are disabled (`src/swisstopo_mcp/api_client.py:90-94`).

Three explicit Pass-Criteria remain unmet at the code layer:

1. **No HTTPS scheme enforcement.** `assert_host_allowed` inspects only `urlparse(url).hostname` (`src/swisstopo_mcp/api_client.py:69`); an `http://` URL to an allow-listed host passes. This is reachable: `src/swisstopo_mcp/geodata.py:447` builds `coll_url` from `ogc_base`, a value read out of the upstream geodienste.ch catalogue response (`src/swisstopo_mcp/geodata.py:96-104`, `:113`), and `src/swisstopo_mcp/geodata.py:464` does the same for `items_url`. The scheme of those two URLs is upstream-influenced, not fixed by this repo.
2. **No resolved-IP blocklist anywhere in the code layer.** A grep for `getaddrinfo|ipaddress|socket\.|proxy` over `src/` returns zero hits — no DNS resolution plus `ip_network` membership check, no egress proxy.
3. **IPv6 is uncovered.** The NetworkPolicy `except` list at `deploy/kubernetes.yaml:104-108` contains IPv4 CIDRs only; `::1/128` and `fe80::/10` are not excluded and there is no IPv6 `ipBlock` rule.

The `169.254.169.254` defence therefore exists only in the Kubernetes NetworkPolicy (`deploy/kubernetes.yaml:100-111`, TCP/443 only, RFC1918 plus `169.254.0.0/16` excluded) and does not apply to local-stdio or plain `docker run` deployments.

### Expected Behavior
- HTTPS scheme validated before every outbound request
- Resolved IP checked against a private / link-local / loopback blocklist
- DNS resolved once and the resolved IP used for the request (no TOCTOU)
- `169.254.169.254` explicitly blocked
- IPv6 loopback (`::1`) and link-local (`fe80::/10`) blocked
- In production: an egress proxy (Smokescreen or equivalent) as defence-in-depth

### Evidence
- Allow-list and pre-request check: `src/swisstopo_mcp/api_client.py:51-64` (ALLOWED_HOSTS), `api_client.py:67-74` (assert_host_allowed), `api_client.py:162-163` (call site in `request_with_retry`)
- Direct client calls that bypass `request_with_retry` still assert first: `src/swisstopo_mcp/oereb.py:98`, `src/swisstopo_mcp/oereb.py:161`
- Redirects disabled: `src/swisstopo_mcp/api_client.py:90-94`
- Network-layer blocklist (containerised deployment only): `deploy/kubernetes.yaml:100-111`
- Regression test asserts rejection of `169.254.169.254`, `localhost` and a suffix-trick host: `tests/test_egress_allowlist.py:27-38`

Gaps:
- HTTPS scheme is never validated before an outbound request (`src/swisstopo_mcp/api_client.py:67-74`)
- Attacker-influenced scheme reaches the request builder at `src/swisstopo_mcp/geodata.py:447` and `:464`, sourced from the upstream catalogue at `src/swisstopo_mcp/geodata.py:96-104`
- No resolved-IP range check at the code layer; `169.254.169.254` is blocked only by `deploy/kubernetes.yaml:104-108`
- IPv6 loopback and link-local are blocked at no layer
- No egress proxy

### Risk Description
A compromised or spoofed geodienste.ch catalogue response can downgrade two live request URLs to `http://`, because `geodata.py` takes both scheme and path from that payload and `assert_host_allowed` only inspects the hostname. Plaintext HTTP on the wire removes certificate validation, so an on-path attacker between the server and an allow-listed host can inject arbitrary geodata content that the LLM will present as authoritative Swiss federal data.

Separately, for the two deployment modes that are actually the default here — local stdio and plain `docker run` — there is no metadata-IP defence at all. The NetworkPolicy that carries the whole IP-blocklisting criterion applies only to the Kubernetes deployment. If any allow-listed hostname ever resolves into a private or link-local range (DNS compromise, a poisoned `/etc/hosts` on a developer machine, a hostile split-horizon resolver), the request goes through unchallenged. This server holds no credentials of its own, so the immediate loss is not token theft but internal reachability from a process that is generally trusted to only talk to public geodata endpoints.

### Remediation
1. In `src/swisstopo_mcp/api_client.py`, extend `assert_host_allowed` to validate the scheme in the same place the hostname is validated:

```python
def assert_host_allowed(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise PermissionError(f"Non-HTTPS egress blocked: {parsed.scheme}://{parsed.hostname}")
    if parsed.hostname not in ALLOWED_HOSTS:
        raise PermissionError(f"Host not on egress allow-list: {parsed.hostname}")
```

2. Add a resolved-IP guard in the same module, called from `assert_host_allowed`, so it covers every call path including the two direct-client sites in `oereb.py`:

```python
import ipaddress, socket

_BLOCKED_NETS = [
    ipaddress.ip_network(n) for n in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
        "127.0.0.0/8", "169.254.0.0/16",
        "::1/128", "fe80::/10", "fc00::/7",
    )
]

def assert_resolved_ip_public(hostname: str) -> None:
    for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP):
        ip = ipaddress.ip_address(sockaddr[0])
        if any(ip in net for net in _BLOCKED_NETS):
            raise PermissionError(f"Host {hostname} resolves to blocked address {ip}")
```

3. Add the IPv6 exclusions to `deploy/kubernetes.yaml:104-108` — an `ipBlock` for `::/0` with `except: ["::1/128", "fe80::/10", "fc00::/7"]` alongside the existing IPv4 rule.
4. Extend `tests/test_egress_allowlist.py` with two cases: `http://api3.geo.admin.ch/...` must raise `PermissionError`, and a monkeypatched `getaddrinfo` returning `169.254.169.254` for an allow-listed host must raise.
5. Optional defence-in-depth: document an egress-proxy deployment option in `docs/network-egress.md` for operators who run this outside Kubernetes.

Note that step 2 alone does not close the TOCTOU window — that is tracked separately as SEC-005. Steps 1 and 3 are unconditional wins and should not wait for it.

### Effort Estimate
S (<1d)


### SEC-005

## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-005
**PDF-Reference:** Sec 4.4

### Observed Behavior
No DNS pinning of any kind exists. A grep for `getaddrinfo|gethostbyname|dns\.resolve|sni_hostname|SSLContext` over `src/` returns zero hits. Requests are issued with the hostname URL (`src/swisstopo_mcp/api_client.py:171-175`), so httpx performs its own resolution at connect time; there is no resolve-once-then-pin path, no custom transport and no egress proxy — the shared client is built with only `timeout`, `User-Agent` and `follow_redirects` (`src/swisstopo_mcp/api_client.py:88-94`).

`SECURITY.md:25` claims `follow_redirects=False ... (SEC-005)`. That attribution is wrong: redirect suppression (`src/swisstopo_mcp/api_client.py:93`) prevents redirect-based host switching, which is a SEC-004 concern. It gives no protection against a TOCTOU rebind of an already-allow-listed hostname, so a future reviewer reading SECURITY.md will conclude this check is handled when it is not.

Two real compensating controls do exist. The reachable hostname set is a fixed frozenset of federal and cantonal domains (`src/swisstopo_mcp/api_client.py:51-64`), so rebinding requires DNS control over `geo.admin.ch` or a cantonal OEREB domain. And in the Kubernetes deployment a rebind to a private or link-local address is dropped at the network layer (`deploy/kubernetes.yaml:100-111`). TLS certificate verification is left at the httpx default — no `verify=False` anywhere in `src/` — so a rebound connection would additionally fail hostname validation for an attacker without a valid certificate.

### Expected Behavior
- DNS resolution happens once, before the HTTP request
- The resolved IP is used for the TCP connection (pinned URL or custom resolver)
- The original hostname is preserved via the `Host` header and SNI for the TLS handshake
- Certificate validation runs against the original hostname, not the IP
- Tests verify exactly one DNS lookup per request

### Evidence
- No pinning primitives anywhere: grep for `getaddrinfo|gethostbyname|dns\.resolve|sni_hostname|SSLContext` over `src/` returns zero hits
- Requests issued against the hostname URL: `src/swisstopo_mcp/api_client.py:171-175`
- Client construction with no custom transport and no `proxy=`: `src/swisstopo_mcp/api_client.py:88-94`; no Smokescreen sidecar in `Dockerfile` or `deploy/kubernetes.yaml`
- No resolver is mocked in `tests/`; network tests use respx transport mocking (`tests/test_coords.py:116`, `tests/test_lv95_input.py`), which never exercises resolution
- Mislabelled control: `SECURITY.md:25` attributes SEC-005 to `follow_redirects=False` (`src/swisstopo_mcp/api_client.py:93`)
- Compensating controls: fixed host frozenset `src/swisstopo_mcp/api_client.py:51-64`; egress NetworkPolicy `deploy/kubernetes.yaml:100-111`; httpx default certificate verification retained

Gaps:
- DNS resolution is not performed once and pinned; the connect-time lookup is httpx's own
- Original hostname is not carried via explicit `Host` header / SNI, because no pinning exists to require it
- No regression test proving one resolution per request
- The compensating network-layer control is absent for local-stdio and plain `docker run` modes

### Risk Description
The exploit path is narrow but real. An attacker who controls DNS answers for an allow-listed domain — a hostile or compromised resolver on the host, a poisoned upstream cache, or a developer machine on an untrusted network — can answer the allow-list check with a public address and the connect-time lookup with `127.0.0.1`, `169.254.169.254` or an RFC1918 address. `assert_host_allowed` validated a hostname, not the address the socket actually reaches, so the check passes and the connection targets an internal service.

TLS verification limits what an attacker gains from this: without a valid certificate for `geo.admin.ch`, the handshake fails and the request errors rather than returning attacker-controlled content. So the realistic outcome is a connection attempt to an internal address (a port-probe primitive from a trusted process), not silent data injection. In Kubernetes even that is dropped by the egress policy. In local-stdio and plain-Docker runs — the default modes for this server — nothing stops the connection attempt.

The more immediate operational risk is the mislabelled control. `SECURITY.md:25` states SEC-005 is addressed, which means the gap will not be re-examined by anyone who trusts that file.

### Remediation
1. Correct `SECURITY.md:25` first — this is a five-minute fix and it is the item most likely to cause the gap to persist. Move `follow_redirects=False` under SEC-004 and add an honest SEC-005 row stating that DNS pinning is not implemented, that the reachable host set is a fixed frozenset, and that the network-layer compensation applies to the Kubernetes deployment only.
2. Implement pinning in `src/swisstopo_mcp/api_client.py` as a custom httpx transport that resolves once and reuses the address, keeping SNI and the `Host` header on the original hostname:

```python
class PinnedTransport(httpx.AsyncHTTPTransport):
    async def handle_async_request(self, request):
        host = request.url.host
        ip = await _resolve_once(host)          # single getaddrinfo, blocklist-checked (SEC-004)
        request.extensions["sni_hostname"] = host
        request.headers["Host"] = host
        request.url = request.url.copy_with(host=ip)
        return await super().handle_async_request(request)
```

Wire it in at the client construction site (`src/swisstopo_mcp/api_client.py:88-94`) via `transport=PinnedTransport()`. Certificate validation stays at the httpx default and now validates against `sni_hostname`, i.e. the original hostname.

3. Share the resolver with the SEC-004 blocklist so the single lookup serves both purposes — resolve, range-check, then connect to that exact address. Doing SEC-004 step 2 and this item as one change avoids resolving twice.
4. Add `tests/test_dns_pinning.py`: monkeypatch the resolver with a counter, issue one mocked request through the real transport, and assert the counter is exactly 1. Add a second case where the resolver returns a private address and assert `PermissionError`.
5. Extend `docs/network-egress.md` with a note that DNS pinning is a code-layer control that applies in all deployment modes, unlike the NetworkPolicy.

### Effort Estimate
M (1-3d)


### SEC-014

## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway-Pattern

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-014
**PDF-Reference:** Sec 5.3

### Observed Behavior
No tool allow-list configuration exists in the repo. `find . -iname '*allowlist*' -o -iname '*tool-policy*' -o -iname '*gateway-config*'` returns nothing, and grep for `allowed_tools|tool_allowlist|whitelist` over `deploy/` and `src/` returns no match. All 23 tools registered in `src/swisstopo_mcp/server.py:87-654` are exposed unconditionally to every caller, and `tools/list` returns the full manifest regardless of who is asking.

There is no server-side role or group check as defence-in-depth either — grep for `group|role|team` combined with check/validate/require over `src/` returns nothing. That is consistent with `auth_model=none`: there are no claims to check against, so a role gate would have nothing to gate on.

This is a documented, reasoned deferral rather than an oversight. `SECURITY.md:52-61` records tool allow-listing as a portfolio/gateway-layer control with an explicit rationale — that it "belongs to the MCP host/gateway that aggregates multiple servers, not to an individual server exposing a fixed, read-only tool set" — and states the residual risk is bounded by the egress allow-list and the read-only tool surface. `SECURITY.md:68-73` names the re-evaluation trigger: "is aggregated behind a shared MCP gateway".

The risk-bounding claims check out. All 23 tools carry `readOnlyHint: true` / `destructiveHint: false` in their annotations (e.g. `src/swisstopo_mcp/server.py:89-95`, `349-357`, `636-643`), and outbound reach is capped by the frozenset at `src/swisstopo_mcp/api_client.py:51-64`.

### Expected Behavior
- In an enterprise context: a tool allow-list per team/role, documented in gateway or server config
- The allow-list is explicitly default-deny — only listed tools are exposed
- Server-side defence-in-depth: a group/role check for sensitive tools, complementing the gateway
- Denied tool calls are audited
- The tool list the LLM client sees is filtered per team/role in the `tools/list` response

### Evidence
- No allow-list artefact anywhere: `find . -iname '*allowlist*' -o -iname '*tool-policy*' -o -iname '*gateway-config*'` returns nothing; grep for `allowed_tools|tool_allowlist|whitelist` over `deploy/` and `src/` returns no match
- All 23 tools registered unconditionally: `src/swisstopo_mcp/server.py:87-654`
- No role/group check in `src/`; no `require_group` decorator and no `ctx.user_claims` usage — consistent with `auth_model=none`
- Documented deferral with rationale: `SECURITY.md:52-61`; re-evaluation trigger: `SECURITY.md:68-73`
- Read-only annotations on every tool: `src/swisstopo_mcp/server.py:89-95`, `349-357`, `636-643`
- Egress cap: `src/swisstopo_mcp/api_client.py:51-64`

Gaps:
- No per-team/per-role allow-list documented anywhere (Pass-Criterion 1)
- No default-deny tool exposure — `tools/list` returns the full 23-tool manifest to every caller (Pass-Criteria 2 and 5)
- No server-side group/role check as defence-in-depth (Pass-Criterion 3)
- No audit logging of denied tool calls, because no call can be denied (Pass-Criterion 4)

### Risk Description
This is a documented risk acceptance, not an implemented control, and it should be read that way rather than as a defect in this repo. The check is written for a gateway that fronts multiple servers and needs to decide which team may call which tool. This server exposes a fixed, read-only tool set over Swiss public open data with no authentication, so there is no per-caller identity here to make an allow-list decision against, and no confidential data to withhold from a caller who is not entitled to it.

The residual risk the deferral leaves open is therefore narrow but not zero. Two of the three risks the check names still apply at the portfolio level and none of them can be mitigated inside this repository:

- **Tool-combination compliance.** All 23 tools are individually harmless, but a gateway aggregating this server with a server that has write or send capability creates flows that are only visible at the gateway. Nothing here can see or constrain that.
- **Tool-name shadowing across servers.** Six tools carry no server-identity prefix (see SEC-022), so in a multi-server setup an allow-list keyed on tool name would be ambiguous. That interacts badly with the deferral: the control this server defers to becomes harder to configure correctly because of a defect this server can fix.

What the deferral correctly relies on holds: every tool is read-only and annotated as such, and egress is capped to 10 public geodata hosts. The action for the maintainer is at the portfolio layer.

### Remediation
No code change in this repository is required or appropriate. Concretely:

1. **Keep the deferral, but make it verifiable.** `SECURITY.md:52-61` states the rationale; add a pointer to the two facts it depends on so a future reviewer can confirm them without re-deriving: the read-only annotations (`src/swisstopo_mcp/server.py:89-95` as the representative example) and the egress frozenset (`src/swisstopo_mcp/api_client.py:51-64`). Add a CI test asserting all registered tools have `readOnlyHint: true`, so the deferral's central premise cannot silently become false when a future tool is added.
2. **Fix SEC-022's prefixing**, which is the one part of this problem that lives here. A gateway allow-list is written against tool names; `swisstopo_*` on all 23 tools makes those entries unambiguous.
3. **Track the gateway work at the portfolio level, not as a swisstopo-mcp task.** When a shared MCP gateway is introduced for the Swiss public-data portfolio, that gateway needs a per-team allow-list, default-deny filtering of `tools/list`, and audit logging of denied calls. Record this finding as the input to that work item rather than as an open item against this server.
4. **Re-evaluate on the documented trigger.** `SECURITY.md:68-73` already names it ("is aggregated behind a shared MCP gateway"). Add a second trigger for the case where this server ever gains a non-read-only tool, since that would invalidate the risk-bounding argument the deferral rests on.

### Effort Estimate
S (<1d) for the repository-side items (1, 2 partly overlaps SEC-022, 4). The portfolio gateway itself is out of scope for this server and is not estimated here.


### SEC-015

## Finding: SEC-015 — Pre-Flight Tool-Poisoning Detection

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-015
**PDF-Reference:** Sec 5.3

### Observed Behavior
No pre-flight detection layer exists. Grep for `tool.poisoning|prompt.injection|sanitize.*description|INJECTION_PATTERNS|zero-width|\u200B` over `src/` and `deploy/` returns zero hits; there is no `scan_tool_definition` / `filter_tool_list` equivalent. There are no detection tests — `tests/` contains no poisoning-detection module — and no SIEM alerting: `.github/workflows/security.yml` runs only gitleaks, and no rule or alert threshold for `tool_poisoning_detected` / `tool_poisoning_warning` events exists anywhere in `deploy/` or `docs/`.

As with SEC-014 this is a documented deferral, and here the structural argument is stronger. `SECURITY.md:62-64` records cross-server tool-poisoning detection as a host/gateway responsibility and notes that "this server's tool definitions are version-controlled and shipped from this repository; there is no dynamic or remote tool registration". `SECURITY.md:68-73` lists dynamic/remote tool registration as an explicit re-evaluation trigger.

That argument is verifiable in code: all 23 tool names, descriptions and annotations are static literals in `src/swisstopo_mcp/server.py:87-654`, and there is no registration path that reads a tool definition from a network response or a config file — no `mcp.add_tool` or equivalent dynamic registration call anywhere in `src/`.

### Expected Behavior
- A pre-flight detection layer implemented at the gateway
- At least four pattern classes covered: system prompts, override phrases, invisible characters, homoglyphs
- High-risk tool definitions filtered before forwarding (default-deny)
- Medium-risk definitions passed through but logged
- Audit events to a SIEM with alerting configured
- Tests verifying detection for standard attack patterns

### Evidence
- No detection layer: grep for `tool.poisoning|prompt.injection|sanitize.*description|INJECTION_PATTERNS|zero-width|\u200B` over `src/` and `deploy/` returns zero hits
- No detection tests in `tests/`; `.github/workflows/security.yml` runs gitleaks only; no alert rule in `deploy/` or `docs/`
- Documented deferral with structural justification: `SECURITY.md:62-64`; re-evaluation trigger: `SECURITY.md:68-73`
- The justification is verifiable: all 23 tool names, descriptions and annotations are static literals at `src/swisstopo_mcp/server.py:87-654`; no dynamic or remote registration path exists in `src/`

Gaps:
- No detection layer, so none of the four required pattern classes (system prompts, override phrases, invisible characters, homoglyphs) are covered (Pass-Criteria 1-2)
- No default-deny filtering of high-risk definitions and no logging of medium-risk ones (Pass-Criteria 3-4)
- No audit events to a SIEM and no alerting threshold (Pass-Criterion 5)
- No tests for standard attack patterns (Pass-Criterion 6)
- The German/French injection-pattern extension raised in the check's remediation is unaddressed — relevant for this portfolio since the tool descriptions here are German

### Risk Description
This check targets a gateway that aggregates potentially untrusted servers. swisstopo-mcp is a single leaf server whose own tool definitions are static and version-controlled, which makes it the *subject* of such a scan rather than the place to run one. Running a poisoning detector here would mean scanning its own literals against itself — the definitions it would scan are the ones in its git history, already covered by code review.

So the residual risk is genuinely low for this repository, and the deferral is honest. What remains open, and what the deferral does not eliminate:

- **Nothing scans this server's descriptions before they reach an LLM.** Code review is the only control. The tool descriptions are German prose (`src/swisstopo_mcp/server.py:87-654`), and the check's own remediation notes that standard injection-pattern lists are English-centric. A German override phrase or a zero-width character introduced in a future PR would not be caught by any automated check in this repo, and gitleaks does not look for this class of content.
- **This server cannot protect its users from a sibling server.** If a user runs swisstopo-mcp alongside a poisoned server, that server's descriptions can redirect calls intended for these tools. Six unprefixed tool names (see SEC-022) make this materially easier, since a poisoned definition can claim a name this server also uses.
- **The premise holds only while it holds.** The whole deferral rests on there being no dynamic tool registration. That is true today and nothing in the repo enforces it beyond convention.

### Remediation
The detection layer itself belongs to whatever gateway fronts the portfolio and should not be built into this server. Three repository-side items make the deferral durable rather than merely stated:

1. **Add a self-scan to CI**, not as a gateway substitute but as a guard on this server's own definitions. A test in `tests/` that pulls the registered tool manifest and asserts no description contains invisible characters, homoglyph-substituted ASCII, or override phrases:

```python
INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
OVERRIDE_DE = re.compile(
    r"(ignoriere|missachte|vergiss)\s+(alle\s+)?(vorherigen|bisherigen|obigen)"
    r"|system\s*[-_ ]?prompt|du\s+bist\s+jetzt", re.I)

@pytest.mark.parametrize("tool", TOOLS)
def test_description_is_clean(tool):
    assert not INVISIBLE.search(tool.description)
    assert not OVERRIDE_DE.search(tool.description)
```

   Include German and French patterns, since the descriptions in this portfolio are German — the check's remediation names this explicitly and it is the part most likely to be missed if an off-the-shelf English pattern list is adopted later.

2. **Enforce the deferral's premise.** Add a test asserting the registered tool count and the set of tool names match a committed expectation, so a dynamic-registration path cannot be introduced without a deliberate test update. This pairs naturally with the SEC-022 hash-snapshot work — one manifest snapshot serves both checks.
3. **Sharpen `SECURITY.md:62-64`** to state which control actually covers this server today (code review plus, once item 1 lands, the CI self-scan), rather than leaving the impression that nothing applies until a gateway exists. Keep the existing re-evaluation trigger and add one for the introduction of any config-driven or remotely-sourced tool description.

### Effort Estimate
S (<1d) for the repository-side items. The gateway-side detection layer is out of scope for this server and is not estimated here.


### SEC-018

## Finding: SEC-018 — Input-Validation an Tool-Boundaries (Pydantic strict / Zod)

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-018
**PDF-Reference:** Sec 3 / Sec 4 (Defense-in-Depth)

### Observed Behavior
The tool boundary itself is strict and this was verified at runtime, not only by grep. All 23 tools take a single Pydantic model parameter, and every one of those models declares `model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)` — `geocoding.py:19` and `:41`, `rest_api.py:40`, `:54`, `:75`, `:84`, `:92`, `:96`, `:100`, `stac.py:19` and `:32`, `wmts.py:29`, `height.py:28` and `:42`, `oereb.py:49` and `:61`, `coords.py:181`, `geodata.py:158` and `:199`, `openplz.py:247`, `:257`, `:304`. Whitelist patterns are centralised and positively anchored (`src/swisstopo_mcp/api_client.py:39-43`).

Three deviations keep this off pass:

1. **The shared `SwissPointInput` base model declares no `model_config`** (`src/swisstopo_mcp/coords.py:77-108`). Runtime-verified: `SwissPointInput(lat=47.0, lon=8.0, evil="x")` is accepted, `SwissPointInput(lat="47.0", lon="8.0")` coerces strings to floats, and `SwissPointInput.model_config == {}`. The tool surface is safe today only because all five subclasses re-declare the config (`height.py:28`, `rest_api.py:54`, `:92`, `:96`, `oereb.py:49`).
2. **Three `sr` arguments are unbounded integers forwarded into upstream query params.** `sr: int = Field(default=4326, ...)` with no `ge`/`le`, no `Literal` and no validator at `geocoding.py:36` (GeocodeInput), `geocoding.py:46` (ReverseGeocodeInput) and `rest_api.py:89` (GetFeatureInput); the values reach the upstream request at `geocoding.py:95`, `geocoding.py:132` and `rest_api.py:368`. The helper written for exactly this, `validate_sr()` at `api_client.py:345-352`, is dead code — no call site anywhere in `src/`. By contrast `HeightInput`, `ElevationProfileInput` and `IdentifyInput` do guard `sr` via `check_deprecated_sr` (`height.py:37`, `height.py:71`, `rest_api.py:70`).
3. **Several string fields have no `max_length`.** `IdentifyInput.layers` (`rest_api.py:56-61`) and `FindFeaturesInput.layer` / `search_field` (`rest_api.py:78`, `:80`) carry `min_length` and a pattern but no upper bound, so an arbitrarily long comma-separated layer string passes validation into the upstream query string.

### Expected Behavior
- All tool arguments have schema validation
- Numeric fields carry `ge`/`le` constraints — no unbounded range
- String fields carry `min_length`/`max_length` and ideally a `pattern`
- Patterns are whitelist-based, not blacklist-based
- With Pydantic: `strict=True` and `extra="forbid"` set explicitly
- Validation errors surface as `isError` in the tool result, not as a server crash
- Tests cover edge cases: over-long strings, out-of-range numbers, unknown fields

### Evidence
- Strict config on every tool-boundary model: `geocoding.py:19`, `:41`, `rest_api.py:40`, `:54`, `:75`, `:84`, `:92`, `:96`, `:100`, `stac.py:19`, `:32`, `wmts.py:29`, `height.py:28`, `:42`, `oereb.py:49`, `:61`, `coords.py:181`, `geodata.py:158`, `:199`, `openplz.py:247`, `:257`, `:304`
- Runtime-verified against the installed package: `HeightInput(lat=47.0, lon=8.0, evil='x')` rejected; `HeightInput(lat='47.0', lon='8.0')` rejected; `IdentifyInput(..., evil=1)` rejected; `ConvertCoordinatesInput(easting='8.5', northing='47.4')` rejected
- Centralised whitelist patterns: `src/swisstopo_mcp/api_client.py:39-43` (TEXT_PATTERN, ID_PATTERN, COORDS_PATTERN, LANG_PATTERN, CANTON_PATTERN), applied at `geocoding.py:21-27`, `rest_api.py:42-48`, `rest_api.py:78-81`, `oereb.py:63-73`, `height.py:44-52`
- `ConvertCoordinatesInput` is well bounded: `coords.py:181` plus the range/axis-swap validator at `coords.py:202-227` against `coords.py:48-49`
- Missing config on the shared base: `src/swisstopo_mcp/coords.py:77-108`; runtime-verified `SwissPointInput(lat=47.0, lon=8.0, evil='x')` ACCEPTED and `SwissPointInput.model_config == {}`
- Unbounded `sr`: `geocoding.py:36`, `geocoding.py:46`, `rest_api.py:89`; reaching upstream at `geocoding.py:95`, `geocoding.py:132`, `rest_api.py:368`; unused validator at `api_client.py:345-352`
- Missing `max_length`: `rest_api.py:56-61`, `rest_api.py:78`, `rest_api.py:80`

Gaps:
- `SwissPointInput` (`coords.py:77`) omits `strict=True` / `extra="forbid"`; protection depends entirely on each subclass repeating it
- `GeocodeInput.sr`, `ReverseGeocodeInput.sr` and `GetFeatureInput.sr` are unconstrained ints passed to the upstream API; `validate_sr()` exists but is never called
- Several string fields lack `max_length` (`rest_api.py:56`, `:78`, `:80`)
- `tests/test_input_validation.py` covers patterns, strict mode and extra-field rejection for `GeocodeInput` / `GetFeatureInput` / `GetOerebExtractInput` but has no case asserting `SwissPointInput`'s own config, which is why the omission survived

### Risk Description
No tool is exposed through `SwissPointInput` directly today, so this is a latent regression rather than a live hole — but it is the exact failure mode the check calls out. The next point-based tool added to this server inherits from `SwissPointInput`, and if its author assumes the base class carries the strict config (a reasonable assumption for a shared base model), that tool silently ships with `extra="ignore"` and type coercion. Silent coercion of LLM-supplied strings to floats is the specific case that matters here: an LLM emitting `"47.0"` instead of `47.0` for a coordinate would be accepted rather than corrected, and the coercion has no range awareness — the coordinate-validation logic added at `coords.py:202-227` lives on a sibling model, not on the base.

The unbounded `sr` fields let the LLM forward an arbitrary integer into three upstream geo.admin.ch query strings. The upstream rejects unknown spatial-reference codes, so this is a garbage-in-error-out path rather than an injection vector — but it produces an upstream 4xx surfaced as a tool error instead of a clean local validation message, and it means the `sr=2056` correctness guard that three other tools apply is absent on these three. A purpose-built validator sits unused two files away, so the cost of not fixing this is unusually low-value.

The missing `max_length` on layer strings lets a very long comma-separated value reach the upstream URL. The practical outcome is an upstream 414 or a slow request, not a bypass — but it is unbounded input crossing a trust boundary, which the check requires bounding.

### Remediation
1. In `src/swisstopo_mcp/coords.py`, add the config to the shared base at line 77 so subclasses inherit it rather than each re-declaring it:

```python
class SwissPointInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)
    lat: float = Field(...)
    lon: float = Field(...)
```

The five subclasses (`height.py:28`, `rest_api.py:54`, `:92`, `:96`, `oereb.py:49`) can keep their declarations — Pydantic merges them — but the base must no longer depend on them.

2. Wire up the dead validator. In `geocoding.py:36`, `geocoding.py:46` and `rest_api.py:89`, replace the bare `sr: int = Field(default=4326, ...)` with a constrained field plus the existing helper:

```python
sr: int = Field(default=4326, description="...")

@field_validator("sr")
@classmethod
def _check_sr(cls, v: int) -> int:
    return validate_sr(v)   # api_client.py:345
```

Alternatively use `Literal[2056, 4326, 21781, 3857]` if the accepted set is genuinely closed — but then delete `validate_sr()` rather than leaving it dead.

3. Add `max_length` to `rest_api.py:56-61` (`layers`), `rest_api.py:78` (`layer`) and `rest_api.py:80` (`search_field`). A bound of 512 for the comma-separated `layers` and 128 for the two single-value fields is generous relative to real layer IDs.
4. Extend `tests/test_input_validation.py` with a case that asserts `SwissPointInput.model_config` contains `extra == "forbid"` and `strict is True`, and a case per fixed `sr` field asserting an out-of-set value raises. The base-model case is the one that would have caught this; add it so the next refactor does not reintroduce the gap.

All four items are one-line-to-few-line changes in files that already have the surrounding patterns in place.

### Effort Estimate
S (<1d)


### SEC-021

## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-021
**PDF-Reference:** Anhang B5 + B12

### Observed Behavior
The code layer is solid. `ALLOWED_HOSTS` is a frozenset with an inline comment stating it is deliberately not env-derived so it cannot be silently widened at runtime (`src/swisstopo_mcp/api_client.py:51-64`), including the new REFRAME host at `api_client.py:56`. `assert_host_allowed` (`api_client.py:67-74`) is called before the first attempt in `request_with_retry` (`api_client.py:162-163`), which covers every request helper, and the two handlers that call the client directly assert first (`src/swisstopo_mcp/oereb.py:98`, `:161`). No call site passes `check_host=False`. The new host is documented (`docs/network-egress.md:13`), recorded in the CHANGELOG (`CHANGELOG.md:50`), covered by two tests (`tests/test_egress_allowlist.py:23-48`, `tests/test_coords.py:190-197`), and a 5-step update procedure exists (`docs/network-egress.md:40-49`).

The network layer is where this falls short, in two ways:

1. **The egress documentation contradicts the shipped manifest.** `docs/network-egress.md:34-38` states that "the server runs locally over stdio today and is not cloud-deployed, so no Kubernetes NetworkPolicy / security-group egress rule is shipped. If/when the server is containerised, add a network-layer egress allow-list". But `deploy/kubernetes.yaml:87-118` ships exactly that policy, `docs/deployment.md:5-6` references it as "the network-layer half of SEC-021", and the audit profile records `is_cloud_deployed=true`. A maintainer following the update procedure at `docs/network-egress.md:48` ("only relevant for cloud deployment") would skip updating a policy that exists.
2. **The network-layer control is a CIDR/port policy, not a host allow-list.** `deploy/kubernetes.yaml:101-108` permits TCP/443 to the entire public internet minus private ranges; it does not restrict egress to the 10 hosts in `ALLOWED_HOSTS`. DNS is correctly permitted (`deploy/kubernetes.yaml:112-118`), so that criterion is met, but the policy does not mirror the code-layer list.

Two further documentation defects: `SECURITY.md:24` describes the allow-list as "restricted to `*.geo.admin.ch` and the cantonal OEREB endpoints", stale since `geodienste.ch`, `overpass.osm.ch` and `openplzapi.org` were added (`api_client.py:60-62`); and `assert_host_allowed` checks only the hostname, never the scheme (`api_client.py:69`) — see SEC-004.

### Expected Behavior
- Code-layer allow-list as a `frozenset` in code, not config-mutable
- Network-layer egress control via NetworkPolicy / security group / equivalent
- Allow-list hosts documented in `docs/network-egress.md` or the README
- A pre-request check (`assert_host_allowed`) called before every outbound request
- A documented update procedure for allow-list extensions
- The DNS resolution path explicitly permitted at the network layer

Both layers must hold for this check to pass.

### Evidence
- Frozenset allow-list with anti-widening rationale: `src/swisstopo_mcp/api_client.py:51-64`; REFRAME host at `api_client.py:56`
- Central pre-request enforcement: `api_client.py:67-74`, called at `api_client.py:162-163`; covers `geo_admin_request` (`:194`), `geo_admin_request_text` (`:206`), `reframe_request` (`:221`), `stac_request` (`:229`), `openplz_request` (`:245`), `geodata.py:113`/`:449`/`:464`, `overpass.py:159`; direct-client sites assert first at `src/swisstopo_mcp/oereb.py:98` and `:161`
- Documentation and changelog for the new host: `docs/network-egress.md:13`, `CHANGELOG.md:50`
- Update procedure: `docs/network-egress.md:40-49`
- NetworkPolicy `swisstopo-mcp-egress`: `deploy/kubernetes.yaml:90-118`, with DNS at `deploy/kubernetes.yaml:112-118`
- Tests: `tests/test_egress_allowlist.py:23-25` (parametrised over ALLOWED_HOSTS), `:27-38` (rejects `evil.example.com`, `169.254.169.254`, `api3.geo.admin.ch.evil.com`, `localhost`), `:41-48` (all OEREB_ENDPOINTS hosts on the list); `tests/test_coords.py:190-197` (REFRAME host allowed, suffix-trick rejected)

Gaps:
- `docs/network-egress.md:34-38` claims no NetworkPolicy is shipped while `deploy/kubernetes.yaml:90-118` ships one — stale text contradicting the manifest and the `is_cloud_deployed=true` profile
- The network-layer control is CIDR-based, not host-based; it does not mirror `ALLOWED_HOSTS`
- `SECURITY.md:24` describes the allow-list as `*.geo.admin.ch` plus cantonal OEREB endpoints — stale since `api_client.py:60-62`
- `assert_host_allowed` checks only the hostname, never the scheme (`api_client.py:69`) — relevant because `geodata.py:447` and `:464` build URLs from an upstream catalogue value (`geodata.py:96-104`)

### Risk Description
The two-layer requirement exists for one specific failure mode: a compromised code image where the code-layer check no longer runs. That is precisely what today's network layer does not cover. `deploy/kubernetes.yaml:101-108` permits TCP/443 to `0.0.0.0/0` minus private ranges, so a modified or malicious image could reach any public HTTPS endpoint — an exfiltration channel for anything the process can read, and a command-and-control path. Since the data this server handles is public Swiss OGD, the exfiltration value is low; the realistic concern is the outbound channel itself and the loss of the defence-in-depth guarantee the check is written to provide.

The documentation contradiction is the more urgent of the two, because it is self-perpetuating. `docs/network-egress.md:34-38` tells a maintainer that the network layer is out of scope for this server. Anyone adding a host to `ALLOWED_HOSTS` and following the documented 5-step procedure will therefore skip step 4, and the shipped NetworkPolicy will drift further from the code-layer list with each addition. The stale `SECURITY.md:24` description compounds this: a reviewer checking which hosts this server may reach gets an answer three hosts short of the truth.

### Remediation
1. **Fix `docs/network-egress.md:34-38` first.** Replace the "not cloud-deployed, no NetworkPolicy shipped" paragraph with a pointer to `deploy/kubernetes.yaml:90-118` and a statement of what that policy does and does not cover (port/CIDR restriction, not per-host). Remove the "only relevant for cloud deployment" qualifier from the update procedure at `docs/network-egress.md:48` and make step 4 unconditional.
2. **Refresh `SECURITY.md:24`** to list all 10 hosts, or better, to reference `docs/network-egress.md:13` as the single source of truth so it cannot go stale again.
3. **Narrow the network layer toward the code-layer list.** A Kubernetes NetworkPolicy cannot match on hostname, so choose one of:
   - Add an egress-proxy sidecar (Smokescreen or equivalent) configured with the same 10 hosts, and restrict the NetworkPolicy to permit egress only to the proxy. This gives a true host allow-list at the network layer and reuses the documented list.
   - Or, if the proxy is too heavy, resolve the 10 hosts to their current address ranges and narrow the `ipBlock` in `deploy/kubernetes.yaml:101-108` accordingly, with a documented refresh cadence. This is weaker and brittle against upstream IP changes — note that trade-off in `docs/network-egress.md` if chosen.
4. **Add a consistency test.** A test that reads `ALLOWED_HOSTS` and asserts every member appears in the `docs/network-egress.md` table (and, once step 3 lands, in the proxy config) turns the drift this finding describes into a CI failure rather than a documentation review item.
5. Add the scheme check to `assert_host_allowed` per SEC-004 remediation step 1 — the same one-line change closes the last gap listed here.

### Effort Estimate
M (1-3d)


### SEC-022

## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-022
**PDF-Reference:** Anhang B4

### Observed Behavior
Namespace prefixing is inconsistent across the 23-tool surface. 17 tools carry the `swisstopo_` server prefix (`src/swisstopo_mcp/server.py:88`, `108`, `145`, `165`, `186`, `207`, `235`, `256`, `279`, `307`, `328`, `349`, `372`, `394`, `423`, `456`, `475`) while 6 do not: `list_available_layers` (`server.py:504`), `query_geodata` (`server.py:525`), `query_osm_features` (`server.py:552`), `lookup_postal_code` (`server.py:586`), `find_commune` (`server.py:609`) and `search_address` (`server.py:636`).

Those 6 are exactly the collision-prone generic form the check's fail pattern describes. `search_address`, `find_commune`, `query_geodata` and `lookup_postal_code` are names any other Swiss-data MCP server in this portfolio could plausibly register — and the server's own instructions text tells the model it sits alongside swiss-statistics-mcp and zurich-opendata-mcp (`src/swisstopo_mcp/server.py:70-74`), i.e. the multi-server aggregation scenario where shadowing bites.

The unprefixed set grew in the two most recent feature releases rather than shrinking: the geodata façade tools were added at `CHANGELOG.md:131-152` and the three OpenPLZ tools at `CHANGELOG.md:80-107`, both without a prefix, while every tool added in the same period under the swisstopo API families kept it (`CHANGELOG.md:11-23`).

No tool-definition hash snapshot exists. `tool-hashes.json` is absent from the repo root and neither `.github/workflows/publish.yml` nor `.github/workflows/ci.yml` contains a hash / sha256 / tool-snapshot step, so rug-pull detection by a host against a published baseline is not possible.

Two criteria are partly served. `CHANGELOG.md` does name tool-definition changes explicitly and in detail — new tools with rationale (`CHANGELOG.md:11-23`, `:33-44`, `:45-57`), a Changed entry explaining what was deliberately not altered (`:59-66`), and a Fixed entry describing the `sr` input-contract change that alters existing tool schemas (`:68-75`). Versioning is coherent: `pyproject.toml:8` and `server.json:5` both read `0.2.0` (the earlier mismatch is recorded as fixed at `CHANGELOG.md:76-77`).

### Expected Behavior
- All tools carry a namespace prefix with the server identity
- The server-identity prefix is consistent across all tools and not config-mutable
- At release, a hash snapshot of the tool definitions is generated and stored in the repo
- CHANGELOG entries name tool-definition changes explicitly
- Tool-description changes carry a user re-approval note in the CHANGELOG
- Breaking tool changes trigger a major version bump

### Evidence
- Prefixed tools (17): `src/swisstopo_mcp/server.py:88`, `108`, `145`, `165`, `186`, `207`, `235`, `256`, `279`, `307`, `328`, `349`, `372`, `394`, `423`, `456`, `475`
- Unprefixed tools (6): `src/swisstopo_mcp/server.py:504` (`list_available_layers`), `:525` (`query_geodata`), `:552` (`query_osm_features`), `:586` (`lookup_postal_code`), `:609` (`find_commune`), `:636` (`search_address`)
- Multi-server aggregation context stated in the server's own instructions: `src/swisstopo_mcp/server.py:70-74`
- Unprefixed set introduced in recent releases: `CHANGELOG.md:131-152` (geodata façade), `CHANGELOG.md:80-107` (OpenPLZ); prefixed additions in the same period: `CHANGELOG.md:11-23`
- No hash snapshot: `tool-hashes.json` absent from the repo root; no hash / sha256 / tool-snapshot step in `.github/workflows/publish.yml` or `.github/workflows/ci.yml`
- CHANGELOG discipline (partial credit): `CHANGELOG.md:11-23`, `:33-44`, `:45-57`, `:59-66`, `:68-75`
- Version coherence (partial credit): `pyproject.toml:8`, `server.json:5`, both `0.2.0`; mismatch fix recorded at `CHANGELOG.md:76-77`

Gaps:
- 6 of 23 tools have no server-identity prefix (`server.py:504`, `525`, `552`, `586`, `609`, `636`) — Pass-Criteria 1 and 2 unmet
- No hash snapshot of tool definitions is generated at release and none is stored in the repo — Pass-Criterion 3 unmet
- CHANGELOG entries carry no per-tool hashes and no "re-approval needed in Claude Desktop" note for the `sr` contract change — Pass-Criterion 5 unmet
- The `sr=2056` fix (`CHANGELOG.md:68-75`) narrows an accepted input value on three existing tools — a breaking change to the tool contract — yet shipped inside a minor bump rather than a major — Pass-Criterion 6 arguably unmet

### Risk Description
The check's headline control is a consistent server-identity prefix that makes cross-server shadowing structurally impossible. On 6 of 23 tools it is objectively broken, and the server's own instructions confirm it runs alongside sibling Swiss-data servers. If any of those registers a `search_address` or `find_commune` of its own, the host resolves one name to two definitions. Which server wins depends on host-side load order, so the LLM may silently route a Swiss address lookup to a different server's tool — or a malicious server added to a user's config can deliberately register `search_address` to intercept queries intended for this one. The user sees a plausible answer and has no signal that the source changed. This is not hypothetical for a portfolio whose servers all cover overlapping Swiss geodata.

The missing hash snapshot removes the other half of the defence. Without a published baseline of tool names, descriptions and schemas per release, a host has no way to detect that a tool definition changed between the version the user approved and the version now being served — the rug-pull scenario the check exists for. The `sr` contract change at `CHANGELOG.md:68-75` is a concrete instance: it narrowed an accepted input value on three existing tools, changing what a previously approved tool accepts, and shipped with no re-approval note and no version signal that a contract moved.

### Remediation
1. **Rename the 6 unprefixed tools** in `src/swisstopo_mcp/server.py` to `swisstopo_list_available_layers` (`:504`), `swisstopo_query_geodata` (`:525`), `swisstopo_query_osm_features` (`:552`), `swisstopo_lookup_postal_code` (`:586`), `swisstopo_find_commune` (`:609`) and `swisstopo_search_address` (`:636`).

   Anticipate the objection: those 6 are the deliberately source-neutral façade tools (OSM, OpenPLZ, geodienste — not swisstopo data), so `swisstopo_` reads as a misnomer. The resolution is that the prefix denotes the *server* identity, not the data source, which is what makes it a shadowing defence. If the misnomer is unacceptable, rename the whole surface to a neutral server-identity prefix — but do not leave it mixed.

   This is a breaking change for anyone who has these tool names in a prompt or a client config. Ship it as a major bump (`0.2.0` → `1.0.0` or `0.3.0` with an explicit breaking note in both `pyproject.toml:8` and `server.json:5`), with a CHANGELOG entry listing old → new names and a "re-approval required in Claude Desktop" line.

2. **Add a hash-snapshot step** to `.github/workflows/publish.yml` that dumps the tool manifest and hashes each definition, writing `tool-hashes.json` to the repo root and attaching it to the release:

```python
# scripts/snapshot_tool_hashes.py
import hashlib, json
from swisstopo_mcp.server import mcp

tools = {
    t.name: hashlib.sha256(
        json.dumps(
            {"name": t.name, "description": t.description, "schema": t.inputSchema},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    for t in await mcp.list_tools()
}
json.dump(dict(sorted(tools.items())), open("tool-hashes.json", "w"), indent=2)
```

   Add a CI check in `.github/workflows/ci.yml` that regenerates the file and fails if it differs from the committed one without a CHANGELOG entry — this makes any unannounced tool-definition change visible in review.

3. **Extend the CHANGELOG convention** so tool-definition changes carry the affected tool names, the new hash, and a re-approval note. Retroactively add the re-approval note to the `sr` entry at `CHANGELOG.md:68-75`.
4. **Adopt a semver rule** in `CONTRIBUTING.md`: any change to a tool's name, description or input schema that narrows or renames is a major bump. The `sr` change is the precedent to cite.

Rename and hash-snapshot should ride the same major release so users re-approve once.

### Effort Estimate
M (1-3d)


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **SEC-004** (critical, partial)
2. **ARCH-004** (high, partial)
3. **ARCH-006** (high, partial)
4. **OPS-001** (high, partial)
5. **OPS-003** (high, partial)
6. **SCALE-001** (high, partial)
7. **SCALE-003** (high, partial)
8. **SDK-004** (high, partial)
9. **SEC-005** (high, partial)
10. **SEC-018** (high, partial)
11. **SEC-021** (high, partial)
12. **SEC-022** (high, fail)
13. **ARCH-003** (medium, partial)
14. **ARCH-007** (medium, partial)
15. **ARCH-011** (medium, partial)
16. **ARCH-012** (medium, partial)
17. **CH-004** (medium, partial)
18. **OBS-006** (medium, fail)
19. **SDK-002** (medium, partial)
20. **SDK-003** (medium, partial)
21. **SEC-014** (medium, partial)
22. **SEC-015** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| catalog_version | `sha256:091f446b2796` |
| policy | `fail-or-partial` |
| audit_date | `2026-07-27` |


_Generated by tools/build_report.py — do not edit by hand._
