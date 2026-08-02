# tests/test_live_coverage.py
"""Every tool has a nightly live test (audit OPS-001).

The nightly workflow exists, is valid, runs only the `live` marker and files a
deduplicated issue on failure. What it could not do is detect contract drift for
the ten tools that had no live test at all — including all three ÖREB tools,
which are the only cantonal, per-canton-format upstream in this server and
therefore the most drift-prone thing it talks to.

Counting live tests is not the same as covering tools, so this maps one to the
other: each tool must be named in at least one `@pytest.mark.live` test. The
mapping is by tool name appearing in a live test module, which is coarse — a
test that merely mentions a name would satisfy it — but it is enough to make an
uncovered tool visible, and adding a live test that mentions a tool without
calling it would be a strange thing to do deliberately.
"""

from __future__ import annotations

import ast
import asyncio
import pathlib

import pytest

from swisstopo_mcp.server import mcp

TESTS = pathlib.Path(__file__).resolve().parent

# Tools deliberately without a live test, each with the reason. An entry here is
# a decision; an omission is a gap. The list is asserted non-stale below.
LIVE_EXEMPT: dict[str, str] = {
    # Builds a URL string locally from validated inputs — there is no upstream
    # call to drift. `tests/test_wmts.py` covers the construction.
    "swisstopo_map_url": "pure URL construction, no upstream request",
}


