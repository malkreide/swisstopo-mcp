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
