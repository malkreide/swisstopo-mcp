## Finding: SEC-014 — Tool-Allow-Listing via MCP-Gateway-Pattern

**Severity:** medium
**Status:** closed
**Server:** swisstopo-mcp
**Check-Reference:** SEC-014
**PDF-Reference:** Sec 5.3

### Observed Behavior
No tool allow-list configuration exists in the repo. `find . -iname '*allowlist*' -o -iname '*tool-policy*' -o -iname '*gateway-config*'` returns nothing, and grep for `allowed_tools|tool_allowlist|whitelist` over `deploy/` and `src/` returns no match. All 23 tools registered in `src/swisstopo_mcp/server.py:87-654` are exposed unconditionally to every caller, and `tools/list` returns the full manifest regardless of who is asking.

There is no server-side role or group check as defence-in-depth either — grep for `group|role|team` combined with check/validate/require over `src/` returns nothing. That is consistent with `auth_model=none`: there are no claims to check against, so a role gate would have nothing to gate on.

This is a documented, reasoned deferral rather than an oversight. `SECURITY.md:52-61` records tool allow-listing as a portfolio/gateway-layer control with an explicit rationale — that it "belongs to the MCP host/gateway that aggregates multiple servers, not to an individual server exposing a fixed, read-only tool set" — and states the residual risk is bounded by the egress allow-list and the read-only tool surface. `SECURITY.md:68-73` names the re-evaluation trigger: "is aggregated behind a shared MCP gateway".

The risk-bounding claims check out. All 23 tools carry `readOnlyHint: true` / `destructiveHint: false` in their annotations (e.g. `src/swisstopo_mcp/server.py:89-95`, `349-357`, `636-643`), and outbound reach is capped by the frozenset at `src/swisstopo_mcp/api_client.py:51-64`.

### Expected Behavior
- In an enterprise context: a tool allow-list per team/role, documented in gateway or server config
- The allow-list is explicitly default-deny — only listed tools are exposed
- Server-side defence-in-depth: a group/role check for sensitive tools, complementing the gateway
- Denied tool calls are audited
- The tool list the LLM client sees is filtered per team/role in the `tools/list` response

### Evidence
- No allow-list artefact anywhere: `find . -iname '*allowlist*' -o -iname '*tool-policy*' -o -iname '*gateway-config*'` returns nothing; grep for `allowed_tools|tool_allowlist|whitelist` over `deploy/` and `src/` returns no match
- All 23 tools registered unconditionally: `src/swisstopo_mcp/server.py:87-654`
- No role/group check in `src/`; no `require_group` decorator and no `ctx.user_claims` usage — consistent with `auth_model=none`
- Documented deferral with rationale: `SECURITY.md:52-61`; re-evaluation trigger: `SECURITY.md:68-73`
- Read-only annotations on every tool: `src/swisstopo_mcp/server.py:89-95`, `349-357`, `636-643`
- Egress cap: `src/swisstopo_mcp/api_client.py:51-64`

Gaps:
- No per-team/per-role allow-list documented anywhere (Pass-Criterion 1)
- No default-deny tool exposure — `tools/list` returns the full 23-tool manifest to every caller (Pass-Criteria 2 and 5)
- No server-side group/role check as defence-in-depth (Pass-Criterion 3)
- No audit logging of denied tool calls, because no call can be denied (Pass-Criterion 4)

### Risk Description
This is a documented risk acceptance, not an implemented control, and it should be read that way rather than as a defect in this repo. The check is written for a gateway that fronts multiple servers and needs to decide which team may call which tool. This server exposes a fixed, read-only tool set over Swiss public open data with no authentication, so there is no per-caller identity here to make an allow-list decision against, and no confidential data to withhold from a caller who is not entitled to it.

The residual risk the deferral leaves open is therefore narrow but not zero. Two of the three risks the check names still apply at the portfolio level and none of them can be mitigated inside this repository:

- **Tool-combination compliance.** All 23 tools are individually harmless, but a gateway aggregating this server with a server that has write or send capability creates flows that are only visible at the gateway. Nothing here can see or constrain that.
- **Tool-name shadowing across servers.** Six tools carry no server-identity prefix (see SEC-022), so in a multi-server setup an allow-list keyed on tool name would be ambiguous. That interacts badly with the deferral: the control this server defers to becomes harder to configure correctly because of a defect this server can fix.

What the deferral correctly relies on holds: every tool is read-only and annotated as such, and egress is capped to 10 public geodata hosts. The action for the maintainer is at the portfolio layer.

### Remediation
No code change in this repository is required or appropriate. Concretely:

1. **Keep the deferral, but make it verifiable.** `SECURITY.md:52-61` states the rationale; add a pointer to the two facts it depends on so a future reviewer can confirm them without re-deriving: the read-only annotations (`src/swisstopo_mcp/server.py:89-95` as the representative example) and the egress frozenset (`src/swisstopo_mcp/api_client.py:51-64`). Add a CI test asserting all registered tools have `readOnlyHint: true`, so the deferral's central premise cannot silently become false when a future tool is added.
2. **Fix SEC-022's prefixing**, which is the one part of this problem that lives here. A gateway allow-list is written against tool names; `swisstopo_*` on all 23 tools makes those entries unambiguous.
3. **Track the gateway work at the portfolio level, not as a swisstopo-mcp task.** When a shared MCP gateway is introduced for the Swiss public-data portfolio, that gateway needs a per-team allow-list, default-deny filtering of `tools/list`, and audit logging of denied calls. Record this finding as the input to that work item rather than as an open item against this server.
4. **Re-evaluate on the documented trigger.** `SECURITY.md:68-73` already names it ("is aggregated behind a shared MCP gateway"). Add a second trigger for the case where this server ever gains a non-read-only tool, since that would invalidate the risk-bounding argument the deferral rests on.

### Effort Estimate
S (<1d) for the repository-side items (1, 2 partly overlaps SEC-022, 4). The portfolio gateway itself is out of scope for this server and is not estimated here.

---

### Remediation Status (2026-07-27, batch 3)

**Closed as a documented deferral, now enforced rather than asserted.** The
gateway itself remains out of scope — no single server can allow-list across a
set it cannot see. What changed is that the deferral's premises are checked:
`tests/test_tool_hygiene.py` fails if any tool stops being read-only or becomes
destructive, so the risk-bounding argument cannot quietly go stale.

`SECURITY.md` now points at the two facts the deferral rests on and adds a
re-evaluation trigger for a non-read-only tool. The SEC-022 prefixing landed
earlier, so a future gateway allow-list can name all 23 tools unambiguously.
