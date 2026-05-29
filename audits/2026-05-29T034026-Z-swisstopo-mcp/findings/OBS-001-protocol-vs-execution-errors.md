## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OBS-001
**PDF-Reference:** Sec 6.1
**Check-Status:** partial

### Observed Behavior
Execution errors are returned as plain German text (not raised), but not flagged isError and without standardized codes.

### Expected Behavior
Application errors returned with isError:true; protocol errors use standard JSON-RPC codes.

### Evidence
- Execution errors are caught and returned as user-friendly text, not raised, via handle_api_error (api_client.py:55-77; used in geocoding.py:98, oereb.py:101)
- Tests cover error paths (e.g. test_geocoding.py test_geocode_api_error)

Gaps:
- Errors are returned as plain text, not as structured tool results with isError: true
- No standardized JSON-RPC error codes (-326xx / -320xx) for protocol-level errors

### Risk Description
Clients cannot machine-distinguish an error result from a normal text result.

### Remediation
Return structured error content (isError) for handled execution errors; let unexpected errors bubble for framework JSON-RPC handling.

### Effort Estimate
M (1-3d)
