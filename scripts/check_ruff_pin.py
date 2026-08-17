"""Prueft, dass jedes erreichbare ruff die in pyproject.toml gepinnte Version ist.

Der Sinn eines lokalen Gates ist, dass es dasselbe Ergebnis liefert wie die CI.
Ein anderes ruff meldet Abweichungen, die niemand verursacht hat, und
verschweigt umgekehrt welche, die die CI dann rot machen.

Der Pin steht an genau einer Stelle und wird beim Install auch gezogen. Er
wirkt trotzdem nicht, wenn frueher im PATH ein anderes ruff liegt: `ruff`
nimmt dann jenes Binary, und der Install meldet dazu nichts.

Geprueft werden beide Wege, auf denen ein Gate ruff erreichen kann, denn im
Portfolio kommen beide vor: `ruff …` nimmt das Binary aus dem PATH,
`python -m ruff …` das installierte Modul. Sie koennen auseinanderlaufen, und
dann haengt das Ergebnis davon ab, welche Form gerade jemand tippt. Was nicht
vorhanden ist, wird uebersprungen; fehlen beide, ist das ein Fehler.

Verwendung:
    python scripts/check_ruff_pin.py     # exit 1 bei Abweichung

Zwei Einschraenkungen, die diese Datei zwischen den Repos kopierbar halten:

  - Nur Standardbibliothek, und kein tomllib: fuenf Server im Portfolio
    fahren ihre CI auch auf Python 3.10, wo es tomllib nicht gibt.
  - Keine Zeile ueber 88 Zeichen und keine impliziten String-Verkettungen
    ueber mehrere Zeilen; lange Meldungen bekommen eine lokale Variable. Im
    Portfolio stehen line-length 88, 100, 110 und 120 nebeneinander, und
    `ruff format` zieht einen Ausdruck zusammen, sobald er in die jeweilige
    Breite passt. Eine Verkettung, die bei 88 auf zwei Zeilen gehoert, waere
    bei 100 eine Zeile - und `ruff format --check` fiele beim Kopieren um.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"

# `"ruff==0.16.1"` als Eintrag einer Dependency-Liste. Bewusst eng: eine
# Spanne (`ruff>=…`) soll nicht als Pin durchgehen.
_PIN = re.compile(r"""['"]ruff==([0-9][^'"\s;]*)['"]""")

# Aus `ruff 0.16.1` bzw. `ruff 0.16.1 (abc1234 2026-01-01)`.
_REPORTED = re.compile(r"([0-9]+\.[0-9]+\.[0-9]+)")

_INSTALL = '    pip install -e ".[dev]"'


def pinned_version() -> str:
    """Die exakt gepinnte Version aus pyproject.toml. Einzige Quelle."""
    text = PYPROJECT.read_text(encoding="utf-8")
    found = sorted(set(_PIN.findall(text)))
    if not found:
        kein = "Kein exakter ruff-Pin (ruff==X.Y.Z) in pyproject.toml."
        grund = "Ohne ihn kann kein lokaler Lauf die CI reproduzieren."
        raise SystemExit(f"{kein} {grund}")
    if len(found) > 1:
        others = ", ".join(repr(v) for v in found)
        grund = "Genau einer muss es sein, sonst ist unklar, welcher gilt."
        raise SystemExit(f"Mehrere ruff-Pins in pyproject.toml: {others}. {grund}")
    return found[0]


def _ask(call: list[str]) -> str | None:
    """Version, die dieser Aufruf meldet - oder None, wenn es ihn nicht gibt."""
    try:
        done = subprocess.run(call, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    match = _REPORTED.search(done.stdout)
    return match.group(1) if match else None


def reachable() -> list[tuple[str, str]]:
    """Jedes ruff, das ein Gate treffen kann: (Aufruf, gemeldete Version)."""
    found = []
    binary = shutil.which("ruff")
    if binary is not None:
        version = _ask([binary, "--version"])
        if version is not None:
            found.append((binary, version))
    module = _ask([sys.executable, "-m", "ruff", "--version"])
    if module is not None:
        found.append((f"{sys.executable} -m ruff", module))
    return found


def main() -> int:
    want = pinned_version()
    found = reachable()
    if not found:
        fehlt = "Kein ruff erreichbar - weder im PATH noch als Modul."
        raise SystemExit(f"{fehlt} Dev-Umgebung installieren:\n{_INSTALL}")
    wrong = [(call, have) for call, have in found if have != want]
    if not wrong:
        print(f"Ruff-Pin OK ({want}; geprueft: {len(found)} Aufrufweg(e))")
        return 0
    print(f"ruff-Version weicht ab. Gepinnt ist {want}.", file=sys.stderr)
    for call, have in wrong:
        print(f"  {call} meldet {have}", file=sys.stderr)
    folge = "Die Gates fallen damit anders aus als in der CI. Angleichen mit:"
    print(f"{folge}\n{_INSTALL}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
