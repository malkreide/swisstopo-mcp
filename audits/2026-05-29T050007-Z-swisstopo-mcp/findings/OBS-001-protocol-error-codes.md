## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OBS-001
**PDF-Reference:** Sec 6.1
**Check-Status:** partial

### Evidence (already in place)
- Execution errors are caught and returned as a structured ToolResponse with is_error=true (models.py, PR #8) instead of raising
- Error paths covered by tests

### Remaining Gaps
- is_error is an envelope field, not the protocol-level CallToolResult.isError
- No standardized JSON-RPC error codes (-326xx/-320xx)

### Remediation
Surface handled errors via the protocol-level CallToolResult.isError and adopt standardized JSON-RPC error codes for protocol errors.

### Effort Estimate
M (1-3d)
