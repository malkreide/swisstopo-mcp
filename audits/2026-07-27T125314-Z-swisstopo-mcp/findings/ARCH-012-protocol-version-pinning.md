## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

**Severity:** medium
**Status:** closed
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-012
**PDF-Reference:** Anhang A9

### Observed Behavior
There is no explicit `protocolVersion` pin in the server code — a case-insensitive grep for `protocol.?version` over `src/` returns zero hits. The FastMCP instance is constructed with `name`, `lifespan` and `instructions` only (`src/swisstopo_mcp/server.py:42-76`), so the negotiated version is whatever the SDK default is.

That gap is largely structural rather than an omission. The pin is not expressible through the SDK's public API: inspecting mcp 1.28.1 in a clean venv, neither `FastMCP.__init__` nor the lowlevel `Server.__init__` accepts a `protocol_version` parameter, and `mcp.types.LATEST_PROTOCOL_VERSION` is `"2025-11-25"`. The version is negotiated during `initialize` and is not author-settable.

A compensating control is in place and deliberate: `pyproject.toml:31-33` pins the SDK to the 1.x major with the inline rationale "Pinned to the 1.x major so an SDK update cannot silently change the negotiated MCP protocol version (ARCH-012). Dependabot proposes bumps." — `mcp[cli]>=1.28.1,<2.0.0`.

Two of the three gaps from the 2026-05-29 run are genuinely closed. Both READMEs now carry the required section (`README.md:340-345` "MCP Protocol Version", `README.de.md:341-347` "MCP-Protokollversion"), each explaining the negotiate-plus-major-pin approach and pointing at Dependabot and `CHANGELOG.md`. Automated SDK update PRs are configured: `.github/dependabot.yml` sets a monthly pip schedule with a dedicated `mcp-sdk` group matching the mcp package, separated from a catch-all `python-deps` group, plus a monthly github-actions entry. `CHANGELOG.md` is in Keep-a-Changelog format with a SemVer reference (`CHANGELOG.md:1-6`), an `[Unreleased]` section and dated releases (`[0.2.0] - 2026-07-20`, `[0.1.0] - 2026-04-02`), and is actively maintained — the three new tools and the 20→25 budget raise are at `CHANGELOG.md:11-28`, and the SDK pin decision itself is logged at `CHANGELOG.md:206`.

What remains is that no concrete spec version is recorded anywhere in the repo, and there is no breaking-change policy.

### Expected Behavior
- `protocolVersion` explicitly pinned in the server code (not "latest", not the default)
- `CHANGELOG.md` present, in Keep-a-Changelog format
- CHANGELOG entries explicitly name spec-version bumps
- README has an "MCP Protocol Version" section naming the currently supported version
- Update policy documented in the README
- Dependabot or Renovate active for monthly SDK update PRs

### Evidence
- No pin in code: case-insensitive grep for `protocol.?version` over `src/` returns zero hits; instance constructed with name/lifespan/instructions only at `src/swisstopo_mcp/server.py:42-76`
- Not expressible via the SDK: inspected mcp 1.28.1 — neither `FastMCP.__init__` nor lowlevel `Server.__init__` accepts a `protocol_version` parameter; `mcp.types.LATEST_PROTOCOL_VERSION` is `"2025-11-25"`
- Compensating major pin with rationale: `pyproject.toml:31-33` (`mcp[cli]>=1.28.1,<2.0.0`)
- CHANGELOG format and maintenance: `CHANGELOG.md:1-6`, `CHANGELOG.md:11-28`, SDK pin decision at `CHANGELOG.md:206`
- README sections in both languages: `README.md:340-345`, `README.de.md:341-347`
- Dependabot config: `.github/dependabot.yml` (monthly pip, `mcp-sdk` group for the mcp package, separate `python-deps` group, monthly github-actions)

Gaps:
- The README "MCP Protocol Version" section names no concrete spec version — neither `README.md:340-345` nor `README.de.md:341-347` states which protocol version is actually negotiated (2025-11-25 under the pinned mcp 1.28.1), so the criterion "README section with the currently supported version" is unmet and there is no baseline against which a future silent change could be detected
- No CHANGELOG entry references a spec version at all: a grep for `2024-11` / `2025-03` / `2025-06` / `2025-11` across `CHANGELOG.md` returns zero hits. The SDK pin is recorded (`CHANGELOG.md:206`) but not the protocol version it currently yields, leaving the audit-trail criterion unmet
- No breaking-change / compatibility-window policy is documented: the README section covers how updates are proposed (Dependabot, monthly) but not what happens when a spec change breaks compatibility — no semver-major trigger rule and no support window for older spec versions

