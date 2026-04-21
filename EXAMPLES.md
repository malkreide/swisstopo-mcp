# Use Cases & Examples — swisstopo-mcp

Real-world queries by audience. Für diesen Server gilt generell: **Kein API-Key erforderlich**.

### 🏫 Bildung & Schule
Lehrpersonen, Schulbehörden, Fachreferent:innen

**Analyse des Schulwegs**
«Wie ist das Höhenprofil für den Schulweg von der Dorfstrasse 12 zur Primarschule? Ist der Weg für die Kinder zu steil?»
→ `swisstopo_elevation_profile(coordinates="47.1234,8.1234;47.1250,8.1300")`
Warum nützlich: Erlaubt Lehrpersonen und Schulleitungen, die Sicherheit und physische Zumutbarkeit von Schulwegen, Exkursionen oder Wanderungen anhand präziser topografischer Daten schnell zu beurteilen.

**Historische Entwicklung der Schulgemeinde im Geografieunterricht**
«Finde historische Luftbilder und Karten unserer Gemeinde, damit wir sehen, wie sich die Siedlungsfläche in den letzten 50 Jahren verändert hat.»
→ `swisstopo_search_geodata(query="Orthofoto historisch")`
Warum nützlich: Bietet direktes, fesselndes Anschauungsmaterial für den Unterricht und macht die räumliche Entwicklung der eigenen Umgebung für Schülerinnen und Schüler greifbar.

### 👨‍👩‍👧 Eltern & Schulgemeinde
Elternräte, interessierte Erziehungsberechtigte

**Zonenzugehörigkeit für Hauskauf und Umbau**
«Wir interessieren uns für ein Haus an der Seestrasse 10 in Uster. Liegt das in einer Wohnzone oder Gewerbezone? Zeige mir das auf einer Karte.»
→ `swisstopo_geocode(search_text="Seestrasse 10, Uster")`
→ `swisstopo_map_url(lat=47.345, lon=8.718, layers="ch.are.bauzonen", zoom=10)`
Warum nützlich: Gibt Familien sofortige Klarheit über die baulichen Gegebenheiten, das Entwicklungspotenzial und das direkte Umfeld bei wichtigen Wohnortentscheidungen.

**Gefahrenzonen im Wohnquartier prüfen**
«Gibt es am Standort unseres Hauses (Koordinaten 46.852, 9.531) Naturgefahren wie Hochwasser oder Erdrutschgefahr?»
→ `swisstopo_identify_features(layers="ch.bafu.gefahrenkarten-uebersicht", lat=46.852, lon=9.531)`
Warum nützlich: Klärt Familien schnell über mögliche naturgegebene Risiken am Wohnort auf und hilft bei Entscheidungen zu Präventionsmassnahmen oder Versicherungen.

### 🗳️ Bevölkerung & öffentliches Interesse
Allgemeine Öffentlichkeit, politisch und gesellschaftlich Interessierte

**Überprüfung von Bauvorhaben in der Nachbarschaft**
«Welche baurechtlichen Einschränkungen gelten für die Bauparzelle bei den Koordinaten 47.376, 8.541 in Zürich? Ich möchte den ÖREB-Auszug sehen.»
→ `swisstopo_get_egrid(lat=47.376, lon=8.541, canton="ZH")`
→ `swisstopo_get_oereb_extract(egrid="CH123456789012", canton="ZH")`
Warum nützlich: Schafft Transparenz für die Nachbarschaft bei geplanten Bauprojekten und macht komplexe rechtliche Katasterinformationen für Laien verständlich zugänglich.

**Details zu Gebäuden und Infrastruktur nachschlagen**
«Zeig mir alle amtlichen Gebäudeauskünfte (GWR) zur Adresse Bundesplatz 1 in Bern, zum Beispiel das Baujahr.»
→ `swisstopo_geocode(search_text="Bundesplatz 1, Bern")`
→ `swisstopo_identify_features(layers="ch.bfs.gebaeude_wohnungs_register", lat=46.947, lon=7.444)`
Warum nützlich: Fördert das Verständnis öffentlicher Gebäude und gibt zivilgesellschaftlichen Akteuren detaillierte Einblicke in amtliche Registerdaten für eigene Recherchen.

### 🤖 KI-Interessierte & Entwickler:innen
MCP-Enthusiast:innen, Forscher:innen, Prompt Engineers, öffentliche Verwaltung

**Automatisierte Grundstücksanalyse (Multi-Server)**
«Ermittle die Eigentumsbeschränkungen (ÖREB) für das Grundstück beim Paradeplatz in Zürich und prüfe, ob es dort gemäss Zürcher Open Data Einträge zu Denkmalschutz oder Bauprojekten gibt.»
→ `swisstopo_get_egrid(lat=47.369, lon=8.538, canton="ZH")` (via swisstopo-mcp)
→ `swisstopo_get_oereb_extract(egrid="CH767982496078", canton="ZH")` (via swisstopo-mcp)
→ `zurich_search_datasets(query="Denkmalschutz")` (via [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp))
Warum nützlich: Demonstriert die enorme Stärke, föderale Geodaten der Swisstopo nahtlos mit lokalen städtischen Datensätzen zu verknüpfen, um umfassende, automatisierte Dossiers für beliebige Grundstücke zu generieren.

**Geocoding und Reisezeit-Berechnung (Multi-Server)**
«Suche die exakten Koordinaten für das Bundeshaus in Bern und berechne dann die Reisezeit mit dem Zug vom Hauptbahnhof Zürich dorthin.»
→ `swisstopo_geocode(search_text="Bundesplatz 3, Bern")` (via swisstopo-mcp)
→ `transport_get_connections(from_location="Zürich HB", to_location="46.946, 7.444")` (via [swiss-transport-mcp](https://github.com/malkreide/swiss-transport-mcp))
Warum nützlich: Zeigt, wie zuverlässiges amtliches Geocoding als unverzichtbare Basis für komplexe Mobilitäts- und Routingabfragen über mehrere MCP-Server hinweg dient.

### 🔧 Technische Referenz: Tool-Auswahl nach Anwendungsfall

| Ich möchte… | Tool(s) | Auth nötig? |
|-------------|---------|-------------|
| **eine Adresse in Koordinaten umwandeln (oder umgekehrt)** | `swisstopo_geocode`, `swisstopo_reverse_geocode` | Nein |
| **die Höhe über Meer für einen Ort wissen** | `swisstopo_get_height` | Nein |
| **ein Höhenprofil für eine Route berechnen** | `swisstopo_elevation_profile` | Nein |
| **Kartenlinks zum Teilen im Browser generieren** | `swisstopo_map_url` | Nein |
| **herunterladbare Geodaten (3D, Orthofotos) finden** | `swisstopo_search_geodata`, `swisstopo_get_collection` | Nein |
| **herausfinden, was sich an einem bestimmten Punkt befindet** | `swisstopo_search_layers`, `swisstopo_identify_features` | Nein |
| **ein spezifisches Kartenobjekt nach ID oder Attribut suchen** | `swisstopo_find_features`, `swisstopo_get_feature` | Nein |
| **baurechtliche Eigentumsbeschränkungen (ÖREB) abfragen** | `swisstopo_get_egrid`, `swisstopo_get_oereb_extract` | Nein |
