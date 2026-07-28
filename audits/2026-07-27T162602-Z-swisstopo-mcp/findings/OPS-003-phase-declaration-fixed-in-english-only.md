## Finding: OPS-003 — Phasenarchitektur: Read-only First, dann Write, dann Multi-Agent

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** OPS-003
**PDF-Reference:** Anhang C4
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
The headline contradiction from the previous run is closed: `README.md:319` and
`README.de.md:317` both declare Phase 2.5, matching `docs/roadmap.md`. Tool
annotations match the declared phase — all 24 registrations carry `readOnlyHint=True`
and `destructiveHint=False`, verified mechanically.

Three things claimed were not fully delivered. The status table and advance criteria
went into `README.md:322-332` only; `README.de.md:317-322` has neither — the same
bilingual-drift failure mode as the original finding. Both READMEs still assert
"Phase-1 read-only wrapper" 138 lines further down (`README.md:457`,
`README.de.md:451`). And the two documents name each other as authoritative:
`README.md:320` calls the roadmap "the single authority for phase state", while
`docs/roadmap.md:3-4` points back at the README.

### Expected Behavior
- One authoritative phase declaration, consistent across all documents
- Explicit advance criteria per phase

### Evidence
- The headline contradiction from run 2026-07-27T125314-Z is closed: README.md:319 and README.de.md:317 both declare "Phase 2.5 — Consolidation of `swiss-geodata-mcp`", which matches the docs/roadmap.md heading "## Phase 2.5 — Consolidation of `swiss-geodata-mcp` (✅ done)".
- A phase status table and explicit advance criteria were added — but to the ENGLISH README only. README.md:322-332 carries the table (Read tools / Write tools / Transport / Last audit) plus the three advance conditions. README.de.md:317-322 is three sentences of prose with neither table nor criteria. The remediation is half-applied, which is the same bilingual-drift failure mode as the original finding.
- Residual Phase-1 claims survive inside both READMEs: README.md:457 ("it is a Phase-1 read-only wrapper") and README.de.md:451 ("Er ist ein Phase-1-Read-only-Wrapper"), 138 lines below the section that declares Phase 2.5. A reader landing on the MCP-Primitives section still gets the old answer.
- The two documents each name the other as authoritative: README.md:320 calls docs/roadmap.md "the single authority for phase state", while docs/roadmap.md:3-4 says "The current phase is declared in the README (\"Security & Compliance\" section)". The circular reference means neither is authoritative.
- Phase matches the tool annotations, verified mechanically: all 24 @mcp.tool declarations in src/swisstopo_mcp/server.py carry readOnlyHint=True (24 occurrences) and destructiveHint=False (24 occurrences); `grep -rn 'destructiveHint=True' src/` returns nothing.
- The phase correction is recorded in the CHANGELOG under Unreleased (CHANGELOG.md:65-67), satisfying the ARCH-012 synergy requirement.

Gaps:
- README.de.md needs the same status table and advance criteria as README.md:322-332, or the two documents are not synchronised.
- README.md:457 / README.de.md:451 still assert Phase 1 and must be reworded.
- Circular authority claim between README.md:320 and docs/roadmap.md:3-4 must be resolved to one document.
- The check's Phase-1→2 gate requires an ISDS classification and a DSG Verarbeitungsverzeichnis; neither exists in docs/ (only deployment.md, geodaten-erweiterung-phase1.md, merge-plan-swiss-geodata-mcp.md, network-egress.md, roadmap.md), and the roadmap's Phase-1 checklist does not list them. Arguably reducible for federal open data with no personal data, but the gate is not documented as waived.
- README.md:327 lists the Last audit as `audits/2026-07-27T162602-Z-swisstopo-mcp/` — this run, which is still in progress and has no report yet. The claim precedes the evidence.

### Risk Description
The circular authority claim means neither document is authoritative, so the next
contradiction has nothing to be resolved against. A reader landing on the
MCP-Primitives section still gets the Phase-1 answer, which understates the current
surface. This is documentation risk rather than runtime risk, but the phase
declaration is what gates the write-tool review — it needs to be unambiguous.

### Remediation
1. Port the status table and advance criteria into `README.de.md`.
2. Reword `README.md:457` and `README.de.md:451`.
3. Break the circle: make `docs/roadmap.md` the single authority and have both READMEs
   link to it without restating.
4. The check's Phase-1→2 gate wants an ISDS classification and a DSG
   Verarbeitungsverzeichnis. Neither exists. For federal open data with no personal
   data the case for waiving them is strong — but document the waiver rather than
   leaving the gate silently unmet.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Remediated in the previous run; half-applied. Note `README.md:327` cites this run as the last audit — a claim that preceded its evidence, and is only made true by this report.

### Auditor Notes
The specific defect the previous run named — READMEs saying Phase 1 while
the roadmap said 2.5 — is genuinely fixed in the phase sections. But three
checkable things the remediation claimed are not fully there: the German
README got neither the table nor the criteria, both READMEs still contain
a literal "Phase-1 read-only wrapper" sentence further down, and the two
documents point at each other for authority. Tool annotations do match the
declared phase, which is the substantive half of the check. Partial.