### Risk Description
The missing pin in code is not actionable — the Python SDK does not expose it, and the 1.x major pin at `pyproject.toml:31-33` is the best available substitute, documented as such. Marking it as an open defect would be marking the SDK's design as this server's defect.

The gap that does matter is cheap and self-defeating in a specific way: the major pin exists to prevent a silent protocol-version change, but because no file in the repo records which version is currently negotiated, exactly the drift the pin is meant to prevent would be undetectable by reading the repo. If a patch-level mcp bump inside the 1.x range moves `LATEST_PROTOCOL_VERSION` — which is permitted by the constraint `>=1.28.1,<2.0.0` — nothing in the README, the CHANGELOG or the tests would show it. A maintainer investigating a client compatibility complaint six months from now has no baseline to diff against and must reconstruct the version by inspecting the installed SDK, which is precisely the reconstruction work the audit-trail criterion exists to eliminate.

Given how fast this spec moves (four major updates in 13 months, per the check's own framing), the absent breaking-change policy compounds it: Dependabot will open the PR, and there is no written rule saying whether a protocol change is a major bump for this server or what happens to clients still speaking the old version.

### Remediation
1. **Record the negotiated version in both READMEs.** Extend `README.md:340-345` and `README.de.md:341-347` with the concrete value and where it comes from:

```markdown
## MCP Protocol Version

This server negotiates the MCP protocol version during `initialize`; the
Python SDK does not expose an author-settable pin. As of `mcp` 1.28.1 the
negotiated version is **2025-11-25** (`mcp.types.LATEST_PROTOCOL_VERSION`).
The SDK is pinned to the 1.x major in `pyproject.toml` so an update cannot
silently move it; Dependabot proposes bumps monthly.

### Update Policy
- SDK updates are tested on a feature branch before merge.
- A change to the negotiated protocol version is recorded in CHANGELOG.md
  under `### Changed` with both the old and new version.
- A protocol change that breaks existing clients triggers a major release.
- Compatibility window: the previous spec version is supported for 6 months
  after a bump.
```

Adjust the window to whatever the portfolio actually commits to — the point is that a number exists, not that it is six months.

2. **Add a CHANGELOG entry now**, retroactively, under the release that introduced the current SDK pin: "MCP protocol version negotiated as 2025-11-25 (mcp 1.28.1)". Adopt the convention that every mcp bump PR notes the resulting protocol version, so `CHANGELOG.md` becomes the audit trail the criterion asks for.
3. **Make the drift detectable automatically.** A test is stronger than a documentation convention here, because Dependabot merges are routine:

```python
# tests/test_protocol_version.py
from mcp.types import LATEST_PROTOCOL_VERSION

EXPECTED = "2025-11-25"   # keep in sync with README + CHANGELOG

def test_negotiated_protocol_version_unchanged():
    assert LATEST_PROTOCOL_VERSION == EXPECTED, (
        "SDK protocol version changed — update README, CHANGELOG and this constant, "
        "and assess client compatibility per the update policy."
    )
```

This turns a silent SDK-side change into a red CI run on the Dependabot PR, which is the moment the maintainer can actually act on it.

4. Once items 1–3 land, this check passes. Re-check the pin criterion when an SDK version exposes `protocol_version` on the constructor; until then, `pyproject.toml:31-33` plus the test in item 3 is the complete available control.

### Effort Estimate
S (<1d)

---

### Remediation Status (2026-07-27, follow-up PR)

**Closed** to the extent the SDK allows. A code-level `protocolVersion` pin is
still not expressible in mcp 1.28.1 — verified again in a clean venv. What the
finding asked for beyond that is now present: both READMEs name the concrete
negotiated version (**2025-11-25**, `mcp.types.LATEST_PROTOCOL_VERSION`) and
state an update policy, and `tests/test_protocol_version.py` fails if a
Dependabot bump moves it — a tripwire rather than a documentation convention.
