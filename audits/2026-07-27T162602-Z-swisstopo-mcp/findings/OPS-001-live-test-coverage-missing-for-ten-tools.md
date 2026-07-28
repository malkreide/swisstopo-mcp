## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** OPS-001
**PDF-Reference:** Anhang C1
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
The nightly workflow is real and correct: `.github/workflows/live-test.yml` parses,
triggers on `cron "0 4 * * *"` plus `workflow_dispatch`, runs `pytest tests/ -m live`,
and files a deduplicated issue on failure. The marker is registered
(`pyproject.toml:69-71`) so `-m live` is not a silent no-op, and PR CI runs
`-m "not live"` across 3.11/3.12/3.13. 545 test functions across 27 files.

Coverage is not per-tool. The 17 tool-level live tests leave roughly ten tools with
none: `find_features`, `get_feature`, `layer_info`, `municipality_at`,
`get_collection`, `map_url`, `get_egrid`, `get_oereb_extract`, `oereb_at`,
`search_address`.

### Expected Behavior
- ≥1 live test per tool
- Separated from PR CI so an upstream outage cannot fail an unrelated PR

### Evidence
- The nightly workflow exists and is structurally valid: .github/workflows/live-test.yml parses cleanly (yaml.safe_load → job `live-tests`), triggers on `schedule: cron "0 4 * * *"` plus workflow_dispatch, runs `pytest tests/ -m live -v`, and on failure creates a deduplicated issue labelled `live-test-failure` via actions/github-script (it lists open issues with that label first and only creates one when none exist).
- `live`-marked tests really exist — 19 occurrences of @pytest.mark.live across 10 files, 17 of them tool-level: tests/test_geocoding.py:349,355,362; tests/test_height.py:393,399; tests/test_rest_api.py:361,367; tests/test_openplz.py:371,378,384; tests/test_geodata.py:246,255,268; tests/test_overpass.py:154; tests/test_coords.py:205; tests/test_stac.py:386; tests/test_places.py:282. Two more (tests/test_dns_pinning.py:138,171) cover the SEC-005 TLS/SNI handshake.
- The marker is registered so `-m live` is not a silent no-op: pyproject.toml:69-71 `markers = ["live: live API tests (skipped in CI by default)"]`.
- PR CI excludes them: .github/workflows/ci.yml runs `pytest tests/ -m "not live"` across Python 3.11/3.12/3.13, so an upstream outage cannot fail an unrelated PR — the separation the check asks for.
- Unit-test volume far exceeds the ≥5-per-tool bar: 545 test functions across 27 files for 24 tools.
- GAP — live coverage is not per-tool. Mapping the 17 tool-level live tests to the 24 tools leaves roughly ten with no live test at all: swisstopo_find_features, swisstopo_get_feature, swisstopo_layer_info, swisstopo_municipality_at, swisstopo_get_collection, swisstopo_map_url, swisstopo_get_egrid, swisstopo_get_oereb_extract, swisstopo_oereb_at and swisstopo_search_address. The ÖREB group is the notable one: it is the only cantonal, per-canton-format dependency in the server and therefore the most schema-drift-prone, and nothing nightly touches it.

Gaps:
- ≥1 live test per tool is not met — about ten tools, including the three ÖREB tools, have none.
- respx is used in only 6 of 27 test files (test_coords, test_lv95_input, test_oereb, test_openplz, test_places, test_retry); the rest mock by monkeypatching the api_client helpers, which does not exercise the URL/params/response-parsing layer the check wants respx for.
- Unverifiable in this environment: the workflow pins actions/checkout@v7, actions/setup-python@v6 and actions/github-script@v8. Outbound access to the GitHub API for actions/* is blocked here, so tag existence could not be confirmed. If any tag does not resolve, the nightly run — or specifically the failure-reporting step, which only executes `if: failure()` — fails silently for the reader.

### Risk Description
The point of the nightly job is detecting upstream contract drift. The three ÖREB
tools are the only cantonal, per-canton-format dependency in the server — the most
drift-prone upstream by a wide margin — and nothing nightly touches them. A ZH schema
change would surface as a user-visible failure rather than as a 04:00 issue.

### Remediation
1. Add live tests for the ÖREB cluster first; a known ZH parcel with a stable EGRID is
   enough to detect a schema change.
2. Then the remaining seven, at the same shallow depth — the job is drift detection,
   not correctness.
3. Widen respx use beyond the six files that have it, so the URL/params/parsing layer
   is exercised rather than monkeypatched over.
4. Unverifiable here: the workflow pins `actions/checkout@v7`, `setup-python@v6`,
   `github-script@v8` and outbound access to the GitHub API is blocked in this
   sandbox. If any tag does not resolve, the failure-reporting step — which only runs
   `if: failure()` — fails silently. Confirm the tags resolve.

### Effort Estimate
M (1-3d)

### Relation to run `2026-07-27T125314-Z`
Raised and remediated in the previous run. The workflow claim holds in full; the per-tool criterion was never met.

### Auditor Notes
The specific remediation claim holds: the workflow is real, valid, nightly,
dispatchable, runs only the live marker, and files a deduplicated issue on
failure; the marker is registered and PR CI excludes it. What keeps this
off a pass is the check's per-tool live-coverage criterion. Ten tools have
no live test, so the nightly job cannot detect contract drift for them —
and the ÖREB cluster, the most fragile upstream in the server, is among
them. Unit-side depth is excellent; the respx criterion is met in spirit
for six modules only.
