# Roadmap

Phase model per audit check **OPS-003**. **This document is the single authority
for phase state** — the READMEs and `SECURITY.md` link here rather than restate
it. The previous arrangement had each document naming the other as
authoritative, which meant neither was (audit `2026-07-27T162602-Z`, OPS-003).

## Phase 1 — Read-only wrapper (✅ done)

- [x] Read-only tool surface across the Swisstopo API families, all
      `readOnlyHint: true` (13 tools at the time this phase closed; 24 today —
      see the README for the current list)
- [x] Pydantic v2 input schemas with `strict=True`, `extra="forbid"`, range and
      whitelist-pattern constraints (SEC-018)
- [x] Shared `httpx.AsyncClient`, owned by a reference-counted process-level
      context rather than by the FastMCP lifespan — which the SDK runs per
      session, not per process, on the HTTP transport (SDK-001)
- [x] Code-layer egress allow-list + `follow_redirects=False` (SEC-004/021)
- [x] Error masking for unexpected exceptions (OBS-002)
- [x] CORS with `expose_headers: Mcp-Session-Id` for HTTP transport (SDK-004)
- [x] Audit run against mcp-audit-skill (`audits/`)
- [x] ISDS classification and DSG assessment — [`isds-dsg.md`](isds-dsg.md).
      The check lists both as Phase-1 exit criteria (OPS-003). No processing
      record is maintained; §5 gives the reasons and §6 the triggers that would
      overturn them.

## Phase 2 — Semantic / richer responses (✅ largely done)

- [x] Structured tool returns (`ToolResponse` envelope with
      `source`/`licence`/`provenance`/`count`) instead of markdown strings (SDK-002)
- [x] Structured logging via structlog on stderr (OBS-003)
- [x] `match_type` on search-style tools; empty results are reported as
      `match_type: "none"` rather than as errors (ARCH-003)
- [x] Suggestion mechanism for empty results (ARCH-003): every
      `match_type: "none"` path names a concrete next step, enforced by the
      envelope and by an AST sweep over the call sites; `swisstopo_geocode`
      relaxes a failed query and reports the retry as `match_type: "fuzzy"`
- [x] Resources for static catalogs (ARCH-008): `swisstopo://catalogue/layers`
      exposes the façade layer catalogue, the one deterministic and already
      cached surface here. Two Prompts were added alongside it — the check
      passed without either, but it named both as gaps.
- [x] OpenTelemetry tracing, opt-in via `OTEL_EXPORTER_OTLP_ENDPOINT`, with
      httpx auto-instrumentation so upstream calls nest under the tool span
      (OBS-006)

## Phase 2.5 — Consolidation of `swiss-geodata-mcp` (✅ done)

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
- [x] `swisstopo_oereb_at` collapses the coordinate → EGRID → extract chain into
      one call (ARCH-007). The aggregation rationale per tool cluster lives in
      the README.
- [x] Merged the five api3 tools into `swisstopo_map_query` with an `operation`
      discriminator (ARCH-006, breaking, 0.4.0). 24 → 20 tools, and the last
      obvious 1:1 API mapping is gone. Two earlier entries here recorded this as
      a future-major candidate; this was that major. Operations are named for
      questions (`features_at_point`, not `identify`), a field belonging to
      another operation is refused rather than ignored, and each operation keeps
      its own log/trace label so per-operation observability survives the merge.
- [x] Deprecated and **archived** `swiss-geodata-mcp` (2026-07-27). No external
      users, so no alias-shim period was needed — plan §7.2.
- [x] Re-run the audit against the changed surface — run
      `2026-07-27T125314-Z`, 22 pass / 20 partial / 2 fail.
- [x] Adversarial re-audit after the remediation batch — run
      `2026-07-27T162602-Z`, **24 pass / 20 partial / 0 fail** over the same 44
      applicable checks. The agents were briefed to refute the remediation
      claims rather than confirm them, and did so in six cases; four findings
      are new (SDK-001, OBS-001, OBS-002, SCALE-003). The run's
      `production_ready` flag reads YES only because it gates on hard `fail` —
      two `partial` findings are critical severity. See that run's
      `audit-report.md` §1a for the run-over-run comparison.

## Phase 3 — Write operations (not planned)

No write/send tools are foreseen. Introducing any would require re-running the
Lethal-Trifecta assessment (SEC-019) and a security review before implementation.
