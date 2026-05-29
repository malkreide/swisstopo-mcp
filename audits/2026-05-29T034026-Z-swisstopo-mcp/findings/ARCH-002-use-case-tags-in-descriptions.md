## Finding: ARCH-002 — Tool-Beschreibung mit Use-Case-Tags

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-002
**PDF-Reference:** Sec 2.2
**Check-Status:** partial

### Observed Behavior
Tool descriptions are meaningful single sentences but lack <use_case>/<important_notes> tags and are mostly short.

### Expected Behavior
Descriptions >=100 chars median with use_case/important_notes/example tags.

### Evidence
- Every tool has a meaningful one-sentence German description (server.py docstrings/annotations)
- Server-level instructions give cross-tool usage guidance (server.py:14-23)

Gaps:
- Descriptions lack <use_case> / <important_notes> / <example> tags
- Most descriptions are below the ~100-char median target and omit caveats/limits

### Risk Description
The LLM has less context to disambiguate similar tools (e.g. identify vs find vs get_feature).

### Remediation
Expand descriptions to include a <use_case> tag and caveats; differentiate the three feature-query tools explicitly.

### Effort Estimate
S (<1d)
