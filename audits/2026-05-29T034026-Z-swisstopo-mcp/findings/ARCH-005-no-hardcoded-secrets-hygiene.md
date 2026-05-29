## Finding: ARCH-005 — Keine Hardcoded Secrets: Env-Vars / Secret Manager only

**Severity:** critical
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-005
**PDF-Reference:** Sec 2.1
**Check-Status:** partial

### Observed Behavior
No secrets in code (server uses key-less public APIs). But there is no .gitignore, no .env.example, and no secret-scanning CI.

### Expected Behavior
A .gitignore covering .env*, a .env.example, and a gitleaks/trufflehog CI step.

### Evidence
- No hardcoded secrets in src/ (grep for api_key/password/secret/token literals: 0 hits)
- Only env-var usage is non-secret: oereb.py:23 os.environ.get('SWISSTOPO_OEREB_CANTONS', 'ZH')
- Server uses only public, key-less APIs (api_client.py:10-12)

Gaps:
- No .gitignore in repo — a future .env would not be ignored
- No .env.example present
- No secret-scanning workflow (gitleaks/trufflehog) in .github/workflows/

### Risk Description
A future contributor adding a secret has no guardrails (un-ignored .env, no scan).

### Remediation
Add .gitignore (.env, .env.local, *.secrets), a .env.example, and a gitleaks GitHub Action on push/PR.

### Effort Estimate
S (<1d)
