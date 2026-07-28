# ISDS-Klassifikation & DSG-Einordnung

**Status:** Engineering-Einschätzung, kein Rechtsgutachten.
**Stand:** 2026-07-28 · **Bezug:** Audit-Check OPS-003 (Phase-1-Abschluss), CH-002, CH-005

> **English summary.** This server processes exclusively public Swiss open
> geodata. It holds no accounts, no credentials and no persistent state, and it
> stores nothing. Query inputs (addresses, coordinates) *can* constitute personal
> data when linkable to a person; they are forwarded to federal and cantonal
> upstreams and are not retained here. The protection requirement is assessed as
> **low** for confidentiality and integrity and **low–normal** for availability.
> No processing record under the Swiss DSG is maintained, for the reasons in
> §4 — the operator of a deployment remains responsible for confirming that for
> their own context. §5 lists what would change the conclusion.

Dieses Dokument schliesst die Phase-1-Kriterien aus OPS-003 ab. Es beschreibt,
**was der Server tatsächlich verarbeitet**, nicht was er verarbeiten dürfte.

---

## 1. Systemabgrenzung

`swisstopo-mcp` ist ein zustandsloser MCP-Server, der Anfragen eines
LLM-Clients auf eine feste Liste öffentlicher Geodaten-Endpunkte abbildet
(siehe [`network-egress.md`](network-egress.md)).

| Eigenschaft | Ausprägung |
|---|---|
| Tools | 24, alle `readOnlyHint: true` / `destructiveHint: false` |
| Schreibzugriffe | keine — CI prüft nicht nur die Annotation, sondern auch, dass kein `PUT`/`PATCH`/`DELETE` im Code vorkommt (SEC-014) |
| Authentifizierung | keine, bewusst (SECURITY.md) |
| Persistenz | keine Datenbank, kein Cache auf Platte. Ein In-Memory-Katalog (geodienste.ch, TTL 6 h) und ein DNS-Cache sind der gesamte Zustand |
| Container-Dateisystem | read-only, ausser `/tmp` (64 MiB, `emptyDir`) |

## 2. Informationskategorien

| Kategorie | Herkunft | Bewertung |
|---|---|---|
| **Ausgelieferte Geodaten** | Bund (swisstopo, ARE, BFS), Kantone (ÖREB, geodienste.ch), OSM | Öffentlich. Keine Personendaten. Der ÖREB-Kataster ist rechtsverbindlich, aber öffentlich einsehbar. |
| **Anfrage-Eingaben** | vom aufrufenden Client | **Hier liegt der einzige heikle Punkt.** Eine Adresse oder eine Koordinate kann Personendaten darstellen, sobald sie einer Person zuordenbar ist — z. B. „Wohnort von X". Der Server kennt diesen Bezug nicht und kann ihn nicht herstellen. |
| **Betriebsdaten** | Server selbst | Tool-Name, Korrelations-ID, Dauer, Fehlerflag. Siehe §3. |

Der Server führt **keine** Identitätsauflösung, kein Profiling, keine
Verknüpfung über Anfragen hinweg. Die Korrelations-ID ist pro Aufruf zufällig
und wird nirgends gespeichert.

## 3. Wo Eingaben tatsächlich hingelangen

Das ist der Teil, der nachgeprüft und nicht angenommen wurde.

