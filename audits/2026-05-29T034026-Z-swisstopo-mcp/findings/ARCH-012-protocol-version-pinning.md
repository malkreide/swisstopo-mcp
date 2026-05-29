## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-012
**PDF-Reference:** Anhang A9
**Check-Status:** partial

### Observed Behavior
protocolVersion is not pinned (FastMCP default); no Dependabot/Renovate; no protocol-version README section.

### Expected Behavior
Explicit protocol_version pin, CHANGELOG noting spec bumps, README policy, and automated SDK update PRs.

### Evidence
- CHANGELOG.md present in Keep-a-Changelog format with versioned entries

Gaps:
- protocolVersion is NOT pinned in code — FastMCP default is used (silent break risk on SDK update)
- No README 'MCP Protocol Version' section / update policy
- No Dependabot/Renovate config for SDK update PRs

### Risk Description
A future mcp SDK update could silently change the negotiated protocol version.

### Remediation
Pin protocol_version explicitly, add a README 'MCP Protocol Version' section, and add .github/dependabot.yml grouping the mcp package.

### Effort Estimate
S (<1d)
