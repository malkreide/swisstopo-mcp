# Roadmap

Phase model per audit check **OPS-003**. The current phase is declared in the
README ("Security & Compliance" section).

## Phase 1 — Read-only wrapper (✅ done)

- [x] Read-only tool surface across the Swisstopo API families, all
      `readOnlyHint: true` (13 tools at the time this phase closed; 23 today —
      see the README for the current list)
- [x] Pydantic v2 input schemas with `strict=True`, `extra="forbid"`, range and
      whitelist-pattern constraints (SEC-018)
- [x] Shared `httpx.AsyncClient` via FastMCP lifespan (SDK-001)
- [x] Code-layer egress allow-list + `follow_redirects=False` (SEC-004/021)
- [x] Error masking for unexpected exceptions (OBS-002)
- [x] CORS with `expose_headers: Mcp-Session-Id` for HTTP transport (SDK-004)
- [x] Audit run against mcp-audit-skill (`audits/`)

## Phase 2 — Semantic / richer responses (✅ largely done)

- [x] Structured tool returns (`ToolResponse` envelope with
      `source`/`licence`/`provenance`/`count`) instead of markdown strings (SDK-002)
- [x] Structured logging via structlog on stderr (OBS-003)
- [x] `match_type` on search-style tools; empty results are reported as
      `match_type: "none"` rather than as errors (ARCH-003)
- [ ] Suggestion mechanism for empty results — still open (ARCH-003)
- [ ] Resources for static catalogs (e.g. notable map layers) (ARCH-008)

## Phase 2.5 — Consolidation of `swiss-geodata-mcp` (🔄 in progress)

Merging the sibling server into this one, per
[`merge-plan-swiss-geodata-mcp.md`](merge-plan-swiss-geodata-mcp.md). Decision
on the plan's open question §7.3 (portfolio doctrine): **merge**, with this
server as the base.

- [x] Official REFRAME coordinate conversion, exposed as
      `swisstopo_convert_coordinates` (new egress host `geodesy.geo.admin.ch`).
      The local polynomial stays the internal fast path — measured deviation is
      0.05–0.20 m, below the tolerance of the tools that use it, and a
      `live` test fails if it ever exceeds one metre.
- [x] LV95 coordinate input on the point-based tools, via the shared
      `SwissPointInput` contract. Prerequisite for LV95-native clients to
      migrate. Fixed a silent wrong answer on the way: `sr=2056` used to send
      degrees upstream labelled as metres.
- [x] Ported `swisstopo_zoning_at`, `swisstopo_municipality_at` and
      `swisstopo_layer_info`; tool budget raised 20 → 25.
- [ ] Deprecate and archive `swiss-geodata-mcp` (no external users, so no
      alias-shim period is needed — plan §7.2).
- [x] Re-run the audit against the changed surface — run
      `2026-07-27T125314-Z`, 22 pass / 20 partial / 2 fail. Not
      production-ready; see that run's `audit-report.md`.

## Phase 3 — Write operations (not planned)

No write/send tools are foreseen. Introducing any would require re-running the
Lethal-Trifecta assessment (SEC-019) and a security review before implementation.
