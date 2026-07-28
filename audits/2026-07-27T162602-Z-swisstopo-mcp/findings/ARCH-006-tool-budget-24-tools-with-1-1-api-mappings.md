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
