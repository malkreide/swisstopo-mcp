# Contributing to swisstopo-mcp

[🇩🇪 Deutsche Version](CONTRIBUTING.de.md)

Thank you for your interest in contributing! This server is part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide).

---

## Reporting Issues

Use [GitHub Issues](https://github.com/malkreide/swisstopo-mcp/issues) to report bugs or request features.

Please include:
- Python version and OS
- Full error message or description of unexpected behaviour
- Steps to reproduce

---

## Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `pytest tests/ -m "not live"`
5. Commit using [Conventional Commits](https://www.conventionalcommits.org/): `feat: add new tool`
6. Push and open a Pull Request against `main`

---

## Code Style

- Python 3.11+
- [Ruff](https://github.com/astral-sh/ruff) for linting and formatting
- Type hints required for all public functions
- Tests required for new tools (in `tests/`)
- Follow the existing FastMCP / Pydantic v2 patterns in `server.py`

---

## Data Sources

This server uses six Swisstopo API families -- all without authentication (OEREB requires a canton parameter):

| Source | Documentation |
|--------|--------------|
| REST API | [api3.geo.admin.ch](https://api3.geo.admin.ch/) |
| Geocoding | [api3.geo.admin.ch](https://api3.geo.admin.ch/) |
| Height Service | [api3.geo.admin.ch](https://api3.geo.admin.ch/) |
| STAC Catalog | [data.geo.admin.ch](https://data.geo.admin.ch/) |
| WMTS | [wmts.geo.admin.ch](https://wmts.geo.admin.ch/) |
| OEREB Cadastre | Cantonal endpoints |

When adding new data sources, follow the **No-Auth-First** principle: Phase 1 uses only open, authentication-free endpoints. Authenticated APIs are introduced in later phases with graceful degradation.

---

## The live suite: when it runs, and who sees a red result

**Cadence:** daily at 04:00 UTC, plus on demand via *Actions → Live API tests → Run
workflow*. See [`.github/workflows/live-test.yml`](.github/workflows/live-test.yml).

**Who sees it:** A red run opens an issue labelled `live-test-failure` (title: “Nightly live API tests failed”). A second red run recognises the open issue **by its label**, not by its title, and appends to that same thread. Remove the label by hand and the next red run opens a second issue. A green run does **not** close the issue by itself — once the failure is fixed it needs closing by hand, otherwise the next reader mistakes the old failure for the new one.

**A red live run does not necessarily mean *our* bug.** It means the contract
with the source has changed, or the source is down. Both belong seen; only the
first belongs fixed. Please read the run before disabling the job — that is how
this check dies, and it is the only one in the repository that can contradict a
wrong assumption about api3.geo.admin.ch. Every other test asserts against a fixture, and
the fixture was written from the same assumption as the code.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).

## Versioning of tool definitions

A tool's **name, description and input schema** are what a client approves.
Changing any of them means the client is running against a definition it never
saw, so:

- Renaming a tool, or narrowing/renaming a field in its input schema, is a
  **breaking change**: bump the version and add a CHANGELOG entry listing
  old → new plus a "re-approval required" line.
- `tool-hashes.json` must be regenerated (`python scripts/snapshot_tool_hashes.py`)
  and committed in the same change. CI fails if it is stale.
- Precedent: restricting `sr` to 4326 (0.2.x) and the six tool renames (0.3.0).
