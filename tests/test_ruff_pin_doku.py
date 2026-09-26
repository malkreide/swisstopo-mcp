"""Die Projektanweisung darf den gepinnten ruff-Stand nicht wiederholen.

`scripts/check_ruff_pin.py` nennt `pyproject.toml` die einzige Quelle und
liest sonst nichts. Eine Version, die daneben in der Prosa steht, ist deshalb
keine Bequemlichkeit, sondern eine zweite Quelle — und die veraltet still,
weil kein Gate Prosa liest.

Sie ist es auch geworden. Am 26.9.2026 wurde das Portfolio vermessen: Von 44
Projektanweisungen nannten 23 eine ruff-Version als Behauptung ueber den
aktuellen Pin, ohne dass ein Gate sie hielt; 13 davon waren zu diesem
Zeitpunkt bereits falsch, um bis zu vier Minor-Schritte. Wer der Prosa folgte,
installierte die falsche Version und lief in den Abbruch genau des Gates, das
die Prosa erklaert.

**Was hier verboten ist, und was nicht.** Verboten ist, den *aktuellen* Pin in
der Anweisung zu nennen — in jeder Schreibweise, an jeder Stelle. Erlaubt
bleibt die erzaehlte Vergangenheit: «`ci.yml` rief vorher `ruff==0.16.1` auf»
beschreibt einen vergangenen Zustand und wird von einem Bump nicht falsch.
Erlaubt bleiben auch die Versionen anderer Pakete.

Damit gibt es hier **kein Fenster**: kein Abstand zum Wort «ruff», keine
Zeilengrenze, keine Liste erlaubter Umgebungen. Gesucht wird ein Wert, nicht
eine Nachbarschaft. Ein Fenster ist immer eine Zahl, die jemand richtig raten
muss, und die Portfolio-Messung hat gezeigt, wie verschieden die Prosa
denselben Satz schreibt: als `ruff==X`, als «Der Pin `X` steht in», als
`rev: vX`, als Ueberschrift «ruff — X, genau eine Quelle». Ein Muster, das am
Wort «ruff» haengt, faengt die Haelfte davon nicht.

**Was dieser Test nicht leistet.** Eine Zahl, die weder den aktuellen Pin
nennt noch zu einem anderen Paket gehoert — also ein Tippfehler oder eine
erfundene Version — bleibt unentdeckt. Das ist bewusst in Kauf genommen: Die
gemessene Drift entsteht nicht durch Tippfehler, sondern dadurch, dass jemand
den *richtigen* Stand dokumentiert und der Pin danach weiterzieht. Genau
dieser Weg ist hier zu.

Der Pin wird nicht mit einem zweiten Regex gelesen, sondern durch
`pinned_version()` aus dem Gate — sonst stuenden fuer dieselbe Frage wieder
zwei Quellen da, und dieser Test waere die dritte.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_GATE = _ROOT / "scripts" / "check_ruff_pin.py"
_CLAUDE_MD = _ROOT / "CLAUDE.md"


def _pin() -> str:
    """Der gepinnte Wert, gelesen vom Gate selbst — eine Quelle, ein Leser."""
    spec = importlib.util.spec_from_file_location("_check_ruff_pin", _GATE)
    assert spec is not None and spec.loader is not None, f"{_GATE} nicht ladbar"
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return str(modul.pinned_version())


def _muster(pin: str) -> re.Pattern[str]:
    """Der Pin als Wert, mit Grenzen — kein Fenster um ein Stichwort.

    Das optionale `v` gehoert dazu: `.pre-commit-config.yaml` schreibt den
    Stand als `rev: vX.Y.Z`, und ein Repo, das den Hook erwaehnt, wiederholt
    ihn genau in dieser Form.

    Der Lookbehind schliesst Wortzeichen UND den Punkt aus, damit ein laengerer
    Wert den kuerzeren nicht ausloest: Stuende der Pin auf `0.16.3`, faende ein
    Muster ohne Grenze ihn auch in `10.16.3` und in einer fremden Version, die
    mit denselben Stellen endet. Der Lookahead schliesst die Ziffer aus, damit
    `0.16.30` nicht als `0.16.3` gilt. Ein Satzpunkt danach ist dagegen
    erlaubt — `…auf 0.16.3.` nennt den Pin.
    """
    return re.compile(rf"(?<![\w.])v?{re.escape(pin)}(?!\d)")


def _stellen(text: str, pin: str) -> list[str]:
    muster = _muster(pin)
    return [
        f"Zeile {nr}: {zeile.strip()}"
        for nr, zeile in enumerate(text.splitlines(), start=1)
        if muster.search(zeile)
    ]


def test_gate_liefert_den_pin() -> None:
    """Positivkontrolle: Ohne Pin misst die Zusicherung unten ihre eigene Stille.

    Geprueft wird nicht eine eigene Vorstellung von der Form — die waere enger
    als das, was `pinned_version()` zulaesst — sondern die Bedingung, auf die
    es ankommt: dass das Muster genau den Wert wiedererkennt, den das Gate
    liest. Laufen die beiden auseinander, sucht der Test nach nichts.
    """
    pin = _pin()
    assert pin, "Kein Pin gelesen — dann prueft dieser Test nichts."
    assert _muster(pin).search(f"Der Pin ist {pin}.")


def test_die_projektanweisung_wird_wirklich_gelesen() -> None:
    """Zweite Positivkontrolle: Eine fehlende Datei fiele sonst als «grün» auf."""
    assert _CLAUDE_MD.is_file(), "CLAUDE.md fehlt — der Test misst nichts."
    assert _CLAUDE_MD.read_text(encoding="utf-8").strip(), "CLAUDE.md ist leer."


def test_die_projektanweisung_nennt_den_pin_nicht() -> None:
    """Der Pin steht in pyproject.toml. Ein zweites Mal ist ein Mal zu viel."""
    pin = _pin()
    stellen = _stellen(_CLAUDE_MD.read_text(encoding="utf-8"), pin)
    assert not stellen, (
        f"CLAUDE.md nennt den gepinnten Stand ({pin}) und ist damit eine zweite "
        "Versionsquelle, die ein Dependabot-Bump nicht nachzieht:\n  "
        + "\n  ".join(stellen)
        + "\nAuf pyproject.toml verweisen statt die Zahl zu wiederholen."
    )


def test_der_erkenner_trifft_die_schreibweisen_des_portfolios() -> None:
    """Die Gegenprobe: Ein Muster, das nichts trifft, waere oben immer gruen.

    Die Faelle sind nicht erfunden, sondern die Formen, in denen die Messung
    vom 26.9.2026 den Pin in den Projektanweisungen gefunden hat.
    """
    pin = _pin()
    formen = [
        f"**ruff: eine Quelle.** `pyproject.toml`, `dev`-Extra, `ruff=={pin}`.",
        f"**ruff: eine Quelle.** Der Pin `{pin}` steht in `pyproject.toml`.",
        f"### ruff — {pin}, genau eine Quelle",
        f"`.pre-commit-config.yaml` traegt `rev: v{pin}` ein zweites Mal.",
        f"ruff ist an genau einer Stelle gepinnt, naemlich auf {pin}.",
        f"Gepinnt auf `ruff == {pin}`, einzige Fundstelle: `pyproject.toml`.",
    ]
    uebersehen = [f for f in formen if not _stellen(f, pin)]
    assert not uebersehen, f"Erkenner uebersieht: {uebersehen}"


def test_fremde_zahlen_bleiben_erlaubt() -> None:
    """Was nicht der aktuelle Pin ist, darf dastehen — sonst waere der Test Laerm.

    `9.9.9` steht hier fuer eine fremde Version, damit diese Datei nicht selbst
    die zweite Quelle wird, die sie verbietet.
    """
    pin = _pin()
    erlaubt = [
        "`ci.yml` rief ruff vorher per `uv run --with ruff==9.9.9` auf.",
        "Am 29.8.2026 lief ruff durch.",
        "Die Paketversion ist 9.9.9.",
        f"1{pin} ist eine andere Zahl.",
        f"{pin}0 ist eine andere Zahl.",
    ]
    fehlalarm = [z for z in erlaubt if _stellen(z, pin)]
    assert not fehlalarm, f"Erkenner schlaegt faelschlich an: {fehlalarm}"
