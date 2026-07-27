## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

**Severity:** high
**Status:** closed
**Server:** swisstopo-mcp
**Check-Reference:** SDK-004
**PDF-Reference:** Sec 3.1

### Observed Behavior

The CORS layer itself is correct and test-covered, but every cross-origin MCP request from a configured origin is rejected by the SDK's transport-security layer before it ever reaches the CORS-wrapped handler.

- CORS middleware is configured on the Streamable-HTTP app with the critical header exposed: `expose_headers=["Mcp-Session-Id"]` and `allow_headers` including `Mcp-Session-Id` — `src/swisstopo_mcp/server.py:676-682`.
- Origins are never wildcarded: `allow_origins=allowed_origins or []` (`src/swisstopo_mcp/server.py:678`), fed from `SWISSTOPO_ALLOWED_ORIGINS` via pydantic-settings (`src/swisstopo_mcp/config.py:25-31`, passed at `src/swisstopo_mcp/server.py:696`). The default is the empty list, i.e. no cross-origin access unless explicitly configured.
- `allow_credentials` is not enabled (absent at `src/swisstopo_mcp/server.py:676-682`), which is correct for `auth_model=none` and avoids the wildcard+credentials CORS violation.
- Regression tests assert the configuration: `tests/test_http_app.py:19-33` check `expose_headers`, `allow_headers`, the explicit origin list and the no-origins default.
- **Runtime defect (reproduced against a running instance):** `POST /mcp` with `Origin: https://client.example.com` — an origin explicitly configured via `SWISSTOPO_ALLOWED_ORIGINS` — returns **HTTP 403 "Invalid Origin header"**. The response still carries `access-control-expose-headers: Mcp-Session-Id`, so CORS is fine; the request is killed one layer earlier. The preflight is also fine: `OPTIONS /mcp` with the same Origin returns HTTP 200 with `access-control-allow-origin: https://client.example.com`, `access-control-allow-methods: GET, POST, OPTIONS` and `access-control-allow-headers` including `Mcp-Session-Id`. A `POST` without any `Origin` header returns HTTP 200 plus an `mcp-session-id` header, so the session mechanism itself works.

Root cause: `transport_security` is never passed to `FastMCP(...)` at `src/swisstopo_mcp/server.py:42-44`. A grep for `transport_security` / `TransportSecuritySettings` across `src/`, `tests/` and `docs/` returns nothing — the identifier does not appear anywhere in the repository. mcp 1.28.1 therefore auto-enables DNS-rebinding protection with a localhost-only allow-list derived from the server's internal host, which stays `127.0.0.1` (`mcp/server/fastmcp/server.py:177-183`): `allowed_origins = [http://127.0.0.1:*, http://localhost:*, http://[::1]:*]`.

`SWISSTOPO_ALLOWED_ORIGINS` therefore reaches `CORSMiddleware` only. This is the exact "CORS looks right, browser client still breaks" symptom SDK-004 exists to prevent, only moved one layer down. See SCALE-001 for the matching `Host`-header failure — both share this single root cause.

### Expected Behavior

Per the check's Pass Criteria:

- CORS middleware configured while HTTP/SSE transport is active
- `expose_headers` contains `Mcp-Session-Id`
- `allow_headers` contains `Mcp-Session-Id` for follow-up requests
- `allow_origins` is an explicit list in production, never a wildcard
- Runtime (Modus 2): a cross-origin `POST /mcp` carrying `Origin: <configured origin>` returns `Access-Control-Allow-Origin`, `Access-Control-Expose-Headers: Mcp-Session-Id` **and a usable `Mcp-Session-Id`** — i.e. a browser client can complete a session, not merely pass the preflight.

### Evidence

- File: `src/swisstopo_mcp/server.py:42-44` — `FastMCP("swisstopo_mcp", lifespan=lifespan, instructions=...)`; no `transport_security=` argument.
- File: `src/swisstopo_mcp/server.py:676-682` — CORS middleware with `expose_headers=["Mcp-Session-Id"]` (correct).
- File: `src/swisstopo_mcp/config.py:25-31` — `allowed_origins` / `origins_list`, consumed only by `CORSMiddleware` at `src/swisstopo_mcp/server.py:696`.
- File: `tests/test_http_app.py:19-33` — asserts middleware kwargs only; no test issues a real cross-origin `POST`, which is why the 403 was invisible to CI.
- Upstream: mcp 1.28.1 `mcp/server/fastmcp/server.py:177-183` — auto-derived localhost-only origin allow-list when the internal host is `127.0.0.1`.
- Runtime probe (auditor, Modus 2):
  ```
  OPTIONS /mcp  Origin: https://client.example.com  -> HTTP 200
                access-control-allow-origin: https://client.example.com
                access-control-allow-headers: ... Mcp-Session-Id
  POST    /mcp  Origin: https://client.example.com  -> HTTP 403 "Invalid Origin header"
  POST    /mcp  (no Origin)                         -> HTTP 200 + mcp-session-id
  ```

