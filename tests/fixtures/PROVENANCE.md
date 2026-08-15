# Herkunft der Fixtures

Aufgezeichnet am **2026-08-15** mit `python scripts/record_fixtures.py`.

Eine Antwort je **Anfrage**, nicht je Endpunkt: dieser Server spricht mit sieben
Hosts, aber in weit mehr Abfrageformen — der `/rest/services`-Zweig allein
bedient fuenf Operationen. Sieben Dateien wuerden die Portfolio-Regel erfuellen
und fast nichts belegen.

Die Antworten stammen aus dem geteilten Client (gleicher User-Agent, gleiches
Timeout, gleiche Transportschicht wie im Betrieb), abgegriffen ueber einen
httpx-Response-Hook. Ausgeloest hat sie jeweils das Werkzeug selbst — so belegt
die Aufzeichnung auch, dass das Werkzeug genau diese Anfrage schickt.

Der **Schluessel** unten ist, woran der Test eine Anfrage wiedererkennt: die URL,
bei POST um eine Kurzfassung des Rumpfes ergaenzt. Zugeordnet wird danach und
nicht nach Reihenfolge — `_query_geodienste` faehrt seine Kantone per
`asyncio.gather`, und eine Zuordnung nach Reihenfolge waere im gruenen Fall
bloss zufaellig richtig.

Neu gesetzt ist die Einrueckung; gekuerzt ist allein die **Zahl** der Eintraege
der laengsten Liste. Kein Feld eines behaltenen Eintrags ist angetastet, und
Zaehlfelder daneben stehen wie geliefert — die Quelle meint damit die
Gesamtzahl, nicht die Zahl der gelieferten Zeilen.

Die Fehlerpfade — Timeout, 5xx, leere Trefferliste — bleiben handgeschrieben.
Sie lassen sich nicht auf Zuruf aufzeichnen und sind als Erfindung in Ordnung.

## `elevation_profile_1.json`

- **Werkzeuge:** `swisstopo_elevation_profile`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/profile.json?geom=%7B%22type%22%3A%22LineString%22%2C%22coordinates%22%3A%5B%5B2683304.0346262627%2C1247925.5974930264%5D%2C%5B2683925.9269017293%2C1248279.0709856586%5D%5D%7D&nb_points=200&sr=2056`
- **Auswahl:** 5 von 200 Listeneintraegen (je Liste die ersten 5), aus 21717 Bytes Rohantwort
- **Groesse:** 830 Bytes
- **SHA-256:** `54fbfc0170c3e019d3531bd56a2eed55463c73b1dad79649459f154bcc66c6ac`

## `find_commune_1.json`

- **Werkzeuge:** `find_commune_tool`
- **Schluessel:** `https://openplzapi.org/ch/Localities?name=Z%C3%BCrich`
- **Auswahl:** 5 von 10 Listeneintraegen (je Liste die ersten 5), aus 2281 Bytes Rohantwort
- **Groesse:** 1758 Bytes
- **SHA-256:** `89de04fc0ad8d3e775555acff3a8998ba9f67c8d5d0af282fcc98303a80e4e70`

## `geocode_1.json`

- **Werkzeuge:** `swisstopo_geocode`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/SearchServer?type=locations&searchText=Bahnhofplatz+1%2C+8001+Z%C3%BCrich&sr=4326&limit=10&returnGeometry=true`
- **Auswahl:** ungekuerzt
- **Groesse:** 1102 Bytes
- **SHA-256:** `1eab665579649ea65b01c8dc7df113da90d1ef451601c4ba758beeaaa212d856`

## `get_collection_1.json`

- **Werkzeuge:** `swisstopo_get_collection`
- **Schluessel:** `https://data.geo.admin.ch/api/stac/v0.9/collections/ch.swisstopo.swissalti3d`
- **Auswahl:** 20 von 22 Listeneintraegen (je Liste die ersten 5), aus 1624 Bytes Rohantwort
- **Groesse:** 1837 Bytes
- **SHA-256:** `e8a45f6848c1e9282a62d2e3456c07e0a9cbf17bf8d689ea407995215b9de178`

## `get_egrid_1.json`

- **Werkzeuge:** `swisstopo_get_egrid`, `swisstopo_oereb_at`
- **Schluessel:** `https://maps.zh.ch/oereb/v2/getegrid/json/?EN=2683304.0346262627,1247925.5974930264`
- **Auswahl:** ungekuerzt
- **Groesse:** 307 Bytes
- **SHA-256:** `ce09b0460d85ef2e58f340e51fd8be05195ce285b70675ac844bd1fcb1771f05`

