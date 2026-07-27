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
