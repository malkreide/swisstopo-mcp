## Finding: ARCH-004 — Inversion of Control: Transport-agnostische Server-Logik

**Severity:** high
**Status:** closed
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-004
**PDF-Reference:** Sec 2.1

### Observed Behavior
The substance of Inversion of Control holds. No tool handler touches transport internals — a grep for `request.headers` / `remote_addr` / `websocket` / `stdin` / `stdout` across `src/` returns zero hits inside handlers, and the only starlette imports are function-local inside `build_http_app` (`src/swisstopo_mcp/server.py:667-669`), i.e. in transport wiring rather than tool code. Where a handler needs session context it takes the transport-agnostic MCP `Context` (`src/swisstopo_mcp/server.py:337` for `swisstopo_elevation_profile`, `server.py:484` for `swisstopo_get_oereb_extract`), which is the documented pass pattern. Both transports are served from one entrypoint and one FastMCP instance (`src/swisstopo_mcp/server.py:686-701`, with `build_http_app` at `server.py:674` deriving from the same `mcp` object), so tool outputs cannot diverge by construction, and the lifespan is shared — one `httpx.AsyncClient` created at `src/swisstopo_mcp/server.py:27-39` and attached at construction time (`server.py:44`).

A pydantic-settings `Settings` object exists and is used for transport config (`src/swisstopo_mcp/config.py:12-33`, env prefix `SWISSTOPO_`, `.env` support), consumed at `src/swisstopo_mcp/server.py:23`, `694`, `696`, `697` and covered by `tests/test_config.py:8-30`. Container and Kubernetes override it by environment only (`Dockerfile:22-27`, `deploy/kubernetes.yaml:39-42`), never by a code fork.

Two criteria are unmet:

1. **Transport is selected by CLI flag, not by env var.** `src/swisstopo_mcp/server.py:689-694` reads `sys.argv` for `--http`; `Settings` has no `transport` field (`src/swisstopo_mcp/config.py:22-26`).
2. **Configuration does not run exclusively through `Settings`.** `src/swisstopo_mcp/oereb.py:33` reads `os.environ.get("SWISSTOPO_OEREB_CANTONS", "ZH")` at every call of `get_active_cantons()`, and `src/swisstopo_mcp/logging_config.py:32` falls back to `os.environ.get("SWISSTOPO_LOG_LEVEL")`. Both contradict the module docstring at `src/swisstopo_mcp/config.py:3-5` ("come from a single Settings object instead of ad-hoc sys.argv / os.environ reads"), and `SWISSTOPO_OEREB_CANTONS` is documented in `.env.example:7` but has no field in `Settings` at all.

### Expected Behavior
- Tool handlers use only `ctx: Context` for client/session information, never direct request access
- Server code supports at least stdio plus SSE/Streamable HTTP, selectable via env var
- Configuration runs through a settings object (pydantic-settings or equivalent), not global module vars or ad-hoc env reads
- Tools produce identical outputs regardless of transport
- Lifespan / setup code is shared across all transports

### Evidence
- Handlers are transport-clean: grep for `request.headers` / `remote_addr` / `websocket` / `stdin` / `stdout` across `src/` returns zero hits inside handlers; starlette imports are function-local at `src/swisstopo_mcp/server.py:667-669`; the single `httpx.RequestError` reference at `src/swisstopo_mcp/api_client.py:176` is the outbound client, not the inbound transport
- Transport-agnostic Context usage: `src/swisstopo_mcp/server.py:337`, `server.py:484`
- One entrypoint, one FastMCP instance: `src/swisstopo_mcp/server.py:686-701`; `build_http_app` at `server.py:674`
- Shared lifespan: `src/swisstopo_mcp/server.py:27-39`, attached at `server.py:44`
- Settings object: `src/swisstopo_mcp/config.py:12-33`; consumed at `src/swisstopo_mcp/server.py:23`, `694`, `696`, `697`; tested at `tests/test_config.py:8-30`; env-only overrides at `Dockerfile:22-27`, `deploy/kubernetes.yaml:39-42`
- Ad-hoc config reads: `src/swisstopo_mcp/oereb.py:33`, `src/swisstopo_mcp/logging_config.py:32`; contradicted docstring at `src/swisstopo_mcp/config.py:3-5`; undeclared knob documented at `.env.example:7`

