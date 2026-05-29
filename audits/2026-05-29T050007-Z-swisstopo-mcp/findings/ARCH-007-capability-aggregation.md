## Finding: ARCH-007 — Capability-Aggregation: Composability intern, Atomarität extern

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-007
**PDF-Reference:** Sec 2.3
**Check-Status:** partial

### Evidence (already in place)
- Most tools return thought-complete results; elevation_profile aggregates points

### Remaining Gaps
- Layer discovery (search_layers -> get_feature) remains a multi-call chain; no internal multi-source aggregation

### Remediation
Optionally add a higher-level tool that resolves a layer query and returns features in one call for the common case; otherwise document the discovery chain.

### Effort Estimate
M (1-3d)
