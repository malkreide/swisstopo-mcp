# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `docs/roadmap.md` and a "Security & Compliance" README section (phase
  declaration, Lethal-Trifecta assessment, MCP-primitives rationale) —
  audit findings OPS-003 / SEC-019 / ARCH-008.
- `.github/dependabot.yml` for monthly pip + GitHub-Actions update PRs
  (audit finding ARCH-012).
- CORS configured on the Streamable-HTTP app with
  `expose_headers: Mcp-Session-Id` (audit finding SDK-004).

### Changed
- All tool input models now use Pydantic `strict=True` plus whitelist
  `pattern` constraints on free-text fields (audit finding SEC-018).
- Unexpected exceptions no longer leak their raw text to the client; intentional
  validation messages are preserved (audit finding OBS-002).
- Empty geocoding results now return an actionable hint instead of a bare
  "no results" string (audit finding ARCH-003).
- Pinned `mcp[cli]` to the `1.x` major; CI now also runs on the `master`
  branch.

### Security
- Added an explicit code-layer egress allow-list (`ALLOWED_HOSTS` frozenset +
  `assert_host_allowed`) checked before every outbound request; documented in
  `docs/network-egress.md` (audit finding SEC-021).

### Changed
- HTTP client is now created once at server startup via a FastMCP lifespan and
  reused across all tool calls (connection pooling) instead of being recreated
  per call (audit finding SDK-001).
- Outbound requests no longer follow redirects (`follow_redirects=False`),
  reducing redirect-based SSRF surface (audit findings SEC-004/005).

## [0.1.0] - 2026-04-02

### Added
- Initial release with 13 tools across 6 API families
- **REST API** (4 tools): Layer search, feature identification, attribute search, feature details
- **Geocoding** (2 tools): Address geocoding, reverse geocoding
- **Height** (2 tools): Point height, elevation profile
- **STAC** (2 tools): Geodata catalog search, collection details
- **WMTS** (1 tool): Map URL generation
- **OEREB** (2 tools): Property ID (EGRID) lookup, cadastral extract
- Dual transport: stdio (Claude Desktop) + Streamable HTTP (cloud)
- GitHub Actions CI (Python 3.11, 3.12, 3.13)
- Bilingual documentation (DE/EN)
