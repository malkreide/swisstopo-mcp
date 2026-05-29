# tests/test_context.py
"""Tests for Context progress/logging in long-running tools (audit finding SDK-003)."""
from __future__ import annotations

from unittest.mock import AsyncMock

from swisstopo_mcp.height import ElevationProfileInput, elevation_profile
from swisstopo_mcp.models import ToolResponse


async def test_elevation_profile_reports_progress_with_ctx(monkeypatch):
    async def mock_request(path, params=None):
        return [{"alts": {"COMB": 500}, "dist": 0}, {"alts": {"COMB": 510}, "dist": 50}]

    monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
    ctx = AsyncMock()
    result = await elevation_profile(
        ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5"), ctx=ctx
    )
    assert isinstance(result, ToolResponse)
    ctx.info.assert_awaited()  # progress/info emitted via Context
    ctx.report_progress.assert_awaited()


async def test_elevation_profile_works_without_ctx(monkeypatch):
    async def mock_request(path, params=None):
        return [{"alts": {"COMB": 500}, "dist": 0}, {"alts": {"COMB": 510}, "dist": 50}]

    monkeypatch.setattr("swisstopo_mcp.height.geo_admin_request", mock_request)
    # ctx is optional — direct calls (and unit tests) pass None
    result = await elevation_profile(ElevationProfileInput(coordinates="46.9,7.4;47.0,7.5"))
    assert isinstance(result, ToolResponse) and result.count == 2
