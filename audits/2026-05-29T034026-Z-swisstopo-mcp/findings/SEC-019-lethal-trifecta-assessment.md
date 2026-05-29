## Finding: SEC-019 — Lethal Trifecta vermeiden: Server-Separation Read vs Write/Send

**Severity:** critical
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-019
**PDF-Reference:** Anhang B1
**Check-Status:** partial

### Observed Behavior
Architecturally safe (read-only, public data, trusted sources => <=1 of 3 trifecta legs), but no documented assessment exists.

### Expected Behavior
A Lethal-Trifecta assessment table in README or docs/.

### Evidence
- Read vs Write/Send separation is satisfied: all 13 tools are read-only (readOnlyHint=True), no send/write capability
- Trifecta score is at most 1/3: no private data (Public Open Data), no external send, content from trusted federal APIs only

Gaps:
- No documented Lethal-Trifecta assessment in README or docs/

### Risk Description
Knowledge of the safe-by-design decision is lost on maintainer changes.

### Remediation
Add a short 'Lethal Trifecta Bewertung' table to README documenting: no private data, trusted-only content, no external send.

### Effort Estimate
S (<1d)
