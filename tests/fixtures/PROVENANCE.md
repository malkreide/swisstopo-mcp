# Herkunft der Fixtures

Aufgezeichnet am **2026-10-28** mit `python scripts/record_fixtures.py`.

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
- **SHA-256:** `c89fe007c1a4a57cd3f7cbaaa8e18c3870d74265bc9eeb4c1f24ae62776287dc`

## `get_collection_1.json`

- **Werkzeuge:** `swisstopo_get_collection`
- **Schluessel:** `https://data.geo.admin.ch/api/stac/v0.9/collections/ch.swisstopo.swissalti3d`
- **Auswahl:** 20 von 22 Listeneintraegen (je Liste die ersten 5), aus 1624 Bytes Rohantwort
- **Groesse:** 1837 Bytes
- **SHA-256:** `dd6d75a7133b46bab59dbf5fdea81b70bf141d7f886e8fa01e5d5da26cd24678`

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
- **Auswahl:** 145 von 1342 Listeneintraegen (je Liste die ersten 5), aus 3519730 Bytes Rohantwort
- **Groesse:** 26452 Bytes
- **SHA-256:** `6ffc04fd277bfff4c4166213b981eba0b3d8cdd67cd08e563cca44e2c0179baa`

## `lookup_postal_code_1.json`

- **Werkzeuge:** `lookup_postal_code_tool`
- **Schluessel:** `https://openplzapi.org/ch/Localities?postalCode=8001`
- **Auswahl:** ungekuerzt
- **Groesse:** 354 Bytes
- **SHA-256:** `cadb109dcb21829dfa214044f06abb3a83968e92f518b0a1eb5e0cbae005c4f5`

## `map_query_features_at_point_1.json`

- **Werkzeuge:** `swisstopo_map_query`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=8.5417%2C47.3769&geometryType=esriGeometryPoint&layers=all%3Ach.bfs.gebaeude_wohnungs_register&tolerance=10&sr=4326&returnGeometry=false&mapExtent=8.5317%2C47.3669%2C8.5517%2C47.3869&imageDisplay=100%2C100%2C96`
- **Auswahl:** 25 von 164 Listeneintraegen (je Liste die ersten 5), aus 235627 Bytes Rohantwort
- **Groesse:** 11646 Bytes
- **SHA-256:** `718b584525834ca00207bef7ddb82e80fbbf26ea3836badf4a5addf2a77c483e`

## `map_query_layer_info_1.json`

- **Werkzeuge:** `swisstopo_map_query`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/api/MapServer/ch.bfs.gebaeude_wohnungs_register`
- **Auswahl:** 25 von 99 Listeneintraegen (je Liste die ersten 5), aus 9804 Bytes Rohantwort
- **Groesse:** 1118 Bytes
- **SHA-256:** `fab6b56aa402e27177e11c0010825c3e06a245db11820b3396c5da43f0796429`

## `map_query_layer_info_2.txt`

- **Werkzeuge:** `swisstopo_map_query`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/all/MapServer/ch.bfs.gebaeude_wohnungs_register/legend?lang=de`
- **Auswahl:** ungekuerzt
- **Groesse:** 2194 Bytes
- **SHA-256:** `b7ab1a7f216723a9636cdeda0e328ccdb8fe9706095e6ed9a69578627ea3fabf`

## `map_query_search_layers_1.json`

- **Werkzeuge:** `swisstopo_map_query`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/SearchServer?type=layers&searchText=Geb%C3%A4ude&lang=de&limit=10`
- **Auswahl:** 5 von 10 Listeneintraegen (je Liste die ersten 5), aus 16000 Bytes Rohantwort
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
- **Auswahl:** 285 von 351 Listeneintraegen (je Liste die ersten 5), aus 81330 Bytes Rohantwort
- **Groesse:** 77081 Bytes
- **SHA-256:** `cebd0742118c1123affc4204a4fb14bf6944afe157ab766402b17c0691dcaabb`

## `query_geodata_oereb_1.json`

