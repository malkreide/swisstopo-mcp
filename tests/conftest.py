# tests/conftest.py
"""Suite-wide fixtures.

## Why DNS pinning is off for the unit suite

`SWISSTOPO_PIN_DNS` defaults to **on** since 0.4.0 (audit SEC-004/SEC-005).
`PinnedTransport` implements that by resolving the hostname and rewriting
`request.url` to the resolved address *before* delegating to
`httpx.AsyncHTTPTransport` — which is precisely the layer `respx` patches. With
pinning active, a route registered for `https://api3.geo.admin.ch/...` never
matches, because what reaches the mock is `https://13.226.251.104/...`.

That is not a defect in either component. Pinning is a network-layer control and
it is doing exactly its job; the mocks are asserting against the URL the *caller*
asked for. They simply cannot both be in the stack.

The second reason matters more, and would apply even without `respx`: with
pinning on, every test that touches the HTTP path performs a real
`socket.getaddrinfo`. A unit suite that silently depends on DNS is slower, fails
differently on an offline machine, and — as happened here — passes or fails
depending on whether the developer's environment happens to set `HTTPS_PROXY`
(which disables pinning, since a proxy owns resolution). Tests should not be
sensitive to that.

So pinning is disabled here, deliberately and visibly, rather than by accident of
environment.

## What covers the on-path instead

Turning a shipped default off for the whole suite would leave that default
untested, which is how this regression reached CI in the first place. Two things
close that:

- `tests/test_dns_pinning.py` drives `PinnedTransport` directly. It never reads
  `settings.pin_dns`, so this fixture does not reach it.
- `TestTheShippedDefaultDoesNotBreakOrdinaryRequests` in the same module opts
  back in explicitly and drives a real request through `_build_client()` and
  `request_with_retry` with pinning enabled — the exact path that broke.

A test needing the shipped default can request it the same way: monkeypatch
`settings.pin_dns` back to `True` after this fixture has run.
"""
from __future__ import annotations

import pytest

from swisstopo_mcp.config import settings


@pytest.fixture(autouse=True)
def _pinning_off_for_mocked_network(monkeypatch):
    """Disable DNS pinning for the unit suite. See the module docstring."""
    monkeypatch.setattr(settings, "pin_dns", False)
