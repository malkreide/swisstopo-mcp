## Finding: SCALE-001 — Streamable HTTP statt stdio für Cloud-Deployments

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SCALE-001
**PDF-Reference:** Sec 5.1

### Observed Behavior

The transport architecture is right, but the cloud endpoint does not answer `initialize` when reached under the hostname the deployment actually uses.

- Transport is selectable, not hardcoded to stdio: `--http` switches to Streamable HTTP served by uvicorn, otherwise `mcp.run()` (stdio) — `src/swisstopo_mcp/server.py:686-701`. Host and port come from pydantic-settings env vars `SWISSTOPO_HTTP_HOST` / `SWISSTOPO_HTTP_PORT` (`src/swisstopo_mcp/config.py:22-24`), with `--port` as an override (`src/swisstopo_mcp/server.py:693-694`).
- The container/cloud path selects HTTP explicitly in the image manifest: `CMD ["python", "-m", "swisstopo_mcp.server", "--http", "--port", "8000"]` (`Dockerfile:38`) with `SWISSTOPO_HTTP_HOST=0.0.0.0` set only in the container (`Dockerfile:24-26`); `deploy/kubernetes.yaml:38-45` exposes containerPort 8000 and re-sets the env var. No stdio in the cloud path.
- No legacy WebSocket transport anywhere: a grep for `websocket` / `ws://` / `wss://` across `src/` returns nothing; the app is built from `mcp.streamable_http_app()` (`src/swisstopo_mcp/server.py:674`).
- **Runtime (Modus 2), localhost:** the HTTP endpoint works when reached with a localhost `Host` header. `POST /mcp` initialize returns HTTP 200 with a full capabilities/serverInfo response (`serverInfo` `swisstopo_mcp`, `protocolVersion` `2025-06-18`) and an `mcp-session-id` header; `GET /healthz` returns 200 `{"status":"ok"}` (`src/swisstopo_mcp/server.py:671-675`).
- **Runtime defect (reproduced against a running instance):** started with `SWISSTOPO_HTTP_HOST=0.0.0.0` and called as `POST /mcp` with `Host: swisstopo-mcp.example.com` — the hostname `deploy/ingress-sticky-sessions.yaml` forwards — the server returns **HTTP 421 "Invalid Host header"**, while `GET /healthz` with the same `Host` still returns **HTTP 200**.

Root cause is identical to SDK-004: `transport_security` is never passed to `FastMCP(...)` (`src/swisstopo_mcp/server.py:42-44`; the identifier appears nowhere in the repository). mcp 1.28.1 therefore auto-pins `allowed_hosts` to `[127.0.0.1:*, localhost:*, [::1]:*]` because FastMCP's internal host stays `127.0.0.1` (`mcp/server/fastmcp/server.py:177-183`), regardless of the uvicorn bind address.

Secondary observations:

- Transport selection is by CLI flag (`--http`), not by an env var such as `MCP_TRANSPORT`. Acceptable, since the deployment manifest sets it explicitly (`Dockerfile:38`), but the transport cannot be switched by env alone in a K8s Deployment without overriding the command.
- No deployment-level smoke test asserts that `initialize` returns 200 through the public hostname.

### Expected Behavior

Per the check's Pass Criteria:

- Env-based transport selection covering stdio and streamable-http/sse
- The cloud deployment uses streamable-http or sse, not stdio
- No WebSocket implementation remains in the code
- **The cloud endpoint answers `initialize` with HTTP 200** — the criterion that fails here, since it must hold for requests carrying the deployment's real hostname, not only for `Host: 127.0.0.1`

### Evidence

