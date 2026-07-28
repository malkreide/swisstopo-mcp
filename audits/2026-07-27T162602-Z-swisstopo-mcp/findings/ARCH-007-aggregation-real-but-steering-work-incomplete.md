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

---

### Remediation Status (2026-07-28, follow-up PR)

**Closed.** The description and README gaps were fixed earlier in this batch;
the parallelisation criterion is closed here.

**Already fixed earlier:**

- `swisstopo_get_egrid` no longer describes itself as a "Vorstufe", and both it
  and `swisstopo_get_oereb_extract` now point at `swisstopo_oereb_at`. This was
  the claim the re-audit falsified — I had asserted it, a targeted replacement
  had silently failed, and the agent was right. Verified at runtime after
  fixing, and the `2026-07-28` `tool-hashes.json` pins the descriptions.
- Both READMEs' "Tool workflows" sections name `swisstopo_oereb_at` as the
  cadastre path instead of documenting the superseded chain.

**Closed here — criterion 2, parallelisation.** `geodata.py` looped over
discovered geodienste collections one request at a time; `asyncio.gather`
appeared nowhere in `src/`.

The naive fix would have been a regression. The sequential loop had a real
virtue the finding does not mention: it stopped as soon as it had `limit`
records, often after a single request. A `gather` over every collection throws
that away — and a single geodienste dataset can hold **24** collections
(measured against `av_0`), so all-at-once means 24 requests against a cantonal
service on every call, to save latency only when the early ones come back empty.

So the fan-out runs in **waves** of 4, which keeps the early exit and still cuts
the worst case by the wave size, with a cap of 12 collections per call. When the
cap bites, the response says so — a cap nobody is told about reads as "this is
everything", which is the same class of quiet-untruth this audit has been about.

Six tests hold all three properties, because a fix satisfying only the first
would be worse than the defect: requests actually overlap (peak concurrency > 1,
verified to fail at concurrency 1), concurrency stays bounded, the early exit
survives (filling `limit` in the first wave must not query the rest), results
stay deterministic despite concurrency, the truncation note appears when the cap
bites, and does not appear when it did not.

**Deliberately unchanged:** `swisstopo_get_egrid` and `swisstopo_search_layers`
still return pointers rather than self-contained results. Both are now shadowed
by an aggregate and both describe themselves that way, which is the shape the
check wants; removing them would be a breaking change belonging with ARCH-006.