| Pfad | Enthält Eingaben? |
|---|---|
| Upstream-Request | **Ja** — das ist der Zweck. Ziel ist eine feste Allow-List von zehn Hosts, ausschliesslich HTTPS, keine Redirects. |
| Normales Log (stderr) | **Nein.** `tool_invoked` / `tool_completed` protokollieren Tool-Name, Korrelations-ID, Dauer und Zeichenzahl — keine Argumente. Ein Test hält das fest. |
| Fehler-Log (stderr) | **Ja, teilweise.** `handled_error` protokolliert `str(e)`, und eine Validierungsmeldung kann die Eingabe zitieren („Ort 'X' konnte nicht geokodiert werden"). `overpass_error_page` protokolliert bis zu 1000 Zeichen der Upstream-Fehlerseite, die die abgesendete Abfrage samt Koordinaten enthalten kann. |
| Antwort an den Client | Ja, als Echo in der Zusammenfassung — Upstream-Texte selbst werden nicht durchgereicht (OBS-002). |
| Tracing (nur wenn aktiviert) | **Eingeschränkt.** Der Tool-Span trägt nur Name und Fehlerflag. Die httpx-Child-Spans werden vor dem Export bereinigt: Query-String, Fragment und Userinfo entfallen (OBS-006). **Der Pfad bleibt erhalten** und kann eine vom Aufrufer gelieferte Kennung tragen (`collection_id`, Feature-IDs). |
| Platte | Nein. |

**Konsequenz für den Betrieb:** stderr eines Deployments ist wie ein Log zu
behandeln, das gelegentlich Anfrage-Inhalte enthält — also mit derselben
Aufbewahrungsfrist und demselben Zugriffsschutz wie andere Applikationslogs.
Wer Tracing aktiviert, exportiert zusätzlich Pfade an das
Observability-Backend, das üblicherweise eine andere Zugriffsliste hat.

## 4. ISDS-Schutzbedarf

| Schutzziel | Bedarf | Begründung |
|---|---|---|
| **Vertraulichkeit** | tief | Die ausgelieferten Daten sind öffentlich. Der Restbedarf betrifft ausschliesslich die Anfrage-Inhalte (§3), nicht die Antworten. |
| **Integrität** | tief–normal | Verfälschte Geodaten könnten eine Fehlentscheidung stützen — insbesondere beim ÖREB-Kataster, der rechtsverbindliche Eigentumsbeschränkungen abbildet. Deshalb: HTTPS erzwungen, keine Redirects, Egress-Allow-List, Quellen- und Lizenzangabe an jeder Antwort. Der Server ist jedoch **nie** die rechtsverbindliche Quelle; das ist die zuständige Amtsstelle. |
| **Verfügbarkeit** | tief | Ein Ausfall verhindert Auskünfte, verursacht aber keinen Datenverlust — es gibt keinen Zustand, der verloren gehen könnte. Sessions überleben einen Pod-Ausfall bewusst nicht (siehe `deployment.md`). |

**Einstufung: tiefer Schutzbedarf.** Keine besonders schützenswerten
Personendaten im Sinne von DSG Art. 5 lit. c, keine Amtsgeheimnisse, keine
Klassifizierung über „intern" hinaus.

## 5. DSG-Einordnung

**Es wird kein Verarbeitungsverzeichnis nach DSG Art. 12 geführt.** Begründung:

1. Der Server ist **kein Verantwortlicher** im Sinne von DSG Art. 5 lit. j für
   die Anfrage-Inhalte. Er entscheidet weder über Zweck noch über Mittel der
   Bearbeitung — das tut die aufrufende Anwendung. Der Server ist Werkzeug.
2. Es findet **keine Aufbewahrung** statt. Ohne Speicherung existiert kein
   Datenbestand, über den ein Verzeichnis Auskunft geben könnte.
3. Die Bearbeitung ist auf die Weiterleitung an amtliche Stellen beschränkt,
   die ihrerseits verantwortlich sind.

**Das entlastet den Betreiber nicht.** Wer diesen Server in eine Anwendung
einbindet, die Personendaten bearbeitet, führt das Verzeichnis für *diese*
Anwendung und nimmt den Server dort als Bearbeitungsschritt auf. Die Angaben
in §3 sind genau dafür gedacht.

## 6. Was diese Einschätzung umstösst

Jeder dieser Punkte macht eine Neubewertung nötig — sie sind identisch mit den
Auslösern in [`SECURITY.md`](../SECURITY.md) und bewusst redundant genannt:

- **Schreib- oder Sendefunktionen** (Phase 3). Dann entstehen Bearbeitungen mit
  Aussenwirkung, und die Lethal-Trifecta-Bewertung (SEC-019) ist zu wiederholen.
- **Authentifizierung.** Sobald Nutzeridentitäten existieren, entstehen
  Personendaten im Server selbst — Sessions, Zuordnungen, Logs mit Bezug.
- **Persistenz jeder Art** — Cache auf Platte, Query-Historie, Analytics.
- **Eine Datenquelle mit Personenbezug.** Alle heutigen Quellen liefern
  Sachdaten. Ein Handelsregister- oder Einwohner-Endpunkt wäre eine andere
  Kategorie.
- **Tracing mit Pfad-Kennungen in einem Backend mit weiterem Zugriffskreis** —
  siehe §3, letzte Zeile.

## 7. Grenzen dieses Dokuments

Es ist eine technische Bestandsaufnahme durch die Entwicklung, kein
Rechtsgutachten und keine Freigabe. Es beschreibt den Code in diesem Repository
zum genannten Stand. Ein konkretes Deployment kann durch Konfiguration
(aktiviertes Tracing, Log-Weiterleitung, vorgelagerte Authentifizierung) eine
andere Einstufung erfordern; die Verantwortung dafür liegt beim Betreiber.
