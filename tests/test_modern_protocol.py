"""Die 2026-07-28-Wire, end-to-end durch den echten ASGI-Stack gemessen.

`tests/test_protocol_version.py` haelt fest, *welche* Revisionen das SDK kennt,
und misst die Decke der Handshake-Aera. Was bis hierher niemand gemessen hat:
ob dieser Server die moderne Aera ueberhaupt bedient. Die Konstanten
`LATEST_MODERN_VERSION == "2026-07-28"` zu vergleichen, sagt etwas ueber das
SDK aus — nichts darueber, ob eine Anfrage in dieser Revision durch
`build_http_app()` hindurchkommt, durch die CORS-Middleware, durch die
Transport-Security und bis zu einem Tool.

Der Unterschied zur Handshake-Aera, und der Grund, warum das eigene Tests
braucht:

* Es gibt kein `initialize`. Jede Anfrage ist ein in sich geschlossener POST
  mit dem Umschlag in `params._meta` — Protokollversion, Client-Capabilities,
  optional Client-Info.
* Es gibt keine `Mcp-Session-Id`. Der Server merkt sich zwischen zwei Anfragen
  nichts.
* Die Identitaet des Servers wird nie ausgehandelt. Sie steht als
  `serverInfo`-Stempel im `_meta` **jeder** Antwort, und `server/discover`
  liefert Capabilities und Instructions. Das ist der einzige Kanal; was dort
  fehlt, erfaehrt ein Client gar nicht.
* Die Aera wird am Header `MCP-Protocol-Version` geroutet
  (`StreamableHTTPSessionManager._handle_request`): ein Wert, der nicht in
  `HANDSHAKE_PROTOCOL_VERSIONS` steht, geht auf den modernen Pfad. Ohne den
  Header landet dieselbe Anfrage im Handshake-Transport.

Die Tests unten fahren deshalb durchweg echte HTTP-Anfragen gegen
`build_http_app()`, nicht `MCPServer`-Methoden direkt.
"""

from __future__ import annotations

import json
import pathlib
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from mcp.shared.inbound import (
    MCP_METHOD_HEADER,
    MCP_NAME_HEADER,
    MCP_PROTOCOL_VERSION_HEADER,
)
from mcp.types.version import LATEST_MODERN_VERSION, MODERN_PROTOCOL_VERSIONS
from mcp_types.jsonrpc import (
    HEADER_MISMATCH,
    METHOD_NOT_FOUND,
    UNSUPPORTED_PROTOCOL_VERSION,
)

from swisstopo_mcp import __version__
from swisstopo_mcp.server import (
    LIST_CACHE_TTL_MS,
    SERVER_DESCRIPTION,
    SERVER_TITLE,
    SERVER_WEBSITE_URL,
    build_http_app,
)

MODERN = LATEST_MODERN_VERSION

# Die Umschlag-Schluessel der Spec, in der Schreibweise, die ueber die Leitung
# geht. Bewusst ausgeschrieben statt aus `mcp_types` importiert: der Test soll
# die Drahtform festhalten, die ein fremder Client sendet. Importiert ginge
# eine Umbenennung still durch — der Test schriebe dann nur noch das SDK ab.
PROTOCOL_VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _envelope(version: str = MODERN) -> dict[str, Any]:
    return {
        PROTOCOL_VERSION_KEY: version,
        CLIENT_CAPABILITIES_KEY: {},
        CLIENT_INFO_KEY: {"name": "modern-probe", "version": "1"},
    }


@asynccontextmanager
async def modern_client():
    """Ein Client auf der echten App, inklusive Lifespan und Middleware.

    Bewusst ein Kontextmanager und keine Fixture: die Lifespan oeffnet eine
    anyio-Task-Group, und eine async-Generator-Fixture betritt sie in einer
    anderen Task als der, in der pytest-asyncio sie wieder verlaesst. Der Test
    ist dann gruen und der Teardown wirft «Attempted to exit cancel scope in a
    different task» — gemessen. So laeuft beides in derselben Task, dasselbe
    Muster wie in `tests/test_protocol_version.py`.
    """
    app = build_http_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            yield client


async def _post(
    client: httpx.AsyncClient,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    name: str | None = None,
    version: str = MODERN,
    header_method: str | None = None,
) -> httpx.Response:
    """Eine Anfrage in der modernen Aera.

    `header_method` weicht nur dort vom Rumpf ab, wo ein Test die
    Kopfzeilen-Sprosse der Validierungsleiter treffen will.
    """
    body_params = dict(params or {})
    body_params["_meta"] = _envelope(version)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        MCP_PROTOCOL_VERSION_HEADER: version,
        MCP_METHOD_HEADER: header_method if header_method is not None else method,
    }
    if name is not None:
        headers[MCP_NAME_HEADER] = name
    return await client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": body_params},
    )


