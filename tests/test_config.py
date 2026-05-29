# tests/test_config.py
"""Tests for the pydantic-settings configuration (audit finding ARCH-004)."""
from __future__ import annotations

from swisstopo_mcp.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.http_host == "127.0.0.1"
    assert s.http_port == 8000
    assert s.log_level == "INFO"
    assert s.origins_list == []


def test_env_override(monkeypatch):
    monkeypatch.setenv("SWISSTOPO_HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("SWISSTOPO_HTTP_PORT", "9000")
    monkeypatch.setenv("SWISSTOPO_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SWISSTOPO_ALLOWED_ORIGINS", "https://a.example, https://b.example")
    s = Settings(_env_file=None)
    assert s.http_host == "0.0.0.0"
    assert s.http_port == 9000
    assert s.log_level == "DEBUG"
    assert s.origins_list == ["https://a.example", "https://b.example"]


def test_origins_list_ignores_blanks(monkeypatch):
    monkeypatch.setenv("SWISSTOPO_ALLOWED_ORIGINS", " , ,https://x.example, ")
    assert Settings(_env_file=None).origins_list == ["https://x.example"]
