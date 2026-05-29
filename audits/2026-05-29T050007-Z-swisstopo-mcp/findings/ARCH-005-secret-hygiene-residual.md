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
