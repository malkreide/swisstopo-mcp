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

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
