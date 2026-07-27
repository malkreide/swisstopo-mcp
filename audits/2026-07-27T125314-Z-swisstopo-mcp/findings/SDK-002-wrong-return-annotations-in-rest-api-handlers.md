## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

**Severity:** medium
**Status:** closed
**Server:** swisstopo-mcp
**Check-Reference:** SDK-002
**PDF-Reference:** Sec 3.1

### Observed Behavior

Every MCP-visible tool return is a structured, schema-exposed Pydantic v2 envelope, confirmed at runtime — but four inner handlers misstate their return type.

What is in place:

- All 23 registered tools annotate `-> ToolResponse`, including the three new REST tools (`src/swisstopo_mcp/server.py:358` `zoning_at`, `:381` `municipality_at`, `:403` `layer_info`) and the new coords tool (`src/swisstopo_mcp/server.py:432` `convert_coordinates`).
- Runtime verification against the live server object: `mcp.list_tools()` returns 23 tools and every one carries a non-null `outputSchema` — the `ToolResponse` envelope (`summary` / `results` / `count` / `match_type` / `source` / `license` / `provenance` / `retrieved_at` / `is_error`). No tool falls back to an unschema'd dict.
- The envelope satisfies the structural criteria: `Literal` types for enumerables (`Provenance` / `MatchType` at `src/swisstopo_mcp/models.py:15-16`), `Field(default_factory=list)` for `results` (`src/swisstopo_mcp/models.py:63-65`), `extra="forbid"` (`src/swisstopo_mcp/models.py:60`), and `ok()` / `error()` constructors that always set `count` consistently (`src/swisstopo_mcp/models.py:76-100`).
- Pydantic ≥ 2 is a hard dependency (`pyproject.toml:38` `"pydantic>=2.0.0"`) and v2-only APIs are used throughout (`ConfigDict`, `model_validator(mode="after")` — e.g. `src/swisstopo_mcp/coords.py:19, :110, :202`); no v1 syntax (`.parse_obj` / `class Config`) anywhere in `src/`.

What fails:

- **Four inner handlers in `src/swisstopo_mcp/rest_api.py` declare `-> str` but return `ToolResponse` objects on every path:** `search_layers` (`src/swisstopo_mcp/rest_api.py:289`, returns `ToolResponse` at `:302` and `:308`), `identify_features` (`:312`, returns at `:330` / `:336`), `find_features` (`:340`, returns at `:353` / `:359`), `get_feature` (`:363`, returns at `:372` / `:378`). The new handlers in the same file are correct (`zoning_at` `src/swisstopo_mcp/rest_api.py:406`, `municipality_at` `:436`, `layer_info` `:471`, all `-> ToolResponse`), so the file is internally inconsistent.
- **No static type checker is configured** to catch this class of drift: `pyproject.toml:65-78` enables ruff with `select = [E, F, W, I, UP]` only — no mypy or pyright in the dependencies or in `.github/workflows/ci.yml`.

### Expected Behavior

Per the check's Pass Criteria:

- Pydantic ≥ 2.0 in the dependencies
- Tools have explicit return annotations (BaseModel / TypedDict / dataclass) — and those annotations must state the type actually returned
- Search/list tools use a consistent response envelope with `source`, `provenance`, `results`, `count`
- Pydantic fields use `Field(default=...)` / `Field(default_factory=...)` for defaults
- `Literal` types for enumerable values instead of bare `str`

### Evidence

- File: `src/swisstopo_mcp/rest_api.py:289` — `async def search_layers(...) -> str:` while returning `ToolResponse` at `:302` and `:308`.
- File: `src/swisstopo_mcp/rest_api.py:312` (returns at `:330`, `:336`), `:340` (returns at `:353`, `:359`), `:363` (returns at `:372`, `:378`) — same defect.
- Counter-example in the same file: `src/swisstopo_mcp/rest_api.py:406`, `:436`, `:471` — correct `-> ToolResponse`.
- File: `src/swisstopo_mcp/models.py:15-16, 60, 63-65, 76-100` — envelope definition, `extra="forbid"`, constructors.
- File: `pyproject.toml:38` — `pydantic>=2.0.0`; `pyproject.toml:65-78` — ruff with `select = [E, F, W, I, UP]`, no type checker.
- Runtime: `mcp.list_tools()` → 23 tools, all with a non-null `outputSchema`.

### Risk Description

The client-facing schema is unaffected today, because FastMCP derives the `outputSchema` from the decorated wrappers in `src/swisstopo_mcp/server.py`, not from the inner handlers — this was verified at runtime. The damage is therefore to type-correctness and reviewability, and it is a live trap rather than an abstract one:

- The annotations are simply wrong and would fail any mypy or pyright gate, which is a blocker for adding one later — a first type-check run starts with four errors that look like real bugs.
- More concretely: a future contributor reading `-> str` on `src/swisstopo_mcp/rest_api.py:289` may add an early-return `return "no layers found"` on a new branch. That passes ruff, passes review (it matches the declared signature), and silently breaks the envelope contract for that one tool — the client receives a bare string where the schema promises `summary` / `results` / `count` / `source` / `license`, which for this server also means the CH-004 attribution disappears from that path.
- The inconsistency within a single file (`:289/:312/:340/:363` wrong, `:406/:436/:471` right) makes the correct pattern non-obvious to anyone extending `rest_api.py`.

### Remediation

1. Correct the four annotations in `src/swisstopo_mcp/rest_api.py` — a mechanical change on four lines:

   ```diff
   - async def search_layers(...) -> str:          # rest_api.py:289
   + async def search_layers(...) -> ToolResponse:
   - async def identify_features(...) -> str:      # rest_api.py:312
   + async def identify_features(...) -> ToolResponse:
   - async def find_features(...) -> str:          # rest_api.py:340
   + async def find_features(...) -> ToolResponse:
   - async def get_feature(...) -> str:            # rest_api.py:363
   + async def get_feature(...) -> ToolResponse:
   ```

2. Add a static type gate so the drift cannot recur. In `pyproject.toml`, add `mypy` to `[project.optional-dependencies].dev` and a `[tool.mypy]` section scoped to `src/` (start permissive — `check_untyped_defs = true`, `warn_return_any = true` — and tighten later); add a `mypy src/` step to `.github/workflows/ci.yml` next to the existing ruff step.
3. Optional hardening while in the file: a small unit test asserting `isinstance(result, ToolResponse)` for each of the four handlers makes the contract enforced at runtime as well, independent of the type checker.

### Effort Estimate

S (<1d) — four one-line edits; the mypy gate adds a few hours, mostly for the first clean run.

---

### Remediation Status (2026-07-27, follow-up PR)

**Closed.** The four `-> str` annotations in `rest_api.py` now say
`-> ToolResponse`. A mypy gate was added (`[tool.mypy]` in `pyproject.toml`,
`mypy src/` step in CI) so the drift cannot recur silently. Fixing the
resulting 34 errors also converted all 23 tool `annotations={...}` dicts to the
typed `ToolAnnotations`, and cleaned up three genuine `Any`-leaks in
`geodata.py` and `oereb.py`. mypy is clean on `src/`.
