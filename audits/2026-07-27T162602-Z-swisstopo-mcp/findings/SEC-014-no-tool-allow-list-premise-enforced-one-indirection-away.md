## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway-Pattern

**Severity:** medium
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-014
**PDF-Reference:** Sec 5.3
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
No tool allow-list exists in any form, and none is possible without an auth layer —
the server is unauthenticated by design (`SECURITY.md:45-51`), so there are no claims
to check. All 24 tools are returned to any caller.

The deferral's premises are enforced in CI, which is more than prose:
`tests/test_tool_hygiene.py:60-72` fails the build if any tool lacks `readOnlyHint` or
sets `destructiveHint`, and `tests/test_egress_allowlist.py:113-143` fails in both
directions if the code frozenset and `docs/network-egress.md` drift apart. Both run on
every push across three Python versions.

The read-only gate enforces a *declaration*, not a *property*: it reads
`t.annotations.readOnlyHint`, a self-asserted hint. A future tool that writes while
still carrying `readOnlyHint=True` passes. The claim happens to hold today — the only
non-GET in `src/` is the Overpass query POST (`overpass.py:159-165`), a read expressed
as POST — but that was verified by the auditor, not by the test.

### Expected Behavior
- Default-deny tool allow-list per team/role
- Server-side group/role check for sensitive tools
- Audit logging for denied calls

### Evidence
- No tool allow-list exists in any form: no gateway config, no allowed_tools/tool_allowlist/denied_tools key anywhere in deploy/ or the repo, and no per-role or per-group filtering of the tools/list response. src/swisstopo_mcp/server.py registers all 24 tools unconditionally; mcp.list_tools() at runtime returns all 24 to any caller. Server-side defence-in-depth via group/role claims is impossible by construction — the server is unauthenticated (SECURITY.md:45-51), so there are no claims to check.
- The deferral is documented and its premise IS enforced in CI, which is more than prose: SECURITY.md:60-69 states the deferral, and tests/test_tool_hygiene.py:60-66 fails the build if any tool lacks readOnlyHint, tests/test_tool_hygiene.py:68-72 fails if any tool sets destructiveHint. .github/workflows/ci.yml:29-31 runs the suite on every push and PR across three Python versions, so the premise cannot quietly become false. Verified: 570 tests pass.
- The test enforces a *declaration*, not a *property*. It reads t.annotations.readOnlyHint — a self-asserted hint on the tool registration (e.g. src/swisstopo_mcp/server.py:112-118). A future tool that performs a write while still carrying readOnlyHint=True would pass the gate. The substantive read-only claim happens to hold today — no POST/PUT/DELETE to a mutating endpoint exists in src/, the only non-GET is the Overpass query POST at src/swisstopo_mcp/overpass.py:159-165, which is a read expressed as POST — but that is verified by me, not by the test.
- The second CI-enforced premise is real and stronger: egress is a frozenset at src/swisstopo_mcp/api_client.py:55, and tests/test_egress_allowlist.py:113-143 fails in both directions if code and docs/network-egress.md drift apart. That genuinely bounds what a compromised or mis-specified tool can reach.

Gaps:
- No default-deny tool allow-list per team/role — the check's primary criterion — and none is possible without an auth layer.
- No server-side group/role check for sensitive tools (no auth model).
- No audit logging or alerting for denied tool calls, because nothing is ever denied.
- The read-only premise is enforced at the annotation level only; a write-capable tool that lies in its annotations would slip past tests/test_tool_hygiene.py:60-72.

### Risk Description
Architecturally correct to defer for a single unauthenticated read-only server, and
the risk-bounding argument is backed by real gates. The residual is that "enforced in
CI" carries more weight in `SECURITY.md` than it earns: the gate stands one
indirection away from the premise it substitutes for.

### Remediation
1. Add a test that asserts the property, not the annotation: no handler issues a
   non-GET request except the known Overpass POST. That converts the premise from
   auditor-verified to CI-verified.
2. Reword `SECURITY.md:60-69` to say the annotation contract is gated, not that
   read-only-ness is.
3. Revisit if auth is ever introduced — the whole check becomes applicable at that
   point.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Recorded as a documented deferral. Sustained, with the caveat above made explicit.

### Auditor Notes
I was asked to judge whether the tests enforce the deferral's premises or
merely look like they do. Verdict: they enforce a real, load-bearing thing
(the annotation contract and the egress frozenset/doc sync), and they will
actually fail — I ran them. But the read-only gate checks what a tool
*declares*, not what it *does*, so it is one indirection away from the
premise it is standing in for. Worth stating plainly rather than letting
'enforced in CI' carry more weight than it earns.
Partial: the check's actual criteria (default-deny allow-list, role scoping,
denied-call auditing) are entirely absent. Not fail, because the deferral is
architecturally correct for a single unauthenticated read-only server and
the risk-bounding argument is backed by real gates.

---

### Remediation Status (2026-07-28, follow-up PR)

**The deferral stands; the gap under it is closed.**

The check's own criteria — a default-deny allow-list per team/role, server-side
group scoping, audit events for denied calls — remain absent and remain
impossible: this server has no auth model, so there is no principal to scope
against. That part of the finding is not something a single unauthenticated
server can satisfy, and `SECURITY.md` continues to say so.

What *was* actionable is the sentence the finding closes on: *"the read-only
gate checks what a tool **declares**, not what it **does**, so it is one
indirection away from the premise it is standing in for … verified by me, not by
the test."* That is now verified by the test.

`TestReadOnlyIsAPropertyNotOnlyAnAnnotation` parses every module in `src/`,
finds each outbound HTTP call — `request_with_retry("METHOD", …)`,
`client.get/post/...`, `client.request("METHOD", …)` — and asserts:

- no `PUT`, `PATCH` or `DELETE` anywhere;
- every non-GET is a **named** exception carrying its reason. The only entry is
  Overpass, which expresses a read as `POST` because the query travels in the
  request body;
- no method is assembled at runtime, since a computed verb would slip past a
  static check;
- **listed exceptions still occur** — an allow-list that outlives its entries
  drifts into permission;
- the sweep found at least 10 call sites, so it cannot pass vacuously.

Verified in both directions against deliberate defects: a
`request_with_retry("DELETE", …)` added to `stac.py` failed two assertions by
file and line, and flipping the Overpass `POST` to `GET` failed the
stale-exception test.

The annotation test is retained. The two together are the point: the annotation
is what a tool *says*, the method sweep is what it *does*, and SEC-014's
risk-bounding argument needs the second one to be true.

**On audit logging for denied calls**, which the finding lists as absent because
"nothing is ever denied": egress refusals *are* denials, and since the OBS-002
work they are logged under `egress_blocked` with the host and reason while the
caller gets a fixed message. That is not the role-scoped denial logging the
check envisages, but it is no longer true that nothing is recorded.

Both security policies were rewritten — they previously stated the gap
explicitly ("CI enforces the *annotation*, not the property"), which was honest
and is now simply out of date.
