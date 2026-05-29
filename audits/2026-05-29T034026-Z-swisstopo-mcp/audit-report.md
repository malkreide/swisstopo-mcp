# MCP-Server Audit-Report — `swisstopo-mcp`

**Audit-Datum:** 2026-05-29
**Skill-Version:** 1.0.0
**Catalog-Version:** 68 checks (catalog_hash 091f446b...)

---

## 1. Executive Summary

Server `swisstopo-mcp` wurde gegen 36 anwendbare Best-Practice-Checks geprüft. 12 bestanden, 24 Findings dokumentiert (4 critical, 11 high, 9 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: SDK-001.

**Production-Readiness:** NO

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
| ARCH | 4 | 0 | 7 | 0 | 0 |
| CH | 0 | 0 | 1 | 0 | 0 |
| OBS | 1 | 1 | 2 | 0 | 0 |
| OPS | 2 | 0 | 1 | 0 | 0 |
| SCALE | 0 | 0 | 1 | 0 | 0 |
| SDK | 0 | 1 | 3 | 0 | 0 |
| SEC | 5 | 0 | 7 | 0 | 0 |
| **Total** | **12** | **2** | **22** | **0** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| ARCH-005 | ARCH | critical | partial |
| SEC-004 | SEC | critical | partial |
| SEC-009 | SEC | critical | partial |
| SEC-019 | SEC | critical | partial |
| ARCH-004 | ARCH | high | partial |
| OBS-001 | OBS | high | partial |
| OBS-002 | OBS | high | partial |
| OPS-003 | OPS | high | partial |
| SCALE-002 | SCALE | high | partial |
| SDK-001 | SDK | high | fail |
| SDK-004 | SDK | high | partial |
| SEC-005 | SEC | high | partial |
| SEC-007 | SEC | high | partial |
| SEC-018 | SEC | high | partial |
| SEC-021 | SEC | high | partial |
| ARCH-002 | ARCH | medium | partial |
| ARCH-003 | ARCH | medium | partial |
| ARCH-007 | ARCH | medium | partial |
| ARCH-008 | ARCH | medium | partial |
| ARCH-012 | ARCH | medium | partial |
| CH-004 | CH | medium | partial |
| OBS-003 | OBS | medium | fail |
| SDK-002 | SDK | medium | partial |
| SDK-003 | SDK | medium | partial |

**Gesamt:** 24 Findings

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


### ARCH-003

## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-003
**PDF-Reference:** Sec 2.2
**Check-Status:** partial

### Observed Behavior
geocoding returns the bare string 'Keine Ergebnisse gefunden.'; no match_type or suggestions.

### Expected Behavior
Empty results should carry match_type and an actionable note (term refinement or fuzzy suggestions).

### Evidence
- OEREB tools return actionable 'not found' messages with next steps (oereb.py:84-88, 124-125)

Gaps:
- Geocoding returns the bare string 'Keine Ergebnisse gefunden.' (geocoding.py:53) — classic empty-result anti-pattern
- No match_type field and no fuzzy/suggestion fallback for empty results

### Risk Description
Bare 'no results' encourages LLM hallucination or premature abort.

### Remediation
Return a structured note with match_type=none and a hint (e.g. suggest broadening the query or checking spelling) for empty geocode/search results.

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

### Observed Behavior
Handlers are transport-agnostic, but transport is chosen via ad-hoc sys.argv parsing rather than a settings object.

### Expected Behavior
Configuration via a pydantic-settings Settings object; transport selectable by env var.

### Evidence
- Tool handlers take only typed Pydantic params, no request/transport object (server.py:45-274)
- Server supports both stdio (default) and streamable-http (server.py:277-285)
- Tool logic is identical across transports (registration is transport-independent)

Gaps:
- Transport is selected by ad-hoc sys.argv parsing (server.py:280-283), not a pydantic-settings Settings object
- No ctx: Context used for client info

### Risk Description
Ad-hoc argv parsing is harder to test and to extend for cloud config.

### Remediation
Introduce a pydantic-settings Settings (transport, host, port, log_level) and drive mcp.run from it.

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


### ARCH-007

## Finding: ARCH-007 — Capability-Aggregation: Composability intern, Atomarität extern

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-007
**PDF-Reference:** Sec 2.3
**Check-Status:** partial

### Observed Behavior
Layer discovery requires chaining search_layers -> identify/find -> get_feature; no internal multi-source aggregation.

### Expected Behavior
Tools should return thought-complete results; where useful, aggregate internally with asyncio.gather.

### Evidence
- Most tools return self-contained results (geocode, get_height, oereb_extract, map_url)
- elevation_profile aggregates multiple points into one result (height.py)

Gaps:
- Layer discovery is a multi-call chain (search_layers -> get_feature returns IDs used in follow-ups)
- No asyncio.gather-style internal aggregation across sources

### Risk Description
Chaining increases latency and chaining-hallucination risk.

### Remediation
Consider a higher-level tool that resolves a layer query and returns features in one call for the common case; document the discovery chain otherwise.

### Effort Estimate
M (1-3d)


### ARCH-008

## Finding: ARCH-008 — Drei Primitive nutzen: Tools, Resources und Prompts

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-008
**PDF-Reference:** Anhang A2
**Check-Status:** partial

### Observed Behavior
Server exposes Tools only; no Resources/Prompts and no documented rationale.

### Expected Behavior
Use >=2 primitives, or document why tools-only.

### Evidence
- Server exposes Tools only; no @mcp.resource or @mcp.prompt (grep: 0 hits)

Gaps:
- Uses only 1 of 3 primitives and provides no documented justification for tools-only (read-only static lookups like map layers are Resource candidates)

### Risk Description
Static lookups (e.g. notable map layers) are Resource candidates; tools-only inflates the manifest.

### Remediation
Either add a Resource for static layer catalogs, or add a README 'MCP-Primitive' section justifying tools-only for this phase.

### Effort Estimate
S (<1d)


### ARCH-012

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


### CH-004

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


### OBS-001

## Finding: OBS-001 — Protocol vs. Execution Errors: korrekte Trennung

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OBS-001
**PDF-Reference:** Sec 6.1
**Check-Status:** partial

### Observed Behavior
Execution errors are returned as plain German text (not raised), but not flagged isError and without standardized codes.

### Expected Behavior
Application errors returned with isError:true; protocol errors use standard JSON-RPC codes.

### Evidence
- Execution errors are caught and returned as user-friendly text, not raised, via handle_api_error (api_client.py:55-77; used in geocoding.py:98, oereb.py:101)
- Tests cover error paths (e.g. test_geocoding.py test_geocode_api_error)

Gaps:
- Errors are returned as plain text, not as structured tool results with isError: true
- No standardized JSON-RPC error codes (-326xx / -320xx) for protocol-level errors

### Risk Description
Clients cannot machine-distinguish an error result from a normal text result.

### Remediation
Return structured error content (isError) for handled execution errors; let unexpected errors bubble for framework JSON-RPC handling.

### Effort Estimate
M (1-3d)


### OBS-002

## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OBS-002
**PDF-Reference:** Sec 6.2
**Check-Status:** partial

### Observed Behavior
Known errors are masked nicely, but the generic fallback returns f'{type(e).__name__}: {e}', and FastMCP has no mask_error_details=True.

### Expected Behavior
No raw exception strings reach the client; mask_error_details enabled.

### Evidence
- handle_api_error produces clean German messages for known HTTP/timeout/connect errors (api_client.py:59-75)
- No traceback.format_exc()/sys.exc_info() in any tool return

Gaps:
- Generic fallback api_client.py:77 returns f'{type(e).__name__}: {e}' — raw exception string may leak internals (e.g. URLs)
- FastMCP not initialized with mask_error_details=True

### Risk Description
The fallback can leak internal detail (e.g. request URLs) into the LLM context.

### Remediation
Replace the generic fallback with a constant user-message and log the detail to stderr; set FastMCP(mask_error_details=True).

### Effort Estimate
S (<1d)


### OBS-003

## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OBS-003
**PDF-Reference:** Sec 6.3
**Check-Status:** fail

### Observed Behavior
No structured logger and no logging at all in the codebase.

### Expected Behavior
structlog/loguru with JSON output and per-call bound context.

### Evidence
- No print() in src/ (no stdout pollution)

Gaps:
- No structured logger (structlog/loguru) in dependencies and no logging used at all
- No JSON/logfmt output, no severity levels, no per-call bound context (tool/session/correlation id)

### Risk Description
No operational visibility; incidents are hard to diagnose.

### Remediation
Add structlog (configured to sys.stderr, JSON renderer) and emit bound info/error logs per tool call. Keep stdout clean for stdio.

### Effort Estimate
M (1-3d)


### OPS-003

## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** OPS-003
**PDF-Reference:** Anhang C4
**Check-Status:** partial

### Observed Behavior
De-facto Phase 1 (all read-only) but phase is not declared and there is no roadmap.

### Expected Behavior
Explicit phase declaration in README and a docs/roadmap.md.

### Evidence
- De-facto Phase 1 (read-only wrapper): all 13 tools are readOnlyHint=True, no destructive tools

Gaps:
- Phase is not explicitly declared in README
- No docs/roadmap.md (no docs/ directory at all)

### Risk Description
Reviewers cannot tell what is in/out of scope for the current phase.

### Remediation
Add a 'Phase' section to README (Phase 1: read-only wrapper) and a docs/roadmap.md.

### Effort Estimate
S (<1d)


### SCALE-002

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


### SDK-001

## Finding: SDK-001 — FastMCP Lifespan via @asynccontextmanager + AsyncExitStack

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SDK-001
**PDF-Reference:** Sec 3.1
**Check-Status:** fail

### Observed Behavior
FastMCP is created without a lifespan; api_client._get_client() builds a brand-new httpx.AsyncClient on every tool call (`async with await _get_client()`).

### Expected Behavior
A @asynccontextmanager lifespan should create one shared httpx.AsyncClient on server startup and close it on shutdown; tools reuse it for connection pooling.

### Evidence
- FastMCP is constructed without lifespan (server.py:12-24)

Gaps:
- api_client.py:26-32 _get_client() creates a NEW httpx.AsyncClient per request (used via 'async with await _get_client()' in every handler) — exactly the documented anti-pattern: no connection pooling/reuse
- No @asynccontextmanager lifespan, no shared client on server.state

### Risk Description
A new client per call means no connection pooling (slower, more TCP/TLS handshakes) and risks resource/socket leakage under load or on errors.

### Remediation
Add a lifespan to FastMCP that opens a single httpx.AsyncClient (timeout=30, follow_redirects=False) and stores it on server.state; refactor geo_admin_request/stac_request/oereb handlers to use the shared client. Close it in the finally block.

### Effort Estimate
M (1-3d)


### SDK-002

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


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SDK-003
**PDF-Reference:** Sec 3.1
**Check-Status:** partial

### Observed Behavior
No tool injects ctx: Context; no progress reporting or ctx logging.

### Expected Behavior
Long-running tools (>2s) take ctx and report progress; tools log via ctx.info.

### Evidence
- Most tools are single fast upstream calls where progress reporting is unnecessary

Gaps:
- No tool injects ctx: Context (grep: 0 hits) — no ctx.report_progress/ctx.info
- Potentially slower tools (elevation_profile, oereb_extract) provide no progress feedback

### Risk Description
Low for fast single-call tools; elevation_profile/oereb give no progress feedback.

### Remediation
Add ctx: Context to elevation_profile (and oereb_extract) and call ctx.report_progress/ctx.info.

### Effort Estimate
S (<1d)


### SDK-004

## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SDK-004
**PDF-Reference:** Sec 3.1
**Check-Status:** partial

### Observed Behavior
No CORS middleware configured, yet README advertises SSE for browser access.

### Expected Behavior
CORS with expose_headers including Mcp-Session-Id and explicit allow_origins.

### Evidence
- Streamable-HTTP transport is supported (server.py:283)

Gaps:
- No CORS middleware / expose_headers configured anywhere in src/
- README advertises 'Cloud Deployment (SSE for browser access)' but without Access-Control-Expose-Headers: Mcp-Session-Id, browser clients would break

### Risk Description
Browser clients cannot read Mcp-Session-Id and break on follow-up requests.

### Remediation
Wrap the streamable-http app in CORSMiddleware with expose_headers=['Mcp-Session-Id'], allow_headers including it, and an env-driven allow_origins list (no wildcard with credentials).

### Effort Estimate
S (<1d)


### SEC-004

## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

**Severity:** critical
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-004
**PDF-Reference:** Sec 4.4
**Check-Status:** partial

### Observed Behavior
follow_redirects=True is set on the shared httpx config (api_client.py:31); no resolved-IP blocklist or explicit https enforcement. No tool takes a user URL, but redirects from upstream are followed.

### Expected Behavior
HTTPS enforced before each request; resolved IP checked against private/link-local/loopback blocklist (incl. 169.254.169.254); redirects either disabled or re-validated.

### Evidence
- No tool accepts a user-supplied URL; all request hosts are fixed constants (api_client.py:10-12, wmts.py:48) or a hardcoded canton registry (oereb.py:15-18)
- All upstream bases are https://

Gaps:
- api_client.py:31 sets follow_redirects=True — an upstream redirect could reach internal/metadata endpoints (redirect-based SSRF)
- No resolved-IP blocklist for private/link-local ranges (169.254.169.254 not blocked)
- No explicit https scheme enforcement before request

### Risk Description
A compromised/misbehaving upstream could 3xx-redirect the client to an internal address or cloud-metadata endpoint, enabling SSRF.

### Remediation
Set follow_redirects=False (or validate each redirect target host against the allow-list). Even with fixed hosts, add an assert on resolved IP not in private ranges. Keep https-only.

### Effort Estimate
S (<1d)


### SEC-005

## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-005
**PDF-Reference:** Sec 4.4
**Check-Status:** partial

### Observed Behavior
No DNS pinning; httpx resolves per request. Combined with follow_redirects=True this leaves a TOCTOU/rebinding path, though hosts are fixed trusted federal domains.

### Expected Behavior
Resolve once, pin the IP for the TCP connection, keep the original hostname for TLS SNI/cert validation.

### Evidence
- Request hosts are fixed, trusted federal domains; no user-controlled hostname, so DNS-rebinding surface is minimal

Gaps:
- No DNS pinning (resolve-once + pinned IP); httpx default resolution
- follow_redirects=True (api_client.py:31) reintroduces a rebinding/redirect risk path

### Risk Description
Low in practice (fixed trusted hosts), but redirect-following weakens the guarantee.

### Remediation
Primary mitigation is disabling redirect-following (see SEC-004). DNS pinning is optional defense-in-depth given the fixed host set.

### Effort Estimate
S (<1d)


### SEC-007

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


### SEC-009

## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

**Severity:** critical
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-009
**PDF-Reference:** Sec 4.6
**Check-Status:** partial

### Observed Behavior
No custom session handling; HTTP session IDs are delegated entirely to FastMCP. auth_model=none so there is no per-user binding.

### Expected Behavior
For authenticated HTTP servers, session IDs must be crypto-random and bound to a validated user_id.

### Evidence
- No custom/insecure session handling in src/ — HTTP session IDs are fully delegated to FastMCP's streamable-http manager
- auth_model=none and data is public read-only, so there is no per-user session to bind

Gaps:
- Session security relies entirely on FastMCP defaults; not independently verified in-repo
- No user_id:session_id binding (not applicable without auth, but undocumented)

### Risk Description
Low — public, read-only data; session hijacking yields only access already available to anyone.

### Remediation
Document that HTTP mode relies on FastMCP-managed sessions and carries no auth (public data). If auth is ever added, implement user_id:session_id binding.

### Effort Estimate
S (<1d)


### SEC-018

## Finding: SEC-018 — Input-Validation an Tool-Boundaries (Pydantic strict / Zod)

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-018
**PDF-Reference:** Sec 3 / Sec 4 (Defense-in-Depth)
**Check-Status:** partial

### Observed Behavior
All inputs are Pydantic v2 models with extra='forbid' and ge/le + min/max bounds. Missing strict=True and whitelist patterns on free-text fields.

### Expected Behavior
strict=True to stop coercion; whitelist 'pattern' on free-text args.

### Evidence
- All tool inputs are Pydantic models with extra='forbid' (geocoding/rest_api/stac/height/oereb)
- Numeric ranges bounded (ge/le): limit 1-50, lat 45.8-47.9, lon 5.9-10.5, zoom 1-13, tolerance 0-200
- String fields bounded: min_length/max_length (e.g. search_text 2-200)

Gaps:
- model_config does not set strict=True — Pydantic coercion is allowed ('1' -> 1)
- Free-text fields (search_text, layer, search_field, topics) have no whitelist 'pattern' constraint

### Risk Description
Type coercion can mask bugs; unconstrained free-text widens the injection/encoding surface (low given downstream is HTTP query params).

### Remediation
Add strict=True to each model_config and add conservative regex patterns to search_text/layer/search_field/topics.

### Effort Estimate
S (<1d)


### SEC-019

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


### SEC-021

## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-021
**PDF-Reference:** Anhang B5 + B12
**Check-Status:** partial

### Observed Behavior
Outbound hosts are constrained only implicitly via hardcoded base constants and the canton registry; no explicit enforcement, follow_redirects=True can bypass, no network policy.

### Expected Behavior
A frozenset code-layer allow-list checked before each request, plus network-layer egress control and docs.

### Evidence
- Outbound hosts are effectively constrained by hardcoded base constants and a fixed canton registry dict (api_client.py:10-12, oereb.py:15-18)

Gaps:
- No explicit assert_host_allowed()/frozenset egress allow-list enforced before requests
- follow_redirects=True can bypass the implicit allow-list to an arbitrary host
- No network-layer egress policy and no docs/network-egress.md

### Risk Description
Without enforcement, a future code change or a redirect could reach an unintended host.

### Remediation
Introduce ALLOWED_HOSTS = frozenset({...}) and assert_host_allowed(url) called in _get_client callers; set follow_redirects=False; document in docs/network-egress.md.

### Effort Estimate
M (1-3d)


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **ARCH-005** (critical, partial)
2. **SEC-004** (critical, partial)
3. **SEC-009** (critical, partial)
4. **SEC-019** (critical, partial)
5. **ARCH-004** (high, partial)
6. **OBS-001** (high, partial)
7. **OBS-002** (high, partial)
8. **OPS-003** (high, partial)
9. **SCALE-002** (high, partial)
10. **SDK-001** (high, fail)
11. **SDK-004** (high, partial)
12. **SEC-005** (high, partial)
13. **SEC-007** (high, partial)
14. **SEC-018** (high, partial)
15. **SEC-021** (high, partial)
16. **ARCH-002** (medium, partial)
17. **ARCH-003** (medium, partial)
18. **ARCH-007** (medium, partial)
19. **ARCH-008** (medium, partial)
20. **ARCH-012** (medium, partial)
21. **CH-004** (medium, partial)
22. **OBS-003** (medium, fail)
23. **SDK-002** (medium, partial)
24. **SDK-003** (medium, partial)

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
