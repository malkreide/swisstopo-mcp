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
| Egress | Code-layer HTTPS allow-list (`ALLOWED_HOSTS` frozenset) restricted to `*.geo.admin.ch` and the cantonal OEREB endpoints (SEC-004 / SEC-021) — see [docs/network-egress.md](docs/network-egress.md) |
| Redirects | `follow_redirects=False` on the shared `httpx` client, so an upstream cannot redirect to an off-list host (SEC-005) |
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

- **Tool allow-listing** belongs to the MCP host/gateway that aggregates
  multiple servers, not to an individual server exposing a fixed, read-only
  tool set. Until a central gateway exists, the risk is bounded by the egress
  allow-list and the read-only tool surface.
- **Cross-server tool-poisoning detection** is a host/gateway responsibility.
  This server's tool definitions are version-controlled and shipped from this
  repository; there is no dynamic or remote tool registration.

## Re-evaluation triggers

These decisions should be revisited if the server ever:

- gains **write/send** capability or starts processing **PII**, or
- registers tools **dynamically** / from remote sources, or
- is aggregated behind a shared MCP gateway (then implement tool
  allow-listing and poisoning detection there).
