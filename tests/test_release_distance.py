#!/usr/bin/env python3
"""Der woechentliche Bericht ueber die Distanz zwischen Repo und PyPI.

Gegenstand ist `scripts/check_release_distance.py`. Der Anlass steht dort im
Modul-Docstring: 0.4.1 lag 55 Tage auf PyPI, waehrend im Repo unter derselben
Nummer 93 Commits dazukamen — darunter die Korrektur eines OEREB-Parsers, der
gegen die Quelle falsch antwortete.

Was diese Tests eigentlich absichern, ist nicht die Rechnung, sondern die
**Reihenfolge der Zweige**. Ein Bericht, der bei fehlender Messung `clear`
meldet, ist schlimmer als gar keiner: er meldet jahrelang gruen und niemand
sieht nach. Deshalb steht unten fuer jeden Grund, aus dem die Messung
ausfallen kann, ein eigener Fall — und jeder davon prueft ausdruecklich, dass
er **nicht** `clear` heisst.

Nur Standardbibliothek, kein Netz. `pypi_neueste` wird hier nicht gefahren;
die Funktion ist der einzige Netzpfad und in `klassifizieren` durch die beiden
Parameter `pypi_version`/`pypi_date` vertreten.
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_release_distance as crd  # noqa: E402

HEUTE = dt.date(2026, 9, 26)

# Ein vollstaendig gesunder Aufruf. Jeder Test unten aendert genau das, worum
# es ihm geht — so steht in der Testzeile, was den Ausgang verursacht, und
# nicht ein Wust von Parametern, die alle gleich aussehen.
GESUND = dict(
    repo_version="0.5.0",
    pypi_version="0.5.0",
    pypi_date="2026-07-01",
    tag_gefunden=True,
    tag_ist_head=False,
    ausgeliefert=0,
    commits=0,
    heute=HEUTE,
    min_age_days=14,
)


def befund(**abweichung):
    return crd.klassifizieren(**{**GESUND, **abweichung})


# ---------------------------------------------------------------------------
# Was die Messung verhindert, ist `unknown` — nie `clear`
# ---------------------------------------------------------------------------


def test_ohne_version_im_pyproject_ist_nichts_gemessen():
    b = befund(repo_version=None)
    assert b.state == "unknown"


def test_ohne_pypi_antwort_ist_nichts_gemessen():
    """Netzfehler und unbekanntes Paket enden beide bei `pypi_version=None`.

    Die Unterscheidung waere hier auch nicht zu treffen — und sie aendert am
    Ausgang nichts: in beiden Faellen hat die Messung nicht stattgefunden.
    """
    b = befund(pypi_version=None, pypi_date=None)
    assert b.state == "unknown"


def test_ein_fehlender_tag_ist_unknown_und_nicht_sauber():
    """Der wahrscheinlichste Ausfall — und der teuerste, wenn er falsch faellt.

    `actions/checkout` holt ohne `fetch-depth: 0` keine Tags. Ohne Tag sind
    null Commits zu zaehlen, und genau das sieht aus wie «nichts
    unveroeffentlicht». Die Zahlen unten sind deshalb die eines sauberen
    Laufs: bestuende der Test, weil irgendetwas anderes auffaellig ist, wuerde
    er die Verwechslung nicht ausschliessen.
    """
    b = befund(tag_gefunden=False, tag_ist_head=False, commits=0, ausgeliefert=0)
    assert b.state == "unknown"
    assert "fetch-depth" in b.reason


def test_der_fehlende_tag_schlaegt_auch_eine_offene_distanz():
    """Reihenfolge, andersherum geprueft: die Zahlen einer echten Distanz,
    aber ohne Tag. Sie stammen dann aus keiner belastbaren Quelle, also darf
    `distance` nicht herauskommen — `unknown` ist die ehrliche Antwort."""
    b = befund(tag_gefunden=False, commits=40, ausgeliefert=11, pypi_date="2026-01-01")
    assert b.state == "unknown"


# ---------------------------------------------------------------------------
# Sauber — aus vier verschiedenen Gruenden
# ---------------------------------------------------------------------------


def test_ein_vorbereitetes_release_ist_keine_distanz():
    b = befund(repo_version="0.6.0", pypi_version="0.5.0")
    assert b.state == "clear"
    assert "Repo voraus" in b.reason


def test_ein_repo_hinter_pypi_wird_benannt():
    """Auch `clear`, aber der Log soll den Fall nicht verschweigen: eine
    Nummer im Repo, die kleiner ist als die publizierte, ist ueberraschend
    genug, dass jemand sie lesen sollte."""
    b = befund(repo_version="0.4.0", pypi_version="0.5.0")
    assert b.state == "clear"
    assert "HINTER" in b.reason


def test_head_auf_dem_release_commit_wird_als_solcher_begruendet():
    """Hier traegt der **Grund** die Zusicherung, nicht der Zustand.

    Gemessen: nimmt man den `tag_ist_head`-Zweig ganz heraus, bleibt der
    Ausgang `clear` — der Fall faellt dann durch den Zweig darunter, weil auf
    dem Release-Commit per Konstruktion null Commits und null ausgelieferte
    Aenderungen anstehen. Eine Zusicherung auf `state` allein haette also
    keine Zaehne. Was verloren ginge, ist die Auskunft: statt «HEAD ist der
    Release-Commit» stuende im Log «0 Commit(s) seit v0.5.0, keiner fasst
    ausgelieferten Code an» — richtig geraten, aber aus dem falschen Zweig.
    """
    b = befund(tag_ist_head=True)
    assert b.state == "clear"
    assert "Release-Commit" in b.reason


def test_commits_ohne_ausgelieferten_code_sind_keine_distanz():
    """Doku, CI und Tests erreichen ueber PyPI niemanden.

    Ohne diese Zusicherung meldete der Bericht jede Woche eine Distanz, die
    keine ist — und waere nach zwei Montagen so viel wert wie ein Gate, das
    immer rot ist.
    """
    b = befund(commits=30, ausgeliefert=0, pypi_date="2026-01-01")
    assert b.state == "clear"
    assert b.ausgeliefert == 0


def test_kurz_nach_einem_release_wird_nicht_gemeldet():
    b = befund(commits=5, ausgeliefert=3, pypi_date="2026-09-20", min_age_days=14)
    assert b.state == "clear"
    assert b.alter_tage == 6


# ---------------------------------------------------------------------------
# Distanz
# ---------------------------------------------------------------------------


def test_alter_release_mit_ausgeliefertem_code_meldet_distanz():
    b = befund(commits=93, ausgeliefert=33, pypi_date="2026-08-02")
    assert b.state == "distance"
    assert b.alter_tage == 55
    assert b.commits == 93
    assert b.ausgeliefert == 33


def test_die_schwelle_schliesst_ihren_eigenen_wert_ein():
    """Genau `min_age_days` alt heisst melden, nicht noch eine Woche warten.

    Die Grenze ist ein `<`, kein `<=`; ein Vorzeichenfehler dort verschoebe
    jede Meldung um sieben Tage, ohne dass ein anderer Test es merkte.
    """
    assert befund(ausgeliefert=1, commits=1, pypi_date="2026-09-12").state == "distance"
    assert befund(ausgeliefert=1, commits=1, pypi_date="2026-09-13").state == "clear"


def test_die_zahlen_stehen_im_befund_und_nicht_nur_im_text():
    """Der Workflow baut den Issue-Text aus den Feldern, nicht aus `reason`."""
    b = befund(
        commits=50,
        ausgeliefert=11,
        pypi_date="2026-07-24",
        repo_version="0.6.0",
        pypi_version="0.6.0",
    )
    assert (b.version, b.pypi_version, b.pypi_date) == ("0.6.0", "0.6.0", "2026-07-24")
    assert (b.commits, b.ausgeliefert, b.alter_tage) == (50, 11, 64)


# ---------------------------------------------------------------------------
# Datumsarithmetik
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("roh", ["", None, "unbekannt", "2026-13-45"])
def test_ein_unlesbares_datum_ergibt_kein_alter(roh):
    """Kein Absturz und kein erfundenes Alter.

    Der Fall landet ueber die Schwelle in `clear` — das ist gewollt: ein
    Bericht, der aus einem kaputten Datum eine Meldung baut, erzeugt genau das
    Rauschen, das ihn abschaltet.
    """
    assert crd._alter_in_tagen(roh, HEUTE) == 0


def test_ein_zeitstempel_mit_uhrzeit_wird_auf_den_tag_gekuerzt():
    assert crd._alter_in_tagen("2026-08-02T14:31:07.123456Z", HEUTE) == 55


# ---------------------------------------------------------------------------
# Erhebung gegen ein echtes Git-Repo
# ---------------------------------------------------------------------------


def _git(pfad: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(pfad),
            "-c",
            "user.name=T",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        check=True,
        capture_output=True,
    )


def _commit(pfad: Path, datei: str, text: str) -> None:
    ziel = pfad / datei
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(text, encoding="utf-8")
    _git(pfad, "add", datei)
    _git(pfad, "commit", "-m", f"touch {datei}")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Ein Miniatur-Repo mit Tag v1.0.0 und drei Commits danach.

    Handgeschriebene Fixtures kodieren die Annahme des Autors; hier laeuft
    deshalb echtes git statt einer nachgebauten Ausgabe. Was `git show
    --name-only` druckt, ist genau die Annahme, an der `commits_seit` haengt.
    """
    _git(tmp_path, "init", "-q", "-b", "master")
    _commit(tmp_path, "src/pkg/__init__.py", "x = 1\n")
    _git(tmp_path, "tag", "v1.0.0")
    _commit(tmp_path, "docs/README.md", "doku\n")
    _commit(tmp_path, "src/pkg/api.py", "y = 2\n")
    _commit(tmp_path, ".github/workflows/ci.yml", "on: push\n")
    monkeypatch.setattr(crd, "ROOT", tmp_path)
    return tmp_path


