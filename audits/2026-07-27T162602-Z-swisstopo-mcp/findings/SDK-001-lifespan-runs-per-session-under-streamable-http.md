## Finding: SDK-001 — FastMCP Lifespan via @asynccontextmanager + AsyncExitStack

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SDK-001
**PDF-Reference:** Sec 3.1
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
The structural criteria all pass: `@asynccontextmanager` lifespan at `server.py:30-46`,
passed via `lifespan=` at `server.py:51`, cleanup in `finally`, and no per-call client
construction on the happy path.

The claimed invariant does not hold on the HTTP transport, measured rather than read.
A freshly started `--http` server logged 0 `server_started` events at boot; after
three `initialize` POSTs it had logged exactly 3 `server_started` and 0
`server_stopped`. The lifespan runs **once per MCP session**, not once per process,
so the docstring at `server.py:32-33` ("one shared httpx.AsyncClient for the server's
lifetime") is false under `--http`.

Because `_shared_client` is a module global (`api_client.py:209`), each new session's
`set_shared_client()` clobbers the previous one. Worse, session teardown is
destructive: `DELETE /mcp` for one of three open sessions returned 200 and ran
`set_shared_client(None)` (`server.py:44`) plus `shutdown_tracing()` (`server.py:45`).
The two surviving sessions then fall through to the ephemeral per-call branch at
`api_client.py:258` — the exact anti-pattern this check forbids — with tracing torn
down underneath them.

### Expected Behavior
- One shared client for the process lifetime
- No client constructed per tool call

### Evidence
- Lifespan is present and correctly shaped: `@asynccontextmanager async def lifespan(server: FastMCP)` at src/swisstopo_mcp/server.py:30-46, passed to the constructor at src/swisstopo_mcp/server.py:51 (`lifespan=lifespan`), with cleanup in a `finally` block (`await client.aclose()` at src/swisstopo_mcp/server.py:43).
- Tool handlers do not create a client per call: the shared instance is registered via set_shared_client() (src/swisstopo_mcp/server.py:38) and returned wrapped in a non-closing adapter by _get_client() (src/swisstopo_mcp/api_client.py:239-258), so `async with await _get_client()` reuses the pool instead of closing it. follow_redirects=False and a 30s timeout are set on the client at src/swisstopo_mcp/api_client.py:220-225.
- RUNTIME DEFECT (measured, not read): under streamable-http the lifespan runs once per MCP SESSION, not once per process. A freshly started `python -m swisstopo_mcp.server --http --port 8770` logged 0 `server_started` events at boot; after three `initialize` POSTs it had logged exactly 3 `server_started` and 0 `server_stopped`. The docstring at src/swisstopo_mcp/server.py:32-33 ('one shared httpx.AsyncClient for the server's lifetime') does not hold on the HTTP transport.
- Because `_shared_client` is a module-level global (src/swisstopo_mcp/api_client.py:209), each new session's `set_shared_client(client)` (src/swisstopo_mcp/server.py:38) clobbers the previous session's client. With N concurrent sessions, N clients exist but only the newest is ever used; the older ones sit idle holding their pools until their own session ends.
- Session teardown is destructive to surviving sessions: DELETE /mcp for one of three open sessions returned HTTP 200 and produced exactly 1 `server_stopped` while 2 sessions stayed open. That path runs `set_shared_client(None)` (src/swisstopo_mcp/server.py:44) — the two live sessions then fall through to the ephemeral per-call branch at src/swisstopo_mcp/api_client.py:258, i.e. exactly the anti-pattern this check forbids — and `shutdown_tracing()` (src/swisstopo_mcp/server.py:45), which calls `provider.shutdown()` and sets `_tracer = None` (src/swisstopo_mcp/observability.py:87-102), killing tracing process-wide for the surviving sessions.

Gaps:
- No test asserts the lifespan runs once per process; tests/test_shared_client.py:33-44 only exercises set/get in isolation and cannot see the per-session re-entry.
- No guard against concurrent sessions clobbering the global — a refcount, an AsyncExitStack owned by the ASGI app lifespan, or storing the client on the app/server state instead of a module global would all fix it.
- setup_tracing()/shutdown_tracing() are not idempotent across overlapping sessions; `_instrumented` is guarded (observability.py:78) but `_tracer` and the TracerProvider are not.

### Risk Description
Reachable with two concurrent clients, which is the normal case for any deployment
that is not one desktop app. When one client disconnects, every other live session
silently degrades to a fresh `httpx.AsyncClient` per tool call: no connection reuse, a
new TLS handshake per request, and — since `_build_client` is where the pinned
transport and `follow_redirects=False` are set — the security posture is at least
reconstructed each time rather than inherited, but at a latency cost that grows with
load. Tracing stops process-wide for the survivors.

### Remediation
1. Move client ownership out of the per-session lifespan. Either an `AsyncExitStack`
   owned by the ASGI app lifespan, or store the client on the app/server state rather
   than a module global.
2. Failing that, refcount: `set_shared_client` increments, teardown decrements and
   only closes at zero. Same for `setup_tracing`/`shutdown_tracing`, which are not
   idempotent across overlapping sessions (`_instrumented` is guarded,
   `_tracer` and the provider are not).
3. Add the test that would have caught it: start the HTTP app, open two sessions,
   close one, assert the other still resolves the shared client.
4. Correct the docstring at `server.py:32-33` — it states a per-process invariant the
   HTTP transport does not provide.

### Effort Estimate
M (1-3d)

### Relation to run `2026-07-27T125314-Z`
New in this run. `2026-07-27T125314-Z` recorded SDK-001 as passing on the structural criteria without driving a running HTTP server.

### Auditor Notes
The structural pass criteria are all met (asynccontextmanager, lifespan= in the
constructor, cleanup in finally, no per-call client construction on the happy
path), so this is not a fail. But the claimed invariant was verified against a
running server rather than read, and it does not hold for the transport this
server ships in its container: the lifespan is per-session. The consequence is
concrete and reachable with two concurrent clients — ending one session nulls
the shared client for the others, degrading them to a fresh httpx.AsyncClient
per tool call, and tears down the tracer provider underneath them. Correct for
stdio, broken under --http, hence partial.
