## Finding: SEC-007 — Container-Sandboxing: Docker / chroot mit minimalen Privilegien

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-007
**PDF-Reference:** Sec 4.5
**Check-Status:** partial

### Observed Behavior
No Dockerfile or k8s manifests exist; server runs as local stdio.

### Expected Behavior
If containerized, non-root USER (>=10000), readOnlyRootFilesystem, drop ALL caps, seccomp RuntimeDefault.

### Evidence
- No container artifacts present (no Dockerfile, no k8s manifests) — no container attack surface today
- Deployment is local-stdio

Gaps:
- If containerized for cloud later, a hardened Dockerfile (non-root USER >=10000, readOnlyRootFilesystem, drop ALL caps, seccomp RuntimeDefault) must be added — none exists yet

### Risk Description
None today (no container). Becomes relevant only on cloud/container deployment.

### Remediation
Defer until cloud deployment is planned; then add a hardened multi-stage Dockerfile and (if k8s) a securityContext per the catalog pattern.

### Effort Estimate
M (1-3d)
