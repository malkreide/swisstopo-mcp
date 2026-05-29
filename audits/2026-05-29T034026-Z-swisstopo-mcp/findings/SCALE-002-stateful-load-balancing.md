## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SCALE-002
**PDF-Reference:** Sec 5.2
**Check-Status:** partial

### Observed Behavior
No multi-instance deployment; HTTP mode is single-instance. No sticky-session/shared-state config.

### Expected Behavior
If scaled, sticky sessions on Mcp-Session-Id or a shared session store.

### Evidence
- Server is primarily local-stdio; HTTP mode is single-instance for local use
- No multi-instance load-balanced deployment exists (is_cloud_deployed=false)

Gaps:
- If scaled horizontally over HTTP, no sticky-session (LB affinity on Mcp-Session-Id) or shared-state session store is configured
- No deployment manifests (railway/render/k8s) to verify affinity

### Risk Description
None today; relevant only if horizontally scaled over HTTP.

### Remediation
Defer until cloud scaling is planned; then add LB affinity on Mcp-Session-Id or a Redis-backed session manager.

### Effort Estimate
M (1-3d)
