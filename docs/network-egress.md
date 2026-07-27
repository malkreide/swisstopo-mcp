# Network Egress Policy

`swisstopo-mcp` only ever talks to a small, fixed set of Swiss federal and
cantonal geodata hosts. This is enforced at the code layer by an explicit
allow-list (audit check **SEC-021**) and complements the SSRF hardening from
**SEC-004 / SEC-005** (HTTPS-only upstreams, `follow_redirects=False`).

## Allowed hosts

| Host | Purpose | Tools |
|---|---|---|
| `api3.geo.admin.ch` | REST (SearchServer/MapServer), Geocoding, Height | swisstopo_search_layers, swisstopo_identify_features, swisstopo_find_features, swisstopo_get_feature, swisstopo_geocode, swisstopo_reverse_geocode, swisstopo_get_height, swisstopo_elevation_profile |
| `geodesy.geo.admin.ch` | REFRAME — official LV95<->WGS84 coordinate transformation | swisstopo_convert_coordinates |
| `data.geo.admin.ch` | STAC catalog | swisstopo_search_geodata, swisstopo_get_collection |
| `wmts.geo.admin.ch` | WMTS tiles | (map references) |
| `map.geo.admin.ch` | Shareable map viewer URLs | swisstopo_map_url |
| `oereb.geo.zh.ch` | OEREB cadastre — canton ZH | swisstopo_get_egrid, swisstopo_get_oereb_extract |
| `www.oereb2.apps.be.ch` | OEREB cadastre — canton BE | swisstopo_get_egrid, swisstopo_get_oereb_extract |
| `geodienste.ch` | Interkantonale Basisgeodaten (services catalogue + WMS/WFS/OGC API Features) | swisstopo_list_available_layers, swisstopo_query_geodata |
| `overpass.osm.ch` | OpenStreetMap Overpass API (Swiss instance) — POI queries (ODbL) | swisstopo_query_osm_features |
| `openplzapi.org` | OpenPLZ API — administrative address level (BFS + swisstopo OGD) | swisstopo_lookup_postal_code, swisstopo_find_commune, swisstopo_search_address |

## Enforcement

- **Code layer:** `ALLOWED_HOSTS` is a `frozenset` in
  [`src/swisstopo_mcp/api_client.py`](../src/swisstopo_mcp/api_client.py). It is
  **not** loaded from an environment variable, so it cannot be silently widened
  at runtime. `assert_host_allowed(url)` is called before every outbound request
  in `geo_admin_request`, `stac_request`, `request_with_retry`, and the OEREB
  handlers; a non-allowed host raises `PermissionError`. The shared
  `request_with_retry` wrapper checks the host once before the first attempt.
- **Redirects:** the shared `httpx.AsyncClient` uses `follow_redirects=False`,
  so an upstream cannot redirect a request to an off-list host.
- **Network layer (deployment):** a Kubernetes `NetworkPolicy` **is** shipped, in
  [`deploy/kubernetes.yaml`](../deploy/kubernetes.yaml). Be precise about what it
  does: it blocks egress to private CIDR ranges and permits DNS, ports 80/443.
  It is a **CIDR and port restriction, not a per-host allow-list** — a
  NetworkPolicy cannot match on hostname, so it cannot mirror the table above.

  Closing that gap needs an egress proxy. The **ACL is now shipped** —
  [`deploy/smokescreen-acl.yaml`](../deploy/smokescreen-acl.yaml), generated from
  `ALLOWED_HOSTS` by `scripts/render_egress_acl.py` and checked in CI, so the
  network layer cannot drift from the code layer.

  The **deployment manifest is shipped too**:
  [`deploy/egress-proxy.yaml`](../deploy/egress-proxy.yaml) adds the Smokescreen
  sidecar, points the server at it via `HTTPS_PROXY`, and replaces the permissive
  NetworkPolicy with one that permits DNS plus proxied HTTPS only. Applying it is
  a deliberate operator step — see the apply order in that file's header — because
  it changes how every request leaves the pod.

  Until it is applied, the code-layer list remains the only per-host control, and
  it protects the process, not a compromised image.

- **DNS pinning (SEC-005):** available, off by default. `SWISSTOPO_PIN_DNS=true`
  makes the client connect to the address the SSRF guard vetted, keeping SNI and
  the Host header on the hostname so certificate validation is unaffected —
  verified against `api3.geo.admin.ch` and `geodesy.geo.admin.ch`, where the same
  connection *without* SNI fails with `IP address mismatch`.

  It is automatically inert behind a forward proxy, since the proxy resolves the
  name itself. Note that this makes pinning and the egress proxy above mutually
  exclusive by design: pick the proxy for a cluster deployment, pinning for a
  direct-egress one.

## Update procedure

Adding a new allowed host (e.g. a new cantonal OEREB endpoint) requires:

1. Add the canton endpoint to `OEREB_ENDPOINTS` in
   [`src/swisstopo_mcp/oereb.py`](../src/swisstopo_mcp/oereb.py) (for OEREB hosts).
2. Add the hostname to `ALLOWED_HOSTS` in `api_client.py`.
3. Add a row to the table above.
4. Add/extend the network-layer egress rule (applies to every deployment).
5. Open a PR with a justification and a CHANGELOG entry.
