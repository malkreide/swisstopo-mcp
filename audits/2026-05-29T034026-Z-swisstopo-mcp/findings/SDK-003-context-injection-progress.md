## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SDK-003
**PDF-Reference:** Sec 3.1
**Check-Status:** partial

### Observed Behavior
No tool injects ctx: Context; no progress reporting or ctx logging.

### Expected Behavior
Long-running tools (>2s) take ctx and report progress; tools log via ctx.info.

### Evidence
- Most tools are single fast upstream calls where progress reporting is unnecessary

Gaps:
- No tool injects ctx: Context (grep: 0 hits) — no ctx.report_progress/ctx.info
- Potentially slower tools (elevation_profile, oereb_extract) provide no progress feedback

### Risk Description
Low for fast single-call tools; elevation_profile/oereb give no progress feedback.

### Remediation
Add ctx: Context to elevation_profile (and oereb_extract) and call ctx.report_progress/ctx.info.

### Effort Estimate
S (<1d)
