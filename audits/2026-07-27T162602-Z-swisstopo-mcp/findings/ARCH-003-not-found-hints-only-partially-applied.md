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