- File: `src/swisstopo_mcp/server.py:42-44` — `FastMCP(...)` constructed without `transport_security=`.
- File: `src/swisstopo_mcp/server.py:686-701` — `--http` / uvicorn vs `mcp.run()` transport selection.
- File: `Dockerfile:38` and `Dockerfile:24-26` — cloud path pins `--http --port 8000` with `SWISSTOPO_HTTP_HOST=0.0.0.0`.
- File: `deploy/kubernetes.yaml:38-45` (containerPort/env), `deploy/kubernetes.yaml:49-60` (liveness/readiness probes on `/healthz`).
- File: `deploy/ingress-sticky-sessions.yaml` — routes MCP traffic with `Host: swisstopo-mcp.example.com`.
- Upstream: mcp 1.28.1 `mcp/server/fastmcp/server.py:177-183` — auto-derived localhost-only `allowed_hosts`.
- Runtime probe (auditor, Modus 2):
  ```
  POST /mcp     Host: 127.0.0.1:8000                -> HTTP 200 + mcp-session-id
  POST /mcp     Host: swisstopo-mcp.example.com     -> HTTP 421 "Invalid Host header"
  GET  /healthz Host: swisstopo-mcp.example.com     -> HTTP 200 {"status":"ok"}
  ```

### Risk Description

As shipped, `deploy/kubernetes.yaml` + `deploy/ingress-sticky-sessions.yaml` route MCP traffic with `Host: swisstopo-mcp.example.com`, so **every MCP request receives HTTP 421** — while liveness and readiness probes (`deploy/kubernetes.yaml:49-60`, path `/healthz`) stay green, because `/healthz` is mounted outside the MCP app (`src/swisstopo_mcp/server.py:671-675`) and is not host-validated.

That is a silent-failure deployment, precisely the failure mode SCALE-001 names: "Server startet, Health-Check grün, aber Client-Verbindungen schlagen fehl." Concretely:

- Kubernetes reports the Deployment as healthy and available; no alert fires, no restart happens, no pod is marked unready.
- 100 % of client traffic fails with a status code (421) that most MCP clients surface as an opaque connection error, not as a misconfiguration hint.
- Rollouts and autoscaling proceed normally on a service that answers nothing, so the outage can persist indefinitely until a human tries the endpoint by hand.

Together with the SDK-004 origin rejection, the HTTP transport as shipped is reachable only from localhost.

### Remediation

Same single fix as SDK-004 — pass `TransportSecuritySettings` to `FastMCP` with the deployment's hostnames and origins.

1. `src/swisstopo_mcp/config.py`: add `allowed_hosts: str = ""` plus an `allowed_hosts_list` property mirroring `origins_list`, driven by `SWISSTOPO_ALLOWED_HOSTS`.
2. `src/swisstopo_mcp/server.py:42-44`:

   ```diff
   + from mcp.server.transport_security import TransportSecuritySettings
   +
     mcp = FastMCP(
         "swisstopo_mcp",
         lifespan=lifespan,
   +     transport_security=TransportSecuritySettings(
   +         enable_dns_rebinding_protection=True,
   +         allowed_hosts=settings.allowed_hosts_list,
   +         allowed_origins=settings.origins_list,
   +     ),
         instructions=(...),
     )
   ```

   Keep the localhost defaults in the list so the local `--http` workflow is unaffected, and keep DNS-rebinding protection on (SEC-005).
3. `deploy/kubernetes.yaml:39-44`: add `SWISSTOPO_ALLOWED_HOSTS` with the ingress hostname from `deploy/ingress-sticky-sessions.yaml`; document the variable in `.env.example` and `docs/deployment.md` as a mandatory setting for any non-localhost deployment.
4. Make the health probe meaningful: either point the readiness probe at a path inside the MCP app, or add a startup smoke check (a script in `deploy/` or a CI job) that issues `POST /mcp` `initialize` with `Host: <public hostname>` and fails on anything other than HTTP 200. Without this, the next host-validation regression is again invisible.
5. Optional, addressing the secondary gap: honour a `SWISSTOPO_TRANSPORT` env var alongside `--http` in `src/swisstopo_mcp/server.py:686-701` so the transport can be switched in a Deployment without overriding `command`.

### Effort Estimate

S (<1d) — one constructor argument and one env var; the deployment smoke test adds a few hours.
