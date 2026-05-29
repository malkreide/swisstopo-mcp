## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SDK-002
**PDF-Reference:** Sec 3.1
**Check-Status:** partial

### Observed Behavior
Inputs use Pydantic v2 well, but tool returns are markdown/text strings rather than structured models.

### Expected Behavior
Structured returns (BaseModel/TypedDict) with a consistent envelope (source/provenance/results/count).

### Evidence
- Pydantic >=2.0.0 in dependencies; inputs use Pydantic v2 ConfigDict
- All tool handlers have explicit '-> str' return annotations

Gaps:
- Tool returns are formatted markdown/text strings, not structured BaseModel/TypedDict
- No response envelope with source/provenance/results/count (limits machine-readability)

### Risk Description
String returns are not machine-readable; the LLM/client cannot reliably parse fields.

### Remediation
Introduce a response envelope model for search/list tools and return structured objects; keep a human-readable summary field if desired.

### Effort Estimate
L (1-2w)