def _result(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = json.loads(response.text)
    assert "error" not in payload, payload["error"]
    return payload["result"]


def _error(response: httpx.Response, status: int) -> dict[str, Any]:
    assert response.status_code == status, response.text
    return json.loads(response.text)["error"]


# ---------------------------------------------------------------------------
# Die Aera selbst
# ---------------------------------------------------------------------------


async def test_server_discover_nennt_die_moderne_revision():
    """`server/discover` ersetzt `initialize` — ein zweites Verzeichnis gibt es nicht.

    Die Liste selbst kommt aus dem SDK. Gemessen wird deshalb nicht, *dass* sie
    stimmt, sondern dass dieser Server sie ueberhaupt ausliefert: ein Server,
    der die moderne Aera nicht bedient, antwortet hier gar nicht erst mit 200.
    """
    async with modern_client() as client:
        result = _result(await _post(client, "server/discover"))

    assert result["supportedVersions"] == list(MODERN_PROTOCOL_VERSIONS)
    assert MODERN in result["supportedVersions"]
    assert result["instructions"], "ohne initialize sind die Instructions nur hier zu haben"
    assert result["capabilities"]["tools"] is not None


async def test_discover_traegt_den_frischehinweis():
    """`server/discover` steht in `CACHE_HINTS` — hier zahlt es sich aus.

    Die uebrigen Eintraege prueft `tests/test_cache_hints.py` ueber eine
    `Client`-Sitzung. Fuer `server/discover` kann es das nicht: die Methode
    existiert in der Handshake-Aera nicht. Ohne diesen Test bliebe gerade der
    Eintrag ungeprueft, dessen Antwort ein moderner Client zuerst holt.
    """
    async with modern_client() as client:
        result = _result(await _post(client, "server/discover"))

    assert result["ttlMs"] == LIST_CACHE_TTL_MS
    assert result["cacheScope"] == "public"


async def test_ein_werkzeugaufruf_laeuft_ueber_die_moderne_wire():
    """Der tragende Fall: ein Tool antwortet ohne Handshake und ohne Session.

    `swisstopo_map_url` rechnet nur lokal (WGS84 → LV95 und ein URL-String),
    der Test braucht also weder Netz noch Fixture.
    """
    async with modern_client() as client:
        result = _result(
            await _post(
                client,
                "tools/call",
                {
                    "name": "swisstopo_map_url",
                    "arguments": {"params": {"lat": 46.9481, "lon": 7.4474}},
                },
                name="swisstopo_map_url",
            )
        )

    assert result["isError"] is False
    assert result["structuredContent"]["is_error"] is False
    assert "map.geo.admin.ch" in json.dumps(result["structuredContent"])


async def test_beide_aeren_listen_dieselben_werkzeuge():
    """Kein Werkzeug haengt an einer Aera.

    Die 20 Tools werden beim Import per Dekorator registriert, es gibt keine
    Verzweigung nach Protokollversion. Die Zusicherung ist billig und faellt in
    dem Moment, in dem jemand eine einbaut — dann muessen die READMEs es sagen,
    statt dass ein Client es herausfindet.
    """
    async with modern_client() as client:
        modern = _result(await _post(client, "tools/list"))
        handshake = await _handshake_tool_names(client)

    modern_names = sorted(tool["name"] for tool in modern["tools"])

    assert modern_names == handshake
    assert len(modern_names) == 20


async def _handshake_tool_names(client: httpx.AsyncClient) -> list[str]:
    """`tools/list` ueber die alte Aera: initialize, initialized, dann listen."""
    base = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    opened = await client.post(
        "/mcp",
        headers=base,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "legacy-probe", "version": "1"},
            },
        },
    )
    session = {**base, "mcp-session-id": opened.headers["mcp-session-id"]}
    await client.post(
        "/mcp", headers=session, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
    )
    listed = await client.post(
        "/mcp",
        headers={**session, "MCP-Protocol-Version": "2025-11-25"},
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    body = listed.text
    for line in body.splitlines():  # SSE-Rahmen abstreifen
        if line.startswith("data: "):
            body = line[len("data: ") :]
    return sorted(tool["name"] for tool in json.loads(body)["result"]["tools"])


# ---------------------------------------------------------------------------
# Die Identitaet — auf dieser Wire der einzige Kanal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["server/discover", "tools/list", "prompts/list"])
async def test_jede_antwort_stempelt_die_paketversion(method):
    """Ohne `initialize` gibt es keinen anderen Ort, an dem die Version stuende.

    Vor dieser Zusicherung trug jede Antwort `{"name": "swisstopo_mcp",
    "version": ""}`: `MCPServer` defaultet `version` auf den Leerstring und
    erfindet nie eine. Ein Client konnte nicht sagen, welche Fassung ihm
    antwortet, und ein Fehlerbericht konnte sie nicht nennen.

    Gegenprobe: entfernt man `version=__version__` am Konstruktor, faellt genau
    dieser Test (dreimal, einmal je Methode).
    """
    async with modern_client() as client:
        result = _result(await _post(client, method))

    stamp = result["_meta"][SERVER_INFO_KEY]
    assert stamp["name"] == "swisstopo_mcp"
    assert stamp["version"] == __version__
    assert stamp["version"], "der Leerstring ist die SDK-Vorgabe, keine Auskunft"


async def test_die_identitaet_nennt_anzeigename_und_herkunft():
    """Titel, Beschreibung und Website spiegeln `server.json`.

    Ein Client, der den Server nicht ueber die Registry gefunden hat, soll
    dieselbe Auskunft bekommen wie einer, der es getan hat.
    """
    async with modern_client() as client:
        stamp = _result(await _post(client, "tools/list"))["_meta"][SERVER_INFO_KEY]

    assert stamp["title"] == SERVER_TITLE
    assert stamp["description"] == SERVER_DESCRIPTION
    assert stamp["websiteUrl"] == SERVER_WEBSITE_URL


def test_die_identitaet_stimmt_mit_dem_registry_manifest_ueberein():
    """`server.json` und die Wire-Identitaet duerfen nicht auseinanderlaufen.

    Zwei Stellen, dieselbe Aussage — genau die Konstellation, in der eine von
    beiden veraltet, ohne dass etwas rot wird. Die Versionsnummer prueft
    `scripts/check_version_sync.py`; hier geht es um Beschreibung und Website.
    """
    manifest = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))

    assert manifest["description"] == SERVER_DESCRIPTION
    assert manifest["websiteUrl"] == SERVER_WEBSITE_URL


