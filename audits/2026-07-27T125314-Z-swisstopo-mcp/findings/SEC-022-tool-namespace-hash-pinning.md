## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

**Severity:** high
**Status:** closed
**Server:** swisstopo-mcp
**Check-Reference:** SEC-022
**PDF-Reference:** Anhang B4

### Observed Behavior
Namespace prefixing is inconsistent across the 23-tool surface. 17 tools carry the `swisstopo_` server prefix (`src/swisstopo_mcp/server.py:88`, `108`, `145`, `165`, `186`, `207`, `235`, `256`, `279`, `307`, `328`, `349`, `372`, `394`, `423`, `456`, `475`) while 6 do not: `list_available_layers` (`server.py:504`), `query_geodata` (`server.py:525`), `query_osm_features` (`server.py:552`), `lookup_postal_code` (`server.py:586`), `find_commune` (`server.py:609`) and `search_address` (`server.py:636`).

Those 6 are exactly the collision-prone generic form the check's fail pattern describes. `search_address`, `find_commune`, `query_geodata` and `lookup_postal_code` are names any other Swiss-data MCP server in this portfolio could plausibly register — and the server's own instructions text tells the model it sits alongside swiss-statistics-mcp and zurich-opendata-mcp (`src/swisstopo_mcp/server.py:70-74`), i.e. the multi-server aggregation scenario where shadowing bites.

The unprefixed set grew in the two most recent feature releases rather than shrinking: the geodata façade tools were added at `CHANGELOG.md:131-152` and the three OpenPLZ tools at `CHANGELOG.md:80-107`, both without a prefix, while every tool added in the same period under the swisstopo API families kept it (`CHANGELOG.md:11-23`).

No tool-definition hash snapshot exists. `tool-hashes.json` is absent from the repo root and neither `.github/workflows/publish.yml` nor `.github/workflows/ci.yml` contains a hash / sha256 / tool-snapshot step, so rug-pull detection by a host against a published baseline is not possible.

Two criteria are partly served. `CHANGELOG.md` does name tool-definition changes explicitly and in detail — new tools with rationale (`CHANGELOG.md:11-23`, `:33-44`, `:45-57`), a Changed entry explaining what was deliberately not altered (`:59-66`), and a Fixed entry describing the `sr` input-contract change that alters existing tool schemas (`:68-75`). Versioning is coherent: `pyproject.toml:8` and `server.json:5` both read `0.2.0` (the earlier mismatch is recorded as fixed at `CHANGELOG.md:76-77`).

### Expected Behavior
- All tools carry a namespace prefix with the server identity
- The server-identity prefix is consistent across all tools and not config-mutable
- At release, a hash snapshot of the tool definitions is generated and stored in the repo
- CHANGELOG entries name tool-definition changes explicitly
- Tool-description changes carry a user re-approval note in the CHANGELOG
- Breaking tool changes trigger a major version bump

### Evidence
- Prefixed tools (17): `src/swisstopo_mcp/server.py:88`, `108`, `145`, `165`, `186`, `207`, `235`, `256`, `279`, `307`, `328`, `349`, `372`, `394`, `423`, `456`, `475`
- Unprefixed tools (6): `src/swisstopo_mcp/server.py:504` (`list_available_layers`), `:525` (`query_geodata`), `:552` (`query_osm_features`), `:586` (`lookup_postal_code`), `:609` (`find_commune`), `:636` (`search_address`)
- Multi-server aggregation context stated in the server's own instructions: `src/swisstopo_mcp/server.py:70-74`
- Unprefixed set introduced in recent releases: `CHANGELOG.md:131-152` (geodata façade), `CHANGELOG.md:80-107` (OpenPLZ); prefixed additions in the same period: `CHANGELOG.md:11-23`
- No hash snapshot: `tool-hashes.json` absent from the repo root; no hash / sha256 / tool-snapshot step in `.github/workflows/publish.yml` or `.github/workflows/ci.yml`
- CHANGELOG discipline (partial credit): `CHANGELOG.md:11-23`, `:33-44`, `:45-57`, `:59-66`, `:68-75`
- Version coherence (partial credit): `pyproject.toml:8`, `server.json:5`, both `0.2.0`; mismatch fix recorded at `CHANGELOG.md:76-77`

Gaps:
- 6 of 23 tools have no server-identity prefix (`server.py:504`, `525`, `552`, `586`, `609`, `636`) — Pass-Criteria 1 and 2 unmet
- No hash snapshot of tool definitions is generated at release and none is stored in the repo — Pass-Criterion 3 unmet
- CHANGELOG entries carry no per-tool hashes and no "re-approval needed in Claude Desktop" note for the `sr` contract change — Pass-Criterion 5 unmet
- The `sr=2056` fix (`CHANGELOG.md:68-75`) narrows an accepted input value on three existing tools — a breaking change to the tool contract — yet shipped inside a minor bump rather than a major — Pass-Criterion 6 arguably unmet

