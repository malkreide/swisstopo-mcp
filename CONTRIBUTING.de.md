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

## Lizenz

Mit Ihrem Beitrag erklären Sie sich damit einverstanden, dass Ihre Beiträge unter der [MIT-Lizenz](LICENSE) lizenziert werden.