Gaps:
- Transport is selected by CLI flag (`sys.argv`, `src/swisstopo_mcp/server.py:689-694`), not by env var / Settings field — `Settings` has no `transport` field (`src/swisstopo_mcp/config.py:22-26`)
- `src/swisstopo_mcp/oereb.py:33` reads `os.environ` at call time, so the enabled-canton set is a hidden global re-read per invocation, making the OEREB tool surface dependent on ambient process state rather than injected config

### Risk Description
Neither gap is a security issue, which is why the impact is operational rather than exploitable — but the second one is more than cosmetic.

`src/swisstopo_mcp/oereb.py:33` re-reads `SWISSTOPO_OEREB_CANTONS` on every call to `get_active_cantons()`. That makes the set of cantons the OEREB tools will serve a function of ambient process state at call time, not of configuration captured at startup. Practical consequences: the value cannot be validated (a typo'd canton code fails silently per call rather than at startup, where `Settings` would reject it), it cannot be logged at startup as part of the effective configuration, and a test or a caller that mutates `os.environ` changes tool behaviour mid-process. Because `SWISSTOPO_OEREB_CANTONS` is documented in `.env.example:7` but absent from `Settings`, an operator reading `config.py` to learn what is configurable will not find it — and `config.py:3-5` actively tells them there is nothing else to look for.

The transport gap bites in container orchestration. `Dockerfile:22-27` and `deploy/kubernetes.yaml:39-42` configure everything else by environment; transport alone requires an argv change, which means switching a deployment from stdio to HTTP is a container-command edit rather than an env-var edit. That is a different change-management path for one setting than for all the others, and it is the one setting most likely to differ between local and deployed runs.

### Remediation
1. **Add a `transport` field to `Settings`** in `src/swisstopo_mcp/config.py:22-26` and let the CLI flag override it rather than be the only path:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SWISSTOPO_", env_file=".env")
    transport: Literal["stdio", "streamable-http"] = "stdio"
    oereb_cantons: str = "ZH"
    log_level: str = "INFO"
    ...
```

Then in `src/swisstopo_mcp/server.py:689-694`:

```python
transport = "streamable-http" if "--http" in sys.argv else settings.transport
```

This keeps `--http` working for existing users while making `SWISSTOPO_TRANSPORT=streamable-http` the deployment path, and it aligns transport with every other setting in `Dockerfile:22-27` and `deploy/kubernetes.yaml:39-42`.

2. **Route the OEREB cantons through `Settings`.** Replace the call-time read at `src/swisstopo_mcp/oereb.py:33` with a lookup on the injected settings object, and validate it at startup:

```python
# config.py
oereb_cantons: str = "ZH"

@field_validator("oereb_cantons")
@classmethod
def _known_cantons(cls, v: str) -> str:
    unknown = {c.strip().upper() for c in v.split(",")} - set(OEREB_ENDPOINTS)
    if unknown:
        raise ValueError(f"Unknown canton codes: {sorted(unknown)}")
    return v

# oereb.py:33
def get_active_cantons(settings: Settings) -> set[str]:
    return {c.strip().upper() for c in settings.oereb_cantons.split(",")}
```

A typo'd canton then fails at startup with a clear message instead of producing an empty result set at call time.

3. **Fold the logging fallback in.** `src/swisstopo_mcp/logging_config.py:32` should take `settings.log_level` rather than reading `os.environ` — `Settings` already carries the field, so this is a signature change, not a new knob.
4. **Extend `tests/test_config.py:8-30`** with cases for `SWISSTOPO_TRANSPORT` and `SWISSTOPO_OEREB_CANTONS`, including the invalid-canton rejection. That is what makes `config.py:3-5`'s claim true rather than aspirational.

### Effort Estimate
S (<1d)

---

### Remediation Status (2026-07-27, follow-up PR)

**Closed.** `transport` and `oereb_cantons` are now `Settings` fields.
`--http` still wins on the command line so existing invocations keep working,
but `SWISSTOPO_TRANSPORT=streamable-http` is the deployment path. `oereb.py`
no longer reads `os.environ` directly — the contradiction with `config.py`'s
own docstring is gone.

**Behavioural note:** the OEREB canton list is now read once at startup rather
than on every call. That is what the check asks for, but it means a change
requires a restart. Six tests that monkeypatched the env var at call time were
updated to set the setting instead.
