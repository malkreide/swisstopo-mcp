## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

**Severity:** high
**Status:** closed
**Server:** swisstopo-mcp
**Check-Reference:** OPS-003
**PDF-Reference:** Anhang C4

### Observed Behavior

A phase is declared and the code matches the read-only discipline, but the declaration contradicts the roadmap and the Phase 1 → 2 gate was crossed without its required artefacts.

What is in place:

- A phase is declared in the README: `README.md:313-317` ("### Phase — This server is in **Phase 1 — Read-only wrapper**. All 23 tools are `readOnlyHint: true` / `destructiveHint: false`; there are no write or send capabilities."), mirrored at `README.de.md:311-316`.
- The declared phase is consistent with the actual tool annotations: 23 of 23 `@mcp.tool` registrations in `src/swisstopo_mcp/server.py` carry `readOnlyHint: True` (e.g. `server.py:91, 148, 168, 352, 375, 397, 426`) and `grep -rn 'destructiveHint.*True' src/` returns zero hits. No write, send, mail or webhook tool exists.
- A roadmap file exists with phase-specific tasks: `docs/roadmap.md` — Phase 1 Read-only wrapper (`:6-19`, marked done, 7 checked items including the audit run against mcp-audit-skill), Phase 2 Semantic/richer responses (`:21-30`), Phase 2.5 Consolidation of swiss-geodata-mcp (`:32-49`), Phase 3 Write operations (`:51-55`, "not planned", with an explicit requirement to re-run the Lethal-Trifecta assessment and a security review before any write tool).

What fails:

- **Contradictory phase declaration.** `README.md:315` says the server is in Phase 1, but `docs/roadmap.md:6` marks Phase 1 "(✅ done)", `docs/roadmap.md:21` marks Phase 2 "(✅ largely done)" with structured returns, structlog and `match_type` checked off (`:23-27`), and `docs/roadmap.md:32` declares Phase 2.5 "(🔄 in progress)". The three tools audited in this run were delivered under Phase 2.5 (`docs/roadmap.md:45-47`) and `src/swisstopo_mcp/server.py:494` labels the geodata facade "(Phase-2 Geodaten-Erweiterung)". A reader consulting the README gets a different phase than a reader consulting the roadmap.
- **Missing Phase 1 → 2 prerequisites.** The check requires the transition to be gated on a completed audit run, an ISDS classification and a DSG-Verarbeitungsverzeichnis. Only the audit run exists (`docs/roadmap.md:18`, `audits/` with four run directories). A case-insensitive grep for `isds|verarbeitungsverzeichnis|dsg|datenschutz` over `README.md`, `README.de.md`, `docs/` and `SECURITY.md` returns **zero hits** — neither artefact exists, yet the roadmap already reports Phase 2 as largely done and Phase 2.5 in progress.
- **No phase transitions in the CHANGELOG.** `grep -in 'phase' CHANGELOG.md` returns only four incidental hits (`:133-134` and `:151` referencing `docs/geodaten-erweiterung-phase1.md` and its live probe; `:186` noting that a roadmap and a README security section were added). No entry records the Phase 1 → Phase 2 or Phase 2 → Phase 2.5 transition or its sign-off.
- `docs/roadmap.md:49` lists "Re-run the audit against the changed surface" as an open Phase-2.5 item — the roadmap itself acknowledges that the current run was still outstanding when the tools shipped.

### Expected Behavior

Per the check's Pass Criteria:

- The current phase is declared explicitly in the README (Phase 1 / 2 / 3), single-sourced
- The phase matches the actual tool annotations (no Phase-1 server with destructive tools)
- A roadmap file with phase-specific tasks exists
- Phase transitions require documented prerequisites — Phase 1 → 2: audit run, ISDS classification and DSG-Verarbeitungsverzeichnis complete
- Phase transitions are documented in the CHANGELOG

### Evidence

