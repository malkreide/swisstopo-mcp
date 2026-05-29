# syntax=docker/dockerfile:1
#
# Hardened container image for swisstopo-mcp (audit finding SEC-007).
# Runs the Streamable-HTTP transport as a non-root user.

FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
# Install the package + dependencies into an isolated prefix.
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim AS runtime

# Non-root user with a high, fixed UID/GID (SEC-007).
RUN useradd --uid 10001 --user-group --create-home --shell /usr/sbin/nologin mcp

COPY --from=builder /install /usr/local

USER 10001

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # In a container we must bind all interfaces — set ONLY here, never as a
    # code default (SEC-016). The code default stays 127.0.0.1.
    SWISSTOPO_HTTP_HOST=0.0.0.0 \
    SWISSTOPO_LOG_LEVEL=INFO

EXPOSE 8000

# Liveness probe target; uses stdlib (no curl in slim).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status==200 else 1)"

# Designed to run with a read-only root filesystem + tmpfs /tmp:
#   docker run --read-only --tmpfs /tmp --cap-drop ALL \
#     --security-opt no-new-privileges -p 8000:8000 swisstopo-mcp
CMD ["python", "-m", "swisstopo_mcp.server", "--http", "--port", "8000"]
