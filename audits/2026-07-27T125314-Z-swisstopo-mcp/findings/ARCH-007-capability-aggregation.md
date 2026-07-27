## Finding: ARCH-007 — Capability-Aggregation: Composability intern, Atomarität extern

**Severity:** medium
**Status:** closed
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

---

### Remediation Status (2026-07-27, batch 4)

**Closed.** `swisstopo_oereb_at` collapses the coordinate → EGRID → extract
chain into one call. The EGRID is an upstream identifier, not something the
caller asked for, which is exactly the pattern the check names. EGRID
resolution was extracted into `_fetch_egrid_features()` so the aggregate does
not re-enter the tool layer to reach it; `swisstopo_get_egrid` stays for
callers who want the parcel ID, and its description no longer bills it as a
precursor.

The precedence rule the finding asked for is now an explicit rule in
`instructions` — Bauzone, Gemeinde and ÖREB each name the direct tool and say
when the generic one applies — and it is cross-referenced from the competing
tool descriptions, since `instructions` alone is not reliably consulted per
selection decision.

Costs one budget slot: 24 of 25.
