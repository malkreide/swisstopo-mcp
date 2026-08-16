#!/usr/bin/env python3
"""ruff und mypy stehen an genau einer Stelle — und bleiben dort.

Beide sind Gates (`ruff check`, `ruff format --check`, `mypy src/`), und beide
waren als Spanne deklariert: `ruff>=0.4.0,<0.17` und `mypy>=1.10.0`. Bei ruff
kam erschwerend hinzu, dass `ci.yml` mit einem eigenen
`pip install ruff==0.16.1` nachlegte — der Schritt lief nach dem Install des
Extras und gewann gegen pyproject, der Wert dort war also wirkungslos. Ein
frisches `pip install -e ".[dev]"` loeste auf 0.16.3 auf: lokaler Lauf und Gate
waren sich ueber die Version uneinig.

Die Begruendung der frueheren ruff-Deckelung bleibt erfuellt. Sie war als
Review-Gate gedacht, nicht als Freeze — Dependabot schlaegt den Bump auch bei
`==` vor, und ein Pin driftet zusaetzlich nicht innerhalb einer Minor.
"""

from __future__ import annotations

import pathlib
import re
import tomllib

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_WORKFLOWS = _ROOT / ".github" / "workflows"

# Formen, in denen ein Schritt ein Paket eigenstaendig installiert. Die erste
# Fassung kannte nur `pip install <werkzeug>` und liess damit
# `pip install --upgrade ruff==…`, `pip install "ruff==…"`, `pip3 install`,
# `uv tool install` und `uv run --with ruff==…` durch — allesamt Formen, die
# den Pin genauso ueberstimmen. Aufgefallen ist das in einem Codex-Review.
_INSTALL_FORM = re.compile(
    r"(?:pip3?\s+install|python\s+-m\s+pip\s+install|uv\s+pip\s+install"
    r"|uv\s+tool\s+install|uv\s+add|pipx\s+install|--with)\b"
)


def _installiert_werkzeug(zeile: str) -> str | None:
    """Das Gate-Werkzeug, das diese Zeile als benanntes Paket installiert.

    `pip install -e ".[dev]"` zieht beide ebenfalls herein — das ist aber der
    richtige Weg und darf nicht anschlagen. Entscheidend ist, ob nach dem
    Install-Befehl ein eigenes Argument mit dem Werkzeugnamen steht.
    Anfuehrungszeichen sind erlaubt, ein vorangehendes Wort-, Pfad- oder
    Bindestrich-Zeichen nicht: sonst zaehlten `ruff-lsp` und
    `scripts/ruff_helper.py` mit.
    """
    treffer = _INSTALL_FORM.search(zeile)
    if not treffer:
        return None
    rest = zeile[treffer.end() :]
    for werkzeug in _WERKZEUGE:
        if re.search(rf"""(?<![\w./-])["']?{werkzeug}(?![\w-])""", rest):
            return werkzeug
    return None


def _workflow_dateien() -> list[pathlib.Path]:
    """Beide Endungen: GitHub laedt `*.yml` UND `*.yaml`."""
    return sorted([*_WORKFLOWS.glob("*.yml"), *_WORKFLOWS.glob("*.yaml")])


_WERKZEUGE = ("ruff", "mypy")


def _dev_abhaengigkeiten() -> list[str]:
    daten = tomllib.loads((_ROOT / "pyproject.toml").read_text())
    return daten["project"]["optional-dependencies"]["dev"]


def test_beide_werkzeuge_sind_exakt_gepinnt() -> None:
    """Eine Spanne laesst lokalen Lauf und CI verschiedene Versionen fahren."""
    specs = _dev_abhaengigkeiten()
    for werkzeug in _WERKZEUGE:
        treffer = [s for s in specs if re.match(rf"^{werkzeug}\b", s)]
        assert len(treffer) == 1, f"genau ein {werkzeug}-Specifier erwartet, gefunden: {treffer}"
        assert re.fullmatch(rf"{werkzeug}==\d+\.\d+\.\d+", treffer[0]), (
            f"{werkzeug} muss als {werkzeug}==X.Y.Z gepinnt sein, gefunden {treffer[0]!r}. "
            "Eine Spanne laesst lokal und in der CI verschiedene Versionen laufen."
        )