## `height_1.json`

- **Werkzeuge:** `swisstopo_get_height`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/height?easting=2683304.0346262627&northing=1247925.5974930264&sr=2056`
- **Auswahl:** ungekuerzt
- **Groesse:** 24 Bytes
- **SHA-256:** `895a240c89d6058ea7cffa68bd1e6f25c2227a58101a9d1833545ed50f70237f`

## `list_layers_1.json`

- **Werkzeuge:** `list_available_layers_tool`
- **Schluessel:** `https://geodienste.ch/info/services.json`
- **Auswahl:** 130 von 1327 Listeneintraegen (je Liste die ersten 5), aus 3469919 Bytes Rohantwort
- **Groesse:** 26072 Bytes
- **SHA-256:** `c9f408843e96ea69ff16ca05235ab72307ed7295b5cf2516634607eca2ef6fd5`

## `lookup_postal_code_1.json`

- **Werkzeuge:** `lookup_postal_code_tool`
- **Schluessel:** `https://openplzapi.org/ch/Localities?postalCode=8001`
- **Auswahl:** ungekuerzt
- **Groesse:** 354 Bytes
- **SHA-256:** `cadb109dcb21829dfa214044f06abb3a83968e92f518b0a1eb5e0cbae005c4f5`

## `map_query_features_at_point_1.json`

- **Werkzeuge:** `swisstopo_map_query`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=8.5417%2C47.3769&geometryType=esriGeometryPoint&layers=all%3Ach.bfs.gebaeude_wohnungs_register&tolerance=10&sr=4326&returnGeometry=false&mapExtent=8.5317%2C47.3669%2C8.5517%2C47.3869&imageDisplay=100%2C100%2C96`
- **Auswahl:** 25 von 164 Listeneintraegen (je Liste die ersten 5), aus 235575 Bytes Rohantwort
- **Groesse:** 11724 Bytes
- **SHA-256:** `6ef1fa86e00ef3d87797b59871386c345c49c529c54a9397a875b9c29b37413a`

## `map_query_layer_info_1.json`

- **Werkzeuge:** `swisstopo_map_query`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/api/MapServer/ch.bfs.gebaeude_wohnungs_register`
- **Auswahl:** 45 von 140 Listeneintraegen (je Liste die ersten 5), aus 10981 Bytes Rohantwort
- **Groesse:** 1429 Bytes
- **SHA-256:** `98935ad2bb492770ac392d644b0a995fb15777780687b158f57c501308796d41`

## `map_query_layer_info_2.txt`

- **Werkzeuge:** `swisstopo_map_query`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/all/MapServer/ch.bfs.gebaeude_wohnungs_register/legend?lang=de`
- **Auswahl:** ungekuerzt
- **Groesse:** 2194 Bytes
- **SHA-256:** `5c769ab268cc91c496106adde592dd4867674b074bbbf61ba9161882f4585e98`

## `map_query_search_layers_1.json`

- **Werkzeuge:** `swisstopo_map_query`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/SearchServer?type=layers&searchText=Geb%C3%A4ude&lang=de&limit=10`
- **Auswahl:** 5 von 10 Listeneintraegen (je Liste die ersten 5), aus 13384 Bytes Rohantwort
- **Groesse:** 6939 Bytes
- **SHA-256:** `afd11399f76c65307dd560e71e441d3b9bd915a1bbfc575b3092bec86a2fb9f1`

## `municipality_at_1.json`

- **Werkzeuge:** `swisstopo_municipality_at`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=2683304.0346262627%2C1247925.5974930264&geometryType=esriGeometryPoint&layers=all%3Ach.swisstopo.swissboundaries3d-gemeinde-flaeche.fill&mapExtent=0%2C0%2C100%2C100&imageDisplay=100%2C100%2C96&tolerance=0&sr=2056&lang=de&returnGeometry=false`
- **Auswahl:** ungekuerzt — der Server filtert *in* dieser Liste, ein Schnitt auf die ersten Zeilen erfaende einen Negativbefund
- **Groesse:** 185204 Bytes
- **SHA-256:** `11ac0b2a1d7fafc5b3170147be1ced4d1c567a6e7fe93f6f3ce0e6c208018ddd`

## `oereb_at_1.json`

- **Werkzeuge:** `swisstopo_oereb_at`
- **Schluessel:** `https://maps.zh.ch/oereb/v2/extract/json/?EGRID=CH119192997709&GEOMETRY=false&LANG=de`
- **Auswahl:** 285 von 340 Listeneintraegen (je Liste die ersten 5), aus 81862 Bytes Rohantwort
- **Groesse:** 75611 Bytes
- **SHA-256:** `9e8f98d23c3b22a4174f177c80c1fde82454ef1adfde6f16c8e53127cc7dceb3`

