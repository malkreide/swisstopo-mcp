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

## Tracing (OBS-006)

`structlog` already emits a `duration_ms` per tool call. Tracing adds the
causal view: a slow tool call is attributable to the upstream request inside it
only if the two share a trace, which the httpx auto-instrumentation provides.

| Variable | Effect |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | **The switch.** Unset or empty → tracing is entirely off. |
| `OTEL_SERVICE_NAME` | Service name in the backend (default `swisstopo-mcp`). |
| `OTEL_RESOURCE_ATTRIBUTES` | Extra resource attributes, e.g. `deployment.environment=production`. |

These use the standard `OTEL_` prefix rather than `SWISSTOPO_`, so existing
OpenTelemetry tooling and collector sidecars pick them up unchanged.

Spans carry the tool name and whether the result was an error — **never the
tool arguments**. Coordinates, addresses and search terms are user input and do
not belong in an observability backend. There is also no `mcp.user.id`: the
server is unauthenticated, so no such identity exists.

Tracing initialises *before* the shared httpx client, because the
instrumentation patches the client class; a client built earlier would never
be traced.

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

The base manifest ships with `replicas: 1` on purpose. MCP Streamable-HTTP keeps
session state **per pod**, so a client's follow-up requests must reach the same
pod. Raising `replicas` on the plain Deployment breaks sessions on their second
request — intermittently, which reads like flaky clients rather than a
misconfiguration.

### The supported multi-replica path

Three artefacts, applied together:

| File | Provides |
|---|---|
| [`deploy/statefulset.yaml`](../deploy/statefulset.yaml) | A StatefulSet plus a **headless** Service, so each pod gets stable DNS. A ClusterIP Service hides pods behind one virtual IP, which defeats per-pod affinity. |
| [`deploy/haproxy.cfg`](../deploy/haproxy.cfg) | Affinity on `Mcp-Session-Id`: the id is **learned from the `initialize` response** and matched on later requests. |
| [`deploy/haproxy-deployment.yaml`](../deploy/haproxy-deployment.yaml) | Runs HAProxy with that config and exposes `swisstopo-mcp-lb`. |

```bash
kubectl apply -f deploy/kubernetes.yaml           # NetworkPolicy, base Service
kubectl delete deployment swisstopo-mcp           # replaced by the StatefulSet
kubectl apply -f deploy/statefulset.yaml
kubectl create configmap swisstopo-mcp-haproxy --from-file=deploy/haproxy.cfg
kubectl apply -f deploy/haproxy-deployment.yaml
```

Point your Ingress at **`swisstopo-mcp-lb`**, not at the application Service —
routing straight to the pods bypasses the affinity this arrangement exists for.

**HAProxy itself runs one replica, deliberately.** Each process holds its own
stick-table, so two instances behind a round-robin Service would learn different
halves of the session map — the same defect one layer up. Scaling it needs a
`peers` section so the instances replicate the table to each other; that is not
shipped, because an untested second config is exactly what this section is
correcting.

The base Service in `kubernetes.yaml` sets `sessionAffinity: ClientIP` as a
crude fallback. It is inert at one replica and it does **not** substitute for the
above: behind an ingress, kube-proxy sees the ingress pod as the source, so every
client looks like one client and lands on one backend — sessions survive, load
balancing does not.

### Why `stick on` is not enough

The obvious config is `stick on req.hdr(Mcp-Session-Id)`, and this repository
shipped exactly that. It does not work, and it looks like it does.

`stick on` is shorthand for `stick match` + `stick store-**request**`. The MCP
session id is minted by the *server* and returned in the response to
`initialize` — that request carries no `Mcp-Session-Id` at all, so nothing is
ever stored. The client's next request is the first to carry the header, misses
the empty table, gets round-robined to a replica that with three servers is
wrong two times in three, and is then pinned there until the entry expires.

The config therefore uses the canonical pattern for a server-generated
identifier:

```
stick store-response res.hdr(Mcp-Session-Id)
stick match          req.hdr(Mcp-Session-Id)
```

### Verifying affinity

The repository's tests check that the config and manifests agree with each other
— that the store-response directive is present, that the backends resolve to the
headless Service this repo creates, that the ConfigMap the Deployment mounts is
the one the command above builds. They **cannot** prove HAProxy routes
correctly; that needs a running cluster. Verify it manually once after applying:

```bash
# 1. Open a session and keep both the id and the pod that served it.
curl -sD- -X POST http://<lb>/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
       "protocolVersion":"2025-11-25","capabilities":{},
       "clientInfo":{"name":"affinity-check","version":"0"}}}' \
  | grep -i mcp-session-id

# 2. Send several follow-ups with that id. All must succeed — a 404 means the
#    request reached a pod that does not hold the session.
for i in $(seq 1 10); do
  curl -s -o /dev/null -w '%{http_code}\n' -X POST http://<lb>/mcp \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -H "Mcp-Session-Id: <id>" \
    -d '{"jsonrpc":"2.0","id":2,"method":"ping"}'
done

# 3. Confirm the stick-table actually holds the entry.
kubectl exec deploy/swisstopo-mcp-haproxy -- \
  sh -c 'echo "show table mcp_backend" | socat stdio /var/run/haproxy.sock'
```

Ten consecutive `200`s with three replicas is the signal: without affinity the
round-robin would land elsewhere within the first few requests.

**Failover is a deliberate non-goal.** Session state lives in the pod, so a pod
that dies takes its sessions with it — clients get `404` and must re-initialise.
Affinity routes sessions; it does not replicate them. Surviving pod loss needs a
shared session store (option C below), which is not implemented.

### Alternatives

- **NGINX Ingress cookie affinity**
  ([`deploy/ingress-sticky-sessions.yaml`](../deploy/ingress-sticky-sessions.yaml))
  works only for clients that persist cookies. MCP hosts such as Claude Desktop
  and `mcp-remote` are not browsers, so this is **not** a general substitute —
  it is listed for the browser-client case only.
- **A shared session store** (e.g. Redis via a FastMCP `SessionManager`) removes
  the affinity requirement entirely and would also survive pod loss. Not
  implemented here.

