# Sicherheitsrichtlinie & Sicherheitslage

[🇬🇧 English Version](SECURITY.md)

`swisstopo-mcp` wurde gegen den internen MCP-Best-Practice-Audit-Katalog
gehärtet (siehe [`audits/`](audits/)). Dieses Dokument fasst die Sicherheitslage
zusammen und dokumentiert die Kontrollen, die bewusst auf der Portfolio-/
Gateway-Ebene statt innerhalb dieses einzelnen Servers behandelt werden.

## Schwachstelle melden

Bitte eröffnen Sie ein privates Security Advisory im GitHub-Repository oder
kontaktieren Sie die in [`README.md`](README.md) genannte betreuende Person.
Melden Sie ausnutzbare Schwachstellen nicht über öffentliche Issues.

## Zusammenfassung der Sicherheitslage

Dies ist ein **read-only**-, **PII-freier**, **Public-Open-Data**-MCP-Server.
Alle 13 Tools fragen ausschliesslich eine fixe Allow-List schweizerischer
Bundes- und Kantonsgeodaten-Hosts ab. Bereits umgesetzte Härtung:

| Bereich | Kontrolle |
|---|---|
| Egress | HTTPS-Allow-List auf Code-Ebene (`ALLOWED_HOSTS`-Frozenset), beschränkt auf `*.geo.admin.ch` und die kantonalen OEREB-Endpunkte (SEC-004 / SEC-021) — siehe [docs/network-egress.md](docs/network-egress.md) |
| Redirects | `follow_redirects=False` am gemeinsamen `httpx`-Client, sodass ein Upstream nicht auf einen Host ausserhalb der Liste umleiten kann (SEC-005) |
| TLS | Zertifikatsprüfung standardmässig aktiv für alle Upstream-Requests |
| Eingabe | Strikte Pydantic-v2-Validierung an jeder Tool-Grenze (SEC-018) |
| Secrets | Nur Umgebungsvariablen; `.gitignore` schützt `.env`; keine hartcodierten Secrets (ARCH-005) |
| Fehler | Upstream-/Exception-Texte landen auf stderr und erreichen das Modell nie (OBS-002) |
| Stdout | Reserviert für den JSON-RPC-Stream; Logging auf stderr fixiert |
| Trifecta | Höchstens 1 von 3 Lethal-Trifecta-Beinen vorhanden — read-only, öffentliche Daten, kein Write/Send (SEC-019) |
| Container | Gehärtetes `Dockerfile` (non-root, read-only Root-Dateisystem, gedroppte Capabilities) für HTTP-Deployments (SEC-007) — siehe [docs/deployment.md](docs/deployment.md) |

Die vollständigen Berichte finden sich unter [`audits/`](audits/), die
Härtungs-Historie in [CHANGELOG.md](CHANGELOG.md).

## Read-only by Design (Phase 1)

Dieser Server befindet sich in **Phase 1 — Read-only-Wrapper**. Alle 13 Tools
sind `readOnlyHint: true` / `destructiveHint: false`; es gibt keine schreibenden
oder versendenden Funktionen. Spätere Phasen siehe [docs/roadmap.md](docs/roadmap.md).

## Sessions & Authentifizierung

Der Server ist bewusst nicht authentifiziert — er liefert ausschliesslich
öffentliche Open Data. Über HTTP werden Session-IDs vollständig vom FastMCP-
Framework verwaltet; es gibt keinen benutzerspezifischen Zustand, also nichts,
woran eine Session gebunden werden müsste. Würde später eine authentifizierte
Variante eingeführt, müssen Session-IDs an die validierte Benutzeridentität
gebunden werden (Audit-Finding SEC-009).

## Kontrollen auf Portfolio-Ebene

Die folgenden Punkte sind bewusst **nicht** innerhalb dieses Servers umgesetzt.
Sie sind portfolioweite Anliegen und werden am besten auf einer MCP-Gateway-/
Host-Ebene durchgesetzt; das Restrisiko ist hier gering, weil der Server
read-only ist und nur einen fixen Satz vertrauenswürdiger Public-Data-Anbieter
erreicht.

- **Tool-Allow-Listing** gehört zum MCP-Host/-Gateway, das mehrere Server
  aggregiert, nicht zu einem einzelnen Server mit fixem, read-only Tool-Set.
  Solange kein zentrales Gateway existiert, ist das Risiko durch die
  Egress-Allow-List und die read-only Tool-Oberfläche begrenzt.
- **Server-übergreifende Tool-Poisoning-Erkennung** ist eine Host-/Gateway-
  Verantwortung. Die Tool-Definitionen dieses Servers sind versionskontrolliert
  und werden aus diesem Repository ausgeliefert; es gibt keine dynamische oder
  entfernte Tool-Registrierung.

## Anlässe zur Neubewertung

Diese Entscheidungen sollten überdacht werden, sobald der Server:

- **Schreib-/Sende**-Funktionen erhält oder **PII** verarbeitet, oder
- Tools **dynamisch** / aus entfernten Quellen registriert, oder
- hinter einem gemeinsamen MCP-Gateway aggregiert wird (dann Tool-Allow-Listing
  und Poisoning-Erkennung dort umsetzen).
