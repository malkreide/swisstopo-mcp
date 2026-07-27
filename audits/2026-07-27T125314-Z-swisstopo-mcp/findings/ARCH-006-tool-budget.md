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