def test_der_tag_wird_gefunden_und_ist_nicht_head(repo):
    assert crd.tag_und_head("1.0.0") == (True, False)


def test_ein_unbekannter_tag_meldet_sich_als_fehlend(repo):
    """Positivkontrolle zum Test darueber: derselbe Aufruf, andere Nummer.

    Ohne ihn koennte `tag_und_head` konstant `(True, …)` liefern und beide
    Tests blieben gruen.
    """
    assert crd.tag_und_head("9.9.9") == (False, False)


def test_ein_tag_auf_head_wird_als_solcher_erkannt(repo):
    _git(repo, "tag", "v2.0.0")
    assert crd.tag_und_head("2.0.0") == (True, True)


def test_nur_commits_an_ausgeliefertem_code_zaehlen(repo):
    """Drei Commits seit dem Tag, einer davon in `src/`."""
    assert crd.commits_seit("1.0.0") == (3, 1)


def test_pyproject_zaehlt_als_ausgeliefert(repo):
    """Eine angehobene Abhaengigkeits-Untergrenze ist eine ausgelieferte
    Aenderung, auch wenn kein Modul angefasst wurde."""
    _commit(repo, "pyproject.toml", '[project]\nname = "x"\n')
    assert crd.commits_seit("1.0.0") == (4, 2)


