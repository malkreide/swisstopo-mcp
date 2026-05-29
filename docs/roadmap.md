# Roadmap

Phase model per audit check **OPS-003**. The current phase is declared in the
README ("Security & Compliance" section).

## Phase 1 — Read-only wrapper (✅ current)

- [x] 13 tools across 6 Swisstopo API families, all `readOnlyHint: true`
- [x] Pydantic v2 input schemas with `strict=True`, `extra="forbid"`, range and
      whitelist-pattern constraints (SEC-018)
- [x] Shared `httpx.AsyncClient` via FastMCP lifespan (SDK-001)
- [x] Code-layer egress allow-list + `follow_redirects=False` (SEC-004/021)
- [x] Error masking for unexpected exceptions (OBS-002)
- [x] CORS with `expose_headers: Mcp-Session-Id` for HTTP transport (SDK-004)
- [x] Audit run against mcp-audit-skill (`audits/`)

## Phase 2 — Semantic / richer responses (planned)

- [ ] Structured tool returns (Pydantic response envelope with
      `source`/`provenance`/`count`) instead of markdown strings (SDK-002)
- [ ] Structured logging via structlog on stderr (OBS-003)
- [ ] `match_type` + suggestion mechanism for empty results (ARCH-003)
- [ ] Resources for static catalogs (e.g. notable map layers) (ARCH-008)

## Phase 3 — Write operations (not planned)

No write/send tools are foreseen. Introducing any would require re-running the
Lethal-Trifecta assessment (SEC-019) and a security review before implementation.
