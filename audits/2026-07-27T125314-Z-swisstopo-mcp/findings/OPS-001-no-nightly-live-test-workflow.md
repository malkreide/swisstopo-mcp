## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

**Severity:** high
**Status:** closed
**Server:** swisstopo-mcp
**Check-Reference:** OPS-001
**PDF-Reference:** Anhang C1

### Observed Behavior

The mocked/live split is implemented correctly, but the live half is never executed by automation and does not cover all tools.

What is in place:

- Marker registered and CI excludes live tests: `pyproject.toml:64-66` (`[tool.pytest.ini_options] markers = ['live: live API tests (skipped in CI by default)']`) and `.github/workflows/ci.yml:26-28` runs `pytest tests/ -m "not live"` across a Python 3.11/3.12/3.13 matrix.
- Large mocked unit suite: 22 test modules, ~464 test functions for 23 tools (`tests/test_oereb.py` 61, `tests/test_stac.py` 48, `tests/test_height.py` 47, `tests/test_rest_api.py` 40, `tests/test_geocoding.py` 38, `tests/test_places.py` 28, `tests/test_openplz.py` 27, `tests/test_wmts.py` 26, `tests/test_coords.py` 24, `tests/test_geodata.py` 23, plus regression suites `tests/test_responses.py`, `tests/test_logging.py`, `tests/test_egress_allowlist.py`, `tests/test_input_validation.py`, `tests/test_shared_client.py`, `tests/test_http_app.py`, `tests/test_retry.py`, `tests/test_context.py`). Well above the "5 unit tests per tool" bar.
- `respx` HTTP mocking is used where the transport matters: `tests/test_places.py:12,96,109,117,128,134,142` (all zoning/municipality/layer_info paths), `tests/test_coords.py`, `tests/test_openplz.py`, `tests/test_lv95_input.py`, `tests/test_retry.py`. Other modules mock at the function boundary with monkeypatch instead (e.g. `tests/test_responses.py:37,49,57`).
- The three new tools have proper three-way unit coverage: happy path (`tests/test_places.py:96-107`), error path (`tests/test_places.py:142-147`, upstream 500 → `is_error` with body suppressed), and edge cases (`tests/test_places.py:134-140` empty result as soft miss; `:149-151` missing coordinates → `ValidationError`; `:172-184` historical-only municipality record → soft miss).
- Live tests exist for the new tools and are correctly marked: `tests/test_places.py:282-299` (`@pytest.mark.live class TestPlacesLive` covering `zoning_at`, `municipality_at`, `layer_info` against Zurich LV95 2683531/1247914) and `tests/test_coords.py:205-238` (`@pytest.mark.live TestReframeLive` with a WGS84→LV95→WGS84 roundtrip and a drift guard asserting the local polynomial stays within 1 m of REFRAME).

What is missing:

- **No nightly or manual live-test workflow.** `.github/workflows/` contains only `ci.yml`, `publish.yml` and `security.yml`. None has a `schedule:` trigger or a `pytest -m live` step, so the 17 live tests are never executed by automation. This gap was already recorded in the 2026-05-29 run and is unchanged.
- **5 of 23 tools have no live test:** `swisstopo_find_features` and `swisstopo_get_feature` (`tests/test_rest_api.py:361-378` covers only `search_layers` and `identify_features`), `swisstopo_get_collection` (`tests/test_stac.py:386` covers only `search_geodata`), `swisstopo_get_egrid` and `swisstopo_get_oereb_extract` (`tests/test_oereb.py`: zero live markers despite 61 tests). `tests/test_wmts.py` also has zero live markers, but `swisstopo_map_url` is a pure URL builder with no network call, so that is correct by design.
- Layout note only, not counted against the status: `tests/test_unit.py` and `tests/test_live.py` as named files do not exist; the repo splits per source module and separates live tests by marker within each file, which is functionally equivalent to the check's intent.

### Expected Behavior

Per the check's Pass Criteria:

- At least 5 unit tests per tool, mocked with `respx`
- At least 1 live test per tool, marked `@pytest.mark.live`
- Marker registered in `pyproject.toml`
- CI workflow runs `pytest -m "not live"`
- **A separate nightly/manual live-test workflow** (`schedule:` + `workflow_dispatch` running `pytest -m live`)
- Live tests use test-specific credentials rather than production keys (vacuously satisfied — all upstream endpoints are key-less)

### Evidence

- File: `pyproject.toml:64-66` — live marker registered.
- File: `.github/workflows/ci.yml:26-28` — `pytest tests/ -m "not live"` on a 3.11/3.12/3.13 matrix.
- File: `tests/test_places.py:282-299`, `tests/test_coords.py:205-238` — live tests exist and are correctly marked.
- Directory: `.github/workflows/` — contains only `ci.yml`, `publish.yml`, `security.yml`; no `schedule:` trigger and no `pytest -m live` step anywhere.
- File: `tests/test_rest_api.py:361-378`, `tests/test_stac.py:386`, `tests/test_oereb.py` — live coverage gaps for `find_features`, `get_feature`, `get_collection`, `get_egrid`, `get_oereb_extract`.
- File: `README.md:404` — the README itself flags the cantonal ÖREB endpoint formats (`oereb.geo.zh.ch`, `www.oereb2.apps.be.ch`) as inconsistent.

### Risk Description

Schema drift in the upstream APIs goes undetected until someone runs the live suite by hand. This is not theoretical for the current release: the tool surface just grew onto two upstream layers whose attribute schemas the handlers depend on **by name** —

- `src/swisstopo_mcp/rest_api.py:412-422` reads `ch_bez_d` / `ch_bez_f` / `ch_code_hn` / `bfs_no` / `kt_kz`
- `src/swisstopo_mcp/rest_api.py:443-456` reads `is_current_jahr` / `gemname` / `gde_nr` / `kanton`

The unit fixtures pin those exact names. A rename upstream would leave CI fully green while every zoning and municipality result silently returns nulls — the worst class of failure for a data server, because it is indistinguishable from "no data at this location". The live tests that would catch it exist; nothing runs them.

The unlive-tested pair `swisstopo_get_egrid` / `swisstopo_get_oereb_extract` is the most exposed remainder, since those hit cantonal endpoints whose formats the README already describes as inconsistent — precisely the endpoints most likely to change without notice.

### Remediation

1. Add `.github/workflows/live-test.yml`:

   ```yaml
   on:
     schedule:
       - cron: "0 4 * * *"   # nightly 04:00 UTC
     workflow_dispatch:
   jobs:
     live-tests:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v5
         - uses: actions/setup-python@v6
           with:
             python-version: "3.12"
         - run: pip install -e ".[dev]"
         - run: pytest -m live -v
   ```

   No credentials are needed — all upstreams are key-less. Route failures to an issue or a notification so a red nightly is actually seen; a silently failing schedule reproduces the current situation.
2. Close the live-coverage holes with one live test per tool:
   - `tests/test_oereb.py`: add a `@pytest.mark.live` class covering `swisstopo_get_egrid` and `swisstopo_get_oereb_extract` against a known Zurich parcel, asserting only structural invariants (EGRID present, extract non-empty) so cantonal content changes do not cause false alarms.
   - `tests/test_rest_api.py:361-378`: extend the live class with `find_features` and `get_feature`.
   - `tests/test_stac.py:386`: add a live `get_collection` case.
3. Make schema drift explicit rather than incidental: in the new live tests for zoning and municipality, assert the presence of the attribute names the handlers read (`ch_bez_d`, `bfs_no`, `kt_kz`, `is_current_jahr`, `gemname`, `gde_nr`, `kanton`) so a rename fails loudly with a readable message instead of surfacing as an empty result.

### Effort Estimate

M (1-3d) — the workflow file is an hour; the five missing live tests plus the schema-drift assertions are the bulk of the work.

---

### Remediation Status (2026-07-27, batch 2)

**Closed.** `.github/workflows/live-test.yml` runs the `live` suite nightly at
04:00 UTC plus on demand, and opens a single deduplicated issue on failure.
Keeping `live` out of PR CI stays correct — an upstream outage must not fail an
unrelated PR — but excluded-and-never-run meant an upstream contract change
would surface as a user-facing bug instead of a build failure.