def test_ein_annotierter_tag_wird_aufgeloest(repo):
    """`git rev-parse v1.0.0` gaebe bei einem annotierten Tag das Tag-Objekt
    und nie den Commit — der Vergleich mit HEAD schluege dann immer fehl.
    Deshalb steht dort `rev-list -n 1`."""
    _git(repo, "tag", "-a", "v3.0.0", "-m", "release")
    assert crd.tag_und_head("3.0.0") == (True, True)


# ---------------------------------------------------------------------------
# Einstieg
# ---------------------------------------------------------------------------


def test_eine_distanz_laesst_den_lauf_nicht_scheitern(repo, tmp_path, monkeypatch, capsys):
    """Der Bericht ist kein Gate. Ein Rueckgabewert != 0 machte den Montagslauf
    rot und waere innert Wochen abgeschaltet."""
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "miniatur"\nversion = "1.0.0"\n', encoding="utf-8"
    )
    _git(repo, "add", "pyproject.toml")
    _git(repo, "commit", "-m", "pyproject")
    ausgabe = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(ausgabe))
    code = crd.main(["--min-age-days", "1", "--offline-pypi", "1.0.0:2026-01-01"])
    assert code == 0
    assert "distance" in capsys.readouterr().out
    zeilen = dict(z.split("=", 1) for z in ausgabe.read_text(encoding="utf-8").splitlines())
    assert zeilen["state"] == "distance"
    assert zeilen["version"] == "1.0.0"
    assert int(zeilen["shipped"]) >= 1


