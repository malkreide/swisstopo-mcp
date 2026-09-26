#!/usr/bin/env python3
"""Wie weit ist der Default-Branch dem letzten Release voraus?

## Warum das kein PR-Gate ist

Die Bedingung, die den Missstand beschreibt — «die Version in `pyproject.toml`
ist auf PyPI schon vergeben **und** HEAD liegt hinter keinem Tag» — trifft auf
*jeden* PR nach einem Release zu. Jeder PR erzeugt per Definition
unveroeffentlichte Arbeit. Als blockierendes Gate waere das dauerhaft rot und
damit innert einer Woche abgeschaltet.

Dieses Skript meldet deshalb, es blockiert nicht. Der Workflow
`release-distance.yml` faehrt es woechentlich und legt ein Issue an, wenn die
Distanz eine Schwelle ueberschreitet.

## Was gemessen wird

Am 26.9.2026 wurde das Portfolio von Hand vermessen: 38 von 42 Repos trugen in
`pyproject.toml` eine Nummer, die auf PyPI schon vergeben war, und hatten
Commits jenseits des zugehoerigen Tags. Bei 33 davon fasste mindestens einer
davon ausgelieferten Code an.

Der Anlass war `swisstopo-mcp` selbst: 0.4.1 lag 55 Tage auf PyPI, waehrend im
Repo unter derselben Nummer 93 Commits dazukamen — darunter die Korrektur eines
OEREB-Parsers, der seit dem 3.8. gegen die Quelle falsch antwortete. Der
Verteilweg ist `uvx`, also immer die neueste PyPI-Version; die Korrektur
erreichte sieben Wochen lang niemanden.

Ausgeliefert wird, was ins Wheel kommt: `src/` und `pyproject.toml`. Aenderungen
an `tests/`, `docs/` oder `.github/` erreichen ueber PyPI niemanden und zaehlen
hier nicht — sonst meldete das Skript jede Woche eine Distanz, die keine ist.

## Die dritte Antwort

`classify_live_run.py` haelt die Lehre fest, die hier genauso gilt: Ein Lauf
hat drei Ausgaenge, nicht zwei. Wenn die Messung gar nicht stattfinden konnte —
PyPI nicht erreichbar, das Paket dort unbekannt, der Tag im Checkout nicht
vorhanden — ist das `unknown` und **nicht** `clear`. Ein flacher Checkout ohne
Tags ist der wahrscheinlichste Fall: `actions/checkout` holt ohne
`fetch-depth: 0` weder Historie noch Tags, und ein fehlender Tag sieht sonst
aus wie «nichts unveroeffentlicht».

Nur Standardbibliothek. Netz nur fuer PyPI; alles andere ist lokal.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 — tomllib kam erst mit 3.11
    tomllib = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent.parent

# Was im Wheel landet. `pyproject.toml` zaehlt mit, weil dort die
# Abhaengigkeits-Pins stehen: eine angehobene Untergrenze ist eine
# ausgelieferte Aenderung, auch wenn kein Modul angefasst wurde.
AUSGELIEFERT = ("src/", "pyproject.toml")

DEFAULT_MIN_AGE_DAYS = 14


@dataclass(frozen=True)
class Befund:
    state: str  # "clear" | "distance" | "unknown"
    reason: str
    version: str = ""
    pypi_version: str = ""
    pypi_date: str = ""
    alter_tage: int = 0
    commits: int = 0
    ausgeliefert: int = 0


# ---------------------------------------------------------------------------
# Klassifikation — rein, damit sie ohne Netz und ohne Repo pruefbar ist
# ---------------------------------------------------------------------------


def klassifizieren(
    *,
    repo_version: str | None,
    pypi_version: str | None,
    pypi_date: str | None,
    tag_gefunden: bool,
    tag_ist_head: bool,
    ausgeliefert: int,
    commits: int,
    heute: dt.date,
    min_age_days: int,
) -> Befund:
    """Der Ausgang eines Laufs, aus bereits erhobenen Zahlen.

    Die Reihenfolge der Zweige ist die Aussage: alles, was die Messung
    verhindert, geht nach `unknown`, bevor irgendetwas `clear` heissen kann.
    """
    if not repo_version:
        return Befund("unknown", "Version aus pyproject.toml nicht lesbar")
    if pypi_version is None:
        return Befund("unknown", "PyPI nicht erreichbar oder Paket dort unbekannt", repo_version)

    if repo_version != pypi_version:
        # Entweder ein vorbereitetes Release (Repo voraus) oder etwas
        # Ueberraschendes (Repo hinter PyPI). Beides ist nicht die Falle, um
        # die es hier geht — aber der zweite Fall gehoert in den Log.
        lage = "Repo voraus" if repo_version > pypi_version else "Repo HINTER PyPI"
        return Befund(
            "clear",
            f"Release vorbereitet, nicht publiziert ({lage}: "
            f"pyproject {repo_version}, PyPI {pypi_version})",
            repo_version,
            pypi_version,
            pypi_date or "",
        )

    if not tag_gefunden:
        return Befund(
            "unknown",
            f"Kein Tag fuer v{repo_version} im Checkout — ohne ihn ist die Distanz "
            "nicht messbar (flacher Checkout? `fetch-depth: 0` und Tags noetig)",
            repo_version,
            pypi_version,
            pypi_date or "",
        )

    if tag_ist_head:
        return Befund(
            "clear",
            f"HEAD ist der Release-Commit von v{repo_version}",
            repo_version,
            pypi_version,
            pypi_date or "",
        )

    alter = _alter_in_tagen(pypi_date, heute)

    if ausgeliefert == 0:
        return Befund(
            "clear",
            f"{commits} Commit(s) seit v{repo_version}, keiner fasst ausgelieferten "
            "Code an (nur Doku, CI oder Tests)",
            repo_version,
            pypi_version,
            pypi_date or "",
            alter,
            commits,
            0,
        )

    if alter < min_age_days:
        return Befund(
            "clear",
            f"{ausgeliefert} unveroeffentlichte Aenderung(en) am ausgelieferten Code, "
            f"aber das Release ist erst {alter} Tage alt (Schwelle {min_age_days})",
            repo_version,
            pypi_version,
            pypi_date or "",
            alter,
            commits,
            ausgeliefert,
        )

    return Befund(
        "distance",
        f"{ausgeliefert} von {commits} Commit(s) seit v{repo_version} fassen "
        f"ausgelieferten Code an; letzte Publikation vor {alter} Tagen",
        repo_version,
        pypi_version,
        pypi_date or "",
        alter,
        commits,
        ausgeliefert,
    )


def _alter_in_tagen(pypi_date: str | None, heute: dt.date) -> int:
    if not pypi_date:
        return 0
    try:
        return (heute - dt.date.fromisoformat(pypi_date[:10])).days
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Erhebung
# ---------------------------------------------------------------------------


def projekt() -> tuple[str | None, str | None]:
    """(Dist-Name, Version) aus pyproject.toml."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if tomllib is not None:
        p = tomllib.loads(text).get("project", {})
        return p.get("name"), p.get("version")
    name = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    version = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return (name.group(1) if name else None), (version.group(1) if version else None)


