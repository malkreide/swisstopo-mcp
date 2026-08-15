"""Zugriff auf die aufgezeichneten Antworten in `tests/fixtures/`.

Ein Loader statt `open()` an jeder Stelle: so gibt es genau einen Ort, der weiss,
wo die Aufzeichnungen liegen, und die Tests koennen ueber sie iterieren, statt
eine Liste von Hand zu pflegen, die zurueckbleibt.

Die Zuordnung Anfrage → Datei kommt aus `PROVENANCE.md`. Das ist Absicht: der
Nachweis ist damit nicht bloss Prosa neben den Dateien, sondern traegt den
Abspielbetrieb. Steht dort ein falscher Schluessel, faellt ein Test, statt dass
jemand ihn Jahre spaeter beim Lesen bemerkt.

Der Recorder wird als Modul geladen — nicht ausgefuehrt. Seine Schluesselregel
ist dieselbe, nach der der Dispatcher eine Anfrage wiedererkennt; zwei Kopien
liefen auseinander, und der Dispatcher lieferte dann stillschweigend die
falsche Datei.

Neu aufzeichnen mit `python scripts/record_fixtures.py`.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

WURZEL = Path(__file__).resolve().parent.parent
FIXTURES = WURZEL / "tests" / "fixtures"


@lru_cache(maxsize=1)
def recorder() -> Any:
    """Laedt `scripts/record_fixtures.py` als Modul, ohne `main()` zu rufen."""
    pfad = WURZEL / "scripts" / "record_fixtures.py"
    name = "record_fixtures_probe"
    spec = importlib.util.spec_from_file_location(name, pfad)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError(f"{pfad} laesst sich nicht als Modul laden")
    modul = importlib.util.module_from_spec(spec)
    # Vor dem Ausfuehren registrieren: `@dataclass` schlaegt das eigene Modul in
    # `sys.modules` nach, um Annotationen aufzuloesen, und faellt sonst um.
    sys.modules[name] = modul
    try:
        spec.loader.exec_module(modul)
    finally:
        del sys.modules[name]
    return modul


def schluessel_fuer(request: httpx.Request) -> str:
    """Woran eine Anfrage wiedererkannt wird — dieselbe Regel wie im Recorder."""
    rumpf = request.content.decode("utf-8", "replace") if request.content else ""
    return (
        recorder()
        .Antwort(url=str(request.url), methode=request.method, rumpf=rumpf, text="")
        .schluessel
    )


@lru_cache(maxsize=1)
def schluesselverzeichnis() -> dict[str, str]:
    """Schluessel → Dateiname, gelesen aus PROVENANCE.md."""
    verzeichnis: dict[str, str] = {}
    datei: str | None = None
    for zeile in provenance().splitlines():
        kopf = re.match(r"## `([^`]+)`", zeile)
        if kopf:
            datei = kopf.group(1)
            continue
        eintrag = re.match(r"- \*\*Schluessel:\*\* `(.+)`$", zeile)
        if eintrag and datei:
            verzeichnis[eintrag.group(1)] = datei
    return verzeichnis


def fixture_text(name: str) -> str:
    """Die Aufzeichnung als Text — so, wie sie ueber die Leitung kaeme."""
    pfad = FIXTURES / name
    if not pfad.is_file():
        raise FileNotFoundError(f"keine Aufzeichnung {name} in {FIXTURES}")
    return pfad.read_text(encoding="utf-8")


def fixture_json(name: str) -> Any:
    """Die Aufzeichnung geparst."""
    return json.loads(fixture_text(name))


@lru_cache(maxsize=1)
def recorded_names() -> tuple[str, ...]:
    """Alle Aufzeichnungen im Ordner — nicht die, die ein Test erwartet.

    Der Unterschied ist der Punkt: eine Datei, die niemand erwartet, faellt
    sonst niemandem auf.
    """
    return tuple(sorted(p.name for p in FIXTURES.iterdir() if p.name != "PROVENANCE.md"))


def provenance() -> str:
    return (FIXTURES / "PROVENANCE.md").read_text(encoding="utf-8")
