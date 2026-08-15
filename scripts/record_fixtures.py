#!/usr/bin/env python3
"""Zeichnet je eine echte Antwort pro Abfrage auf.

Warum nicht von Hand geschrieben: eine handgeschriebene Erfolgs-Antwort stimmt
mit dem ueberein, was ihr Autor annahm, und kann die Quelle deshalb nicht
widerlegen. Aufgezeichnet wird darum an demselben Ort, an dem der Server die
Antwort entgegennimmt — ueber einen httpx-Response-Hook auf dem geteilten
Client aus `create_shared_client()`. Damit tragen Aufzeichnung und Betrieb
denselben User-Agent, dasselbe Timeout und dieselbe Transportschicht; eine
nachgebaute Anfrage taete das nicht.

Dieser Server spricht mit sieben Hosts, aber in weit mehr Abfrageformen: der
`/rest/services`-Zweig von geo.admin.ch allein bedient fuenf Operationen, und
`swisstopo_query_geodata` faechert je nach Layer auf drei verschiedene Quellen
auf. Die Portfolio-Regel «eine Antwort je externem Endpunkt» waere mit sieben
Dateien erfuellt und truege fast nichts — aufgezeichnet ist deshalb eine
Antwort je *Anfrage*, die ein Werkzeug abschickt.

Zugeordnet wird beim Abspielen nach der Anfrage und nicht nach der
Reihenfolge: `_query_geodienste` faehrt seine Kantone per `asyncio.gather`, und
eine Zuordnung nach Reihenfolge waere im gruenen Fall bloss zufaellig richtig.
Der Schluessel steht je Datei im Nachweis.

Gekuerzt wird nur die **Zahl** der Eintraege, nie ein Feld. Wie stark, steht je
Datei in PROVENANCE.md.

Aufruf:

    python scripts/record_fixtures.py

Schreibt nach `tests/fixtures/` und erzeugt `tests/fixtures/PROVENANCE.md` neu.
Dateien, die kein Plan-Eintrag mehr erzeugt, werden geloescht — sonst waechst
der Ordner und der Nachweis bleibt zurueck.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))

from swisstopo_mcp import api_client, server  # noqa: E402

FIXTURES = WURZEL / "tests" / "fixtures"

VERSUCHE = 4

# Wie viele Eintraege einer Trefferliste bleiben. Die Form einer Zeile belegen
# fuenf genauso gut wie zweihundert; die Zahl steht je Datei im Nachweis.
ZEILEN = 5

# Zuerich HB, in WGS84 und als Adresse — ein Ort quer durch alle Werkzeuge,
# damit die Aufzeichnungen zueinander passen und ein Test sie gegeneinander
# halten kann.
ZUERICH = {"lat": 47.3769, "lon": 8.5417}
ADRESSE = "Bahnhofplatz 1, 8001 Zürich"


@dataclass(frozen=True)
class Aufruf:
    """Ein Werkzeugaufruf, der Anfragen ausloesen soll."""

    name: str
    werkzeug: str
    klasse: str
    eingabe: dict[str, Any]
    # Werkzeuge mit `ctx`-Parameter bekommen einen stillen Platzhalter.
    braucht_ctx: bool = False
    # Kuerzen ist nur dort harmlos, wo der Server die Liste ganz liest. Filtert
    # er *in* ihr, schneidet ein Schnitt auf die ersten Zeilen womoeglich genau
    # die Zeile weg, die er sucht — und das Werkzeug meldet dann einen
    # Negativbefund, den die Quelle nie gegeben hat. Beide Faelle unten sind so
    # aufgefallen, nicht ausgedacht.
    kuerzen: bool = True
    notiz: str = ""


PLAN: list[Aufruf] = [
    Aufruf("geocode", "swisstopo_geocode", "GeocodeInput", {"search_text": ADRESSE}),
    Aufruf(
        "reverse_geocode",
        "swisstopo_reverse_geocode",
        "ReverseGeocodeInput",
        dict(ZUERICH),
    ),
    Aufruf("height", "swisstopo_get_height", "HeightInput", dict(ZUERICH)),
    Aufruf(
        "elevation_profile",
        "swisstopo_elevation_profile",
        "ElevationProfileInput",
        {"coordinates": "47.3769,8.5417;47.3800,8.5500"},
        braucht_ctx=True,
    ),
    Aufruf("zoning_at", "swisstopo_zoning_at", "ZoningAtInput", dict(ZUERICH)),
    Aufruf(
        "municipality_at",
        "swisstopo_municipality_at",
        "MunicipalityAtInput",
        dict(ZUERICH),
        kuerzen=False,
        notiz="Ungekuerzt: der Layer fuehrt ein Polygon je historischem Jahr "
        "(177 fuer Zuerich), und das Werkzeug sucht darin das mit "
        "`is_current_jahr`. Die ersten fuenf sind es nicht.",
    ),
    # Fuenf Operationen desselben Werkzeugs — fuenf Abfrageformen.
    Aufruf(
        "map_query_search_layers",
        "swisstopo_map_query",
        "MapQueryInput",
        {"operation": "search_layers", "query": "Gebäude"},
    ),
    Aufruf(
        "map_query_features_at_point",
        "swisstopo_map_query",
        "MapQueryInput",
        {
            "operation": "features_at_point",
            "layers": "ch.bfs.gebaeude_wohnungs_register",
            # tolerance=0 trifft bei einem Punkt-Layer nur die exakte
            # Koordinate; der Standard 0 passt zu Flaechen-Layern wie
            # ch.are.bauzonen. Aufgezeichnet wird die gefuellte Antwort — die
            # leere bleibt handgeschrieben, sie belegt keine Form.
            "tolerance": 10,
            **ZUERICH,
        },
    ),
    Aufruf(
        "map_query_layer_info",
        "swisstopo_map_query",
        "MapQueryInput",
        {"operation": "layer_info", "layer": "ch.bfs.gebaeude_wohnungs_register"},
    ),
    Aufruf(
        "search_geodata",
        "swisstopo_search_geodata",
        "SearchGeodataInput",
        {"query": "swissalti"},
    ),
    Aufruf(
        "get_collection",
        "swisstopo_get_collection",
        "GetCollectionInput",
        {"collection_id": "ch.swisstopo.swissalti3d"},
    ),
    Aufruf("get_egrid", "swisstopo_get_egrid", "GetEgridInput", {**ZUERICH, "canton": "ZH"}),
    Aufruf(
        "oereb_at",
        "swisstopo_oereb_at",
        "OerebAtInput",
        {**ZUERICH, "canton": "ZH"},
        braucht_ctx=True,
        notiz="EGRID-Aufloesung und OEREB-Auszug in einem Aufruf.",
    ),
    Aufruf(
        "list_layers",
        "list_available_layers_tool",
        "ListLayersInput",
        # Ohne Kantonsfilter aufgezeichnet, und das ist der Grund: der
        # geodienste-Katalog fuehrt einen Eintrag je (Thema, Kanton) — 1137
        # Stueck, 4,1 MB. Mit `canton="ZH"` musste er ungekuerzt in den Ordner,
        # weil die ersten fuenf Eintraege keinen freien ZH-Layer enthalten und
        # das Werkzeug daraufhin «keine Layer fuer diesen Filter» meldete: ein
        # Negativbefund, den die Quelle nie gegeben hat. So bleibt der Schnitt
        # rein positionsbasiert, und der Kantonsfilter wird im Test gegen den
        # Kanton geprueft, der in der Aufzeichnung tatsaechlich vorkommt.
        {"source": "geodienste"},
    ),
    Aufruf(
        "query_geodata_strassen",
        "query_geodata_tool",
        "QueryGeodataInput",
        {"layer": "strassenverzeichnis", "point": "47.3769,8.5417"},
    ),
    Aufruf(
        "query_geodata_oereb",
        "query_geodata_tool",
        "QueryGeodataInput",
        {"layer": "oereb-verfuegbarkeit", "point": "47.3769,8.5417"},
    ),
    Aufruf(
        "query_osm",
        "query_osm_features_tool",
        "QueryOsmFeaturesInput",
        {"feature_type": "pharmacy", "area": "47.3769,8.5417", "radius_m": 500},
        braucht_ctx=True,
    ),
    Aufruf(
        "lookup_postal_code",
        "lookup_postal_code_tool",
        "LookupPostalCodeInput",
        {"postal_code": "8001"},
    ),
    Aufruf(
        "find_commune",
        "find_commune_tool",
        "FindCommuneInput",
        {"name": "Zürich"},
        braucht_ctx=True,
    ),
    Aufruf(
        "search_address",
        "search_address_tool",
        "SearchAddressInput",
        {"query": "Bahnhofplatz 8001"},
    ),
]


@dataclass
class Antwort:
    """Eine gesehene Antwort samt der Anfrage, die sie ausgeloest hat."""

    url: str
    methode: str
    rumpf: str
    text: str
    werkzeuge: list[str] = field(default_factory=list)
    darf_kuerzen: bool = True
    dateiname: str = ""
    original_bytes: int = 0
    gekuerzt_von: int = 0
    behalten: int = 0
    sha256: str = ""
    bytes: int = 0

    @property
    def schluessel(self) -> str:
        """Woran eine Anfrage beim Abspielen wiedererkannt wird.

        Die URL allein genuegt nicht: Overpass schickt seine Abfrage im Rumpf,
        und zwei POSTs an dieselbe Adresse waeren sonst ununterscheidbar.
        """
        if not self.rumpf:
            return self.url
        return f"{self.url}#{hashlib.sha256(self.rumpf.encode()).hexdigest()[:12]}"


def _endung(text: str) -> str:
    """`.json`, wenn die Antwort JSON ist — sonst `.txt`.

    Nicht jede Quelle antwortet mit JSON: der Legenden-Endpunkt von geo.admin
    liefert HTML. Eine solche Datei `.json` zu nennen waere eine Behauptung
    ueber ihren Inhalt, die nicht stimmt.
    """
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return ".txt"
    return ".json"


def _hook_fuer(gesehen: list[Antwort]) -> Callable[[httpx.Response], Awaitable[None]]:
    """Baut den Response-Hook fuer einen Versuch.

    Eigene Funktion, damit die Liste als Argument gebunden ist und nicht als
    Schleifenvariable aus dem umgebenden Namensraum (ruff B023).
    """

    async def hook(response: httpx.Response) -> None:
        await response.aread()
        gesehen.append(
            Antwort(
                url=str(response.request.url),
                methode=response.request.method,
                rumpf=response.request.content.decode("utf-8", "replace"),
                text=response.text,
            )
        )

    return hook


class _StillerKontext:
    """Der `ctx`, den MCPServer sonst reicht — hier ohne Ausgabe."""

    async def info(self, *a: object, **kw: object) -> None: ...

    async def warning(self, *a: object, **kw: object) -> None: ...

    async def error(self, *a: object, **kw: object) -> None: ...

    async def debug(self, *a: object, **kw: object) -> None: ...

    async def report_progress(self, *a: object, **kw: object) -> None: ...


def _eingabe(a: Aufruf) -> Any:
    """Baut das Eingabemodell — die Klasse steht im Plan, nicht in den Annotationen.

    Aus `fn.__annotations__` waere sie nur eine Zeichenkette: die Module stehen
    unter `from __future__ import annotations`.
    """
    for modul in (
        server,
        *(
            sys.modules[f"swisstopo_mcp.{m}"]
            for m in _MODULE
            if f"swisstopo_mcp.{m}" in sys.modules
        ),
    ):
        if hasattr(modul, a.klasse):
            return getattr(modul, a.klasse)(**a.eingabe)
    raise RuntimeError(f"Eingabeklasse {a.klasse} nicht gefunden")


_MODULE = (
    "coords",
    "geocoding",
    "geodata",
    "height",
    "oereb",
    "openplz",
    "overpass",
    "rest_api",
    "stac",
    "wmts",
)


async def _fahre(a: Aufruf, client: httpx.AsyncClient) -> list[Antwort]:
    """Ruft ein Werkzeug und gibt die dabei gesehenen Antworten zurueck."""
    fn = getattr(server, a.werkzeug)
    letzter: Exception | None = None

    for versuch in range(VERSUCHE):
        if versuch:
            await asyncio.sleep(2**versuch)
        gesehen: list[Antwort] = []
        hook = _hook_fuer(gesehen)
        client.event_hooks.setdefault("response", []).append(hook)
        try:
            if a.braucht_ctx:
                await fn(_eingabe(a), _StillerKontext())
            else:
                await fn(_eingabe(a))
        except Exception as e:  # noqa: BLE001 — jeder Fehler ist hier ein Retry-Grund
            letzter = e
            continue
        finally:
            client.event_hooks["response"].remove(hook)

        if not gesehen:
            letzter = RuntimeError(f"{a.werkzeug} hat keine Anfrage abgeschickt")
            continue
        for antwort in gesehen:
            antwort.werkzeuge.append(a.werkzeug)
            antwort.darf_kuerzen = a.kuerzen
        return gesehen

    raise RuntimeError(f"{a.name} nach {VERSUCHE} Versuchen nicht aufgezeichnet: {letzter}")


def _kuerze(daten: Any) -> tuple[int, int, Any]:
    """Kuerzt jede Liste im Baum auf `ZEILEN`; gibt (Eintraege vorher, nachher).

    Nur die Zahl der Eintraege, nie ein Feld. Rekursiv, weil die laengsten
    Listen hier verschachtelt liegen: der OEREB-Auszug traegt sein Glossar und
    seine Eigentumsbeschraenkungen tief im Baum, und ein Schnitt nur auf
    oberster Ebene liesse 173 KB stehen.

    Zaehlfelder daneben (`total`, `numberMatched`, …) bleiben unangetastet: die
    Quelle meint damit die Gesamtzahl und nicht die Zahl der gelieferten
    Zeilen, und genau die liest der Server aus.
    """
    vorher = nachher = 0

    def geh(knoten: Any) -> Any:
        nonlocal vorher, nachher
        if isinstance(knoten, dict):
            return {k: geh(v) for k, v in knoten.items()}
        if isinstance(knoten, list):
            vorher += len(knoten)
            gekuerzt = knoten[:ZEILEN]
            nachher += len(gekuerzt)
            return [geh(v) for v in gekuerzt]
        return knoten

    # Erst laufen lassen, dann die Zaehler lesen. `return vorher, nachher,
    # geh(daten)` wertet von links nach rechts aus und lieferte deshalb immer
    # (0, 0) — der Nachweis schrieb «ungekuerzt» ueber jede gekuerzte Datei.
    ergebnis = geh(daten)
    return vorher, nachher, ergebnis


async def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    heute = datetime.now(UTC).date().isoformat()
    nach_schluessel: dict[str, Antwort] = {}
    zaehler: dict[str, int] = {}

    client = api_client.create_shared_client()
    api_client.set_shared_client(client)
    try:
        for a in PLAN:
            print(f"… {a.werkzeug} ({a.name})", file=sys.stderr)
            for antwort in await _fahre(a, client):
                if antwort.schluessel in nach_schluessel:
                    vorhanden = nach_schluessel[antwort.schluessel]
                    if a.werkzeug not in vorhanden.werkzeuge:
                        vorhanden.werkzeuge.append(a.werkzeug)
                    continue
                zaehler[a.name] = zaehler.get(a.name, 0) + 1
                antwort.dateiname = f"{a.name}_{zaehler[a.name]}{_endung(antwort.text)}"
                nach_schluessel[antwort.schluessel] = antwort
    finally:
        api_client.set_shared_client(None)
        await client.aclose()

    for antwort in nach_schluessel.values():
        antwort.original_bytes = len(antwort.text.encode("utf-8"))
        try:
            daten = json.loads(antwort.text)
        except json.JSONDecodeError:
            # Nicht jede Quelle antwortet mit JSON — geodienste liefert CSV,
            # WMTS ein Bild. Solche Antworten bleiben, wie sie kamen.
            (FIXTURES / antwort.dateiname).write_text(antwort.text, encoding="utf-8")
        else:
            if antwort.darf_kuerzen:
                antwort.gekuerzt_von, antwort.behalten, daten = _kuerze(daten)
            (FIXTURES / antwort.dateiname).write_text(
                json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        roh = (FIXTURES / antwort.dateiname).read_bytes()
        antwort.sha256 = hashlib.sha256(roh).hexdigest()
        antwort.bytes = len(roh)

    antworten = sorted(nach_schluessel.values(), key=lambda x: x.dateiname)
    _schreibe_provenance(antworten, heute)

    # Aufraeumen: was kein Plan-Eintrag mehr erzeugt, hat auch keinen Nachweis.
    geschrieben = {a.dateiname for a in antworten} | {"PROVENANCE.md"}
    for pfad in sorted(FIXTURES.iterdir()):
        if pfad.name not in geschrieben:
            print(f"– entferne veraltet: {pfad.name}", file=sys.stderr)
            pfad.unlink()

    print(f"{len(antworten)} Aufzeichnungen in {FIXTURES}", file=sys.stderr)
    return 0


def _schreibe_provenance(antworten: list[Antwort], heute: str) -> None:
    zeilen = [
        "# Herkunft der Fixtures",
        "",
        f"Aufgezeichnet am **{heute}** mit `python scripts/record_fixtures.py`.",
        "",
        "Eine Antwort je **Anfrage**, nicht je Endpunkt: dieser Server spricht mit sieben",
        "Hosts, aber in weit mehr Abfrageformen — der `/rest/services`-Zweig allein",
        "bedient fuenf Operationen. Sieben Dateien wuerden die Portfolio-Regel erfuellen",
        "und fast nichts belegen.",
        "",
        "Die Antworten stammen aus dem geteilten Client (gleicher User-Agent, gleiches",
        "Timeout, gleiche Transportschicht wie im Betrieb), abgegriffen ueber einen",
        "httpx-Response-Hook. Ausgeloest hat sie jeweils das Werkzeug selbst — so belegt",
        "die Aufzeichnung auch, dass das Werkzeug genau diese Anfrage schickt.",
        "",
        "Der **Schluessel** unten ist, woran der Test eine Anfrage wiedererkennt: die URL,",
        "bei POST um eine Kurzfassung des Rumpfes ergaenzt. Zugeordnet wird danach und",
        "nicht nach Reihenfolge — `_query_geodienste` faehrt seine Kantone per",
        "`asyncio.gather`, und eine Zuordnung nach Reihenfolge waere im gruenen Fall",
        "bloss zufaellig richtig.",
        "",
        "Neu gesetzt ist die Einrueckung; gekuerzt ist allein die **Zahl** der Eintraege",
        "der laengsten Liste. Kein Feld eines behaltenen Eintrags ist angetastet, und",
        "Zaehlfelder daneben stehen wie geliefert — die Quelle meint damit die",
        "Gesamtzahl, nicht die Zahl der gelieferten Zeilen.",
        "",
        "Die Fehlerpfade — Timeout, 5xx, leere Trefferliste — bleiben handgeschrieben.",
        "Sie lassen sich nicht auf Zuruf aufzeichnen und sind als Erfindung in Ordnung.",
        "",
    ]
    for a in antworten:
        zeilen += [
            f"## `{a.dateiname}`",
            "",
            f"- **Werkzeuge:** {', '.join(f'`{w}`' for w in sorted(a.werkzeuge))}",
            f"- **Schluessel:** `{a.schluessel}`",
        ]
        if a.rumpf:
            zeilen.append(f"- **Rumpf:** `{' '.join(a.rumpf.split())[:400]}`")
        if a.gekuerzt_von > a.behalten:
            zeilen.append(
                f"- **Auswahl:** {a.behalten} von {a.gekuerzt_von} Listeneintraegen "
                f"(je Liste die ersten {ZEILEN}), aus {a.original_bytes} Bytes Rohantwort"
            )
        elif not a.darf_kuerzen:
            zeilen.append(
                "- **Auswahl:** ungekuerzt — der Server filtert *in* dieser Liste, "
                "ein Schnitt auf die ersten Zeilen erfaende einen Negativbefund"
            )
        else:
            zeilen.append("- **Auswahl:** ungekuerzt")
        zeilen += [
            f"- **Groesse:** {a.bytes} Bytes",
            f"- **SHA-256:** `{a.sha256}`",
            "",
        ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(zeilen), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
