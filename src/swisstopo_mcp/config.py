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
    # Comma-separated Host header values the server answers MCP requests on.
    # Needed behind an ingress/proxy: the SDK's DNS-rebinding protection rejects
    # any Host it was not told about, and its default list is localhost only
    # (audit SDK-004 / SCALE-001).
    allowed_hosts: str = ""
    log_level: str = "INFO"

    # Loopback defaults so the local `--http` workflow needs no configuration.
    # The `:*` suffix is the SDK's wildcard-port syntax — without it the entries
    # would only match the configured `http_port`, and `--port` overrides it at
    # runtime, which would lock the developer out of their own server.
    _LOCAL_ORIGINS = ("http://localhost", "http://localhost:*", "http://127.0.0.1", "http://127.0.0.1:*")
    _LOCAL_HOSTS = ("localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*")

    @staticmethod
    def _split(value: str) -> list[str]:
        return [v.strip() for v in value.split(",") if v.strip()]

    @staticmethod
    def _merge(defaults: tuple[str, ...], extra: list[str]) -> list[str]:
        merged = list(defaults)
        for v in extra:
            if v not in merged:
                merged.append(v)
        return merged

    @property
    def origins_list(self) -> list[str]:
        """CORS origins — exactly what was configured, no loopback defaults."""
        return self._split(self.allowed_origins)

    @property
    def allowed_hosts_list(self) -> list[str]:
        """Host values for the SDK transport-security middleware.

        A deployment adds its own hostname via SWISSTOPO_ALLOWED_HOSTS; without
        it the SDK's localhost-only default rejects every proxied request with
        421 (audit SCALE-001).
        """
        return self._merge(self._LOCAL_HOSTS, self._split(self.allowed_hosts))

    @property
    def transport_origins_list(self) -> list[str]:
        """Origins for the SDK transport-security middleware.

        Deliberately wider than `origins_list`, which drives CORS: the
        middleware runs *before* CORS, so a loopback browser client would be
        rejected with 403 before CORS is ever consulted (audit SDK-004).
        """
        return self._merge(self._LOCAL_ORIGINS, self.origins_list)


settings = Settings()
