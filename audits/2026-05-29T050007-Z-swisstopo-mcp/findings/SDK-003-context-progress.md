## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SDK-003
**PDF-Reference:** Sec 3.1
**Check-Status:** partial

### Evidence (already in place)
- Most tools are single fast upstream calls where progress reporting is unnecessary

### Remaining Gaps
- No tool injects ctx: Context; elevation_profile/oereb_extract provide no ctx.report_progress feedback

### Remediation
Inject ctx: Context into elevation_profile (and oereb_extract) and call ctx.report_progress/ctx.info for long operations.

### Effort Estimate
S (<1d)
