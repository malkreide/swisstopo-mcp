"""CORS muss die Header durchlassen, nach denen Spec 2026-07-28 routet.

Seit `2026-07-28` traegt jede Streamable-HTTP-Anfrage `Mcp-Method`, `Mcp-Name`
und `Mcp-Protocol-Version`; das SDK liest sie in `mcp.shared.inbound`. Die
Freigabeliste hier war fuer die aeltere Form geschrieben: sie nannte
`Mcp-Session-Id`, den Session-Header, der fuer sich genommen keine Anfrage routet.

Ein Browser darf einen nicht safelisteten Header gar nicht erst senden, wenn der
Server ihn nicht in `Access-Control-Allow-Headers` nennt. Der Preflight endete
mit 400, und zwar bevor ein einziges MCP-Byte floss. stdio- und Python-Clients
kennen keinen Preflight und liefen weiter — deshalb war die Suite gruen,
waehrend jeder Browser-Client ausgesperrt war.

Geprueft mit echten Anfragen gegen die zusammengebaute App. Ein Blick in
`CORS_ROUTING_HEADERS` waere kein Test: die Liste kann vollstaendig sein und
trotzdem nie an der Middleware ankommen.
`Mcp-Session-Id` gehoert dabei weiterhin auf die Liste. Eine fruehere Fassung
dieses Docstrings nannte ihn den Header einer Mechanik, die `2026-07-28`
abgeschafft habe — das stimmt nicht, und der Code hier hat es nie behauptet:
derselbe Server gibt den Header in `expose_headers` frei, damit ein
Browser-Client ihn lesen kann.

Nachgemessen statt aus Spec-Text geschlossen: `MCP_SESSION_ID_HEADER` steht
unveraendert in `mcp/server/streamable_http.py`, und ein echter `initialize`
durch den zusammengebauten ASGI-Stack bekommt eine Session-ID im
Antwort-Header zurueck. `mcp` 2.x bedient beide Protokoll-Aeren; die Session
gehoert zur Handshake-Aera, und die ist es, in der heutige Clients sprechen.
Die Freigabeliste war also nicht falsch besetzt, sondern unvollstaendig.
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


def test_der_session_header_ist_weiterhin_freigegeben(client: TestClient) -> None:
    """Haelt die Aussage im Docstring oben, statt sie nur zu behaupten.

    Eine fruehere Fassung nannte `Mcp-Session-Id` den Header einer Mechanik,
    die `2026-07-28` abgeschafft habe. Das SDK sagt etwas anderes, und dieser
    Test sagt es mit: die Konstante existiert, und der Preflight laesst den
    Header durch.

    Faellt er, ist eines von beidem passiert — die Mechanik ist tatsaechlich
    weg, oder jemand hat den Header aus der Freigabeliste genommen. Beides ist
    eine bewusste Entscheidung und keine, die still passieren darf.
    """
    from mcp.server.streamable_http import MCP_SESSION_ID_HEADER

    assert MCP_SESSION_ID_HEADER == "mcp-session-id"

    resp = preflight(client, MCP_SESSION_ID_HEADER)
    assert resp.status_code == 200, "der Session-Header wird am Preflight abgewiesen"
    assert MCP_SESSION_ID_HEADER in resp.headers["access-control-allow-headers"].lower()


# ── Methoden ───────────────────────────────────────────────────────────────
#
# `DELETE` fehlte in `allow_methods`, und der Preflight wies es mit 400 ab. Ein
# Browser-Client konnte damit Sessions oeffnen, aber nie schliessen; sie liefen
# erst am Timeout aus. Das SDK bedient die Methode sehr wohl —
# `_handle_delete_request` in `mcp.server.streamable_http`, und dessen eigene
# 405-Antwort wirbt mit `Allow: GET, POST, DELETE`. Die Freigabeliste war
# schmaler als der Server.


def _methoden_preflight(client, methode: str):
    """Wie `preflight`, aber die *Methode* ist der Prueffall.

    Der bestehende Helfer verdrahtet `POST` fest — er wurde fuer die Header
    geschrieben. Fuer die Methodenliste muss sie variabel sein.
    """
    return client.options(
        ENDPOINT,
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": methode,
            "Access-Control-Request-Headers": "content-type",
        },
    )


@pytest.mark.parametrize("methode", ["GET", "POST", "DELETE"])
def test_jede_freigegebene_methode_passiert_den_preflight(client, methode: str) -> None:
    """Einzeln parametrisiert, damit im Fehlerfall die Methode im Testnamen
    steht und nicht erst aus einer Sammelmeldung herausgelesen werden muss."""
    resp = _methoden_preflight(client, methode)
    assert resp.status_code == 200, f"Preflight fuer {methode} abgewiesen"
    assert methode.lower() in resp.headers["access-control-allow-methods"].lower()


def test_eine_nicht_freigegebene_methode_wird_abgewiesen(client) -> None:
    """Die Gegenkontrolle. Ohne sie waere der Test darueber auch gegen eine
    Methoden-Wildcard gruen — was eine andere Luecke waere, keine Behebung."""
    assert _methoden_preflight(client, "PATCH").status_code == 400


def test_die_methodenliste_nennt_die_sessionbeendigung() -> None:
    """`DELETE` ist der Grund fuer diese Liste; die Zusicherung haelt ihn fest,
    auch wenn jemand die Liste spaeter umbaut."""
    from swisstopo_mcp.server import CORS_ALLOW_METHODS

    assert "DELETE" in CORS_ALLOW_METHODS
    assert "*" not in CORS_ALLOW_METHODS