def _live_test_sources() -> dict[str, str]:
    """Module name → source of every function/class marked `live`."""
    sources: dict[str, str] = {}
    for path in sorted(TESTS.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "pytest.mark.live" not in text:
            continue
        tree = ast.parse(text)
        chunks: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            marked = any(
                "live" in ast.unparse(dec) and "pytest.mark" in ast.unparse(dec)
                for dec in node.decorator_list
            )
            if marked:
                chunks.append(ast.unparse(node))
        if chunks:
            sources[path.name] = "\n".join(chunks)
    return sources


@pytest.fixture(scope="module")
def live_sources() -> dict[str, str]:
    return _live_test_sources()


@pytest.fixture(scope="module")
def tool_names() -> list[str]:
    return sorted(t.name for t in asyncio.run(mcp.list_tools()))


class TestTheSweepIsMeaningful:
    def test_live_tests_were_found(self, live_sources):
        """A sweep that collects nothing passes vacuously."""
        assert len(live_sources) >= 8, f"only found live tests in {sorted(live_sources)}"

    def test_all_tools_were_enumerated(self, tool_names):
        assert len(tool_names) >= 20


def _handler_name(tool_name: str) -> str:
    """`swisstopo_zoning_at` -> `zoning_at`.

    Live tests call the handler coroutine directly rather than going through the
    MCP layer, so the tool name never appears in them. The `swisstopo_` prefix is
    a hard convention (SEC-022) and `tests/test_tool_namespace.py` fails if a
    tool drops it, so stripping it is a safe mapping.
    """
    return tool_name.removeprefix("swisstopo_")


class TestEveryToolHasALiveTest:
    def test_the_naming_convention_the_mapping_relies_on_holds(self, tool_names):
        assert all(name.startswith("swisstopo_") for name in tool_names), (
            "the tool->handler mapping strips the swisstopo_ prefix; a tool "
            "without it would be silently reported as uncovered"
        )

    def test_no_tool_is_uncovered(self, live_sources, tool_names):
        blob = "\n".join(live_sources.values())
        uncovered = [
            name
            for name in tool_names
            if _handler_name(name) not in blob and name not in LIVE_EXEMPT
        ]
        assert uncovered == [], (
            f"tools with no live test: {uncovered}. The nightly run cannot "
            "detect upstream contract drift for these — add a shallow live test "
            "or list the tool in LIVE_EXEMPT with a reason."
        )

    def test_exemptions_are_not_stale(self, tool_names):
        """A tool that no longer exists should not keep its exemption."""
        gone = [name for name in LIVE_EXEMPT if name not in tool_names]
        assert gone == [], f"LIVE_EXEMPT names tools that no longer exist: {gone}"

    def test_the_oereb_cluster_is_covered(self, live_sources):
        """Named explicitly because it is the sharp case: the only cantonal,
        per-canton-format upstream here, and the audit found none of it tested."""
        blob = "\n".join(live_sources.values())
        for tool in (
            "swisstopo_get_egrid",
            "swisstopo_get_oereb_extract",
            "swisstopo_oereb_at",
        ):
            assert _handler_name(tool) in blob, f"{tool} has no live test"


class TestLiveTestsAreExcludedFromPrCi:
    """The separation the check asks for: an upstream outage must not fail an
    unrelated PR, and `-m live` must not be a silent no-op."""

    def test_the_marker_is_registered(self):
        import tomllib

        pyproject = tomllib.loads((TESTS.parent / "pyproject.toml").read_text(encoding="utf-8"))
        markers = pyproject["tool"]["pytest"]["ini_options"]["markers"]
        assert any(m.startswith("live:") for m in markers), (
            "an unregistered marker makes `-m live` select nothing silently"
        )

    def test_pr_ci_excludes_them(self):
        ci = (TESTS.parent / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert '-m "not live"' in ci

    def test_the_nightly_workflow_runs_only_them(self):
        nightly = (TESTS.parent / ".github" / "workflows" / "live-test.yml").read_text(
            encoding="utf-8"
        )
        assert "-m live" in nightly
        assert "schedule:" in nightly
        assert "workflow_dispatch:" in nightly


class TestTheFailureReportingPathIsRobust:
    """It only runs `if: failure()` — i.e. when something is already broken —
    so it must not itself depend on anything a green run never exercises. It
    previously used a pinned third-party action whose tag resolution was never
    tested on a passing night (audit OPS-001)."""

    @staticmethod
    def _workflow() -> dict:
        import yaml

        return yaml.safe_load(
            (TESTS.parent / ".github" / "workflows" / "live-test.yml").read_text(encoding="utf-8")
        )

    def _report_step(self) -> dict:
        steps = self._workflow()["jobs"]["live-tests"]["steps"]
        matches = [s for s in steps if s.get("if") == "failure()"]
        assert matches, "no failure-reporting step"
        return matches[0]

    def test_the_reporting_step_uses_no_third_party_action(self):
        step = self._report_step()
        assert "uses" not in step, (
            f"the failure path depends on {step.get('uses')}, whose resolution "
            "is never exercised on a green run — a bad pin would fail silently "
            "for exactly the reader who needed the report"
        )
        assert "run" in step

    def test_it_declares_the_permission_it_needs(self):
        """A read-only default token would be discovered on a night when the
        tests had already failed."""
        job = self._workflow()["jobs"]["live-tests"]
        assert job.get("permissions", {}).get("issues") == "write"

    def test_it_deduplicates(self):
        script = self._report_step()["run"]
        assert "gh issue list" in script and "live-test-failure" in script, (
            "without a dedup check the job files one issue per night"
        )

    def test_the_shell_script_parses(self):
        """`bash -n` on the actual script — a syntax error here surfaces only
        during a real failure otherwise."""
        import subprocess
        import tempfile

        script = self._report_step()["run"]
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as handle:
            handle.write(script)
            path = handle.name
        result = subprocess.run(["bash", "-n", path], capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr

    def test_remaining_pinned_actions_are_first_party(self):
        """The tags could not be verified from the audit sandbox and cannot be
        verified from here either — this session's GitHub scope covers only this
        repository. What is checkable is that every remaining pin is an
        `actions/*` action on the always-executed path, where a bad tag fails
        the run loudly on the first night rather than silently."""
        steps = self._workflow()["jobs"]["live-tests"]["steps"]
        used = [s["uses"] for s in steps if "uses" in s]
        assert used, "expected at least the checkout action"
        for action in used:
            assert action.startswith("actions/"), f"third-party action pinned: {action}"
        for step in steps:
            if "uses" in step:
                assert step.get("if") != "failure()", (
                    "an action on the failure-only path is never exercised by a green run"
                )


# ---------------------------------------------------------------------------
# Phase declarations stay consistent (audit OPS-003)
#
# The original defect was the READMEs declaring Phase 1 while the roadmap said
# 2.5, and the remediation reintroduced a variant of it: the status table went
# into the English README only, both files kept a stray "Phase-1 read-only
# wrapper" sentence, and the two documents named *each other* as authoritative,
# so neither was. All of that was found by reading. This makes it mechanical.
# ---------------------------------------------------------------------------

ROOT = TESTS.parent
PHASE_DOCS = ("README.md", "README.de.md", "SECURITY.md", "SECURITY.de.md")


def _declared_phase(text: str) -> set[str]:
    import re

    return set(re.findall(r"Phase[\s-]?(\d(?:\.\d)?)", text))


class TestPhaseDeclarationsAgree:
    @staticmethod
    def _roadmap_phase() -> str:
        import re

        text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        done = re.findall(r"^## Phase ([\d.]+) .*✅", text, re.M)
        assert done, "the roadmap declares no completed phase"
        return done[-1]

    def test_the_roadmap_declares_itself_the_authority(self):
        text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        assert "single authority" in text

    def test_no_document_claims_authority_back(self):
        """The circular reference that made neither document authoritative."""
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        assert "declared in the README" not in roadmap

    def test_every_document_names_the_current_phase(self):
        current = self._roadmap_phase()
        for name in PHASE_DOCS:
            text = (ROOT / name).read_text(encoding="utf-8")
            assert current in _declared_phase(text), (
                f"{name} does not mention Phase {current}, which docs/roadmap.md "
                "declares as current"
            )

    def test_no_document_still_calls_itself_phase_one(self):
        """Both READMEs kept a 'Phase-1 read-only wrapper' sentence 138 lines
        below the section declaring Phase 2.5."""
        import re

        offenders = []
        for name in PHASE_DOCS:
            text = (ROOT / name).read_text(encoding="utf-8")
            if re.search(r"Phase[\s-]1[\s-](read-only|Read-only)", text):
                offenders.append(name)
        assert offenders == [], f"{offenders} still describe the server as a Phase-1 wrapper"


class TestBothReadmesCarryTheSamePhaseTable:
    """The remediation put the status table in the English README only — the
    same bilingual drift the original finding was about."""

    ROWS = ("ISDS", "DSG")

    @staticmethod
    def _phase_section(name: str) -> str:
        text = (ROOT / name).read_text(encoding="utf-8")
        start = text.index("### Phase")
        return text[start : start + 2000]

    def test_both_readmes_have_a_status_table(self):
        for name in ("README.md", "README.de.md"):
            section = self._phase_section(name)
            assert "|---|---|" in section, f"{name} has no phase status table"

    def test_both_readmes_state_the_advance_criteria(self):
        for name, marker in (("README.md", "advance requires"), ("README.de.md", "Phasenwechsel")):
            assert marker in self._phase_section(name), (
                f"{name} does not state what a phase advance requires"
            )

    def test_both_readmes_reference_the_phase_one_exit_criteria(self):
        """ISDS classification and DSG record are the check's Phase-1 gate. They
        were absent and not documented as waived."""
        for name in ("README.md", "README.de.md"):
            section = self._phase_section(name)
            for row in self.ROWS:
                assert row in section, f"{name} phase table has no {row} row"

    def test_the_assessment_document_exists_and_is_reasoned(self):
        doc = (ROOT / "docs" / "isds-dsg.md").read_text(encoding="utf-8")
        assert "Verarbeitungsverzeichnis" in doc
        # A waiver without its trigger conditions is a hand-wave.
        assert "umstösst" in doc or "Neubewertung" in doc
