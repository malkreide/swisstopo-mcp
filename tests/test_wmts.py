# tests/test_wmts.py
from __future__ import annotations

import pytest
from pydantic import ValidationError

from swisstopo_mcp.wmts import MapUrlInput, build_map_url

# ---------------------------------------------------------------------------
# Input Model Validation
# ---------------------------------------------------------------------------


class TestMapUrlInput:
    def test_defaults(self):
        m = MapUrlInput(lat=47.38, lon=8.54)
        assert m.zoom == 8
        assert m.layers is None
        assert m.lang == "de"

    def test_custom_values(self):
        m = MapUrlInput(lat=46.95, lon=7.44, zoom=12, layers="ch.are.bauzonen", lang="fr")
        assert m.zoom == 12
        assert m.layers == "ch.are.bauzonen"
        assert m.lang == "fr"

    def test_lat_too_low(self):
        with pytest.raises(ValidationError):
            MapUrlInput(lat=45.7, lon=8.0)

    def test_lat_too_high(self):
        with pytest.raises(ValidationError):
            MapUrlInput(lat=48.0, lon=8.0)

    def test_lon_too_low(self):
        with pytest.raises(ValidationError):
            MapUrlInput(lat=47.0, lon=5.8)

    def test_lon_too_high(self):
        with pytest.raises(ValidationError):
            MapUrlInput(lat=47.0, lon=10.6)

    def test_lat_lon_at_bounds(self):
        m1 = MapUrlInput(lat=45.8, lon=5.9)
        assert m1.lat == 45.8
        m2 = MapUrlInput(lat=47.9, lon=10.5)
        assert m2.lon == 10.5

    def test_zoom_too_low(self):
        with pytest.raises(ValidationError):
            MapUrlInput(lat=47.0, lon=8.0, zoom=0)

    def test_zoom_too_high(self):
        with pytest.raises(ValidationError):
            MapUrlInput(lat=47.0, lon=8.0, zoom=14)

    def test_zoom_at_bounds(self):
        m1 = MapUrlInput(lat=47.0, lon=8.0, zoom=1)
        assert m1.zoom == 1
        m2 = MapUrlInput(lat=47.0, lon=8.0, zoom=13)
        assert m2.zoom == 13

    def test_layers_none(self):
        m = MapUrlInput(lat=47.0, lon=8.0, layers=None)
        assert m.layers is None

    def test_layers_multiple(self):
        m = MapUrlInput(lat=47.0, lon=8.0, layers="ch.swisstopo.swissimage,ch.are.bauzonen")
        assert "ch.swisstopo.swissimage" in m.layers
        assert "ch.are.bauzonen" in m.layers

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            MapUrlInput(lat=47.0, lon=8.0, foo="bar")


# ---------------------------------------------------------------------------
# Handler: build_map_url
# ---------------------------------------------------------------------------


class TestBuildMapUrl:
    async def test_url_contains_map_geo_admin(self):
        result = await build_map_url(MapUrlInput(lat=47.38, lon=8.54))
        assert "map.geo.admin.ch" in result

    async def test_url_contains_language(self):
        result = await build_map_url(MapUrlInput(lat=47.38, lon=8.54, lang="fr"))
        assert "lang=fr" in result

    async def test_url_contains_zoom(self):
        result = await build_map_url(MapUrlInput(lat=47.38, lon=8.54, zoom=10))
        assert "zoom=10" in result

    async def test_url_contains_lv95_coordinates(self):
        result = await build_map_url(MapUrlInput(lat=47.38, lon=8.54))
        # Zurich area: E ~2683000, N ~1248000 (approximate)
        assert "E=" in result
        assert "N=" in result

    async def test_lv95_conversion_correct(self):
        # Bern: lat=46.9480, lon=7.4474 → approx E=2600000, N=1199000
        result = await build_map_url(MapUrlInput(lat=46.9480, lon=7.4474))
        # Extract E and N values from the result
        import re
        e_match = re.search(r"E=(\d+)", result)
        n_match = re.search(r"N=(\d+)", result)
        assert e_match is not None
        assert n_match is not None
        e_val = int(e_match.group(1))
        n_val = int(n_match.group(1))
        # Bern LV95: E ~2600000, N ~1199000
        assert 2595000 < e_val < 2610000
        assert 1194000 < n_val < 1204000

    async def test_no_layers_param_when_none(self):
        result = await build_map_url(MapUrlInput(lat=47.38, lon=8.54))
        assert "layers=" not in result

    async def test_layers_in_url_when_provided(self):
        result = await build_map_url(MapUrlInput(lat=47.38, lon=8.54, layers="ch.are.bauzonen"))
        assert "layers=ch.are.bauzonen" in result

    async def test_multiple_layers_in_url(self):
        result = await build_map_url(MapUrlInput(
            lat=47.38, lon=8.54,
            layers="ch.swisstopo.swissimage,ch.are.bauzonen"
        ))
        assert "ch.swisstopo.swissimage" in result
        assert "ch.are.bauzonen" in result

    async def test_known_layer_label_displayed(self):
        result = await build_map_url(MapUrlInput(lat=47.38, lon=8.54, layers="ch.are.bauzonen"))
        assert "Bauzonen" in result

    async def test_notable_layers_always_listed(self):
        result = await build_map_url(MapUrlInput(lat=47.38, lon=8.54))
        assert "ch.swisstopo.pixelkarte-farbe" in result
        assert "ch.swisstopo.swissimage" in result
        assert "ch.are.bauzonen" in result
        assert "ch.bfs.gebaeude_wohnungs_register" in result

    async def test_default_lang_is_de(self):
        result = await build_map_url(MapUrlInput(lat=47.38, lon=8.54))
        assert "lang=de" in result

    async def test_returns_markdown_link(self):
        result = await build_map_url(MapUrlInput(lat=47.38, lon=8.54))
        # Should contain a clickable Markdown link
        assert "[" in result and "](" in result

    async def test_unknown_layer_shows_id_as_label(self):
        result = await build_map_url(MapUrlInput(lat=47.38, lon=8.54, layers="ch.custom.unknown"))
        assert "ch.custom.unknown" in result
