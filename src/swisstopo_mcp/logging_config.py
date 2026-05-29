"""Structured logging for swisstopo-mcp (audit finding OBS-003).

Logs are emitted as JSON to **stderr** — never stdout — because stdout is the
MCP protocol channel for stdio transport (see OBS-004). Use `configure_logging()`
once at startup and `log_tool_call(...)` to wrap tool handlers with bound,
per-call context (tool name + correlation id + duration).
"""
from __future__ import annotations

import functools
import logging
import os
import sys
import uuid
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any, TypeVar

import structlog

_configured = False

T = TypeVar("T")


def configure_logging(level: str | None = None) -> None:
    """Configure structlog to render JSON to stderr. Idempotent."""
    global _configured
    if _configured:
        return

    log_level = (level or os.environ.get("SWISSTOPO_LOG_LEVEL", "INFO")).upper()
    level_int = logging.getLevelName(log_level)
    if not isinstance(level_int, int):
        level_int = logging.INFO

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_int),
        # stderr — keep stdout reserved for the MCP protocol (OBS-004).
        logger_factory=structlog.WriteLoggerFactory(file=sys.stderr),
        # Caching is left off so structlog.testing.capture_logs works in tests;
        # the overhead is negligible for this server's call volume.
        cache_logger_on_first_use=False,
    )
    _configured = True


def get_logger(name: str = "swisstopo_mcp") -> Any:
    """Return a structlog logger, configuring logging on first use."""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)


def log_tool_call(tool_name: str) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorate an async tool handler to log invocation/completion/failure with
    a bound correlation id and duration. Transparent to the return value."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            log = get_logger().bind(tool=tool_name, correlation_id=uuid.uuid4().hex[:12])
            log.info("tool_invoked")
            start = perf_counter()
            try:
                result = await func(*args, **kwargs)
            except Exception:
                log.error(
                    "tool_failed",
                    duration_ms=round((perf_counter() - start) * 1000, 1),
                    exc_info=True,
                )
                raise
            log.info(
                "tool_completed",
                duration_ms=round((perf_counter() - start) * 1000, 1),
                result_chars=len(result) if isinstance(result, str) else None,
            )
            return result

        return wrapper

    return decorator