# ---------------------------------------------------------------------------
# Die Validierungsleiter — dass die Anfrage den Klassifikator erreicht
# ---------------------------------------------------------------------------


async def test_ein_widersprochener_routing_header_wird_abgewiesen():
    """`Mcp-Method` und der Rumpf muessen dasselbe sagen.

    Der Test gehoert hierher, obwohl die Leiter im SDK liegt: er belegt, dass
    eine moderne Anfrage den Klassifikator durch *diese* App ueberhaupt
    erreicht — durch CORS-Middleware, Transport-Security und die umgehuellte
    Lifespan. Ein Server, der still auf dem Handshake-Transport landete, gaebe
    hier eine andere Antwort.
    """
    async with modern_client() as client:
        error = _error(await _post(client, "tools/list", header_method="prompts/list"), 400)

    assert error["code"] == HEADER_MISMATCH, error
    assert MCP_METHOD_HEADER in error["message"]


async def test_eine_unbekannte_revision_wird_benannt_abgewiesen():
    """Die Absage nennt, was der Server kann — sonst raet der Client.

    `2026-99-99` ist keine Handshake-Version, die Anfrage wird also auf den
    modernen Pfad geroutet und dort abgewiesen. Dass die unterstuetzte Liste
    mitkommt, ist der Unterschied zwischen «geht nicht» und «nimm das hier».
    """
    async with modern_client() as client:
        error = _error(await _post(client, "tools/list", version="2026-99-99"), 400)

    assert error["code"] == UNSUPPORTED_PROTOCOL_VERSION, error
    assert error["data"]["supported"] == list(MODERN_PROTOCOL_VERSIONS)
    assert error["data"]["requested"] == "2026-99-99"


@pytest.mark.parametrize("method", ["ping", "logging/setLevel"])
async def test_abgeschaffte_methoden_antworten_nicht_mehr(method):
    """`2026-07-28` hat den Lifecycle und `logging/setLevel` gestrichen.

    Festgehalten, weil es wie ein Defekt aussieht, wenn es jemandem auffaellt:
    ein Client, der aus der Handshake-Aera kommt und `ping` gewohnt ist, sieht
    hier 404. Das ist die Spec, kein fehlender Handler.
    """
    params = {"level": "debug"} if method == "logging/setLevel" else None
    async with modern_client() as client:
        error = _error(await _post(client, method, params), 404)

    assert error["code"] == METHOD_NOT_FOUND
