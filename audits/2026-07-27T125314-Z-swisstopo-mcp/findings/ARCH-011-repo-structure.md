## Finding: ARCH-011 — Standardisierte Repo-Struktur (src-Layout, tests, README.de.md)

**Severity:** medium
**Status:** closed
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-011
**PDF-Reference:** Anhang A8

### Observed Behavior
Five of the seven criteria are met cleanly. All five mandatory top-level files are present at the repo root — `README.md`, `README.de.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml` — plus the bilingual extras `CONTRIBUTING.md` / `CONTRIBUTING.de.md` and `SECURITY.md` / `SECURITY.de.md`. All three mandatory directories exist: `src/`, `tests/` (22 test modules, correctly outside `src/`) and `.github/workflows/`. The src-layout is correct — `src/` contains the package directory `src/swisstopo_mcp/` rather than loose `.py` files, and `pyproject.toml` declares it explicitly (hatchling build backend at `pyproject.toml` lines 1-3, `[tool.hatch.build.targets.wheel] packages = ["src/swisstopo_mcp"]` at lines 56-57). CI coverage exceeds the minimum: `.github/workflows/ci.yml:29-37` runs `pytest -m "not live"` plus ruff across Python 3.11/3.12/3.13, `.github/workflows/publish.yml` publishes on release, and `.github/workflows/security.yml` runs gitleaks. `README.de.md` is a genuine parallel document rather than a stub — 20 top-level sections in `README.md` against 19 in `README.de.md`, mapping 1:1 semantically (Overview/Übersicht, Available Tools/Verfügbare Tools, Security & Compliance, MCP Primitives/MCP-Primitive, …).

Two criteria are unmet:

1. **No `tools/` sub-package despite 23 tools.** Tool bodies are split by domain module — `geocoding.py`, `rest_api.py`, `height.py`, `stac.py`, `wmts.py`, `oereb.py`, `geodata.py`, `overpass.py`, `openplz.py`, `coords.py` — and `src/swisstopo_mcp/server.py` contains only registrations that delegate (e.g. `server.py:358`, `return await zoning_at(params)`). But those modules sit flat under `src/swisstopo_mcp/` rather than in `src/swisstopo_mcp/tools/`, and `server.py` is 701 lines against the check's <200-line guidance for a registry file. The bulk of those 701 lines is decorator blocks and docstrings, not logic.
2. **The deviation is not justified anywhere.** `README.md:266-305` and `README.de.md:266-303` render the layout as a tree but give no rationale, and the check explicitly conditions deviations on being argued in the README.

A third, minor discrepancy: `README.de.md` lacks the generated uvx `## Installation` section present at `README.md:484` (between the `BEGIN/END GENERATED: install` markers), which accounts for the 20 vs 19 section count.

### Expected Behavior
- Mandatory top-level files present: `README.md`, `README.de.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml`
- Directories present: `src/`, `tests/`, `.github/workflows/`
- Correct src-layout, no flat package
- CI workflows: at minimum a test workflow (without live tests) and a publish workflow
- `README.de.md` parallel to `README.md` (same top-level sections)
- With > 5 tools: a `tools/` directory with one file per group
- Deviations from the standard are justified in the README

### Evidence
- Mandatory files at the repo root: `README.md`, `README.de.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml`, plus `CONTRIBUTING.md` / `CONTRIBUTING.de.md` and `SECURITY.md` / `SECURITY.de.md`
- Mandatory directories: `src/`, `tests/` (22 modules, outside `src/`), `.github/workflows/`
- src-layout declared: `pyproject.toml` lines 1-3 (hatchling) and 56-57 (`packages = ["src/swisstopo_mcp"]`)
- CI: `.github/workflows/ci.yml:29-37` (pytest `-m "not live"` + ruff, Python 3.11/3.12/3.13), `.github/workflows/publish.yml`, `.github/workflows/security.yml`; the `not live` marker is declared under `[tool.pytest.ini_options]` in `pyproject.toml`
- README parity: 20 top-level sections in `README.md` vs 19 in `README.de.md`, semantically 1:1; the single difference is the generated uvx install block at `README.md:484`
- Domain-module split with a delegating registry: `geocoding.py`, `rest_api.py`, `height.py`, `stac.py`, `wmts.py`, `oereb.py`, `geodata.py`, `overpass.py`, `openplz.py`, `coords.py`; delegation example at `src/swisstopo_mcp/server.py:358`
- Layout documented without rationale: `README.md:266-305`, `README.de.md:266-303`

