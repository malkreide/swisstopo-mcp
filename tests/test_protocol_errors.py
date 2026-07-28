# tests/test_protocol_errors.py
"""The protocol boundary (audit OBS-001).

Every other test in this suite calls handlers or `mcp.call_tool` directly. That
is why the divergence this module covers went unnoticed: handled execution
errors set the *payload* field `is_error`, but the SDK built a `CallToolResult`
with `isError=False` for any tool that returned normally. A spec-conformant
client reads the protocol flag, so it saw success for every handled error and
would pass a German error string downstream as though it were geodata.

These tests drive a real client session over in-memory streams — the same code
path a stdio or HTTP client takes — so the assertions are about what actually
goes over the wire.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

import jsonschema
from mcp.shared.memory import create_connected_server_and_client_session

from swisstopo_mcp.server import mcp


@asynccontextmanager
async def session():
    """Used inline rather than as a fixture: the underlying anyio cancel scope
    must be entered and exited in the same task, and a yielding fixture does
    not guarantee that under pytest-asyncio."""
    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        yield client


class TestHandledErrorsSetTheProtocolFlag:
    async def test_handled_error_sets_iserror(self):
        """An unsupported canton is a handled execution error: returned as a
        result, not raised — but the result must say so."""
        async with session() as s:
            result = await s.call_tool(
                "swisstopo_get_egrid",
                {"params": {"lat": 47.0, "lon": 8.5, "canton": "XX"}},
            )
            assert result.isError is True

    async def test_payload_and_protocol_flags_agree(self):
        async with session() as s:
            result = await s.call_tool(
                "swisstopo_get_egrid",
                {"params": {"lat": 47.0, "lon": 8.5, "canton": "XX"}},
            )
            payload = json.loads(result.content[0].text)
            assert payload["is_error"] is result.isError

    async def test_error_result_keeps_its_structured_content(self):
        """Setting the flag must not cost the envelope — attribution on the
        error path is what CH-004 was about."""
        async with session() as s:
            result = await s.call_tool(
                "swisstopo_get_egrid",
                {"params": {"lat": 47.0, "lon": 8.5, "canton": "XX"}},
            )
            assert result.structuredContent is not None
            assert result.structuredContent["source"] == "ÖREB-Kataster (Kanton)"
            assert result.structuredContent["license"] == "Kantonale ÖREB-Nutzungsbedingungen"
            assert result.content, "content blocks must survive"

    async def test_structured_content_still_matches_the_output_schema(self):
        """The error path bypasses the SDK's output validation, so validate it
        here rather than assuming the envelope conforms."""
        async with session() as s:
            tools = {t.name: t for t in (await s.list_tools()).tools}
            schema = tools["swisstopo_get_egrid"].outputSchema
            assert schema is not None

            result = await s.call_tool(
                "swisstopo_get_egrid",
                {"params": {"lat": 47.0, "lon": 8.5, "canton": "XX"}},
            )
            jsonschema.validate(instance=result.structuredContent, schema=schema)


class TestSuccessIsUnaffected:
    async def test_success_does_not_set_iserror(self):
        async with session() as s:
            result = await s.call_tool(
                "swisstopo_map_url", {"params": {"lat": 47.37, "lon": 8.54, "zoom": 10}}
            )
            assert result.isError is False
            assert result.structuredContent is not None
            assert result.structuredContent["count"] == 1

    async def test_empty_result_is_not_an_error(self, monkeypatch):
        """`match_type: "none"` is a valid answer, not a failure — the
        distinction the flag exists to preserve (ARCH-003)."""
        async with session() as s:
            async def empty(path, params=None):
                return {"results": []}

            monkeypatch.setattr("swisstopo_mcp.geocoding.geo_admin_request", empty)
            result = await s.call_tool(
                "swisstopo_geocode", {"params": {"search_text": "zzzznope"}}
            )
            assert result.isError is False
            assert result.structuredContent["match_type"] == "none"


class TestProtocolErrorsAreDistinct:
    """What the SDK does with an unknown tool or bad arguments, asserted rather
    than assumed. Both READMEs used to claim JSON-RPC `-32602`; a runtime probe
    in audit run `2026-07-27T162602-Z` showed otherwise, and this pins the
    actual behaviour so an SDK upgrade that changes it is visible.
    """

    async def test_unknown_tool_is_an_error_result(self):
        async with session() as s:
            result = await s.call_tool("does_not_exist", {})
            assert result.isError is True

    async def test_invalid_arguments_are_an_error_result(self):
        async with session() as s:
            result = await s.call_tool(
                "swisstopo_geocode", {"params": {"search_text": "x"}}
            )
            assert result.isError is True

    async def test_a_handled_error_is_not_a_protocol_error(self):
        """The separation the check is actually about: an upstream failure must
        not travel as a JSON-RPC error. It arrives as a result with content."""
        async with session() as s:
            result = await s.call_tool(
                "swisstopo_get_egrid",
                {"params": {"lat": 47.0, "lon": 8.5, "canton": "XX"}},
            )
            assert result.isError is True
            assert result.structuredContent is not None, (
                "a handled error keeps its envelope; a protocol error would not"
            )