def test_die_pins_sind_die_einzige_versionsquelle() -> None:
    """Kein Workflow darf ruff oder mypy selbst installieren.

    Ein solcher Schritt laeuft nach dem Install des Extras und ueberstimmt den
    Pin — die Zahl in pyproject waere dann Dekoration.
    """
    for workflow in _workflow_dateien():
        # Kommentare ausgenommen: der in ci.yml zitiert den verbotenen Befehl,
        # um zu erklaeren, warum er nicht zurueckkommen soll.
        zeilen = [z for z in workflow.read_text().splitlines() if not z.lstrip().startswith("#")]
        treffer = [z.strip() for z in zeilen if _installiert_werkzeug(z)]
        assert not treffer, (
            f"{workflow.name} installiert ein Gate-Werkzeug direkt ({treffer}). Dieser "
            "Schritt laeuft nach dem [dev]-Install und ueberstimmt den Pin in pyproject."
        )


def test_der_workflow_scan_findet_ueberhaupt_etwas() -> None:
    """Sichert die Pruefung oben gegen ein leeres Verzeichnis ab.

    Faende der Glob nichts, waere die Schleife leer und die Zusicherung
    trivialerweise wahr — gruen, ohne irgendetwas geprueft zu haben.
    """
    workflows = _workflow_dateien()
    assert len(workflows) >= 2, f"Workflow-Scan findet fast nichts: {workflows}"
    assert any("ruff check" in w.read_text() for w in workflows), (
        "kein Workflow ruft ruff auf — der Scan sucht am falschen Ort"
    )


def test_der_erkenner_kennt_die_gaengigen_installationsformen() -> None:
    """Der Scan ist nur so gut wie das, was er als Install erkennt.

    Ohne diese Tabelle ist die Zusicherung oben gruen, weil sie die Form nicht
    kennt — nicht, weil sie fehlt. Genau so war es: Die erste Fassung suchte
    woertlich nach `pip install <werkzeug>` und uebersah fuenf von sieben
    geprueften Schreibweisen.
    """
    muss_treffen = [
        "run: pip install ruff==0.16.1",
        "run: pip install --upgrade ruff==0.16.1",
        'run: pip install "ruff==0.16.1"',
        "run: pip3 install mypy==2.3.1",
        "run: python -m pip install ruff==0.16.1",
        "run: uv pip install ruff==0.16.1 --system",
        "run: uv tool install ruff==0.16.1",
        "run: uv add mypy==2.3.1",
        "run: pipx install ruff==0.16.1",
        "run: uv run --with ruff==0.16.1 ruff check src/",
        "run: pip install ruff",
        "run: pip install pytest mypy==2.3.1",
    ]
    darf_nicht_treffen = [
        'run: pip install -e ".[dev]"',
        'run: uv pip install -e ".[dev]" --system',
        "run: ruff check src/ tests/",
        "run: ruff format --check src/ tests/",
        "run: mypy src/",
        "run: pip install ruff-lsp",
        "run: pip install uv",
        "run: python -m pip install --upgrade pip",
        "run: uv run --with pip-audit pip-audit",
        "run: python scripts/ruff_helper.py",
        "name: Lint mit ruff",
    ]
    uebersehen = [z for z in muss_treffen if not _installiert_werkzeug(z)]
    assert not uebersehen, f"Erkenner uebersieht: {uebersehen}"
    fehlalarm = [z for z in darf_nicht_treffen if _installiert_werkzeug(z)]
    assert not fehlalarm, f"Erkenner schlaegt faelschlich an: {fehlalarm}"
