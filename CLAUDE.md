# CLAUDE.md

## Teil 1 — Konventionen (portfolio-weit)

### Vor der Arbeit

Klon-Aktualität prüfen: `git fetch origin master && git rev-list --count HEAD..origin/master`
Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht.
Am 3.8.2026 zweimal passiert — beide Male fehlten genau die Commits, die
das Gate einführten, an dem der Branch scheiterte.

Gates lokal fahren, mit der GEPINNTEN ruff-Version aus der CI. Eine andere
Version meldet Abweichungen, die niemand verursacht hat.

### Tests

Gegenprobe ist Pflicht. Ein Test, der grün bleibt, wenn man die
Implementierung entfernt, prüft nichts. Jede neue Zusicherung einzeln
neutralisieren und zeigen, dass genau die zugehörigen Tests fallen.

Zwei Fallen, die beide grün blieben:

- Eine Fake-Uhr, die nur beim Schlafen vorrückt, kann eine Zusicherung über
  echte Zeit nicht widerlegen.
- `monkeypatch.setattr(modul.asyncio, "sleep", ...)` greift ins Modul
  `asyncio` selbst und entschärft die Mechanik im ganzen Prozess. Patche
  einen Modul-Alias (`_sleep = asyncio.sleep`), nicht das fremde Modul.

Handgeschriebene Fixtures kodieren die Annahme des Autors und können sie
nicht widerlegen. Mindestens eine aufgezeichnete Antwort pro externem
Endpunkt, mit Aufnahmedatum.

### Wenn etwas rot ist

Roter Live-Test: erst die Quelle abfragen, dann einordnen. Nicht aus der
Fehlermeldung schliessen. Am 3.8.2026 hiess "nicht gefunden" nicht, dass der
Datensatz weg war, sondern dass die Quelle die Schreibweise ihrer Kopfzeile
gewechselt hatte — vier von sechs Datensätzen produktiv kaputt, alle
Unit-Tests grün.

PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.

Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

## Teil 2 — dieses Repo

**Der Default-Branch heisst `master`, nicht `main`.** PRs gehen dorthin.

**Werkzeug-Versionen — zwei ungleich behandelte Fälle.** `ci.yml` pinnt
`ruff==0.16.1`, das `[dev]`-Extra deklariert `ruff>=0.4.0,<0.17`; ein frisches
`pip install -e ".[dev]"` liefert 0.16.3, also nicht die Version des Gates.
**mypy ist gar nicht gepinnt** (`mypy>=1.10.0`), und `mypy src/` läuft mit dem,
was gerade auflöst — am 16.08.2026 war das 2.3.1. Die Begründung, mit der ruff
gepinnt ist, gilt hier genauso: ein Upstream-Release kann Regeln ändern und
unberührten Code rot machen.

Beides zusammen heisst: Lokale Läufe nur mit den Versionen aus einem frischen
`[dev]`-Install bewerten. Ein mypy aus der Umgebung meldet Fehler, die das
Projekt nicht hat — gemessen: das ambiente 1.19.1 findet in `api_client.py`
einen `no-any-return`, den 2.3.1 nicht sieht.

**Gates, wörtlich aus der CI:**

```bash
pytest tests/ -m "not live"
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
mypy src/
python scripts/snapshot_tool_hashes.py --check
python scripts/render_egress_acl.py --check
python scripts/check_version_sync.py
```

Kein `include` unter `[tool.ruff]` setzen — der Umfang stimmt (59 Dateien über
alle drei Verzeichnisse, nachgemessen).

**Live-Tests:** `.github/workflows/live-test.yml`, nächtlich per Cron
(`0 4 * * *`). Sie sind hier also nicht bloss per `-m "not live"`
ausgeschlossen; DRIFT-005 ist erfüllt.
