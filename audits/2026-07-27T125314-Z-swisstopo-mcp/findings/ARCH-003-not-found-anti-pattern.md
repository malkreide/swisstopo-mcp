## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

**Severity:** medium
**Status:** closed
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

---

### Remediation Status (2026-07-27, batch 2)

**Closed.** `ToolResponse` gained a `note` field, and the bare-negative sites in
`rest_api.py` (layer search, identify, find) and `stac.py` now populate it with
an actionable next step rather than returning an empty list alone. The field is
additive, so no client breaks; the tool hashes are unaffected because they cover
the input schema.
