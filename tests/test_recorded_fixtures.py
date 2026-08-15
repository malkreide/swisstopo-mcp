"""Jedes Werkzeug, gefahren aus einer aufgezeichneten Antwort.

Die handgeschriebenen Stubs im Rest der Suite pruefen die *Fehler*-Pfade — ein
Timeout, ein 5xx, eine leere Trefferliste —, die sich nicht auf Zuruf
aufzeichnen lassen und als Erfindung in Ordnung sind. Was sie nicht koennen: die
Form einer Erfolgs-Antwort belegen. Sie stimmen mit dem ueberein, was ihr Autor
annahm.

Genau daran ist es hier gescheitert: `swisstopo_reverse_geocode` schickte seine
Bounding-Box in WGS84-Grad, obwohl der SearchServer sie nur in LV95 und nur mit
`sr=2056` auswertet. Das Werkzeug fand damit an **keinem** Punkt der Schweiz
eine Adresse und erklaerte das mit «der Punkt liegt womoeglich ausserhalb
besiedelten Gebiets». Die Suite blieb gruen — die Stubs lieferten Treffer, um
die die Quelle nie gebeten worden war.

Sieben Hosts, aber weit mehr Abfrageformen. Aufgezeichnet ist deshalb eine
Antwort je **Anfrage**. Zugeordnet wird beim Abspielen nach der Anfrage und
nicht nach der Reihenfolge — `_query_geodienste` faehrt seine Kantone per
`asyncio.gather`.

Herkunft, Datum, Auswahlregel und SHA-256 je Datei stehen in
`tests/fixtures/PROVENANCE.md`; neu aufzeichnen mit
`python scripts/record_fixtures.py`.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

import httpx
import pytest
import respx
from fixture_data import (
    fixture_json,
    fixture_text,
    provenance,
    recorded_names,
    recorder,
    schluessel_fuer,
    schluesselverzeichnis,
)

from swisstopo_mcp import server

ZUERICH = {"lat": 47.3769, "lon": 8.5417}

# Werkzeug → (Eingabeklasse, Eingabe, braucht ctx). Bewusst noch einmal
# hingeschrieben und nicht aus dem Recorder-PLAN abgeleitet: die Tests sollen
# eine eigene Aussage machen. Dass beide dieselben Werkzeuge fahren, prueft
# `test_der_recorder_faehrt_dieselben_werkzeuge`.
WERKZEUGE: dict[str, tuple[str, dict[str, Any], bool]] = {
    "geocode": ("swisstopo_geocode", {"search_text": "Bahnhofplatz 1, 8001 Zürich"}, False),
    "reverse_geocode": ("swisstopo_reverse_geocode", dict(ZUERICH), False),
    "height": ("swisstopo_get_height", dict(ZUERICH), False),
    "elevation_profile": (
        "swisstopo_elevation_profile",
        {"coordinates": "47.3769,8.5417;47.3800,8.5500"},
        True,
    ),
    "zoning_at": ("swisstopo_zoning_at", dict(ZUERICH), False),
    "municipality_at": ("swisstopo_municipality_at", dict(ZUERICH), False),
    "map_query_search_layers": (
        "swisstopo_map_query",
        {"operation": "search_layers", "query": "Gebäude"},
        False,
    ),
    "map_query_features_at_point": (
        "swisstopo_map_query",
        {
            "operation": "features_at_point",
            "layers": "ch.bfs.gebaeude_wohnungs_register",
            "tolerance": 10,
            **ZUERICH,
        },
        False,
    ),
    "map_query_layer_info": (
        "swisstopo_map_query",
        {"operation": "layer_info", "layer": "ch.bfs.gebaeude_wohnungs_register"},
        False,
    ),
    "search_geodata": ("swisstopo_search_geodata", {"query": "swissalti"}, False),
    "get_collection": (
        "swisstopo_get_collection",
        {"collection_id": "ch.swisstopo.swissalti3d"},
        False,
    ),
    "get_egrid": ("swisstopo_get_egrid", {**ZUERICH, "canton": "ZH"}, False),
    "oereb_at": ("swisstopo_oereb_at", {**ZUERICH, "canton": "ZH"}, True),
    "list_layers": ("list_available_layers_tool", {"source": "geodienste"}, False),
    "query_geodata_strassen": (
        "query_geodata_tool",
        {"layer": "strassenverzeichnis", "point": "47.3769,8.5417"},
        False,
    ),
    "query_geodata_oereb": (
        "query_geodata_tool",
        {"layer": "oereb-verfuegbarkeit", "point": "47.3769,8.5417"},
        False,
    ),
    "query_osm": (
        "query_osm_features_tool",
        {"feature_type": "pharmacy", "area": "47.3769,8.5417", "radius_m": 500},
        True,
    ),
    "lookup_postal_code": ("lookup_postal_code_tool", {"postal_code": "8001"}, False),
    "find_commune": ("find_commune_tool", {"name": "Zürich"}, True),
    "search_address": ("search_address_tool", {"query": "Bahnhofplatz 8001"}, False),
}


class _StillerKontext:
    """Der `ctx`, den MCPServer sonst reicht — hier ohne Ausgabe."""

    async def info(self, *a: object, **kw: object) -> None: ...

    async def warning(self, *a: object, **kw: object) -> None: ...

    async def error(self, *a: object, **kw: object) -> None: ...

    async def debug(self, *a: object, **kw: object) -> None: ...

    async def report_progress(self, *a: object, **kw: object) -> None: ...


@pytest.fixture
def quelle():
    """Beantwortet jede Anfrage aus ihrer eigenen Aufzeichnung und protokolliert mit.

    Nach der *Anfrage* zugeordnet, nicht nach der Reihenfolge: sonst waere
    `_query_geodienste` mit seinem `asyncio.gather` ein Gluecksspiel und die
    Zuordnung im gruenen Fall zufaellig richtig. Eine Anfrage ohne Aufzeichnung
    faellt hier laut auf, statt still eine fremde Datei zu bekommen.
    """
    protokoll: list[httpx.Request] = []
    verzeichnis = schluesselverzeichnis()

    def antwort(request: httpx.Request) -> httpx.Response:
        protokoll.append(request)
        schluessel = schluessel_fuer(request)
        name = verzeichnis.get(schluessel)
        if name is None:
            raise AssertionError(
                f"keine Aufzeichnung fuer diese Anfrage:\n  {schluessel}\n"
                "Neu aufzeichnen mit `python scripts/record_fixtures.py`."
            )
        return httpx.Response(200, text=fixture_text(name))

    with respx.mock:
        respx.route().mock(side_effect=antwort)
        yield protokoll


async def _fahre(name: str):
    """Ruft ein Werkzeug mit der Eingabe aus der Tabelle."""
    werkzeug, eingabe, braucht_ctx = WERKZEUGE[name]
    fn = getattr(server, werkzeug)
    modell = recorder()._eingabe(
        recorder().Aufruf(
            name=name,
            werkzeug=werkzeug,
            klasse=_klasse_fuer(name),
            eingabe=eingabe,
            braucht_ctx=braucht_ctx,
        )
    )
    return await (fn(modell, _StillerKontext()) if braucht_ctx else fn(modell))


def _klasse_fuer(name: str) -> str:
    """Die Eingabeklasse, wie sie im Recorder-Plan steht."""
    for a in recorder().PLAN:
        if a.name == name:
            return a.klasse
    raise KeyError(name)


# --------------------------------------------------------------------------
# Herkunft
# --------------------------------------------------------------------------
def test_provenance_nennt_ein_brauchbares_aufnahmedatum():
    """Eine Aufzeichnung ohne Datum ist eine undatierte Behauptung ueber die Quelle."""
    treffer = re.search(r"Aufgezeichnet am \*\*(\d{4}-\d{2}-\d{2})\*\*", provenance())
    assert treffer, "PROVENANCE.md nennt kein Aufnahmedatum im erwarteten Format"
    wann = dt.date.fromisoformat(treffer.group(1))
    assert wann <= dt.datetime.now(dt.UTC).date(), "Aufnahmedatum liegt in der Zukunft"


def test_jede_fixture_steht_in_der_provenance():
    """Sonst waechst der Ordner und der Nachweis bleibt zurueck."""
    text = provenance()
    fehlend = [n for n in recorded_names() if f"## `{n}`" not in text]
    assert not fehlend, f"ohne Eintrag in PROVENANCE.md: {fehlend}"


def test_jeder_schluessel_zeigt_auf_eine_vorhandene_datei():
    """Der Nachweis traegt hier den Abspielbetrieb — er darf nicht ins Leere zeigen."""
    fehlend = sorted(set(schluesselverzeichnis().values()) - set(recorded_names()))
    assert not fehlend, f"im Nachweis genannt, aber nicht vorhanden: {fehlend}"


def test_keine_aufzeichnung_liegt_unbenutzt_herum():
    """Die Gegenrichtung — eine Datei, die kein Schluessel erreicht, belegt nichts."""
    ueberzaehlig = sorted(set(recorded_names()) - set(schluesselverzeichnis().values()))
    assert not ueberzaehlig, f"von keinem Schluessel erreicht: {ueberzaehlig}"


def test_der_recorder_faehrt_dieselben_werkzeuge():
    """Recorder und Tests duerfen nicht auseinanderlaufen.

    Laedt `scripts/record_fixtures.py` als Modul — `main()` wird nicht gerufen,
    es geht keine Anfrage raus. Damit ist zugleich geprueft, dass der Recorder
    ueberhaupt importierbar ist: ihn ruft im Betrieb niemand auf, und ruff
    kaeme einem Fehler darin nicht bei.
    """
    im_plan = {a.name for a in recorder().PLAN}
    assert im_plan == set(WERKZEUGE), "Recorder und Testtabelle nennen verschiedene Aufrufe"


def test_der_nachweis_meldet_was_gekuerzt_wurde():
    """Ein Nachweis, der ueber jeder Datei «ungekuerzt» schreibt, belegt nichts.

    Genau das tat er: `_kuerze` gab seine Zaehler als `return vorher, nachher,
    geh(daten)` zurueck, und Python liest die beiden Zahlen, *bevor* `geh` sie
    hochzaehlt — also immer (0, 0). Elf der einundzwanzig Aufzeichnungen standen
    damit als vollstaendig im Ordner, obwohl sie gekuerzt sind; die groesste
    trug 130 von 1327 Eintraegen. Wer die Suite las, hielt sie fuer ganze
    Antworten.

    Diese Zusicherung faellt, wenn die Zaehler wieder blind werden.
    """
    modul = recorder()
    vorher, nachher, gekuerzt = modul._kuerze({"a": list(range(modul.ZEILEN * 3))})
    assert (vorher, nachher) == (modul.ZEILEN * 3, modul.ZEILEN), (
        f"_kuerze meldet {vorher}→{nachher} statt {modul.ZEILEN * 3}→{modul.ZEILEN}"
    )
    assert len(gekuerzt["a"]) == modul.ZEILEN
    assert re.search(r"- \*\*Auswahl:\*\* \d+ von \d+ Listeneintraegen", provenance()), (
        "keine einzige Datei im Nachweis ist als gekuerzt ausgewiesen"
    )


@pytest.mark.parametrize("name", sorted(n for n in recorded_names() if n.endswith(".json")))
def test_keine_aufzeichnung_ist_leer(name):
    """Eine leere Antwort sieht aus wie eine gueltige und prueft nichts.

    Beim ersten Lauf waren zwei Dateien leer: die Umkreissuche (ein echter
    Fehler, siehe unten) und `features_at_point` mit `tolerance=0` auf einem
    Punkt-Layer. Diese Zusicherung ist der Grund, warum das auffiel.
    """
    daten = fixture_json(name)
    if isinstance(daten, list):
        assert daten, f"{name} ist eine leere Liste"
        return
    for schluessel in ("results", "features", "elements", "collections"):
        if schluessel in daten:
            assert daten[schluessel], f"{name}.{schluessel} ist leer — neu aufzeichnen"
            return
    assert daten, f"{name} ist leer"


# --------------------------------------------------------------------------
# Der Fund: die Umkreissuche fragte in Grad, die Quelle antwortet nur auf Meter
# --------------------------------------------------------------------------
async def test_die_umkreissuche_fragt_in_lv95(quelle):
    """Der SearchServer wertet die `bbox` nur in LV95 und nur mit `sr=2056` aus.

    Gemessen am 15.08.2026 am Zuercher Hauptbahnhof:

        bbox=Grad, sr=4326 → 0      bbox=LV95, sr=4326 → 0
        bbox=Grad, sr=2056 → 0      bbox=LV95, sr=2056 → 3

    Diese Zusicherung liest die tatsaechlich gestellte Anfrage. Im Ergebnis
    waere der Unterschied unsichtbar gewesen — es kam ja HTTP 200.
    """
    await _fahre("reverse_geocode")
    anfrage = next(r for r in quelle if "SearchServer" in str(r.url))
    assert anfrage.url.params["sr"] == "2056", "ohne sr=2056 wertet die Quelle die bbox nicht aus"
    ecken = [float(v) for v in anfrage.url.params["bbox"].split(",")]
    assert all(v > 1000 for v in ecken), f"die bbox steht nicht in Metern: {ecken}"
    # Und sie liegt um den angefragten Punkt: Zuerich HB ist LV95 ~2683300/1247900.
    assert 2_600_000 < ecken[0] < 2_700_000, ecken
    assert 1_200_000 < ecken[1] < 1_300_000, ecken


async def test_die_umkreissuche_findet_adressen(quelle):
    """Und das ist die Zusicherung, die den Fund festhaelt.

    Vorher lieferte dieses Werkzeug an jedem Punkt der Schweiz `match_type:
    none` mit einer Erklaerung, die nach einem gueltigen Negativbefund klang.
    """
    antwort = await _fahre("reverse_geocode")
    assert antwort.match_type == "exact"
    assert antwort.results, "keine Adressen aus der Aufzeichnung"
    assert antwort.note is None, antwort.note
    assert "Bahnhof" in antwort.summary


def test_die_umkreissuche_kennt_kein_sr_mehr():
    """Ein Feld, das die Anfrage nicht beeinflussen kann, ist eine leere Zusage.

    `sr` liess sich nicht einhalten — die bbox muss LV95 sein. Statt es
    stehenzulassen und still zu ignorieren, ist es weg.
    """
    assert "sr" not in server.ReverseGeocodeInput.model_fields
    assert "radius_m" in server.ReverseGeocodeInput.model_fields


# --------------------------------------------------------------------------
# Die Werkzeuge, jedes an seiner eigenen Antwort
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(WERKZEUGE))
async def test_jedes_werkzeug_liest_seine_aufgezeichnete_antwort(quelle, name):
    """Der eigentliche Punkt: jede Anfrage bekommt *ihre* Antwort.

    Alle mit derselben zu bedienen hiesse, die Aufzeichnung gegen eine Anfrage
    zu halten, die sie nicht beantwortet — genau der Fehler, den eine Fixture je
    Anfrage verhindern soll. Der Dispatcher faellt laut, wenn eine Anfrage
    keine Aufzeichnung hat.
    """
    antwort = await _fahre(name)
    assert not antwort.is_error, antwort.summary
    assert antwort.match_type != "none", f"{name} liefert nichts: {antwort.note}"
    assert quelle, f"{name} hat gar keine Anfrage abgeschickt"


async def test_der_hoehenwert_kommt_als_zeichenkette(quelle):
    """Die Quelle liefert `height` als Zeichenkette, nicht als Zahl.

    Ein Stub mit `{"height": 408.4}` sieht richtiger aus und ist es nicht — wer
    danach rechnet, faellt erst im Betrieb auf.
    """
    roh = fixture_json("height_1.json")["height"]
    assert isinstance(roh, str), "die Quelle liefert die Hoehe nicht mehr als Zeichenkette"
    antwort = await _fahre("height")
    assert roh in antwort.summary


async def test_die_adresssuche_liefert_eine_liste_ohne_umschlag(quelle):
    """OpenPLZ antwortet mit einer nackten Liste, nicht mit `{"results": …}`.

    Zwei Formen, ein Server: geo.admin verpackt, OpenPLZ nicht. Ein Loader, der
    ueberall `results` erwartet, liefert hier still nichts.
    """
    assert isinstance(fixture_json("search_address_1.json"), list)
    assert isinstance(fixture_json("lookup_postal_code_1.json"), list)
    antwort = await _fahre("lookup_postal_code")
    assert "8001" in antwort.summary


async def test_der_oereb_auszug_liest_die_beschraenkungen(quelle):
    """Der Auszug traegt seine Eigentumsbeschraenkungen tief im Baum.

    Ein handgeschriebener Stub haette die Verschachtelung geraten; hier steht
    sie so, wie der Kanton sie liefert.
    """
    daten = fixture_json("oereb_at_1.json")
    beschraenkungen = daten["GetExtractByIdResponse"]["Extract"]["RealEstate"][
        "RestrictionOnLandownership"
    ]
    assert beschraenkungen, "die Aufzeichnung traegt keine Beschraenkungen mehr"
    antwort = await _fahre("oereb_at")
    assert antwort.results, "der Auszug kommt leer beim Modell an"


async def test_der_kantonsfilter_greift_auf_dem_katalog(quelle):
    """Geprueft gegen einen Kanton, der in der Aufzeichnung wirklich vorkommt.

    Der geodienste-Katalog fuehrt einen Eintrag je (Thema, Kanton). Waere hier
    ein fest verdrahtetes Kuerzel gepruft, muesste die Aufzeichnung genau dazu
    passen — und der naechstliegende Weg dahin waere, sie danach auszuwaehlen.
    Ein Fixture, das nach dem gesuchten Wert zurechtgeschnitten ist, belegt
    nichts. Also kommt der Kanton aus der Datei.
    """
    katalog = fixture_json("list_layers_1.json")["services"]
    kanton = next(e["canton"] for e in katalog if e.get("canton"))

    fn = server.list_available_layers_tool
    modell = recorder()._eingabe(
        recorder().Aufruf(
            name="list_layers",
            werkzeug="list_available_layers_tool",
            klasse="ListLayersInput",
            eingabe={"source": "geodienste", "canton": kanton, "free_only": False},
        )
    )
    antwort = await fn(modell)
    assert antwort.results, f"kein Layer fuer «{kanton}», obwohl er im Katalog steht"
    fremde = {r.get("canton") for r in antwort.results} - {kanton, None}
    assert not fremde, f"der Filter laesst fremde Kantone durch: {fremde}"


def test_die_aufzeichnungen_nennen_mehr_als_einen_host():
    """Sonst belegt der Ordner nur einen Teil des Servers."""
    hosts = {httpx.URL(s.split("#")[0]).host for s in schluesselverzeichnis()}
    assert len(hosts) >= 4, f"nur {len(hosts)} Hosts aufgezeichnet: {sorted(hosts)}"


# --------------------------------------------------------------------------
# Die Gegenrichtung
# --------------------------------------------------------------------------
@respx.mock
async def test_eine_leere_trefferliste_bleibt_eine_leere_trefferliste():
    """`results: []` ist eine Aussage der Quelle: dort steht nichts.

    Das darf nicht als Fehler herauskommen — sonst kann das Modell einen echten
    Negativtreffer nicht von einem Ausfall unterscheiden. Und der Hinweis muss
    einen naechsten Schritt nennen.
    """
    respx.route().mock(return_value=httpx.Response(200, text=json.dumps({"results": []})))
    antwort = await _fahre("reverse_geocode")
    assert antwort.match_type == "none"
    assert not antwort.is_error, "eine leere Suche ist kein Fehler"
    assert antwort.note and "municipality_at" in antwort.note


@respx.mock
async def test_ein_abbruch_bleibt_ein_fehler():
    """Und die andere Haelfte: ein Ausfall darf nicht als leeres Ergebnis erscheinen."""
    respx.route().mock(side_effect=httpx.ConnectError("weg"))
    antwort = await _fahre("reverse_geocode")
    assert antwort.is_error, "ein Verbindungsabbruch kam als Erfolg zurueck"
    assert "Verbindung" in antwort.summary
