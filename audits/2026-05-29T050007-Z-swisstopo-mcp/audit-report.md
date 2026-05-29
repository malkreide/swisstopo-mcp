# MCP-Server Audit-Report — `swisstopo-mcp`

**Audit-Datum:** 2026-05-29
**Skill-Version:** 1.0.0
**Catalog-Version:** 68 checks (catalog_hash 091f446b...)

---

## 1. Executive Summary

Server `swisstopo-mcp` wurde gegen 36 anwendbare Best-Practice-Checks geprüft. 29 bestanden, 7 Findings dokumentiert (2 critical, 2 high, 3 medium, 0 low). Production-Readiness: erreicht.

**Production-Readiness:** YES

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swisstopo-mcp` |
| Audit-Datum | 2026-05-29 |
| Skill-Version | 1.0.0 |
| Catalog-Version | 68 checks (catalog_hash 091f446b...) |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 7 | 0 | 4 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 3 | 0 | 1 | 0 | 0 |
| OPS | 3 | 0 | 0 | 0 | 0 |
| SCALE | 1 | 0 | 0 | 0 | 0 |
| SDK | 3 | 0 | 1 | 0 | 0 |
| SEC | 11 | 0 | 1 | 0 | 0 |
| **Total** | **29** | **0** | **7** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| ARCH-005 | ARCH | critical | partial |
| SEC-009 | SEC | critical | partial |
| ARCH-004 | ARCH | high | partial |
| OBS-001 | OBS | high | partial |
| ARCH-002 | ARCH | medium | partial |
| ARCH-007 | ARCH | medium | partial |
| SDK-003 | SDK | medium | partial |

**Gesamt:** 7 Findings

---

## 5. Detail-Findings

### ARCH-002

## Finding: ARCH-002 — Tool-Beschreibung mit Use-Case-Tags

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-002
**PDF-Reference:** Sec 2.2
**Check-Status:** partial

### Evidence (already in place)
- Every tool has a meaningful one-sentence description; server-level instructions give cross-tool guidance

### Remaining Gaps
- Descriptions still lack <use_case>/<important_notes> tags and are mostly under the ~100-char median target

### Remediation
Expand tool descriptions to >=100 chars with <use_case>/<important_notes> tags; differentiate the three feature-query tools.

### Effort Estimate
S (<1d)


### ARCH-004

## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-004
**PDF-Reference:** Sec 2.1
**Check-Status:** partial

### Evidence (already in place)
- Tool handlers are transport-agnostic (only typed params; no request object)
- Server supports stdio + streamable-http

### Remaining Gaps
- Transport/host/port selected via ad-hoc sys.argv + os.environ rather than a pydantic-settings Settings object

### Remediation
Replace ad-hoc sys.argv/os.environ handling with a pydantic-settings Settings object (transport/host/port/log_level).

### Effort Estimate
S (<1d)


### ARCH-005

## Finding: ARCH-005 — Keine Hardcoded Secrets: Env-Vars / Secret Manager only

**Severity:** critical
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-005
**PDF-Reference:** Sec 2.1
**Check-Status:** partial

### Evidence (already in place)
- No hardcoded secrets (grep: 0). Server uses only key-less public APIs.
- .gitignore now present and ignores .env / .env.* (added PR #1)

### Remaining Gaps
- No .env.example with placeholders
- No gitleaks/trufflehog secret-scanning workflow in CI

### Remediation
Add a .env.example with placeholders and a gitleaks GitHub Action on push/PR.

### Effort Estimate
S (<1d)


### ARCH-007

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


### OBS-001

## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OBS-001
**PDF-Reference:** Sec 6.1
**Check-Status:** partial

### Evidence (already in place)
- Execution errors are caught and returned as a structured ToolResponse with is_error=true (models.py, PR #8) instead of raising
- Error paths covered by tests

### Remaining Gaps
- is_error is an envelope field, not the protocol-level CallToolResult.isError
- No standardized JSON-RPC error codes (-326xx/-320xx)

### Remediation
Surface handled errors via the protocol-level CallToolResult.isError and adopt standardized JSON-RPC error codes for protocol errors.

### Effort Estimate
M (1-3d)


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SDK-003
**PDF-Reference:** Sec 3.1
**Check-Status:** partial

### Evidence (already in place)
- Most tools are single fast upstream calls where progress reporting is unnecessary

### Remaining Gaps
- No tool injects ctx: Context; elevation_profile/oereb_extract provide no ctx.report_progress feedback

### Remediation
Inject ctx: Context into elevation_profile (and oereb_extract) and call ctx.report_progress/ctx.info for long operations.

### Effort Estimate
S (<1d)


### SEC-009

## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

**Severity:** critical
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-009
**PDF-Reference:** Sec 4.6
**Check-Status:** partial

### Evidence (already in place)
- No custom session handling; HTTP session IDs delegated to FastMCP
- auth_model=none and data is public read-only → no per-user session to bind; session hijacking has no privilege impact

### Remaining Gaps
- No user_id:session_id binding (not applicable without auth; would be required if auth is added)

### Remediation
Document that HTTP sessions are FastMCP-managed and carry no auth (public data). If auth is added later, bind session id to the validated user_id.

### Effort Estimate
S (<1d)


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **ARCH-005** (critical, partial)
2. **SEC-009** (critical, partial)
3. **ARCH-004** (high, partial)
4. **OBS-001** (high, partial)
5. **ARCH-002** (medium, partial)
6. **ARCH-007** (medium, partial)
7. **SDK-003** (medium, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| catalog_version | `68 checks (catalog_hash 091f446b...)` |
| applies_when_dsl_version | `1.0` |
| policy | `fail-or-partial` |
| audit_date | `2026-05-29` |


_Generated by tools/build_report.py — do not edit by hand._
