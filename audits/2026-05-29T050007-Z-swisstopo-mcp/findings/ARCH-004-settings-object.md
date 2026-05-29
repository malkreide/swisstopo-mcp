## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-004
**PDF-Reference:** Sec 2.1
**Check-Status:** partial

### Evidence (already in place)
- Tool handlers are transport-agnostic (only typed params; no request object)
- Server supports stdio + streamable-http

### Remaining Gaps
- Transport/host/port selected via ad-hoc sys.argv + os.environ rather than a pydantic-settings Settings object

### Remediation
Replace ad-hoc sys.argv/os.environ handling with a pydantic-settings Settings object (transport/host/port/log_level).

### Effort Estimate
S (<1d)