def pypi_neueste(dist: str, timeout: float = 25.0) -> tuple[str | None, str | None]:
    """(neueste Version, Datum ihrer ersten Datei) — oder (None, None).

    `None` heisst hier ausdruecklich «nicht gemessen», nicht «nichts da»: ein
    Netzfehler und ein unbekanntes Paket enden beide so, und beide fuehren
    oben nach `unknown`.
    """
    url = f"https://pypi.org/pypi/{dist}/json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            daten = json.load(r)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError):
        return None, None
    version = daten.get("info", {}).get("version")
    dateien = daten.get("releases", {}).get(version) or []
    datum = min((f["upload_time_iso_8601"] for f in dateien), default=None)
    return version, (datum[:10] if datum else None)


def _git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def tag_und_head(version: str) -> tuple[bool, bool]:
    """(Tag vorhanden, Tag == HEAD). Annotierte Tags werden aufgeloest."""
    tag_sha = _git("rev-list", "-n", "1", f"v{version}")
    if not tag_sha:
        return False, False
    return True, tag_sha == _git("rev-parse", "HEAD")


def commits_seit(version: str) -> tuple[int, int]:
    """(Commits gesamt, davon mit ausgeliefertem Code) zwischen Tag und HEAD."""
    roh = _git("log", "--no-merges", "--format=%H", f"v{version}..HEAD")
    shas = [s for s in roh.splitlines() if s]
    treffer = 0
    for sha in shas:
        dateien = _git("show", "--name-only", "--format=", sha).split()
        if any(d.startswith(AUSGELIEFERT) for d in dateien):
            treffer += 1
    return len(shas), treffer


# ---------------------------------------------------------------------------
# Einstieg
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="check_release_distance")
    ap.add_argument(
        "--min-age-days",
        type=int,
        default=DEFAULT_MIN_AGE_DAYS,
        help="Erst ab diesem Alter der letzten Publikation melden (Vorgabe: %(default)s).",
    )
    ap.add_argument(
        "--offline-pypi",
        metavar="VERSION:DATUM",
        help="PyPI nicht abfragen, sondern diesen Stand annehmen (fuer Tests).",
    )
    args = ap.parse_args(argv)

    dist, version = projekt()

    if args.offline_pypi:
        pv, _, pd = args.offline_pypi.partition(":")
        pypi_version, pypi_date = pv or None, pd or None
    elif dist:
        pypi_version, pypi_date = pypi_neueste(dist)
    else:
        pypi_version, pypi_date = None, None

    tag_gefunden = tag_ist_head = False
    commits = ausgeliefert = 0
    if version and pypi_version == version:
        tag_gefunden, tag_ist_head = tag_und_head(version)
        if tag_gefunden and not tag_ist_head:
            commits, ausgeliefert = commits_seit(version)

    befund = klassifizieren(
        repo_version=version,
        pypi_version=pypi_version,
        pypi_date=pypi_date,
        tag_gefunden=tag_gefunden,
        tag_ist_head=tag_ist_head,
        ausgeliefert=ausgeliefert,
        commits=commits,
        heute=dt.date.today(),
        min_age_days=args.min_age_days,
    )

    print(f"{befund.state}: {befund.reason}")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        # Zeilenumbruch raus, bevor der Grund nach `$GITHUB_OUTPUT` geht — ein
        # mehrzeiliger Wert bricht das `key=value`-Format still auf.
        einzeilig = " ".join(befund.reason.split())
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"state={befund.state}\n")
            fh.write(f"reason={einzeilig}\n")
            fh.write(f"version={befund.version}\n")
            fh.write(f"pypi_version={befund.pypi_version}\n")
            fh.write(f"pypi_date={befund.pypi_date}\n")
            fh.write(f"age_days={befund.alter_tage}\n")
            fh.write(f"commits={befund.commits}\n")
            fh.write(f"shipped={befund.ausgeliefert}\n")

    # Immer 0: Die Distanz ist ein Bericht, kein Fehlschlag. Der Workflow
    # entscheidet anhand von `state`, was damit geschieht.
    return 0


if __name__ == "__main__":
    sys.exit(main())
