## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OBS-002
**PDF-Reference:** Sec 6.2
**Check-Status:** partial

### Observed Behavior
Known errors are masked nicely, but the generic fallback returns f'{type(e).__name__}: {e}', and FastMCP has no mask_error_details=True.

### Expected Behavior
No raw exception strings reach the client; mask_error_details enabled.

### Evidence
- handle_api_error produces clean German messages for known HTTP/timeout/connect errors (api_client.py:59-75)
- No traceback.format_exc()/sys.exc_info() in any tool return

Gaps:
- Generic fallback api_client.py:77 returns f'{type(e).__name__}: {e}' — raw exception string may leak internals (e.g. URLs)
- FastMCP not initialized with mask_error_details=True

### Risk Description
The fallback can leak internal detail (e.g. request URLs) into the LLM context.

### Remediation
Replace the generic fallback with a constant user-message and log the detail to stderr; set FastMCP(mask_error_details=True).

### Effort Estimate
S (<1d)
