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
    muster = re.compile(rf"pip install\s+({'|'.join(_WERKZEUGE)})\b")
    for workflow in sorted(_WORKFLOWS.glob("*.yml")):
        # Kommentare ausgenommen: der in ci.yml zitiert den verbotenen Befehl,
        # um zu erklaeren, warum er nicht zurueckkommen soll.
        zeilen = [z for z in workflow.read_text().splitlines() if not z.lstrip().startswith("#")]
        treffer = [z.strip() for z in zeilen if muster.search(z)]
        assert not treffer, (
            f"{workflow.name} installiert ein Gate-Werkzeug direkt ({treffer}). Dieser "
            "Schritt laeuft nach dem [dev]-Install und ueberstimmt den Pin in pyproject."
        )


def test_der_workflow_scan_findet_ueberhaupt_etwas() -> None:
    """Sichert die Pruefung oben gegen ein leeres Verzeichnis ab.

    Faende der Glob nichts, waere die Schleife leer und die Zusicherung
    trivialerweise wahr — gruen, ohne irgendetwas geprueft zu haben.
    """
    workflows = list(_WORKFLOWS.glob("*.yml"))
    assert len(workflows) >= 2, f"Workflow-Scan findet fast nichts: {workflows}"
    assert any("ruff check" in w.read_text() for w in workflows), (
        "kein Workflow ruft ruff auf — der Scan sucht am falschen Ort"
    )