### Risk Description
The check's headline control is a consistent server-identity prefix that makes cross-server shadowing structurally impossible. On 6 of 23 tools it is objectively broken, and the server's own instructions confirm it runs alongside sibling Swiss-data servers. If any of those registers a `search_address` or `find_commune` of its own, the host resolves one name to two definitions. Which server wins depends on host-side load order, so the LLM may silently route a Swiss address lookup to a different server's tool — or a malicious server added to a user's config can deliberately register `search_address` to intercept queries intended for this one. The user sees a plausible answer and has no signal that the source changed. This is not hypothetical for a portfolio whose servers all cover overlapping Swiss geodata.

The missing hash snapshot removes the other half of the defence. Without a published baseline of tool names, descriptions and schemas per release, a host has no way to detect that a tool definition changed between the version the user approved and the version now being served — the rug-pull scenario the check exists for. The `sr` contract change at `CHANGELOG.md:68-75` is a concrete instance: it narrowed an accepted input value on three existing tools, changing what a previously approved tool accepts, and shipped with no re-approval note and no version signal that a contract moved.

### Remediation
1. **Rename the 6 unprefixed tools** in `src/swisstopo_mcp/server.py` to `swisstopo_list_available_layers` (`:504`), `swisstopo_query_geodata` (`:525`), `swisstopo_query_osm_features` (`:552`), `swisstopo_lookup_postal_code` (`:586`), `swisstopo_find_commune` (`:609`) and `swisstopo_search_address` (`:636`).

   Anticipate the objection: those 6 are the deliberately source-neutral façade tools (OSM, OpenPLZ, geodienste — not swisstopo data), so `swisstopo_` reads as a misnomer. The resolution is that the prefix denotes the *server* identity, not the data source, which is what makes it a shadowing defence. If the misnomer is unacceptable, rename the whole surface to a neutral server-identity prefix — but do not leave it mixed.

   This is a breaking change for anyone who has these tool names in a prompt or a client config. Ship it as a major bump (`0.2.0` → `1.0.0` or `0.3.0` with an explicit breaking note in both `pyproject.toml:8` and `server.json:5`), with a CHANGELOG entry listing old → new names and a "re-approval required in Claude Desktop" line.

2. **Add a hash-snapshot step** to `.github/workflows/publish.yml` that dumps the tool manifest and hashes each definition, writing `tool-hashes.json` to the repo root and attaching it to the release:

```python
# scripts/snapshot_tool_hashes.py
import hashlib, json
from swisstopo_mcp.server import mcp

tools = {
    t.name: hashlib.sha256(
        json.dumps(
            {"name": t.name, "description": t.description, "schema": t.inputSchema},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    for t in await mcp.list_tools()
}
json.dump(dict(sorted(tools.items())), open("tool-hashes.json", "w"), indent=2)
```

   Add a CI check in `.github/workflows/ci.yml` that regenerates the file and fails if it differs from the committed one without a CHANGELOG entry — this makes any unannounced tool-definition change visible in review.

3. **Extend the CHANGELOG convention** so tool-definition changes carry the affected tool names, the new hash, and a re-approval note. Retroactively add the re-approval note to the `sr` entry at `CHANGELOG.md:68-75`.
4. **Adopt a semver rule** in `CONTRIBUTING.md`: any change to a tool's name, description or input schema that narrows or renames is a major bump. The `sr` change is the precedent to cite.

Rename and hash-snapshot should ride the same major release so users re-approve once.

### Effort Estimate
M (1-3d)

---

### Remediation Status (2026-07-27, follow-up PR)

**Closed.** All six unprefixed tools were renamed to `swisstopo_*`, shipped as
a breaking `0.3.0` with the old → new table and a re-approval note in the
CHANGELOG. All 23 tools now carry the prefix; a test asserts it and asserts the
old names are gone, so a 0.3.0 client cannot silently reach one.

The hash snapshot is in place: `scripts/snapshot_tool_hashes.py` writes a
SHA-256 per tool over name + description + input schema to `tool-hashes.json`,
and a CI step runs it with `--check` so a stale snapshot fails the build.

The semver rule is recorded in `CONTRIBUTING.md` / `CONTRIBUTING.de.md`, citing
the `sr` narrowing and these renames as precedent; the `sr` CHANGELOG entry was
retroactively given its re-approval note.

The misnomer objection the finding anticipated is accepted rather than dodged:
the façade and OpenPLZ tools serve non-swisstopo data, but a mixed surface is
worse than a consistent, imprecise one. Recorded in the CHANGELOG.
