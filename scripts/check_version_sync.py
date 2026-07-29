"""
Versions-Synchronität prüfen — und sicherstellen, dass in `src/` keine Version
von Hand gepflegt wird.

`pyproject.toml` ist die einzige Quelle der Wahrheit. Verglichen werden alle
Stellen, die dieselbe Nummer wiederholen:

  - `server.json` (MCP-Registry-Manifest): `version` und jedes
    `packages[*].version`
  - die Versions-Badges der READMEs

Hintergrund: `publish.yml` synchronisiert `server.json` beim Veröffentlichen
aus dem Tag-Namen — die *committete* Version wirkt also nie auf das
publizierte Artefakt und fällt deshalb nicht auf, wenn sie veraltet. Die
README-Badges erzwingt überhaupt nichts.

Zweiter Teil: in `src/` darf keine Versionsnummer stehen. Der Laufzeit-Wert
kommt aus den Paket-Metadaten (`importlib.metadata.version()`); ein wieder
eingefügtes Literal wäre der Beginn derselben Drift, die im ganzen Portfolio
falsche User-Agents erzeugt hat.

Verwendung:
    python scripts/check_version_sync.py     # exit 1 bei Abweichung

Bewusst nur Standardbibliothek — der Check braucht keine Projekt-Installation
und läuft damit auch in schlanken CI-Jobs. Auf Python 3.10 (noch keine
`tomllib`) greift ein Minimal-Parser für die zwei benötigten Felder.
"""

import io
import json
import re
import sys
import tokenize
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 — tomllib kam erst mit 3.11
    tomllib = None

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
SERVER_JSON = ROOT / "server.json"
SRC = ROOT / "src"

# Shields.io-Badge: ![Version](https://img.shields.io/badge/version-X.Y.Z-blue)
_BADGE = re.compile(r"img\.shields\.io/badge/[Vv]ersion-([^-\s)]+)-")


def code_lines(text: str) -> list[str]:
    """Zeilen ohne Kommentare.

    Kommentare dokumentieren im Portfolio genau die Drift, die dieser Check
    verhindern soll — etwa «the User-Agent in server.py carried
    "bakom-mcp/1.0"». Sie zu melden wäre ein Fehlalarm, der die CI grundlos
    rot färbt. Ausgeschnitten wird per `tokenize`, nicht per `split("#")`:
    ein `#` in einem String-Literal darf die Zeile nicht abschneiden.
    """
    lines = text.splitlines()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                row, col = tok.start
                lines[row - 1] = lines[row - 1][:col]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Nicht parsebare Datei: lieber vollständig prüfen als still übergehen.
        return text.splitlines()
    return lines


def find_hardcoded(dist: str) -> list[tuple[str, int, str]]:
    """Manuell gepflegte Versionen in `src/`.

    Zwei Formen kommen im Portfolio vor: der User-Agent (`<dist>/1.2.3`) und
    die `__version__`-Zuweisung. Die Projekt-URL trägt denselben Namen, aber
    keine Ziffer danach — deshalb verlangt das Muster eine gepunktete Zahl.

    Der Fallback im `except PackageNotFoundError`-Zweig (`0.0.0+source`) ist
    ausdrücklich **kein** Treffer: er behauptet gerade keine Version. Erkannt
    wird er am lokalen Segment nach `+`, nicht an der Zahl davor — `0.0.0`
    allein sieht wie eine echte Version aus.
    """
    hits: list[tuple[str, int, str]] = []
    if not SRC.is_dir():
        return hits

    ua = re.compile(rf"{re.escape(dist)}/(\d+\.\d[^\s\"']*)")
    dunder = re.compile(r"""__version__\s*=\s*["']([^"']+)["']""")

    for path in sorted(SRC.rglob("*.py")):
        for lineno, line in enumerate(code_lines(path.read_text(encoding="utf-8")), start=1):
            values = [m.group(1) for m in ua.finditer(line)]
            for m in dunder.finditer(line):
                if re.match(r"\d+\.\d", m.group(1)):
                    values.append(m.group(1))
            if any("+" not in v for v in values):
                hits.append((str(path.relative_to(ROOT)), lineno, line.strip()))
    return hits


def collect_declared(expected: str) -> list[tuple[str, str]]:
    """Alle Stellen, die die Version wiederholen — je (Bezeichnung, Wert)."""
    found: list[tuple[str, str]] = []

    if SERVER_JSON.exists():
        server = json.loads(SERVER_JSON.read_text(encoding="utf-8"))
        found.append(("server.json → version", server.get("version", "")))
        for i, pkg in enumerate(server.get("packages", [])):
            found.append((f"server.json → packages[{i}].version", pkg.get("version", "")))

    for readme in sorted(ROOT.glob("README*.md")):
        for match in _BADGE.finditer(readme.read_text(encoding="utf-8")):
            found.append((f"{readme.name} → Versions-Badge", match.group(1)))

    return found


def read_project() -> dict:
    """`[project]`-Tabelle aus pyproject.toml.

    Ohne `tomllib` (Python 3.10) genügt hier ein Minimal-Parser: gebraucht
    werden nur `name` und `version`, beides einfache Strings direkt unter
    `[project]`. Eine Abhängigkeit auf `tomli` einzuführen, nur damit ein
    Check laufen kann, wäre unverhältnismässig.
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    if tomllib is not None:
        return tomllib.loads(text)["project"]

    section = re.search(r"^\[project\]\s*$(.*?)(?=^\[)", text, re.MULTILINE | re.DOTALL)
    body = section.group(1) if section else text
    out = {}
    for key in ("name", "version"):
        m = re.search(rf'^{key}\s*=\s*"([^"]+)"', body, re.MULTILINE)
        if m:
            out[key] = m.group(1)
    return out


def main() -> None:
    project = read_project()
    dist = project["name"]
    version = project.get("version")

    if version is None:
        # `dynamic = ["version"]`: die Version entsteht beim Bauen, ein
        # Literal in src/ ist dort die Quelle und kein Fehler.
        print("Versions-Sync übersprungen: pyproject.toml nutzt eine dynamische Version.")
        return

    found = collect_declared(version)
    mismatches = [(where, value) for where, value in found if value != version]
    if mismatches:
        print(
            f"DRIFT: pyproject.toml steht auf {version!r}, folgende Stellen weichen ab:",
            file=sys.stderr,
        )
        for where, value in mismatches:
            print(f"  {where} = {value!r}", file=sys.stderr)
        print(
            "\nAlle Stellen im selben Commit bumpen. Hinweis: publish.yml "
            "überschreibt server.json beim Veröffentlichen ohnehin aus dem Tag — "
            "die committete Version bleibt trotzdem die, die Menschen lesen.",
            file=sys.stderr,
        )
        sys.exit(1)

    hardcoded = find_hardcoded(dist)
    if hardcoded:
        print("HARDCODED: Versionsnummer in src/ gefunden:", file=sys.stderr)
        for path, lineno, line in hardcoded:
            print(f"  {path}:{lineno}: {line}", file=sys.stderr)
        print(
            "\nDie Laufzeit-Version kommt aus den Paket-Metadaten "
            "(`__version__`, gespeist aus importlib.metadata). Statt eines "
            "Literals von dort lesen — sonst beginnt dieselbe Drift von vorn.",
            file=sys.stderr,
        )
        sys.exit(1)

    checked = ", ".join(where for where, _ in found) or "keine weiteren Stellen"
    print(f"Versions-Sync OK ({version}; geprüft: {checked}; keine hartkodierte Version in src/)")


if __name__ == "__main__":
    main()