- **Werkzeuge:** `query_geodata_tool`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/all/MapServer/identify?geometryType=esriGeometryPoint&geometry=2683304.0%2C1247925.6&sr=2056&tolerance=0&layers=all%3Ach.swisstopo-vd.stand-oerebkataster&mapExtent=2683254.0%2C1247875.6%2C2683354.0%2C1247975.6&imageDisplay=100%2C100%2C96&returnGeometry=false&lang=de`
- **Auswahl:** ungekuerzt
- **Groesse:** 2714 Bytes
- **SHA-256:** `477289986f7e39f96d62f3a3cb69dff8d35e7118bdce758d6aaed475074fc839`

## `query_geodata_strassen_1.json`

- **Werkzeuge:** `query_geodata_tool`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/api/MapServer/identify?geometryType=esriGeometryPoint&geometry=2683304.0%2C1247925.6&sr=2056&tolerance=15&layers=all%3Ach.swisstopo.amtliches-strassenverzeichnis&mapExtent=2682304.0%2C1246925.6%2C2684304.0%2C1248925.6&imageDisplay=200%2C200%2C96&returnGeometry=false&lang=de`
- **Auswahl:** 5 von 13 Listeneintraegen (je Liste die ersten 5), aus 6037 Bytes Rohantwort
- **Groesse:** 3006 Bytes
- **SHA-256:** `71590ddec2e5bd7acbce1dbda7c302453b6a0ff3cf3c2d1c02c641acc68597cd`

## `query_osm_1.json`

- **Werkzeuge:** `query_osm_features_tool`
- **Schluessel:** `https://overpass.osm.ch/api/interpreter#97a61bbc7858`
- **Rumpf:** `data=[out:json][timeout:25];(node["amenity"="pharmacy"](around:500,47.3769,8.5417);way["amenity"="pharmacy"](around:500,47.3769,8.5417);relation["amenity"="pharmacy"](around:500,47.3769,8.5417););out center tags 50;`
- **Auswahl:** 5 von 11 Listeneintraegen (je Liste die ersten 5), aus 7403 Bytes Rohantwort
- **Groesse:** 4124 Bytes
- **SHA-256:** `35a5788fc77f85a08116cbf5e8d33f3be37f9a5125ff66ec84101820f9944aac`

## `reverse_geocode_1.json`

- **Werkzeuge:** `swisstopo_reverse_geocode`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/SearchServer?type=locations&origins=address&bbox=2682804.0346262627%2C1247425.5974930264%2C2683804.0346262627%2C1248425.5974930264&limit=5&sr=2056&returnGeometry=true`
- **Auswahl:** ungekuerzt
- **Groesse:** 5754 Bytes
- **SHA-256:** `c0d0d51c475162dda4bcc6ab490fed6115c24b4364e3943de8055305aacda215`

## `search_address_1.json`

- **Werkzeuge:** `search_address_tool`
- **Schluessel:** `https://openplzapi.org/ch/FullTextSearch?searchTerm=Bahnhofplatz+8001&page=1&pageSize=20`
- **Auswahl:** ungekuerzt
- **Groesse:** 431 Bytes
- **SHA-256:** `e8f022c48c9fe68f7bcd4ea3c824ffae3c964f1660db43a51ee0e4ac1acedbc8`

## `search_geodata_1.json`

- **Werkzeuge:** `swisstopo_search_geodata`
- **Schluessel:** `https://data.geo.admin.ch/api/stac/v0.9/collections`
- **Auswahl:** 100 von 207 Listeneintraegen (je Liste die ersten 5), aus 245347 Bytes Rohantwort
- **Groesse:** 21786 Bytes
- **SHA-256:** `206ab3230170ecb51227f7607496f490a5b9528fda3e03eec5324346d4172c9d`

## `zoning_at_1.json`

- **Werkzeuge:** `swisstopo_zoning_at`
- **Schluessel:** `https://api3.geo.admin.ch/rest/services/ech/MapServer/identify?geometry=2683304.0346262627%2C1247925.5974930264&geometryType=esriGeometryPoint&layers=all%3Ach.are.bauzonen&mapExtent=0%2C0%2C100%2C100&imageDisplay=100%2C100%2C96&tolerance=0&sr=2056&lang=de&returnGeometry=false`
- **Auswahl:** ungekuerzt
- **Groesse:** 456 Bytes
- **SHA-256:** `5ca88cb5bb640171bdaae2560f4d9d657d8c550f1d764af59b3b4ac6607d0081`
