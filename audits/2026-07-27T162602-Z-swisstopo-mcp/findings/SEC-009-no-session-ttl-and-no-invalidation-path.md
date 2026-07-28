## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

**Severity:** critical
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-009
**PDF-Reference:** Sec 4.6
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
Session-ID generation is cryptographically sound but is the SDK's, not the server's —
`uuid4().hex`, 128 bits from `os.urandom`, with the SDK major pinned at
`pyproject.toml:33` so it cannot change under a minor bump. The SDK's owner-binding
mechanism exists but is inert: with no auth configured the requestor is `None` for
every caller, so the mismatch check compares `None` to `None` and always passes.

Two criteria that are independent of auth are unmet. No session TTL:
`server.py:725` calls `mcp.streamable_http_app()` with defaults and the SDK's
`session_idle_timeout` default is `None`, so sessions live until the process restarts.
No server-side invalidation: `server.py:708-734` adds only `/healthz`.

### Expected Behavior
- Explicit session TTL
- Server-side invalidation path
- Session bound to the authenticated principal

### Evidence
- Session-ID generation is cryptographically sound, but it is the SDK's, not the server's. The server never generates a session id; mcp.server.streamable_http_manager creates `new_session_id = uuid4().hex` (128 bits from os.urandom). The SDK major is pinned at pyproject.toml:33 (`mcp[cli]>=1.28.1,<2.0.0`), so the generator cannot change under a minor bump without a deliberate constraint change.
- The SDK does implement owner binding — `self._session_owners: dict[str, AuthorizationContext]` with a mismatch check on every request — but it is inert here. The requestor is derived from an AuthenticatedUser; with no auth configured (FastMCP is constructed without an auth/token verifier at src/swisstopo_mcp/server.py:49-99) the requestor is None for every caller, so the comparison `requestor != self._session_owners.get(...)` compares None to None and always passes. Anyone presenting a valid Mcp-Session-Id is that session.
- No session TTL is configured. src/swisstopo_mcp/server.py:725 calls mcp.streamable_http_app() with defaults, and FastMCP.streamable_http_app constructs StreamableHTTPSessionManager without a session_idle_timeout; the SDK's default for that parameter is None, i.e. sessions live until the process restarts. The check's criterion 'Session-TTL ist explizit gesetzt' is unmet.
- There is no server-side logout/invalidation endpoint. src/swisstopo_mcp/server.py:708-734 adds only /healthz alongside the MCP mount.
- The residual risk is genuinely low and the deferral is documented honestly: SECURITY.md:45-51 states the server is unauthenticated by design, that there is no per-user state to bind to, and names SEC-009 as the trigger if an authenticated deployment is introduced. All 24 tools are stateless reads against public open data (verified via mcp.list_tools()), so a hijacked session confers no privilege the caller did not already have. Transport-level DNS-rebinding protection with explicit host/origin lists is on at src/swisstopo_mcp/server.py:58-62.

Gaps:
- No session TTL / idle timeout — sessions are unbounded for the process lifetime.
- No server-side session invalidation path (no logout).
- The SDK's user-binding mechanism is present but a no-op because auth_model=none; no compensating binding (e.g. client-IP or a signed token) exists.
- No runtime hijack probe was run against a live HTTP instance; verification is code- and SDK-source-level.

### Risk Description
All 24 tools are stateless reads against public open data, so a hijacked session
confers no privilege the caller did not already have — the exploit value is close to
zero and the deferral in `SECURITY.md:45-51` is honest. What remains is unbounded
session accumulation: with no idle timeout, every session that is never explicitly
deleted is retained for the process lifetime, which is a memory-growth and
resource-exhaustion property rather than a confidentiality one.

### Remediation
1. Set an explicit `session_idle_timeout` when constructing the app. This is a
   one-line change with no auth prerequisite and closes the unbounded-growth
   behaviour.
2. Document the absence of a logout route as deliberate (there is no session-scoped
   state to invalidate) rather than leaving the criterion unaddressed.
3. Keep the SEC-009 trigger in `SECURITY.md` — if an authenticated deployment is ever
   introduced, the inert owner binding becomes load-bearing.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Recorded as a documented deferral. Two of the six criteria are independent of auth and were not examined; neither is met.

### Auditor Notes
I deliberately did not inherit the prior 'documented deferral' framing. Two
of the six pass criteria (TTL, server-side invalidation) are independent of
whether auth exists, and neither is met — the server takes the SDK default
of no idle timeout and adds no logout route. The user-binding criteria are
genuinely inapplicable rather than skipped, and the ID entropy criterion is
met via the SDK's uuid4.
Partial rather than pass on the two unmet criteria; partial rather than
fail because the server holds no session-scoped state and serves only
public data, so the exploit value of a stolen session id is close to zero.

---

### Remediation Status (2026-07-28, follow-up PR)

**Closed.** Both criteria the finding correctly identified as independent of the
auth model are now met — and one of the two turned out already to be.

**1. Session TTL — implemented.** `SWISSTOPO_SESSION_IDLE_TIMEOUT`, default
**1800 s**, the value the SDK's own docstring recommends. FastMCP exposes no
setting for it and builds the manager lazily (`streamable_http_app()` constructs
one only `if self._session_manager is None`), so `_install_session_manager()`
pre-populates it. `0` restores the SDK's unbounded behaviour for an operator who
wants it.

Verified against a running server, both directions:

| | result |
|---|---|
| session idle past the TTL | `404` — reaped, and the SDK logs `Session … idle timeout` |
| session kept active past the TTL | `200` — the deadline is pushed back on each request |

A test also asserts the custom manager still carries the transport-security
settings, since building it by hand could silently drop the DNS-rebinding
protection the SDK would otherwise wire up (SDK-004 / SEC-005).

**2. Server-side invalidation — the finding is incorrect on this point.** It
reads *"There is no server-side logout/invalidation endpoint.
`src/swisstopo_mcp/server.py:708-734` adds only `/healthz`"* — true as written,
but it looks for a custom route and misses the protocol's own mechanism.
`DELETE /mcp` with the session id is the MCP session-termination method and the
SDK implements it. Measured: `DELETE` returns `200`, and the next request on
that session id returns `404`. The criterion was already satisfied; what was
missing was documentation, now in `SECURITY.md` and `SECURITY.de.md`.

**3. Owner binding** stays genuinely inapplicable — no auth model means no
requestor to bind to. The `SECURITY.md` trigger for an authenticated deployment
is unchanged.

The residual risk assessment in the finding stands and is worth repeating: all
24 tools are stateless reads over public open data, so a stolen session id
confers no privilege the caller did not already have. What the TTL fixes is
resource growth, not confidentiality.

Documented in `.env.example`, `deploy/kubernetes.yaml` and both security
policies. Five tests added.
