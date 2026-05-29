## Finding: CH-004 — OGD-CH Lizenz-Compliance: CC BY 4.0 Attribution

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** CH-004
**PDF-Reference:** Custom (OGD-CH-Richtlinien)
**Check-Status:** partial

### Observed Behavior
README references OGD terms generally; tool responses lack source/license attribution fields.

### Expected Behavior
Tool responses carry a source/license field; README lists each source with its CC BY attribution.

### Evidence
- README License section references swisstopo Open Government Data / opendata.swiss terms
- stac.py:59 surfaces the upstream collection 'license' field

Gaps:
- Tool responses generally lack a 'source'/'license'/attribution field (CC BY 4.0 requires attribution)
- No per-source attribution table in README and no explicit CC BY attribution text

### Risk Description
CC BY requires attribution; omitting it in responses is a licence-compliance gap.

### Remediation
Append a source/attribution line to tool outputs (e.g. 'Quelle: swisstopo / geo.admin.ch, CC BY') and add a data-sources table to README.

### Effort Estimate
S (<1d)
