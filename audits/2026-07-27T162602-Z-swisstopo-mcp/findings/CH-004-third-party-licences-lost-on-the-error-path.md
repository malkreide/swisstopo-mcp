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

---

### Remediation Status (2026-07-28, follow-up PR)

**Closed, by removing the possibility rather than the instances.**

The finding's own gap note asked for this: "make source and licence a single
argument … so they cannot drift apart again, since a defaulted licence is
exactly the failure this finding produced twice." Patching the 14 sites would
have fixed this occurrence and left the mechanism intact.

`ToolResponse.ok()` and `.error()` now take `license: str | None = None` and
derive it from `source` via `LICENSE_BY_SOURCE` when it is not given. Omitting
the licence therefore produces the *correct* attribution instead of the
swisstopo default. All 14 sites are corrected without being touched —
runtime-verified across all eight source constants that `error()` and `ok()`
now agree, including `ToolResponse.error(..., source=OSM_SOURCE)` returning
`ODbL — © OpenStreetMap contributors`.

Two guards, because derivation alone only protects the sites that stay silent:

1. **Exhaustiveness.** A test collects every `*_SOURCE` constant in `models.py`
   by introspection and fails if one has no mapping entry. Verified by adding a
   throwaway `NEWTHING_SOURCE` — the test named it.
2. **Stated pairs.** An AST sweep over `src/` finds every
   `ToolResponse.ok/error` call and fails if one pairs a source constant with a
   different source's licence, or states a literal licence not on a declared
   override list. Verified by flipping one `overpass.py` site to
   `SWISSTOPO_LICENSE` — the test named the file and line. It also caught a
   change made during this very remediation, which is the point.
   The sweep asserts it found >50 call sites, so it cannot pass vacuously —
   the failure mode the SEC-021 CI gate had.

Also closed, from the same finding's gap list:

- **Per-record provenance on aggregation.** `list_available_layers` emitted a
  composite `license="gemischt — siehe je Layer"` that pointed at nothing
  readable. Each record now carries its own `license`, and the envelope string
  says where to look.
- **The README ÖREB row** was already extended with `swisstopo_oereb_at` and
  `swisstopo_query_geodata` in the `2026-07-27T162602-Z` batch.

The six `overpass.py` error sites were given `license=OSM_LICENSE` explicitly in
the OBS-002 PR, before this change. Those are now redundant but harmless, and
guard 2 keeps them honest.
