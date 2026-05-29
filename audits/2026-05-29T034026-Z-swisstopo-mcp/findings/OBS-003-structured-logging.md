## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OBS-003
**PDF-Reference:** Sec 6.3
**Check-Status:** fail

### Observed Behavior
No structured logger and no logging at all in the codebase.

### Expected Behavior
structlog/loguru with JSON output and per-call bound context.

### Evidence
- No print() in src/ (no stdout pollution)

Gaps:
- No structured logger (structlog/loguru) in dependencies and no logging used at all
- No JSON/logfmt output, no severity levels, no per-call bound context (tool/session/correlation id)

### Risk Description
No operational visibility; incidents are hard to diagnose.

### Remediation
Add structlog (configured to sys.stderr, JSON renderer) and emit bound info/error logs per tool call. Keep stdout clean for stdio.

### Effort Estimate
M (1-3d)
