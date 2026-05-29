# Network Egress Policy

`swisstopo-mcp` only ever talks to a small, fixed set of Swiss federal and
cantonal geodata hosts. This is enforced at the code layer by an explicit
allow-list (audit check **SEC-021**) and complements the SSRF hardening from
**SEC-004 / SEC-005** (HTTPS-only upstreams, `follow_redirects=False`).

## Allowed hosts

| Host | Purpose | Tools |
|---|---|---|
| `api3.geo.admin.ch` | REST (SearchServer/MapServer), Geocoding, Height | search_layers, identify_features, find_features, get_feature, geocode, reverse_geocode, get_height, elevation_profile |
| `data.geo.admin.ch` | STAC catalog | search_geodata, get_collection |
| `wmts.geo.admin.ch` | WMTS tiles | (map references) |
| `map.geo.admin.ch` | Shareable map viewer URLs | map_url |
| `oereb.geo.zh.ch` | OEREB cadastre — canton ZH | get_egrid, get_oereb_extract |
| `www.oereb2.apps.be.ch` | OEREB cadastre — canton BE | get_egrid, get_oereb_extract |

## Enforcement

- **Code layer:** `ALLOWED_HOSTS` is a `frozenset` in
  [`src/swisstopo_mcp/api_client.py`](../src/swisstopo_mcp/api_client.py). It is
  **not** loaded from an environment variable, so it cannot be silently widened
  at runtime. `assert_host_allowed(url)` is called before every outbound request
  in `geo_admin_request`, `stac_request`, and the OEREB handlers; a non-allowed
  host raises `PermissionError`.
- **Redirects:** the shared `httpx.AsyncClient` uses `follow_redirects=False`,
  so an upstream cannot redirect a request to an off-list host.
- **Network layer (deployment):** the server runs locally over stdio today and
  is not cloud-deployed, so no Kubernetes `NetworkPolicy` / security-group egress
  rule is shipped. If/when the server is containerised, add a network-layer
  egress allow-list mirroring the hosts above (and allow DNS/UDP 53), per the
  SEC-021 pattern.

## Update procedure

Adding a new allowed host (e.g. a new cantonal OEREB endpoint) requires:

1. Add the canton endpoint to `OEREB_ENDPOINTS` in
   [`src/swisstopo_mcp/oereb.py`](../src/swisstopo_mcp/oereb.py) (for OEREB hosts).
2. Add the hostname to `ALLOWED_HOSTS` in `api_client.py`.
3. Add a row to the table above.
4. Add/extend the network-layer egress rule (only relevant for cloud deployment).
5. Open a PR with a justification and a CHANGELOG entry.