def test_der_grund_geht_einzeilig_nach_github_output(tmp_path, monkeypatch):
    """`key=value` in `$GITHUB_OUTPUT` bricht bei einem Zeilenumbruch still
    auf — der Rest des Textes landete dann als eigener, unsinniger Schluessel.

    Der laengste `reason` ist der des fehlenden Tags; er ist im Quelltext
    ueber zwei Zeilen umbrochen und traegt deshalb im f-String keinen
    Umbruch. Dieser Test haelt fest, dass die Zusicherung auch dann gilt, wenn
    jemand dort spaeter ein `\\n` einbaut.
    """
    monkeypatch.setattr(crd, "ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "miniatur"\nversion = "1.0.0"\n', encoding="utf-8"
    )
    monkeypatch.setattr(
        crd,
        "klassifizieren",
        lambda **_: crd.Befund("unknown", "erste Zeile\nzweite Zeile", "1.0.0"),
    )
    ausgabe = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(ausgabe))
    crd.main(["--offline-pypi", "1.0.0:2026-01-01"])
    zeilen = ausgabe.read_text(encoding="utf-8").splitlines()
    assert "reason=erste Zeile zweite Zeile" in zeilen
    assert len(zeilen) == 8


def test_ein_checkout_ohne_tag_meldet_unknown_bis_nach_oben(repo, tmp_path, monkeypatch, capsys):
    """Derselbe Fall wie oben, aber durch `main()` statt gegen `klassifizieren`.

    Gemessen: verdrahtet man in `main()` `tag_gefunden, tag_ist_head = True,
    False` fest, bleiben alle Tests gruen, die nur die Klassifikation fahren —
    die Verdrahtung selbst war unbelegt. Genau das ist der Fall des flachen
    Checkouts: das Skript klassifiziert richtig, wuerde aber nie gefragt.
    """
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "miniatur"\nversion = "1.0.0"\n', encoding="utf-8"
    )
    _git(repo, "tag", "-d", "v1.0.0")
    ausgabe = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(ausgabe))
    assert crd.main(["--offline-pypi", "1.0.0:2026-01-01"]) == 0
    assert "unknown" in capsys.readouterr().out
    assert "state=unknown" in ausgabe.read_text(encoding="utf-8").splitlines()


def test_ohne_github_output_laeuft_der_lauf_durch(repo, monkeypatch):
    """Lokaler Aufruf ohne Actions-Umgebung."""
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "miniatur"\nversion = "1.0.0"\n', encoding="utf-8"
    )
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    assert crd.main(["--offline-pypi", "1.0.0:2026-01-01"]) == 0
