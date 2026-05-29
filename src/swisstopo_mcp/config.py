"""Centralised configuration via pydantic-settings (audit finding ARCH-004).

Server/transport/logging settings come from a single Settings object instead of
ad-hoc `sys.argv` / `os.environ` reads. All variables use the `SWISSTOPO_`
prefix and may also be supplied via a local `.env` file (see `.env.example`).
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SWISSTOPO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # HTTP transport (used with `--http`). Default host stays 127.0.0.1 — a
    # container sets SWISSTOPO_HTTP_HOST=0.0.0.0 itself (SEC-016).
    http_host: str = "127.0.0.1"
    http_port: int = 8000
    # Comma-separated CORS origins for browser MCP clients (no wildcard).
    allowed_origins: str = ""
    log_level: str = "INFO"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