### Risk Description

Any browser-based MCP client hosted on a domain other than the server's is unusable, in **every configuration a deployment can reach** — there is no value of `SWISSTOPO_ALLOWED_ORIGINS` that fixes it, because that variable never reaches the layer doing the rejecting. The failure is maximally hard to diagnose:

- Local stdio tests pass, server-side curl without `Origin` passes, the CORS preflight passes and the unit tests pass. Only the real browser request fails.
- The 403 body says "Invalid Origin header" while the response headers say the origin *is* allowed, so the operator's first move — widening `SWISSTOPO_ALLOWED_ORIGINS` — has no effect and will be repeated for a long time before the SDK layer is suspected.
- Combined with SCALE-001 (HTTP 421 on the deployment's real `Host`), the HTTP transport as shipped serves no client other than one on localhost, while `/healthz` stays green.

### Remediation

Pass an explicit `TransportSecuritySettings` into `FastMCP` so the deployment's origins and hostnames are honoured by the SDK's `TransportSecurityMiddleware`, not just by CORS. Single fix, shared with SCALE-001.

1. `src/swisstopo_mcp/config.py`: add an `allowed_hosts: str = ""` setting with an `allowed_hosts_list` property mirroring `origins_list`, so the deployment hostname is configurable (`SWISSTOPO_ALLOWED_HOSTS`).
2. `src/swisstopo_mcp/server.py:42-44`: construct `FastMCP` with the transport-security settings.

   ```diff
   + from mcp.server.transport_security import TransportSecuritySettings
   +
     mcp = FastMCP(
         "swisstopo_mcp",
         lifespan=lifespan,
   +     transport_security=TransportSecuritySettings(
   +         enable_dns_rebinding_protection=True,
   +         allowed_origins=settings.origins_list,
   +         allowed_hosts=settings.allowed_hosts_list,
   +     ),
         instructions=(...),
     )
   ```

   Keep DNS-rebinding protection enabled (SEC-005 depends on it) — the fix is to feed it the right lists, never to disable it. Retain the localhost entries as defaults so the local `--http` workflow keeps working.
3. `deploy/kubernetes.yaml`: add `SWISSTOPO_ALLOWED_HOSTS=swisstopo-mcp.example.com` next to the existing `SWISSTOPO_ALLOWED_ORIGINS` env var, and document both in `.env.example` and `docs/deployment.md`.
4. `tests/test_http_app.py`: replace the kwargs-inspection-only coverage with an end-to-end test using `httpx.ASGITransport` that issues a real `POST /mcp` initialize with `Origin: https://client.example.com` against an app built with that origin configured, asserting HTTP 200 and a returned `mcp-session-id`. Add the negative case (an unconfigured origin still yields 403).

### Effort Estimate

S (<1d) — one constructor argument, one settings field, one deployment env var, plus the end-to-end regression test that would have caught it.

---

### Remediation Status (2026-07-27, follow-up PR)

**Closed.** `TransportSecuritySettings` is now passed to `FastMCP()` in
`src/swisstopo_mcp/server.py`, fed from two new `Settings` properties
(`allowed_hosts_list`, `transport_origins_list`) plus the new
`SWISSTOPO_ALLOWED_HOSTS` variable. DNS-rebinding protection stays enabled.

The loopback entries use the SDK's `:*` wildcard-port syntax. That detail
mattered: a first attempt pinned them to the configured `http_port`, which
`--port` overrides at runtime — every local request then failed with 421.

Re-measured against a running instance, same requests as the original evidence:

| Request | Before | After |
|---|---|---|
| `POST /mcp`, configured `Origin` | 403 | **200** |
| `POST /mcp`, ingress `Host` | 421 | **200** |
| `POST /mcp`, loopback, no headers | 200 | **200** |
| `POST /mcp`, unconfigured `Origin` | 403 | **403** (still rejected) |
| `POST /mcp`, unconfigured `Host` | 421 | **421** (still rejected) |

Covered by end-to-end tests in `tests/test_http_app.py` that drive the ASGI app
rather than inspecting middleware kwargs — the previous tests passed throughout
the outage precisely because they only checked configuration.
`SWISSTOPO_ALLOWED_HOSTS` is documented in `.env.example`,
`docs/deployment.md` and `deploy/kubernetes.yaml`.
