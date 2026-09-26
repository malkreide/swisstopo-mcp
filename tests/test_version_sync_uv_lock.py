#!/usr/bin/env python3
"""`uv.lock` ist die fuenfte Stelle, die die Versionsnummer wiederholt.

Beim Release 0.5.0 blieb sie auf 0.4.1 stehen. Gebumpt wurden vier Stellen —
`pyproject.toml`, `server.json` (zweimal) und die beiden README-Badges — und
`scripts/check_version_sync.py` prueft genau diese vier. Das Gate war gruen,
waehrend `uv tree --frozen --package swisstopo-mcp` das Wurzelpaket als 0.4.1
meldete; wer die Arbeitskopie ueber `uv sync --locked` oder `uv run --frozen`
konsumiert, bekam die alte Nummer.

Dieselbe Mechanik wie der Anlass des Releases selbst, eine Ebene tiefer: Das
Gate vergleicht die Stellen, die es kennt, gegeneinander — und alle bekannten
waren einvernehmlich richtig.

Behoben wurde die Drift **nicht** durch diesen Check, sondern nebenbei durch
einen Dependency-Bump (PR #106), der die Lockfile neu schrieb. Eine Korrektur
als Nebenwirkung wiederholt sich beim naechsten Release nicht — dieser Test und
die Erweiterung des Checks sind der Ersatz dafuer.

Nur Standardbibliothek, kein Netz.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_version_sync as cvs  # noqa: E402

DIST = "swisstopo-mcp"


def _pyproject_version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]


# ---------------------------------------------------------------------------
# Die Zusicherung selbst
# ---------------------------------------------------------------------------


def test_die_lockfile_fuehrt_dieselbe_version_wie_pyproject():
    """Der Zustand, der beim 0.5.0-Release verletzt war."""
    assert cvs.uv_lock_version(DIST) == _pyproject_version()


def test_das_gate_fuehrt_die_lockfile_in_seiner_liste():
    """Ohne diese Zusicherung koennte der Eintrag still wieder herausfallen.

    Der Test oben allein wuerde das nicht merken: er liest die Lockfile selbst
    und bliebe gruen, auch wenn `collect_declared` sie nicht mehr meldet — und
    damit das Gate wieder blind waere.
    """
    stellen = [where for where, _ in cvs.collect_declared(DIST)]
    assert any(s.startswith("uv.lock") for s in stellen), stellen


# ---------------------------------------------------------------------------
# Zaehne: das Gate muss an einer manipulierten Lockfile scheitern
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_kopie(tmp_path, monkeypatch):
    """Ein Miniatur-Repo, gegen das `main()` laufen kann.

    Die Konstanten des Moduls werden umgebogen statt Dateien im echten Repo
    angefasst — ein Test, der `uv.lock` im Arbeitsverzeichnis manipuliert,
    laesst bei einem Abbruch ein kaputtes Repo zurueck.
    """
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "swisstopo-mcp"\nversion = "9.9.9"\n', encoding="utf-8"
    )
    (tmp_path / "server.json").write_text(
        '{"version": "9.9.9", "packages": [{"version": "9.9.9"}]}', encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "![Version](https://img.shields.io/badge/version-9.9.9-blue)\n", encoding="utf-8"
    )
    lock = tmp_path / "uv.lock"
    lock.write_text(
        '[[package]]\nname = "httpx"\nversion = "0.28.1"\n\n'
        '[[package]]\nname = "swisstopo-mcp"\nversion = "9.9.9"\n'
        'source = { editable = "." }\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(cvs, "ROOT", tmp_path)
    monkeypatch.setattr(cvs, "PYPROJECT", tmp_path / "pyproject.toml")
    monkeypatch.setattr(cvs, "SERVER_JSON", tmp_path / "server.json")
    monkeypatch.setattr(cvs, "UV_LOCK", lock)
    monkeypatch.setattr(cvs, "SRC", tmp_path / "src")
    return lock


def test_die_kopie_ist_fuer_sich_gruen(repo_kopie):
    """Positivkontrolle. Ohne sie wuerde der Test unten auch dann bestehen,
    wenn das Miniatur-Repo aus einem ganz anderen Grund scheitert."""
    cvs.main()


def test_eine_zurueckgebliebene_lockfile_faellt_auf(repo_kopie):
    repo_kopie.write_text(
        repo_kopie.read_text(encoding="utf-8").replace(
            'name = "swisstopo-mcp"\nversion = "9.9.9"', 'name = "swisstopo-mcp"\nversion = "9.9.8"'
        ),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as exc:
        cvs.main()
    assert exc.value.code == 1


def test_die_version_eines_fremden_pakets_zaehlt_nicht(repo_kopie):
    """`httpx` steht mit eigener Version in derselben Datei.

    Ein Leser, der bloss das erste `version = "…"` nach dem Dateianfang nimmt,
    laese 0.28.1 und meldete bei jedem Lauf eine Abweichung — oder, schlimmer,
    vergliche zufaellig passende Nummern.
    """
    repo_kopie.write_text(
        repo_kopie.read_text(encoding="utf-8").replace(
            'name = "httpx"\nversion = "0.28.1"', 'name = "httpx"\nversion = "1.2.3"'
        ),
        encoding="utf-8",
    )
    cvs.main()


def test_ohne_lockfile_laeuft_der_check_unveraendert(repo_kopie):
    """Portfolio-Tauglichkeit: nicht jedes Repo fuehrt eine `uv.lock`."""
    repo_kopie.unlink()
    assert cvs.uv_lock_version(DIST) is None
    cvs.main()


@pytest.mark.parametrize("geschrieben", ["Swisstopo_MCP", "swisstopo.mcp", "SWISSTOPO-MCP"])
def test_der_paketname_wird_normalisiert(repo_kopie, geschrieben):
    """PEP 503: `Foo_Bar.baz` und `foo-bar-baz` sind dasselbe Paket.

    Ein woertlicher Vergleich faende die Zeile nicht, `uv_lock_version` gaebe
    den Leerstring zurueck — und das Gate meldete eine Abweichung, die keine
    ist. Die Gegenrichtung ist die gefaehrlichere: faende es die Zeile nicht
    und uebersaehe das still, waere die Pruefung wieder blind.
    """
    repo_kopie.write_text(
        repo_kopie.read_text(encoding="utf-8").replace(
            'name = "swisstopo-mcp"', f'name = "{geschrieben}"'
        ),
        encoding="utf-8",
    )
    assert cvs.uv_lock_version(DIST) == "9.9.9"
