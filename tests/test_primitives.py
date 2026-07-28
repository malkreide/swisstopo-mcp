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
        assert resources[0].mimeType == "application/json"

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
