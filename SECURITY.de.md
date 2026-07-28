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
Alle 20 Tools fragen ausschliesslich eine fixe Allow-List schweizerischer
Bundes- und Kantonsgeodaten-Hosts ab. Bereits umgesetzte Härtung:

| Bereich | Kontrolle |
|---|---|
| Egress | HTTPS-Allow-List auf Code-Ebene (`ALLOWED_HOSTS`-Frozenset), beschränkt auf `*.geo.admin.ch` und die kantonalen OEREB-Endpunkte (SEC-004 / SEC-021) — siehe [docs/network-egress.md](docs/network-egress.md) |
| Redirects | `follow_redirects=False` am gemeinsamen `httpx`-Client, sodass ein Upstream nicht auf einen Host ausserhalb der Liste umleiten kann (SEC-004) |
| SSRF | Schema-Prüfung plus Resolved-IP-Guard, der Hosts abweist, die mit einer privaten oder Link-local-Adresse antworten (SEC-004) |
| DNS-Pinning | **Implementiert, seit 0.4.0 standardmässig an** (SEC-005). `PinnedTransport` verbindet auf die vom SSRF-Guard geprüfte Adresse und behält Host und SNI auf dem Hostnamen, die Zertifikatsprüfung bleibt also unverändert. Damit ist das Rebinding-Fenster zwischen der Prüfung und dem Lookup von httpx geschlossen — bis und mit 0.3.x blieb es im ausgelieferten Default offen. Abschalten mit `SWISSTOPO_PIN_DNS=0`. Hinter einem Forward-Proxy wirkungslos und dort selbstdeaktivierend, ein Cluster-Deployment mit Egress-Proxy ist also in beiden Fällen unberührt. |
| TLS | Zertifikatsprüfung standardmässig aktiv für alle Upstream-Requests |
| Eingabe | Strikte Pydantic-v2-Validierung an jeder Tool-Grenze (SEC-018) |
| Secrets | Nur Umgebungsvariablen; `.gitignore` schützt `.env`; keine hartcodierten Secrets (ARCH-005) |
| Fehler | Weder Upstream-Texte noch interne Konfiguration erreichen den Aufrufer (OBS-002). Unerwartete Exceptions werden zentral maskiert; Overpass-Fehlerseiten werden gegen eine feste Signaturtabelle klassifiziert statt weitergereicht; Egress-Ablehnungen liefern eine feste Meldung. Alle Details gehen auf stderr. Ausserhalb der Kontrolle dieses Servers: Pydantic-Argumentfehler formatiert das SDK selbst, und `mask_error_details` existiert in mcp 1.28.1 nicht |
| Stdout | Reserviert für den JSON-RPC-Stream; Logging auf stderr fixiert |
| Trifecta | Höchstens 1 von 3 Lethal-Trifecta-Beinen vorhanden — read-only, öffentliche Daten, kein Write/Send (SEC-019) |
| Container | Gehärtetes `Dockerfile` (non-root, read-only Root-Dateisystem, gedroppte Capabilities) für HTTP-Deployments (SEC-007) — siehe [docs/deployment.md](docs/deployment.md) |

Die vollständigen Berichte finden sich unter [`audits/`](audits/), die
Härtungs-Historie in [CHANGELOG.md](CHANGELOG.md).

## Read-only by Design

Dieser Server befindet sich in **Phase 2.5** (siehe
[docs/roadmap.md](docs/roadmap.md) — die alleinige Autorität für den
Phasenstand). Er bleibt ein Read-only-Wrapper: alle 20 Tools sind
`readOnlyHint: true` / `destructiveHint: false`; es gibt keine schreibenden oder
versendenden Funktionen. Die CI erzwingt beide Hälften: `tests/test_tool_hygiene.py`
schlägt fehl, wenn ein Tool `readOnlyHint` verliert, **und** findet statisch jeden
ausgehenden HTTP-Aufruf in `src/` und schlägt bei jeder mutierenden Methode fehl.
Die Annotation ist, was ein Tool behauptet; die Methodenprüfung ist, was es tut.

## Sessions & Authentifizierung

Der Server ist bewusst nicht authentifiziert — er liefert ausschliesslich
öffentliche Open Data. Über HTTP erzeugt das SDK die Session-IDs (`uuid4().hex`,
128 Bit aus `os.urandom`); es gibt keinen benutzerspezifischen Zustand, also
nichts, woran eine Session gebunden werden müsste. Würde später eine
authentifizierte Variante eingeführt, müssen Session-IDs an die validierte
Benutzeridentität gebunden werden (Audit-Finding SEC-009).

Zwei Kontrollen, die kein Auth-Modell voraussetzen, sind aktiv:

