## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** OBS-001
**PDF-Reference:** Sec 6.1
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
Execution errors are handled rather than raised — every handler wraps its body and
returns `ToolResponse.error(...)`, so no upstream failure escapes as a JSON-RPC error.
That is the half of the check that matters most, and it holds across all 24 tools.

The other half does not. The error flag never reaches the protocol layer: a runtime
`tools/call` probe returns a JSON payload containing `"is_error": true` and a tool
result with **no** protocol-level `isError` field. Nothing maps `models.py:86` onto
`mcp.types.CallToolResult.isError`.

Both READMEs (`README.md:450-452`, `README.de.md:444-446`) claim protocol errors are
emitted as JSON-RPC errors with standard codes such as `-32602`. A runtime probe
contradicts this for mcp 1.28.1: unknown tools and missing arguments both come back
as `isError` tool results, not JSON-RPC error objects.

### Expected Behavior
- Execution errors returned as tool results with `isError: true`
- Protocol errors as JSON-RPC errors
- Documented behaviour matches actual behaviour

### Evidence
- Execution errors are handled, not raised: every tool handler wraps its body in try/except and returns ToolResponse.error(...) — e.g. src/swisstopo_mcp/height.py:167-168, src/swisstopo_mcp/rest_api.py:334, src/swisstopo_mcp/stac.py:167. No handler lets an upstream failure escape as a JSON-RPC error.
- But the error flag never reaches the MCP protocol layer. Runtime probe (stdio, tools/call swisstopo_elevation_profile with a single coordinate pair) returns result.content[0].text = a JSON blob containing "is_error": true, and the tool result carries NO protocol-level isError field. The envelope field is defined at src/swisstopo_mcp/models.py:86 and set at models.py:126; nothing maps it onto mcp.types.CallToolResult.isError.
- README.md:450-452 and README.de.md:444-446 claim protocol errors are emitted as JSON-RPC errors with standard codes ("e.g. -32602 invalid params"). Runtime probe contradicts this: an unknown tool returns {"result":{"content":[{"text":"Unknown tool: does_not_exist"}],"isError":true}} and a missing required argument returns an isError tool result carrying the raw Pydantic message — neither is a JSON-RPC error object.
- Error-path test coverage exists for the execution side (tests/test_api_client.py:67-86 asserts the 404/timeout/connect/unexpected classifications) and per-tool error tests exist (e.g. tests/test_openplz.py, tests/test_overpass.py), but no test asserts the shape of the tool result at the protocol boundary — the mismatch between documented and actual protocol behaviour was invisible to the suite.

Gaps:
- ToolResponse.is_error is a payload convention only; a client that reads CallToolResult.isError (the spec mechanism) sees success for every handled error.
- No test exercises tools/call end-to-end and asserts the isError flag, so the documented-vs-actual divergence is uncaught.
- The READMEs' JSON-RPC error-code claim is factually wrong for this SDK version (mcp 1.28.1) and should be corrected or the behaviour changed.

### Risk Description
A spec-conformant client reads `CallToolResult.isError`. Here it reads `false` for
every handled error, because the server invented a payload-level convention instead.
Any consumer that branches on the protocol flag — retry logic, error dashboards, an
orchestrating agent — treats every upstream failure as a success and passes a German
error string downstream as though it were geodata.

### Remediation
1. Set the protocol flag. Return a `CallToolResult` with `isError=True` (or use the
   SDK mechanism that maps onto it) when `ToolResponse.is_error` is true, keeping the
   payload field for backward compatibility.
2. Add an end-to-end test that issues `tools/call` over a real session and asserts the
   flag — no current test crosses the protocol boundary, which is why the
   documentation could drift this far.
3. Correct the JSON-RPC error-code claim in both READMEs to describe what this SDK
   version actually does.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
New in this run. Not raised by `2026-07-27T125314-Z`, which recorded OBS-001 as passing.

### Auditor Notes
The separation the check cares about most — execution errors must not
become JSON-RPC errors — holds cleanly across all 24 tools. What is
missing is the other half: the spec's isError flag on the tool result.
The server invented its own payload field instead, and then documented
protocol behaviour (-32602) that a runtime probe shows the SDK does not
produce. Partial rather than pass because a spec-conformant client cannot
distinguish a handled error from a success without parsing the JSON body.
