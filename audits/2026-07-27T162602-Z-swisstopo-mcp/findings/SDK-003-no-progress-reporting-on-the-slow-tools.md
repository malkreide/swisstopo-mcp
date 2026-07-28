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