Gaps:
- No `tools/` sub-package despite 23 tools; the equivalent split lives as flat per-domain modules under `src/swisstopo_mcp/`, and `src/swisstopo_mcp/server.py` is 701 lines (check guidance: <200 for a registry-only file)
- This deviation is not justified anywhere: `README.md:266-305` and `README.de.md:266-303` show the tree but give no rationale
- `README.de.md` lacks the generated uvx `## Installation` section present at `README.md:484`, so the section inventory is 20 vs 19

### Risk Description
Substantively the intent of the layout rule is honoured, so the impact here is low and documentation-shaped rather than structural. There is no 800-line god-file: tool logic sits in per-domain modules that mirror the upstream API families, `server.py` holds only wiring, and every criterion the rule exists to protect — test isolation, reviewable diffs, findable code — is satisfied by the flat-module arrangement.

What the deviation costs is portfolio consistency, which is the stated reason the rule exists. The audit skill, CI templates and dependency tooling are meant to run identically across 29 servers; a tool-file path that is `src/<pkg>/tools/*.py` on other servers and `src/<pkg>/*.py` here means any portfolio-wide script that globs for tool modules either misses this repo or needs a special case. The same applies to a new maintainer arriving from a sibling server: `src/swisstopo_mcp/` holds tool modules, client code and config side by side with no directory-level signal about which is which.

`server.py` at 701 lines is worth noting but not alarming — it is decorator blocks and docstrings, and splitting it would move the volume rather than reduce it. The real gap the check identifies is that none of this reasoning is written down: a reviewer comparing this repo to the standard sees a deviation with no explanation and cannot tell whether it was considered or overlooked.

### Remediation
Two options; the second is sufficient to pass the check and is the better trade here.

**Option A — conform.** `git mv` the ten domain modules into `src/swisstopo_mcp/tools/` with an `__init__.py` re-exporting the handlers, update imports in `server.py`, and leave `server.py` as the registry. This aligns the path with the portfolio standard but touches every import in the repo and every test module, for no functional gain.

**Option B — justify the deviation (recommended).** Add a short "Project Structure" rationale to `README.md:266-305` and its counterpart at `README.de.md:266-303`, e.g.:

> The tool modules sit flat under `src/swisstopo_mcp/` rather than in a `tools/` sub-package. Each module maps to one upstream API family (`rest_api.py` → api3 MapServer, `stac.py` → STAC, `oereb.py` → cantonal ÖREB, …), which is the axis along which this server's code actually varies; a `tools/` level would add a directory without adding a distinction. `server.py` contains registrations only and delegates every tool body to its domain module.

The check permits deviations that are argued, so two paragraphs close criterion 7. If `server.py`'s length is a concern independent of the directory question, split the registrations by family into `server.py` plus per-family registration modules — but that is a readability call, not a check requirement.

Independently of the option chosen:

1. Add the missing `## Installation` section to `README.de.md` so the section inventory reaches parity, or extend the generator that writes the `BEGIN/END GENERATED: install` block at `README.md:484` to emit the German file too — the latter prevents the drift from recurring at the next regeneration.
2. Consider a CI check comparing `grep -E '^## ' README.md | wc -l` against `README.de.md`, which turns bilingual drift into a test failure. That is cheap and serves ARCH-011 across the whole portfolio.

### Effort Estimate
S (<1d) for Option B plus the README parity fix. Option A is also S but touches far more files for less benefit.

---

### Remediation Status (2026-07-27, batch 2)

**Closed via Option B**, the option the finding itself recommends. Both READMEs
now carry a `Project structure` rationale: modules map one-to-one onto upstream
API families, which is the axis this code varies along, so a `tools/` level
would add a directory without adding a distinction. The check permits argued
deviations.
