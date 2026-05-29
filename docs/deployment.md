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
  -p 8000:8000 \
  swisstopo-mcp
```

Health check: `GET http://localhost:8000/healthz` → `{"status":"ok"}`. The MCP
endpoint is served at `/mcp`.

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
`SWISSTOPO_ALLOWED_ORIGINS` before applying:

```bash
kubectl apply -f deploy/kubernetes.yaml
```

If you scale `replicas` above 1 over HTTP, also address sticky sessions /
shared session state (audit finding SCALE-002): enable LB affinity on the
`Mcp-Session-Id` header or run a shared session store.
