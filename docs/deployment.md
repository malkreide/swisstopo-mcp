# Deployment & Container Hardening

The server is **local-first (stdio)**. This document covers the optional
containerised HTTP deployment and the hardening it ships with — audit finding
**SEC-007** (container sandboxing), with the Kubernetes `NetworkPolicy` also
covering the network-layer half of **SEC-021** (egress).

## Build & run (Docker)

```bash
docker build -t swisstopo-mcp .

# Run hardened: read-only root fs, tmpfs /tmp, no extra caps, no privilege escalation
docker run --rm \
  --read-only --tmpfs /tmp \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  -e SWISSTOPO_ALLOWED_ORIGINS="https://your-client.example.com" \
  -e SWISSTOPO_ALLOWED_HOSTS="swisstopo-mcp.example.com" \
  -p 8000:8000 \
  swisstopo-mcp
```

Health check: `GET http://localhost:8000/healthz` → `{"status":"ok"}`. The MCP
endpoint is served at `/mcp`.

## Host and origin allow-lists (SDK-004 / SCALE-001)

Two separate layers guard the HTTP transport, and they are configured
separately because they run at different points in the request:

| Setting | Layer | Effect when a value is missing |
|---|---|---|
| `SWISSTOPO_ALLOWED_ORIGINS` | CORS + SDK transport security | browser client is refused |
| `SWISSTOPO_ALLOWED_HOSTS` | SDK transport security only | **every** MCP request returns 421 |

The MCP SDK enables DNS-rebinding protection by default and ships a
loopback-only allow-list. Behind an ingress the forwarded `Host` is therefore
unknown to it, and the server answers `421 Invalid Host header` on `/mcp` —
while `/healthz` keeps returning 200, so a Kubernetes readiness probe stays
green and the deployment looks healthy while nothing works.

Set `SWISSTOPO_ALLOWED_HOSTS` to the hostname your clients actually use. Both
lists always include loopback with any port, so the local `--http` workflow
needs no configuration.

Do **not** work around a 421 by disabling DNS-rebinding protection — SEC-005
depends on it. The fix is to name the right hosts.

## Hardening applied (SEC-007)

| Control | Where |
|---|---|
| Non-root user, fixed UID/GID 10001 | `Dockerfile` (`USER 10001`) + k8s `runAsNonRoot` / `runAsUser` |
| No privilege escalation | k8s `allowPrivilegeEscalation: false`, Docker `--security-opt no-new-privileges` |
| Read-only root filesystem | k8s `readOnlyRootFilesystem: true` + `tmpfs` `/tmp`; Docker `--read-only --tmpfs /tmp` |
| Drop all Linux capabilities | k8s `capabilities.drop: ["ALL"]`, Docker `--cap-drop ALL` |
| seccomp default profile | k8s `seccompProfile: RuntimeDefault` (Docker default) |
| Minimal base image | `python:3.11-slim`, multi-stage build |
| `0.0.0.0` only in container, never a code default | `SWISSTOPO_HTTP_HOST` env (code default stays `127.0.0.1`, SEC-016) |

No filesystem tools are exposed, so no host paths are mounted.

## Kubernetes

`deploy/kubernetes.yaml` contains a hardened `Deployment`, a `Service`, and an
egress `NetworkPolicy`. Replace the image reference and set
`SWISSTOPO_ALLOWED_ORIGINS` **and `SWISSTOPO_ALLOWED_HOSTS`** before applying:

```bash
kubectl apply -f deploy/kubernetes.yaml
```

## Scaling out (SCALE-002)

The manifest ships with `replicas: 1` on purpose. MCP Streamable-HTTP keeps
session state **per pod**, so a client's follow-up requests must reach the same
pod. Before raising `replicas`, add one of:

- **Session affinity on `Mcp-Session-Id`** — HAProxy `stick on req.hdr(Mcp-Session-Id)`
  (preferred), or NGINX Ingress cookie affinity. See
  [`deploy/ingress-sticky-sessions.yaml`](../deploy/ingress-sticky-sessions.yaml).
- **A shared session store** (e.g. Redis via a FastMCP `SessionManager`) so any
  pod can serve any session.

Then raise `replicas` in `deploy/kubernetes.yaml`.

