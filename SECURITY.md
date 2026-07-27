# Security Policy & Posture

[🇩🇪 Deutsche Version](SECURITY.de.md)

`swisstopo-mcp` was hardened against the internal MCP best-practice audit
catalogue (see [`audits/`](audits/)). This document summarises the security
posture and records the controls that are deliberately handled at the
portfolio/gateway layer rather than inside this single server.

## Reporting a vulnerability

Please open a private security advisory on the GitHub repository, or contact the
maintainer listed in [`README.md`](README.md). Do not file public issues for
exploitable vulnerabilities.

## Posture summary

This is a **read-only**, **no-PII**, **public-open-data** MCP server. All 13
tools only query a fixed allow-list of Swiss federal and cantonal geodata hosts.
Hardening already in place:

| Area | Control |
|---|---|
| Egress | Code-layer allow-list (`ALLOWED_HOSTS` frozenset) enforcing HTTPS-only and a fixed host set. The authoritative list lives in [docs/network-egress.md](docs/network-egress.md) — it is deliberately not repeated here, so it cannot go stale (SEC-004 / SEC-021) |
| Redirects | `follow_redirects=False` on the shared `httpx` client, so an upstream cannot redirect to an off-list host (SEC-004) |
| SSRF | Scheme check plus a resolved-IP guard rejecting hosts that answer with a private or link-local address (SEC-004) |
| DNS pinning | **Not implemented** (SEC-005). The reachable host set is a fixed frozenset resolved per request, so a rebinding window exists between the guard's lookup and the connection. Mitigating factors: no authentication, no secrets in requests, public data only. The Kubernetes deployment additionally restricts egress at the network layer; the local stdio path has no such compensation |
| TLS | Certificate verification on by default for all upstream requests |
| Input | Pydantic v2 strict validation at every tool boundary (SEC-018) |
| Secrets | Env-vars only; `.gitignore` guards `.env`; no hardcoded secrets (ARCH-005) |
| Errors | Upstream/exception bodies logged to stderr, never forwarded to the model (OBS-002) |
| Stdout | Reserved for the JSON-RPC stream; logging pinned to stderr |
| Trifecta | At most 1 of 3 lethal-trifecta legs present — read-only, public data, no write/send (SEC-019) |
| Container | Hardened `Dockerfile` (non-root, read-only root FS, dropped capabilities) for HTTP deployments (SEC-007) — see [docs/deployment.md](docs/deployment.md) |

See [`audits/`](audits/) for the full reports and [CHANGELOG.md](CHANGELOG.md)
for the hardening history.

## Read-only by design (Phase 1)

This server is in **Phase 1 — read-only wrapper**. All 13 tools are
`readOnlyHint: true` / `destructiveHint: false`; there are no write or send
capabilities. Later phases are tracked in [docs/roadmap.md](docs/roadmap.md).

## Sessions & authentication

The server is unauthenticated by design — it serves only public open data. Over
HTTP, session IDs are managed entirely by the FastMCP framework; there is no
per-user state, so there is nothing user-specific to bind a session to. If an
authenticated deployment is ever introduced, session IDs must be bound to the
validated user identity (audit finding SEC-009).

## Portfolio-level controls

The following concerns are **not** implemented inside this server by design.
They are portfolio-wide and best enforced at an MCP gateway / host layer; the
residual risk here is low because the server is read-only and only reaches a
fixed set of trusted public-data providers.

- **Tool allow-listing** (SEC-014) belongs to the MCP host/gateway that
  aggregates multiple servers, not to an individual server exposing a fixed,
  read-only tool set. Until a central gateway exists, the risk is bounded by two
  facts, both enforced in CI rather than merely asserted here:
  - every tool is read-only — `tests/test_tool_hygiene.py` fails if one is not,
    so this premise cannot quietly become false;
  - egress is a code-level frozenset in
    [`src/swisstopo_mcp/api_client.py`](src/swisstopo_mcp/api_client.py), kept in
    sync with [docs/network-egress.md](docs/network-egress.md) by a test.

  All 23 tools carry the `swisstopo_` prefix (SEC-022), so a future gateway
  allow-list can name them unambiguously.

- **Cross-server tool-poisoning detection** (SEC-015) is a host/gateway
  responsibility — no single server can see across the set. What *is* covered
  here today: tool definitions are version-controlled and shipped from this
  repository, there is no dynamic or remote registration, and
  `tests/test_tool_hygiene.py` scans this server's own descriptions for
  invisible characters and override phrasing (German, French and English), while
  `tool-hashes.json` pins name, description and input schema per tool so a
  change cannot ship unreviewed.

  This is a self-scan, not cross-server detection. It cannot see what another
  server declares.

## Re-evaluation triggers

These decisions should be revisited if the server ever:

- gains **write/send** capability or starts processing **PII** — this voids
  SEC-014's risk-bounding argument outright, which is why the read-only premise
  is asserted by a test, or
- gains any tool whose description is **config-driven or remotely sourced**
  rather than written in this repository — the self-scan only covers what is
  committed here, or
- registers tools **dynamically** / from remote sources, or
- is aggregated behind a shared MCP gateway (then implement tool
  allow-listing and poisoning detection there, with this server's findings
  SEC-014 and SEC-015 as the input to that work).
