# tests/test_primitives.py
"""Resources and Prompts (audit ARCH-008).

ARCH-008 *passed* — the check permits a Tools-only surface when the README says
why, and the reason given was true of this server: every tool takes parameters
that make its result non-addressable by a static URI.

The passing check still named two gaps, and both were real:

1. `list_available_layers` is deterministic, idempotent and already served with
   `provenance="cached"` — the one thing here that behaves like a document
   rather than a query, and still only a tool.
2. Two recurring workflows are prompt-shaped, and ARCH-007 had just shown that
   the precedence rule does not reliably reach the model through tool
   descriptions alone.

These tests hold what was added, and — more usefully — the properties that make
it worth having rather than being primitives for their own sake.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from mcp.server.mcpserver.exceptions import ResourceError, ResourceNotFoundError

from swisstopo_mcp.server import mcp, server_resources

CATALOGUE_URI = "swisstopo://catalogue/layers"


@pytest.fixture(scope="module")
def resources():
    return asyncio.run(mcp.list_resources())


@pytest.fixture(scope="module")
def prompts():
    return asyncio.run(mcp.list_prompts())


class TestTheCatalogueResource:
    def test_it_is_registered(self, resources):
        assert [str(r.uri) for r in resources] == [CATALOGUE_URI]

    def test_it_declares_json(self, resources):
        assert resources[0].mime_type == "application/json"

    def test_its_description_names_the_equivalent_tool(self, resources):
        """A resource that duplicates a tool without saying so is a second way
        to ask the same question with no guidance on which to use."""
        assert "swisstopo_list_available_layers" in (resources[0].description or "")

    async def test_it_returns_the_catalogue_with_provenance(self, monkeypatch):
        from swisstopo_mcp import geodata as gd

        async def fake_catalog(force=False):
            return [
                {
                    "canton": "ZH",
                    "base_topic": "nutzungsplanung",
                    "topic_title": "Nutzungsplanung",
                    "wms": "Freier Zugriff",
                    "opendata_terms_wms": "Freie Nutzung",
                    "contract_required_wms": False,
                    "ogc_api_features": ["https://geodienste.ch/db/np_0/deu/ogcapi"],
                }
            ]

        monkeypatch.setattr(gd, "load_geodienste_catalog", fake_catalog)
        async with server_resources():
            contents = list(await mcp.read_resource(CATALOGUE_URI))
        payload = json.loads(contents[0].content)

        assert payload["count"] == len(payload["layers"])
        assert payload["layers"], "the catalogue came back empty"
        assert payload["provenance"] == "cached"

    async def test_every_record_carries_its_licence(self, monkeypatch):
        """The CH-004 property must hold on this path too — a resource is
        another way the same data leaves the server."""
        from swisstopo_mcp import geodata as gd

        async def fake_catalog(force=False):
            return []

        monkeypatch.setattr(gd, "load_geodienste_catalog", fake_catalog)
        async with server_resources():
            contents = list(await mcp.read_resource(CATALOGUE_URI))
        payload = json.loads(contents[0].content)

        assert payload["license"]
        for record in payload["layers"]:
            assert record.get("license"), f"record without a licence: {record}"


class TestThePrompts:
    def test_both_workflows_are_registered(self, prompts):
        assert {p.name for p in prompts} == {
            "swisstopo_feature_lookup",
            "swisstopo_geodata_download",
        }

    def test_they_take_the_arguments_they_interpolate(self, prompts):
        by_name = {p.name: {a.name for a in (p.arguments or [])} for p in prompts}
        assert by_name["swisstopo_feature_lookup"] == {"ort", "was"}
        assert by_name["swisstopo_geodata_download"] == {"thema"}

    @staticmethod
    async def _render(name: str, args: dict[str, str]) -> str:
        result = await mcp.get_prompt(name, args)
        return "\n".join(
            message.content.text
            for message in result.messages
            if hasattr(message.content, "text")
        )

    async def test_the_arguments_reach_the_text(self):
        text = await self._render(
            "swisstopo_feature_lookup", {"ort": "Bederstrasse 109", "was": "die Bauzone"}
        )
        assert "Bederstrasse 109" in text
        assert "die Bauzone" in text

    async def test_the_precedence_rule_is_stated(self):
        """The reason this prompt exists: ARCH-007 showed the rule does not
        reliably reach the model through tool descriptions alone."""
        text = await self._render(
            "swisstopo_feature_lookup", {"ort": "Zürich", "was": "die Gemeinde"}
        )
        for tool in (
            "swisstopo_zoning_at",
            "swisstopo_municipality_at",
            "swisstopo_oereb_at",
        ):
            assert tool in text, f"the precedence rule omits {tool}"
        assert "swisstopo_get_egrid" in text, "the exception to the rule is missing"

    async def test_it_carries_the_zoning_caveat(self):
        """`zoning_at` is not legally binding, and a prompt that steers a model
        there without saying so is worse than no prompt."""
        text = await self._render(
            "swisstopo_feature_lookup", {"ort": "Zürich", "was": "die Bauzone"}
        )
        assert "nicht rechtsverbindlich" in text
        assert "geodienste:nutzungsplanung" in text

    async def test_it_tells_the_model_to_follow_empty_result_hints(self):
        """Ties the prompt to the ARCH-003 work: a bare negative should send the
        model to the `note`, not end the conversation."""
        text = await self._render(
            "swisstopo_feature_lookup", {"ort": "Zürich", "was": "irgendwas"}
        )
        assert "note" in text and "none" in text

    async def test_the_download_prompt_warns_against_guessing_ids(self):
        text = await self._render("swisstopo_geodata_download", {"thema": "Orthofoto"})
        assert "Orthofoto" in text
        assert "swisstopo_search_geodata" in text
        assert "swisstopo_get_collection" in text
        assert "rate sie nicht" in text


class TestEveryPromptOnlyNamesRealTools:
    """A prompt that names a tool which does not exist is a confident
    instruction to call nothing — worse than silence."""

    async def test_referenced_tools_all_exist(self, prompts):
        import re

        names = {t.name for t in await mcp.list_tools()}
        for prompt in prompts:
            args = {a.name: "x" for a in (prompt.arguments or [])}
            rendered = await mcp.get_prompt(prompt.name, args)
            text = "\n".join(
                m.content.text for m in rendered.messages if hasattr(m.content, "text")
            )
            referenced = set(re.findall(r"swisstopo_[a-z_]+", text))
            unknown = sorted(referenced - names)
            assert unknown == [], f"{prompt.name} names non-existent tools: {unknown}"


class TestTheResourceDoesNotPublishAnOutageAsAnEmptyCatalogue:
    """Raised in review of this PR, and correct.

    The tool this resource wraps degrades gracefully: on an upstream failure it
    returns an envelope with `is_error: true` and no results, which is right for
    a tool call. Serialising that envelope's *results* published `count: 0` and
    an empty list as ordinary JSON — so a geodienste outage was
    indistinguishable from a genuinely empty catalogue.

    That is the same defect class as ARCH-003 (a bare negative read as a
    factual answer) and OBS-001 (an error that presents as success), arriving
    on a surface added in the very commit that closed them. A resource is a
    document; when there is no document, an error is the honest answer.
    """

    @staticmethod
    def _break_upstream(monkeypatch):
        from swisstopo_mcp import geodata as gd

        async def unavailable(force=False):
            raise RuntimeError("geodienste unreachable")

        monkeypatch.setattr(gd, "load_geodienste_catalog", unavailable)

    async def test_an_upstream_outage_raises(self, monkeypatch):
        """The point stands under mcp 2.x: an outage is an error, not a document.

        What changed is how much of it reaches the client. 1.x let the server's
        own message through, so the detail was in ``str(excinfo.value)``. 2.x
        replaces it on purpose — the SDK does
        ``raise ResourceError(f"Error reading resource {uri}") from exc``, with
        the comment "we should not leak the exception to the client".

        So the client now sees a generic message and the detail survives only
        server-side, on ``__cause__``. Both halves are asserted: raising at all
        is the behaviour this test exists for, and the chained cause is where
        the actionable hint went.
        """
        self._break_upstream(monkeypatch)
        async with server_resources():
            with pytest.raises(ResourceError) as excinfo:
                list(await mcp.read_resource(CATALOGUE_URI))

        # `ResourceError` alone does not pin this: `ResourceNotFoundError`
        # subclasses it, so a typo in CATALOGUE_URI would keep the test green
        # while proving only that unknown URIs are rejected. The read has to
        # fail because the *upstream* broke, which is a found resource.
        assert not isinstance(excinfo.value, ResourceNotFoundError), (
            "the resource was not found at all — this no longer tests the outage path"
        )
        # What the client is told: the URI, and nothing about the upstream.
        assert str(CATALOGUE_URI) in str(excinfo.value)
        # What the server keeps: the tool's own diagnostic, via `from exc`.
        causes = []
        err = excinfo.value
        while err is not None:
            causes.append(str(err))
            err = err.__cause__
        assert any("list_available_layers" in c for c in causes), (
            f"the upstream diagnostic was lost entirely, not just sanitised: {causes}"
        )

    async def test_it_does_not_return_an_empty_document(self, monkeypatch):
        """The specific failure: a well-formed JSON body claiming zero layers."""
        self._break_upstream(monkeypatch)
        async with server_resources():
            try:
                contents = list(await mcp.read_resource(CATALOGUE_URI))
            except Exception:
                return  # raising is the correct behaviour
        payload = json.loads(contents[0].content)
        pytest.fail(
            "an upstream outage produced a document instead of an error: "
            f"count={payload['count']}, layers={payload['layers']}"
        )

    async def test_a_genuinely_empty_catalogue_still_serves(self, monkeypatch):
        """The distinction that has to survive: empty is not the same as
        broken. An upstream that answers with nothing is a valid document."""
        from swisstopo_mcp import geodata as gd

        async def empty(force=False):
            return []

        monkeypatch.setattr(gd, "load_geodienste_catalog", empty)
        async with server_resources():
            contents = list(await mcp.read_resource(CATALOGUE_URI))
        payload = json.loads(contents[0].content)
        # The static façade layers are always present, so "empty upstream"
        # still yields a catalogue — which is exactly why the outage case
        # needed a different signal rather than a count of zero.
        assert payload["count"] == len(payload["layers"])
