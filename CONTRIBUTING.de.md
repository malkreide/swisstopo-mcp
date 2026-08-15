# Mitwirken an swisstopo-mcp

[🇬🇧 English Version](CONTRIBUTING.md)

Vielen Dank für Ihr Interesse an einem Beitrag! Dieser Server ist Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide).

---

## Issues melden

Nutzen Sie [GitHub Issues](https://github.com/malkreide/swisstopo-mcp/issues), um Fehler zu melden oder Funktionen vorzuschlagen.

Bitte geben Sie an:
- Python-Version und Betriebssystem
- Vollständige Fehlermeldung oder Beschreibung des unerwarteten Verhaltens
- Schritte zur Reproduktion

---

## Pull Requests

1. Repository forken
2. Feature-Branch erstellen: `git checkout -b feat/ihr-feature`
3. Änderungen vornehmen und Tests ergänzen
4. Sicherstellen, dass alle Tests bestehen: `pytest tests/ -m "not live"`
5. Mit [Conventional Commits](https://www.conventionalcommits.org/) committen: `feat: add new tool`
6. Pushen und einen Pull Request gegen `main` öffnen

---

## Code-Stil

- Python 3.11+
- [Ruff](https://github.com/astral-sh/ruff) für Linting und Formatierung
- Type Hints für alle öffentlichen Funktionen erforderlich
- Docstrings auf Englisch (für internationale Verständlichkeit)
- Tests für neue Tools erforderlich (in `tests/`)
- Den bestehenden FastMCP-/Pydantic-v2-Mustern in `server.py` folgen

---

## Datenquellen

Dieser Server nutzt sechs Swisstopo-API-Familien -- alle ohne Authentifizierung (OEREB erfordert einen Kantons-Parameter):

| Quelle | Dokumentation |
|--------|--------------|
| REST API | [api3.geo.admin.ch](https://api3.geo.admin.ch/) |
| Geocoding | [api3.geo.admin.ch](https://api3.geo.admin.ch/) |
| Hoehenservice | [api3.geo.admin.ch](https://api3.geo.admin.ch/) |
| STAC-Katalog | [data.geo.admin.ch](https://data.geo.admin.ch/) |
| WMTS | [wmts.geo.admin.ch](https://wmts.geo.admin.ch/) |
| OEREB-Kataster | Kantonale Endpunkte |

Beim Hinzufügen neuer Datenquellen gilt das **No-Auth-First**-Prinzip: Phase 1 verwendet ausschliesslich offene, authentifizierungsfreie Endpunkte. Authentifizierte APIs werden in späteren Phasen mit Graceful Degradation eingeführt.

---

## Die Live-Suite: wann sie läuft, und wer ein rotes Ergebnis sieht

**Kadenz:** täglich um 04:00 UTC, dazu jederzeit von Hand über *Actions → Live API tests → Run
workflow*. Siehe [`.github/workflows/live-test.yml`](.github/workflows/live-test.yml).

**Wer es sieht:** Ein roter Lauf öffnet ein Issue mit dem Label `live-test-failure` (Titel: «Nightly live API tests failed»). Ein zweiter roter Lauf erkennt das offene Issue **am Label**, nicht am Titel, und hängt sich an denselben Thread. Wer das Label von Hand entfernt, bekommt beim nächsten roten Lauf ein zweites Issue. Ein grüner Lauf schliesst das Issue **nicht** von selbst — nach einem behobenen Ausfall gehört es von Hand zugemacht, sonst hält der nächste Blick den alten Ausfall für den neuen.

**Ein roter Live-Lauf heisst nicht zwingend «unser Fehler».** Er heisst: Der
Vertrag mit der Quelle hat sich geändert, oder die Quelle ist gerade aus. Beides
gehört gesehen, nur das Erste gehört gefixt. Bitte den Lauf lesen, bevor der Job
deaktiviert wird — so stirbt dieser Check, und er ist der einzige im Repo, der
einer falschen Grundannahme über api3.geo.admin.ch widersprechen kann. Jeder andere Test
prüft gegen eine Fixture, und die Fixture ist aus derselben Annahme geschrieben
wie der Code.

## Lizenz

Mit Ihrem Beitrag erklären Sie sich damit einverstanden, dass Ihre Beiträge unter der [MIT-Lizenz](LICENSE) lizenziert werden.

## Versionierung von Tool-Definitionen

Name, Beschreibung und Eingabeschema eines Tools sind das, was ein Client
freigibt. Ändert sich eines davon, läuft der Client gegen eine Definition, die
er nie gesehen hat:

- Ein Tool umbenennen oder ein Feld im Eingabeschema verengen bzw. umbenennen
  ist ein **Breaking Change**: Version anheben, CHANGELOG-Eintrag mit alt → neu
  und dem Hinweis, dass eine erneute Freigabe nötig ist.
- `tool-hashes.json` muss im selben Change neu erzeugt
  (`python scripts/snapshot_tool_hashes.py`) und committet werden. CI schlägt
  fehl, wenn es veraltet ist.
- Präzedenzfälle: `sr` auf 4326 eingeschränkt (0.2.x), sechs Tool-Umbenennungen
  (0.3.0).
