"""CORS muss die Header durchlassen, nach denen Spec 2026-07-28 routet.

Seit `2026-07-28` traegt jede Streamable-HTTP-Anfrage `Mcp-Method`, `Mcp-Name`
und `Mcp-Protocol-Version`; das SDK liest sie in `mcp.shared.inbound`. Die
Freigabeliste hier war fuer die aeltere Form geschrieben: sie nannte
`Mcp-Session-Id`, den Header genau der Session-Mechanik, die dieselbe Revision
abgeschafft hat.

Ein Browser darf einen nicht safelisteten Header gar nicht erst senden, wenn der
Server ihn nicht in `Access-Control-Allow-Headers` nennt. Der Preflight endete
mit 400, und zwar bevor ein einziges MCP-Byte floss. stdio- und Python-Clients
kennen keinen Preflight und liefen weiter — deshalb war die Suite gruen,
waehrend jeder Browser-Client ausgesperrt war.

Geprueft mit echten Anfragen gegen die zusammengebaute App. Ein Blick in
`CORS_ROUTING_HEADERS` waere kein Test: die Liste kann vollstaendig sein und
trotzdem nie an der Middleware ankommen.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from swisstopo_mcp.server import CORS_ROUTING_HEADERS, build_http_app, mcp

ORIGIN = "https://client.example"
ENDPOINT = "/mcp"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _ = monkeypatch
    return TestClient(build_http_app(allowed_origins=[ORIGIN]))


def preflight(client: TestClient, announced: str):
    """Ein Preflight, der `announced` als Wunschheader anmeldet.

    Der Header muss auf der Anfrage stehen, nicht nur in der Antwort gelesen
    werden: Starlette beantwortet einen Preflight, der einen nicht erlaubten
    Header nennt, mit 400 — das ist die Ablehnung, um die es geht.
    """
    return client.options(
        ENDPOINT,
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": announced,
        },
    )


@pytest.mark.parametrize("header", CORS_ROUTING_HEADERS)
def test_preflight_laesst_jeden_routing_header_durch(client: TestClient, header: str) -> None:
    """Einzeln geprueft: eine gemeinsame Anmeldung koennte durchgehen, obwohl
    nur einer der drei freigegeben ist."""
    resp = preflight(client, header)
    assert resp.status_code == 200, f"Preflight mit {header} wurde abgewiesen"
    assert header.lower() in resp.headers["access-control-allow-headers"].lower()


def test_preflight_laesst_die_routing_header_gemeinsam_durch(client: TestClient) -> None:
    """Was ein Browser tatsaechlich schickt: alle drei auf derselben Anfrage."""
    resp = preflight(client, ", ".join(h.lower() for h in CORS_ROUTING_HEADERS))
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_ein_nicht_freigegebener_header_wird_weiterhin_abgewiesen(client: TestClient) -> None:
    """Negativkontrolle. Ohne sie waeren die Tests oben auch gegen eine
    CORS-Schicht gruen, die jeden Header durchwinkt — ein anderer Fehler, keine
    Behebung."""
    assert preflight(client, "x-nicht-erlaubt").status_code == 400


def test_die_liste_nennt_die_header_die_das_sdk_liest() -> None:
    """Gegen die Konstanten des SDK gehalten statt gegen abgeschriebenen
    Spec-Text: `mcp.shared.inbound` ist, womit der Server die Anfrage
    tatsaechlich liest. Eine Umbenennung dort faellt hier auf, statt als
    Browser-Client, der ohne erkennbaren Grund nicht mehr verbindet."""
    from mcp.shared.inbound import (
        MCP_METHOD_HEADER,
        MCP_NAME_HEADER,
        MCP_PROTOCOL_VERSION_HEADER,
    )

    listed = {h.lower() for h in CORS_ROUTING_HEADERS}
    required = {MCP_METHOD_HEADER, MCP_NAME_HEADER, MCP_PROTOCOL_VERSION_HEADER}
    assert required <= listed, f"nicht freigegeben: {sorted(required - listed)}"


async def test_kein_tool_schema_verlangt_einen_mcp_param_header() -> None:
    """`Mcp-Param-*` traegt ein Tool-Argument als HTTP-Header, angemeldet ueber
    eine `x-mcp-header`-Annotation im Input-Schema. CORS kennt keinen
    Praefix-Wildcard, das erste Tool mit so einer Annotation muss den konkreten
    Header einzeln freigeben. Bisher tut es keines — dieser Test ist die
    Erinnerung an dem Tag, an dem sich das aendert."""
    offenders = [t.name for t in await mcp.list_tools() if "x-mcp-header" in str(t.input_schema)]
    assert not offenders, f"{offenders} brauchen einen Mcp-Param-*-Eintrag in der Freigabeliste"