## `query_geodata_oereb_1.json`

- **Werkzeuge:** `query_geodata_tool`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/all/MapServer/identify?geometryType=esriGeometryPoint&geometry=2683304.0%2C1247925.6&sr=2056&tolerance=0&layers=all%3Ach.swisstopo-vd.stand-oerebkataster&mapExtent=2683254.0%2C1247875.6%2C2683354.0%2C1247975.6&imageDisplay=100%2C100%2C96&returnGeometry=false&lang=de`
- **Auswahl:** ungekuerzt
- **Groesse:** 2714 Bytes
- **SHA-256:** `883af1dea6ebeac60695b74d791cee8256d3a738a9ffc5d91b592694cb1d487b`

## `query_geodata_strassen_1.json`

- **Werkzeuge:** `query_geodata_tool`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometryType=esriGeometryPoint&geometry=2683304.0%2C1247925.6&sr=2056&tolerance=15&layers=all%3Ach.swisstopo.amtliches-strassenverzeichnis&mapExtent=2682304.0%2C1246925.6%2C2684304.0%2C1248925.6&imageDisplay=200%2C200%2C96&returnGeometry=false&lang=de`
- **Auswahl:** 5 von 13 Listeneintraegen (je Liste die ersten 5), aus 6037 Bytes Rohantwort
- **Groesse:** 3016 Bytes
- **SHA-256:** `3db0737df228a0f534223f248cf4f2d5f94d635a43ec2a7cbf19220f380ecdd7`

## `query_osm_1.json`

- **Werkzeuge:** `query_osm_features_tool`
- **Schluessel:** `https://overpass.osm.ch/api/interpreter#97a61bbc7858`
- **Rumpf:** `data=[out:json][timeout:25];(node["amenity"="pharmacy"](around:500,47.3769,8.5417);way["amenity"="pharmacy"](around:500,47.3769,8.5417);relation["amenity"="pharmacy"](around:500,47.3769,8.5417););out center tags 50;`
- **Auswahl:** 5 von 11 Listeneintraegen (je Liste die ersten 5), aus 7357 Bytes Rohantwort
- **Groesse:** 4124 Bytes
- **SHA-256:** `403a2638aca1c36b4b763ac47b3adff7f956590b69af1f81fd5cf7a7b8c98354`

## `reverse_geocode_1.json`

- **Werkzeuge:** `swisstopo_reverse_geocode`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/SearchServer?type=locations&origins=address&bbox=2682804.0346262627%2C1247425.5974930264%2C2683804.0346262627%2C1248425.5974930264&limit=5&sr=2056&returnGeometry=true`
- **Auswahl:** ungekuerzt
- **Groesse:** 5754 Bytes
- **SHA-256:** `0f3f160223c56be71db3926b3ecd51435045f8cca9c2c2f0f78f1f6100aecefb`

## `search_address_1.json`

- **Werkzeuge:** `search_address_tool`
- **Schluessel:** `https://openplzapi.org/ch/FullTextSearch?searchTerm=Bahnhofplatz+8001&page=1&pageSize=20`
- **Auswahl:** ungekuerzt
- **Groesse:** 431 Bytes
- **SHA-256:** `e8f022c48c9fe68f7bcd4ea3c824ffae3c964f1660db43a51ee0e4ac1acedbc8`

## `search_geodata_1.json`

- **Werkzeuge:** `swisstopo_search_geodata`
- **Schluessel:** `https://data.geo.admin.ch/api/stac/v0.9/collections`
- **Auswahl:** 100 von 205 Listeneintraegen (je Liste die ersten 5), aus 240323 Bytes Rohantwort
- **Groesse:** 21782 Bytes
- **SHA-256:** `8ad37f8dcb6b906f95f0d553f2e5177a4e6d2e23b6ff348e4c2f1c87817ceb07`

## `zoning_at_1.json`

- **Werkzeuge:** `swisstopo_zoning_at`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=2683304.0346262627%2C1247925.5974930264&geometryType=esriGeometryPoint&layers=all%3Ach.are.bauzonen&mapExtent=0%2C0%2C100%2C100&imageDisplay=100%2C100%2C96&tolerance=0&sr=2056&lang=de&returnGeometry=false`
- **Auswahl:** ungekuerzt
- **Groesse:** 456 Bytes
- **SHA-256:** `5ca88cb5bb640171bdaae2560f4d9d657d8c550f1d764af59b3b4ac6607d0081`
