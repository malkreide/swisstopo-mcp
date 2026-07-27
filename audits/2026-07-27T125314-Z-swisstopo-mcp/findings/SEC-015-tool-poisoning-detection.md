## Finding: SEC-015 — Pre-Flight Tool-Poisoning Detection

**Severity:** medium
**Status:** closed
**Server:** swisstopo-mcp
**Check-Reference:** SEC-015
**PDF-Reference:** Sec 5.3

### Observed Behavior
No pre-flight detection layer exists. Grep for `tool.poisoning|prompt.injection|sanitize.*description|INJECTION_PATTERNS|zero-width|\u200B` over `src/` and `deploy/` returns zero hits; there is no `scan_tool_definition` / `filter_tool_list` equivalent. There are no detection tests — `tests/` contains no poisoning-detection module — and no SIEM alerting: `.github/workflows/security.yml` runs only gitleaks, and no rule or alert threshold for `tool_poisoning_detected` / `tool_poisoning_warning` events exists anywhere in `deploy/` or `docs/`.

As with SEC-014 this is a documented deferral, and here the structural argument is stronger. `SECURITY.md:62-64` records cross-server tool-poisoning detection as a host/gateway responsibility and notes that "this server's tool definitions are version-controlled and shipped from this repository; there is no dynamic or remote tool registration". `SECURITY.md:68-73` lists dynamic/remote tool registration as an explicit re-evaluation trigger.

That argument is verifiable in code: all 23 tool names, descriptions and annotations are static literals in `src/swisstopo_mcp/server.py:87-654`, and there is no registration path that reads a tool definition from a network response or a config file — no `mcp.add_tool` or equivalent dynamic registration call anywhere in `src/`.

### Expected Behavior
- A pre-flight detection layer implemented at the gateway
- At least four pattern classes covered: system prompts, override phrases, invisible characters, homoglyphs
- High-risk tool definitions filtered before forwarding (default-deny)
- Medium-risk definitions passed through but logged
- Audit events to a SIEM with alerting configured
- Tests verifying detection for standard attack patterns

### Evidence
- No detection layer: grep for `tool.poisoning|prompt.injection|sanitize.*description|INJECTION_PATTERNS|zero-width|\u200B` over `src/` and `deploy/` returns zero hits
- No detection tests in `tests/`; `.github/workflows/security.yml` runs gitleaks only; no alert rule in `deploy/` or `docs/`
- Documented deferral with structural justification: `SECURITY.md:62-64`; re-evaluation trigger: `SECURITY.md:68-73`
- The justification is verifiable: all 23 tool names, descriptions and annotations are static literals at `src/swisstopo_mcp/server.py:87-654`; no dynamic or remote registration path exists in `src/`

Gaps:
- No detection layer, so none of the four required pattern classes (system prompts, override phrases, invisible characters, homoglyphs) are covered (Pass-Criteria 1-2)
- No default-deny filtering of high-risk definitions and no logging of medium-risk ones (Pass-Criteria 3-4)
- No audit events to a SIEM and no alerting threshold (Pass-Criterion 5)
- No tests for standard attack patterns (Pass-Criterion 6)
- The German/French injection-pattern extension raised in the check's remediation is unaddressed — relevant for this portfolio since the tool descriptions here are German

### Risk Description
This check targets a gateway that aggregates potentially untrusted servers. swisstopo-mcp is a single leaf server whose own tool definitions are static and version-controlled, which makes it the *subject* of such a scan rather than the place to run one. Running a poisoning detector here would mean scanning its own literals against itself — the definitions it would scan are the ones in its git history, already covered by code review.

So the residual risk is genuinely low for this repository, and the deferral is honest. What remains open, and what the deferral does not eliminate:

- **Nothing scans this server's descriptions before they reach an LLM.** Code review is the only control. The tool descriptions are German prose (`src/swisstopo_mcp/server.py:87-654`), and the check's own remediation notes that standard injection-pattern lists are English-centric. A German override phrase or a zero-width character introduced in a future PR would not be caught by any automated check in this repo, and gitleaks does not look for this class of content.
- **This server cannot protect its users from a sibling server.** If a user runs swisstopo-mcp alongside a poisoned server, that server's descriptions can redirect calls intended for these tools. Six unprefixed tool names (see SEC-022) make this materially easier, since a poisoned definition can claim a name this server also uses.
- **The premise holds only while it holds.** The whole deferral rests on there being no dynamic tool registration. That is true today and nothing in the repo enforces it beyond convention.

### Remediation
The detection layer itself belongs to whatever gateway fronts the portfolio and should not be built into this server. Three repository-side items make the deferral durable rather than merely stated:

1. **Add a self-scan to CI**, not as a gateway substitute but as a guard on this server's own definitions. A test in `tests/` that pulls the registered tool manifest and asserts no description contains invisible characters, homoglyph-substituted ASCII, or override phrases:

```python
INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
OVERRIDE_DE = re.compile(
    r"(ignoriere|missachte|vergiss)\s+(alle\s+)?(vorherigen|bisherigen|obigen)"
    r"|system\s*[-_ ]?prompt|du\s+bist\s+jetzt", re.I)

@pytest.mark.parametrize("tool", TOOLS)
def test_description_is_clean(tool):
    assert not INVISIBLE.search(tool.description)
    assert not OVERRIDE_DE.search(tool.description)
```

   Include German and French patterns, since the descriptions in this portfolio are German — the check's remediation names this explicitly and it is the part most likely to be missed if an off-the-shelf English pattern list is adopted later.

2. **Enforce the deferral's premise.** Add a test asserting the registered tool count and the set of tool names match a committed expectation, so a dynamic-registration path cannot be introduced without a deliberate test update. This pairs naturally with the SEC-022 hash-snapshot work — one manifest snapshot serves both checks.
3. **Sharpen `SECURITY.md:62-64`** to state which control actually covers this server today (code review plus, once item 1 lands, the CI self-scan), rather than leaving the impression that nothing applies until a gateway exists. Keep the existing re-evaluation trigger and add one for the introduction of any config-driven or remotely-sourced tool description.

### Effort Estimate
S (<1d) for the repository-side items. The gateway-side detection layer is out of scope for this server and is not estimated here.

---

### Remediation Status (2026-07-27, batch 3)

**Closed as a documented deferral with a repository-side self-scan.**
Cross-server detection stays a gateway responsibility. What is now covered
here: `tests/test_tool_hygiene.py` scans this server's own tool descriptions
for invisible characters (zero-width, bidi-override, word-joiner) and for
override phrasing in **German, French and English** — the descriptions in this
portfolio are German, and an English-only pattern list would miss them.
`tool-hashes.json` pins name, description and input schema per tool.

One note worth recording: the first version of the scan contained the invisible
characters *literally* in its own pattern — exactly the failure mode it exists
to catch, and invisible to review. They are now written as `\uXXXX` escapes and
a check confirms none remain in the file.

`SECURITY.md` no longer implies nothing applies until a gateway exists, and
gains a trigger for config-driven or remotely-sourced descriptions.
