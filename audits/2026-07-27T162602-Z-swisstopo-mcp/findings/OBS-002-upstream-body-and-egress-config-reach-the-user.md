## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** OBS-002
**PDF-Reference:** Sec 6.2
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
Central masking is correct for the generic path: `api_client.py:384-414` classifies
HTTP/timeout/connect errors into fixed messages and returns only "Unerwarteter
interner Fehler…" for anything unexpected, logging the detail to stderr. No
`traceback.format_exc()` anywhere in `src/`. Regression-tested at
`tests/test_api_client.py:80-86`.

Two paths bypass it. `overpass.py:145-146` returns `text.strip()[:300]` of any body
containing the substring "error", interpolated into the tool summary at
`overpass.py:176`; executed against a realistic Overpass error page, the summary came
back containing the server path `/opt/osm/db/overpass_db` and the echoed query.
Separately, `api_client.py:133-136` raises `PermissionError` embedding
`sorted(ALLOWED_HOSTS)`, and `handle_api_error` returns it verbatim
(`api_client.py:407-409`), handing the LLM the full ten-host egress allow-list;
`api_client.py:115-118` similarly returns a resolved internal IP.

### Expected Behavior
- No upstream body, URL or internal configuration in a user-facing message

### Evidence
- Central masking exists and is correct for the generic path: src/swisstopo_mcp/api_client.py:384-414 classifies HTTP status / timeout / connect errors into fixed German messages and, for anything unexpected, logs the detail to stderr (api_client.py:413) and returns only "Unerwarteter interner Fehler. Bitte später erneut versuchen." (api_client.py:414). No traceback.format_exc()/sys.exc_info() anywhere in src/.
- LEAK — raw upstream body reaches the user: src/swisstopo_mcp/overpass.py:145-146 falls back to `return text.strip()[:300]` on any body containing the substring "error", and that string is interpolated straight into the tool summary at overpass.py:176 (`f"Overpass-Fehler: {err}"`). Executed against a realistic Overpass error page, the tool summary came back containing the server-side filesystem path `/opt/osm/db/overpass_db`, the RAM figure and the full submitted Overpass query with the user's coordinates.
- LEAK — internal egress configuration reaches the user: src/swisstopo_mcp/api_client.py:133-136 raises PermissionError whose message embeds `sorted(ALLOWED_HOSTS)`; handle_api_error treats PermissionError as a user-facing validation error (api_client.py:407-409, `return f"{prefix}{e}"`), so a blocked request hands the LLM the server's complete ten-host egress allow-list. api_client.py:115-118 similarly returns the resolved internal IP address.
- Argument validation errors are returned verbatim by the SDK: runtime probe of tools/call swisstopo_geocode with an empty params object returned "Error executing tool swisstopo_geocode: 1 validation error for swisstopo_geocodeArguments … https://errors.pydantic.dev/2.13/v/missing" — internal model name and dependency version disclosed. Not the server's code, but `mask_error_details` is not available to mitigate it (see gaps).
- Masking is regression-tested: tests/test_api_client.py:80-82 asserts a RuntimeError produces "Unerwarteter interner Fehler" and tests/test_api_client.py:86 asserts intentional ValueError guidance survives.

Gaps:
- overpass.py:146 must not return the raw body; the 300-char fallback should be dropped or replaced with a fixed message, with the body logged to stderr only.
- PermissionError messages should not travel to the LLM verbatim — the allow-list and resolved IP belong in the log, not the tool result.
- mask_error_details=True is not set on the FastMCP init (src/swisstopo_mcp/server.py:49-62). Verified against the installed SDK: mcp.server.fastmcp.FastMCP.__init__ has no such parameter (mcp 1.28.1), so this pass criterion is not achievable without switching to the standalone fastmcp package. Handled defence-in-depth by the try/except-everything pattern instead.

### Risk Description
The Overpass path is an unconditional passthrough of up to 300 characters of a
third-party HTML body into text the model will read and may quote. Two things follow:
infrastructure disclosure (a filesystem path, tuning figures), and a prompt-injection
channel — a hostile or compromised Overpass instance controls text that lands in the
model's context. The allow-list disclosure is lower impact, since the hosts are public
federal endpoints, but it is internal configuration crossing the trust boundary on a
provokable error.

### Remediation
1. Drop the 300-char fallback at `overpass.py:146`. Log the body to stderr, return a
   fixed message.
2. Split `PermissionError` messages: full detail to the log, a bare "Ziel nicht auf
   der Egress-Allow-List" to the caller. Same for the resolved IP at
   `api_client.py:115-118`.
3. `mask_error_details=True` is **not** available — verified against the installed
   SDK, `mcp.server.fastmcp.FastMCP.__init__` has no such parameter in mcp 1.28.1.
   The try/except-everything pattern is the substitute; note that in `SECURITY.md`
   rather than leaving the criterion looking merely unimplemented.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
New in this run. `2026-07-27T125314-Z` recorded OBS-002 as passing on the strength of the central masking, without checking the module-level paths.

### Auditor Notes
The remediation's core claim — unexpected exceptions are masked — is real
and tested. But the check asks whether ANY upstream body or URL can reach
a user-facing message, and two paths do. The Overpass one is the serious
one: it is an unconditional passthrough of up to 300 characters of a
third-party HTML body, and a realistic Overpass error page contains a
server filesystem path plus the echoed query. The egress-allow-list
disclosure is lower impact (the hosts are public federal endpoints) but is
still internal configuration leaving the trust boundary on a provokable
error. Partial.

---

### Remediation Status (2026-07-28, follow-up PR)

**Closed for both leak paths.**

**1. Overpass error bodies.** `_extract_error` returned `text.strip()[:300]` of
any body containing "error", straight into the summary. Replaced with
`_classify_error`, which matches the body against a fixed signature table
(timeout / out-of-memory / rate-limited / parse error, else a generic message)
and returns *only* those strings. The body goes to `_log.warning`, truncated to
1000 characters, where an operator can read it and the model cannot. The
HTTP-200 `remark` path got the same treatment — it was forwarding upstream text
too, which the finding did not name but which leaks identically.

Regression-tested against a body shaped like a real Overpass error page
(server path, `open64`, the echoed query, the OSM attribution note): every
fragment is asserted absent from the summary, the classification is asserted
still useful (`Rate-Limiting`), the body is asserted present in the log, and a
50 KB junk body is asserted not to inflate the summary.

**2. Egress refusals.** `handle_api_error` grouped `PermissionError` with
`ValueError` and returned it verbatim, so a blocked request disclosed the full
ten-host allow-list or the internal address a name resolved to. `PermissionError`
now has its own branch: the detail is logged under `egress_blocked` and the
caller gets a fixed "Ziel nicht erlaubt (Egress-Richtlinie)" message. Three
tests assert no allow-listed host, no rejected hostname and no resolved IP
appear in the returned string, and that the detail survives in the log.

`ValueError` keeps its message — those are this server's own validation strings,
written to be read by the caller, and masking them would remove real guidance.

**Not addressed, and why:**

- **`mask_error_details=True`** remains unavailable. Re-verified against the
  installed SDK: `mcp.server.fastmcp.FastMCP.__init__` has no such parameter in
  mcp 1.28.1. Reaching it means switching to the standalone `fastmcp` package,
  which is a dependency decision well beyond this finding.
- **Pydantic argument-validation errors** are formatted and returned by the SDK
  before any of this server's code runs, so the internal model name and the
  `errors.pydantic.dev` version link are outside what can be masked here. This
  is the same constraint as above and shares its remedy.

