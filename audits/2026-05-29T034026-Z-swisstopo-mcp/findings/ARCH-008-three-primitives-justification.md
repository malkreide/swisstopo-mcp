## Finding: ARCH-008 — Drei Primitive nutzen: Tools, Resources und Prompts

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-008
**PDF-Reference:** Anhang A2
**Check-Status:** partial

### Observed Behavior
Server exposes Tools only; no Resources/Prompts and no documented rationale.

### Expected Behavior
Use >=2 primitives, or document why tools-only.

### Evidence
- Server exposes Tools only; no @mcp.resource or @mcp.prompt (grep: 0 hits)

Gaps:
- Uses only 1 of 3 primitives and provides no documented justification for tools-only (read-only static lookups like map layers are Resource candidates)

### Risk Description
Static lookups (e.g. notable map layers) are Resource candidates; tools-only inflates the manifest.

### Remediation
Either add a Resource for static layer catalogs, or add a README 'MCP-Primitive' section justifying tools-only for this phase.

### Effort Estimate
S (<1d)
