# CLAUDE.md

## Teil 1 — Konventionen (portfolio-weit)

### Vor der Arbeit

Klon-Aktualität prüfen — Standard-Branch ermitteln, nicht `main` annehmen:

```bash
B=$(git ls-remote --symref origin HEAD | sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p')
git fetch origin "${B:?Standard-Branch nicht ermittelbar}" &&
  git rev-list --count HEAD..FETCH_HEAD
```

Drei Server im Portfolio heissen ihren Standard-Branch `master`
(`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`); dort scheitert ein fest
verdrahtetes `origin/main` mit «couldn't find remote ref main». Wer das für ein
Netzproblem hält, arbeitet weiter auf genau dem veralteten Klon, vor dem dieser
Absatz warnt. Den `:?`-Schutz nicht weglassen: Bei leerem `B` fetcht git still
den Remote-HEAD und endet mit 0.

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

**Werkzeug-Versionen:** `ruff==0.16.1` und `mypy==2.3.1`, beide exakt und beide
nur im `[dev]`-Extra von `pyproject.toml`. Ein Install des Extras reicht also,
lokal wie in der CI. Keine zweite Version in die Workflows schreiben: ein
solcher Schritt läuft nach dem Install und überstimmt den Pin still — für ruff
stand er dort (`test_werkzeug_versionen.py` hält beides fest).
Eine `.pre-commit-config.yaml` gibt es nicht — die andere Stelle, an der ein
abweichender ruff-Pin schlummern kann. Wer eine anlegt, nimmt die Version aus
`pyproject.toml`.

Lokale Läufe trotzdem nur mit den Versionen aus einem frischen `[dev]`-Install
bewerten. Ein Werkzeug aus der Umgebung meldet Fehler, die das Projekt nicht
hat — gemessen: das ambiente mypy 1.19.1 findet in `api_client.py` einen
`no-any-return`, den 2.3.1 nicht sieht.

**Gates, wörtlich aus der CI:**

```bash
pytest tests/ -m "not live"
python scripts/check_ruff_pin.py
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
mypy src/
python scripts/snapshot_tool_hashes.py --check
python scripts/render_egress_acl.py --check
python scripts/check_version_sync.py
```

Kein `include` unter `[tool.ruff]` setzen — der Umfang sind die drei Pfade im
Gate-Befehl selbst. Wer ihn prüfen will, zählt nach statt hier abzulesen:
`ruff check src/ tests/ scripts/ --show-files | wc -l`. `ruff format` meldet
dabei eine Datei mehr als `ruff check`, weil 0.16 auch Markdown formatiert und
damit `tests/fixtures/PROVENANCE.md` mitnimmt — zwei Zahlen, kein Fehler.

**Ein achtes Gate hängt an jedem PR, ausserhalb von `ci.yml`:**
`security.yml` fährt gitleaks. Sein Trigger nennt `branches: [master, main]` —
beide, damit er eine Umbenennung des Default-Branchs überlebt. Lokal braucht
er gitleaks und läuft deshalb nicht nebenbei mit.

Die Matrix setzt kein `fail-fast: false`: Eine rote 3.11 bricht 3.12 und 3.13
ab, bevor sie etwas sagen.

**Live-Tests:** `.github/workflows/live-test.yml`, nächtlich per Cron
(`0 4 * * *`). Sie sind hier also nicht bloss per `-m "not live"`
ausgeschlossen; DRIFT-005 ist erfüllt.