- File: `README.md:313-317` / `README.de.md:311-316` — "Phase 1 — Read-only wrapper".
- File: `docs/roadmap.md:6` (Phase 1 done), `:21-30` (Phase 2 largely done), `:32-49` (Phase 2.5 in progress, incl. `:45-47` for the tools audited here, `:49` audit re-run still open), `:51-55` (Phase 3 gated).
- File: `src/swisstopo_mcp/server.py:494` — geodata facade labelled "(Phase-2 Geodaten-Erweiterung)".
- File: `src/swisstopo_mcp/server.py:91, 148, 168, 352, 375, 397, 426` — `readOnlyHint: True`; zero `destructiveHint: True` in `src/`.
- Grep: `isds|verarbeitungsverzeichnis|dsg|datenschutz` over `README.md`, `README.de.md`, `docs/`, `SECURITY.md` → zero hits.
- File: `CHANGELOG.md:133-134, 151, 186` — the only `phase` hits, none recording a transition.

### Risk Description

The substantive risk this check guards against — "we built writes because we could" — has **not** materialised: 23/23 tools are read-only, and Phase 3 is explicitly gated behind a re-run of SEC-019 and a security review (`docs/roadmap.md:53-55`). The remaining risk is governance, and it is concrete:

- Two contradictory phase declarations produce exactly the uncertainty the check's anti-pattern table names ("Phase nicht deklariert → Maintainer und Reviewer unsicher, was zugelassen ist"). A reviewer who trusts `README.md:315` believes the server is still a Phase-1 wrapper and applies Phase-1 rules to a PR that is in fact a Phase-2.5 change; a reviewer who trusts the roadmap applies looser ones. Neither can point to an authoritative statement.
- The Phase 1 → 2 gate was crossed with no record that anyone considered the ISDS and DSG requirements. For a public-open-data, auth-none, read-only server the substantive compliance risk is low — no personal data is processed, so a Verarbeitungsverzeichnis would be near-empty — but "low risk" is a reason to write a short document, not a reason to skip the gate. As it stands, nothing in the repo shows the exemption was ever assessed, so the next server in the portfolio inherits the precedent that the gate is optional.
- Without CHANGELOG entries, no phase transition has an owner or a date. If a future contributor proposes a write tool, there is no recorded decision trail showing which prerequisites were met and by whom.

### Remediation

1. Make the README the single phase authority and correct it. In `README.md:313-317` and `README.de.md:311-316`, replace the prose Phase-1 statement with a status table stating the actual phase (Phase 2.5 per `docs/roadmap.md:32`) and listing each prerequisite with its status:

   ```markdown
   ## Phase

   This server is in **Phase 2.5 — Consolidation** (see [docs/roadmap.md](./docs/roadmap.md)).

   | Property | Status |
   |---|---|
   | Read tools | 23, all `readOnlyHint: true` |
   | Write tools | none (Phase 3, not planned) |
   | ISDS classification | see `docs/isds-klassifikation.md` |
   | DSG-Verarbeitungsverzeichnis | see `docs/dsg-processing-record.md` |
   | Audit run | 2026-07-27, `audits/2026-07-27T125314-Z-swisstopo-mcp/` |
   ```

   `docs/roadmap.md` then keeps the task lists and stops being a second source of truth for the current phase.
2. Add `docs/isds-klassifikation.md`. For this server it is short: public federal open data, no personal data, no authentication, read-only — classify accordingly and state the reasoning explicitly so the exemption is recorded rather than assumed.
3. Add `docs/dsg-processing-record.md` covering the same ground for DSG: which data categories are processed (none personal — coordinates and public geodata), which upstreams are contacted (`api3.geo.admin.ch`, `geodesy.geo.admin.ch`, cantonal ÖREB endpoints, `overpass.osm.ch`, `openplzapi.org`, `geodienste.ch`), and what is logged (per-call `duration_ms`, no request payloads).
4. Record phase transitions in `CHANGELOG.md`: one entry each for Phase 1 → 2 and Phase 2 → 2.5, naming the date, the prerequisites met and who signed off. Add a line to the contributing/release notes making a CHANGELOG entry mandatory for any future phase change.

### Effort Estimate

S (<1d) — four documentation edits; the two compliance documents are short for this data profile, and no code change is required.

---

### Remediation Status (2026-07-27, batch 2)

**Closed.** Both READMEs now state Phase 2.5, matching `docs/roadmap.md`, which
is named as the single authority. The README carries a status table and the
advance criteria (roadmap items checked, re-audit with no open criticals,
CHANGELOG entry; Phase 3 additionally needs a fresh Lethal-Trifecta assessment).
