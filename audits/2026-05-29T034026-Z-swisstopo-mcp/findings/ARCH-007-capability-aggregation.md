## Finding: ARCH-007 — Capability-Aggregation: Composability intern, Atomarität extern

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-007
**PDF-Reference:** Sec 2.3
**Check-Status:** partial

### Observed Behavior
Layer discovery requires chaining search_layers -> identify/find -> get_feature; no internal multi-source aggregation.

### Expected Behavior
Tools should return thought-complete results; where useful, aggregate internally with asyncio.gather.

### Evidence
- Most tools return self-contained results (geocode, get_height, oereb_extract, map_url)
- elevation_profile aggregates multiple points into one result (height.py)

Gaps:
- Layer discovery is a multi-call chain (search_layers -> get_feature returns IDs used in follow-ups)
- No asyncio.gather-style internal aggregation across sources

### Risk Description
Chaining increases latency and chaining-hallucination risk.

### Remediation
Consider a higher-level tool that resolves a layer query and returns features in one call for the common case; document the discovery chain otherwise.

### Effort Estimate
M (1-3d)