- **Idle-Timeout.** `SWISSTOPO_SESSION_IDLE_TIMEOUT` (Standard 1800 s) beendet
  Sessions ohne Anfragen. Der SDK-Standard ist *kein* Timeout — ein Client, der
  sich ohne Session-Abbau trennt, hinterlässt eine Session für die gesamte
  Prozesslaufzeit. Aktivität verschiebt die Frist; `0` stellt das unbegrenzte
  Verhalten wieder her.
- **Serverseitige Invalidierung.** `DELETE /mcp` mit der Session-ID beendet sie
  sofort — verifiziert: die nächste Anfrage erhält `404`. Das ist der Mechanismus
  des Protokolls selbst, eine eigene Logout-Route existiert daher nicht und
  wird nicht gebraucht.

## Kontrollen auf Portfolio-Ebene

Die folgenden Punkte sind bewusst **nicht** innerhalb dieses Servers umgesetzt.
Sie sind portfolioweite Anliegen und werden am besten auf einer MCP-Gateway-/
Host-Ebene durchgesetzt; das Restrisiko ist hier gering, weil der Server
read-only ist und nur einen fixen Satz vertrauenswürdiger Public-Data-Anbieter
erreicht.

- **Tool-Allow-Listing** gehört zum MCP-Host/-Gateway, das mehrere Server
  aggregiert, nicht zu einem einzelnen Server mit fixem, read-only Tool-Set.
  Solange kein zentrales Gateway existiert, ist das Risiko durch die
  Egress-Allow-List und die read-only Tool-Oberfläche begrenzt — beides in der
  CI erzwungen, nicht bloss behauptet. Read-only wird auf zwei Ebenen geprüft,
  weil die Annotation selbstbehauptet ist und ein schreibendes Tool darin
  schlicht lügen könnte: ein Test schlägt fehl, wenn ein Tool `readOnlyHint`
  verliert, ein zweiter parst `src/` und schlägt bei `PUT`, `PATCH` oder
  `DELETE` fehl. Der einzige Nicht-GET-Aufruf ist Overpass, das seine *Abfrage*
  im Request-Body überträgt; er ist im Test mit dieser Begründung benannt, und
  der Test schlägt auch fehl, wenn diese Ausnahme wegfällt — eine veraltete
  Ausnahme ist eine Erlaubnis, die niemand erteilt hat (Audit
  `2026-07-27T162602-Z`, SEC-014).
- **Server-übergreifende Tool-Poisoning-Erkennung** ist eine Host-/Gateway-
  Verantwortung — kein einzelner Server sieht über die Menge hinweg. Die
  Tool-Definitionen dieses Servers sind versionskontrolliert und werden aus
  diesem Repository ausgeliefert; es gibt keine dynamische oder entfernte
  Tool-Registrierung.

  Zusätzlich prüft `tests/test_tool_hygiene.py` **jede Zeichenkette, die dieser
  Server ins Kontextfenster eines Modells liefert** — Tool-Namen und
  -Beschreibungen, jede `description` in einem Input- oder Output-Schema sowie
  den serverweiten `instructions`-Block. Geprüft wird auf unsichtbare Zeichen,
  Override-Formulierungen (deutsch, französisch, englisch), eingebettete
  Rollen-/System-Marker (`<SYSTEM>`, `[INST]`, `### Instructions:`,
  `<|im_start|>`), verwechselbare kyrillische/griechische Substitutionen, nicht
  kanonische Tool-Namen und eine Längenobergrenze. `tool-hashes.json` fixiert
  zusätzlich Name, Beschreibung und Input-Schema pro Tool.

  Zuvor las der Scan nur Namen und Beschreibungen, während dieser Abschnitt
  behauptete, er decke „die eigenen Beschreibungen" ab. Schema-Feldbeschreibungen
  und der Instructions-Block erreichen das Modell identisch — eine dort platzierte
  Injektion kam durch jede Prüfung (Audit `2026-07-27T162602-Z`, SEC-015). Beides
  wird jetzt durchlaufen, und ein Test stellt sicher, dass der Sweep sie erreicht.

  Jede Musterklasse hat einen eigenen Test mit Beispiel-Payload, damit ein
  stillschweigend kaputtes Muster den Build bricht statt leise zu bestehen.

  Das bleibt ein Selbst-Scan, keine serverübergreifende Erkennung.

## Anlässe zur Neubewertung

Diese Entscheidungen sollten überdacht werden, sobald der Server:

- **Schreib-/Sende**-Funktionen erhält oder **PII** verarbeitet, oder
- Tools **dynamisch** / aus entfernten Quellen registriert, oder
- hinter einem gemeinsamen MCP-Gateway aggregiert wird (dann Tool-Allow-Listing
  und Poisoning-Erkennung dort umsetzen).
