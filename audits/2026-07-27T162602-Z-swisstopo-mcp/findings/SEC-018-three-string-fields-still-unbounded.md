## Finding: SEC-018 — Input-Validation an Tool-Boundaries (Pydantic strict / Zod)

**Severity:** high
**Status:** partial
**Server:** swisstopo-mcp
**Check-Reference:** SEC-018
**PDF-Reference:** Sec 3 / Sec 4 (Defense-in-Depth)
**Run:** 2026-07-27T162602-Z (re-audit)

### Observed Behavior
Verified by runtime introspection of all 24 input models rather than by sampling.
Every model carries `ConfigDict(str_strip_whitespace=True, extra="forbid",
strict=True)`, including the `SwissPointInput` base (`coords.py:90`) so a future
subclass cannot regress. Every integer field has both bounds. `validate_sr()` is wired
at three sites and the other three `sr` fields are guarded by something stricter
(`check_deprecated_sr`, which rejects anything but 4326). `easting`/`northing` look
unbounded but are not — the model validator at `coords.py:140-156` enforces the LV95
Swiss extent. Patterns are whitelist-based throughout.

One claim overreaches. Three string fields have no `max_length`: `stac.py:34-39`
`collection_id` (min_length and a pattern, but no ceiling — and it is interpolated
straight into a URL path at `stac.py:174`), `geocoding.py:32-39` `origins`, and
`wmts.py:34-38` `layers`. A pattern constrains the charset, not the size.

### Expected Behavior
- Length bounds on every string field

### Evidence
- Checked every input model by runtime introspection, not by sampling: all 24 Pydantic models across geocoding/rest_api/stac/wmts/height/coords/oereb/geodata/overpass/openplz carry `model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)`. Not one is permissive. The base SwissPointInput declares it too (src/swisstopo_mcp/coords.py:90) so a future subclass that forgets cannot regress.
- Every integer field has both bounds. Enumerated: limit ge=1/le=50 (src/swisstopo_mcp/geocoding.py:50), le=10, le=30, le=100; tolerance ge=0/le=200 (src/swisstopo_mcp/rest_api.py:66); nb_points ge=2/le=1000 (src/swisstopo_mcp/height.py:58-63); radius_m ge=10/le=5000; zoom ge=1/le=13; bfs_number ge=1/le=9999. No unbounded int.
- validate_sr() is genuinely wired up now, at three sites: src/swisstopo_mcp/geocoding.py:43-48, src/swisstopo_mcp/geocoding.py:61-66 and src/swisstopo_mcp/rest_api.py:102-105. The remaining three `sr` fields are guarded by something stricter — check_deprecated_sr (src/swisstopo_mcp/coords.py:57-74) rejects anything but 4326 — at src/swisstopo_mcp/rest_api.py:72-75, src/swisstopo_mcp/height.py:35-38 and src/swisstopo_mcp/height.py:69-72. No `sr` reaches an upstream unvalidated.
- easting/northing look unbounded at field level but are not: the model validator at src/swisstopo_mcp/coords.py:140-156 rejects degree-magnitude values and enforces the LV95 Swiss extent (2 480 000–2 840 000 / 1 070 000–1 300 000), and src/swisstopo_mcp/coords.py:210-235 does the direction-aware equivalent for ConvertCoordinatesInput. The omission is deliberate and documented at src/swisstopo_mcp/coords.py:104-106.
- Patterns are whitelist-based throughout, defined centrally at src/swisstopo_mcp/api_client.py:43-47 (TEXT/ID/COORDS/LANG/CANTON) — all `^[...]+$` allow-lists, no negative lookahead. tests/test_input_validation.py:14-40 proves rejection of NUL bytes, angle brackets, quotes, backticks and `../../etc/passwd`; tests/test_input_validation.py:44-60 proves strict mode rejects "10" for an int and rejects extra fields.
- THE GAP the remediation overclaims: three string fields still have no max_length, so 'length bounds added' is not true across the board. src/swisstopo_mcp/stac.py:34-39 collection_id has min_length=2 and a pattern but no ceiling — and it is interpolated straight into a URL path at src/swisstopo_mcp/stac.py:174. src/swisstopo_mcp/geocoding.py:32-39 `origins` has a pattern but no length bound. src/swisstopo_mcp/wmts.py:34-38 `layers` has a pattern but no length bound. A pattern constrains the charset, not the size, so a multi-kilobyte value of legal characters passes validation and is forwarded upstream.

Gaps:
- src/swisstopo_mcp/stac.py:34-39 — collection_id: no max_length; value is interpolated into an upstream URL path.
- src/swisstopo_mcp/geocoding.py:32-39 — origins: no max_length.
- src/swisstopo_mcp/wmts.py:34-38 — layers: no max_length.
- TEXT_PATTERN (src/swisstopo_mcp/api_client.py:43) permits ';' '&' '/' '%'. Harmless here — no shell, no SQL, and values go through httpx param encoding — but it is a broader charset than the check's whitelist ideal implies.
- origins is documented as an enum of seven values (address/zipcode/gg25/...) but is validated only as a lowercase-alphanumeric-comma string; a Literal or explicit member check would be exact.

### Risk Description
A multi-kilobyte value of legal characters passes validation and is forwarded upstream.
`collection_id` is the sharp one because it lands in a URL path rather than a query
parameter — the failure mode is a malformed upstream request or an oversized URL
rejected at the edge, not injection, since the charset is already restricted. Low
severity, but the remediation note currently claims more than the code does.

### Remediation
1. Add `max_length` to the three fields: `collection_id` (say 128), `origins` (128),
   `layers` (512 — it is a comma-separated list).
2. Make `origins` a `Literal` over its seven documented values; it is documented as an
   enum but validated as a lowercase-alphanumeric-comma string.
3. `TEXT_PATTERN` (`api_client.py:43`) permits `;` `&` `/` `%`. Harmless here — no
   shell, no SQL, httpx encodes params — but worth a comment saying so deliberately.

### Effort Estimate
S (<1d)

### Relation to run `2026-07-27T125314-Z`
Recorded as closed. Strict mode, extra-forbid, int bounds and sr validation all hold universally; the length-bounds claim does not.

### Auditor Notes
The brief asked me to check every input model rather than a sample, so I
introspected all 24 at runtime and enumerated every field's constraints.
The strict/extra-forbid claim holds universally, the int-bounds claim holds
universally, the validate_sr wiring claim holds (three direct sites plus a
stricter guard on the other three), and the easting/northing 'no bounds'
appearance is a false alarm — a model validator enforces the Swiss extent.
Downgraded to partial on one concrete, reproducible point: the claim that
length bounds were added does not hold for three string fields, one of
which (collection_id) lands directly in an upstream URL path. Small fix,
but the claim currently says more than the code does.

---

### Remediation Status (2026-07-28, follow-up PR)

**Closed.** The three named fields got a `max_length`: `collection_id` 128
(the sharp one — it is interpolated into an upstream URL *path*), `origins` 128,
`layers` 512 (a comma-separated list, so a generous bound, but a bound).

More usefully, the property is now enforced rather than the instances. A sweep
walks every `*Input` model across the ten tool modules, collects every field
whose annotation admits `str`, and fails if one has no `max_length`. It asserts
it found at least 20 models and 15 string fields first, so it cannot pass
vacuously.

**The sweep immediately found three fields this audit run did not name:**
`ListLayersInput.source`, `LookupPostalCodeInput.postal_code` and
`FindCommuneInput.district`. All three turned out to be genuinely bounded — by
anchored fixed-width patterns (`^(swisstopo|geodienste|oereb)$`, `^\d{4}$`,
`^\d{1,4}$`) rather than by `max_length` — so they are exempt. But the
exemption is checked, not merely declared: a second test asserts every exempt
field has an anchored pattern with no unbounded quantifier. Adding
`search_text` to the exempt set to test that guard produced
*"pattern has an unbounded quantifier — add max_length instead"*.

Both directions verified against deliberate defects: removing `max_length` from
`collection_id` named the field, and the bogus exemption was rejected.

Also from the gap list:

- **`origins` is now an actual enum.** The description promised seven values
  while the pattern accepted any lowercase-alphanumeric-comma string. A
  `Literal` cannot express a comma-separated list, so a `field_validator`
  checks each member against `ORIGINS` and the error names the allowed set.
- **`TEXT_PATTERN`'s charset is now documented as deliberate.** It admits
  `;` `&` `/` `%` because real Swiss addresses contain them
  ("Rue de l'Hôpital 3/5"). The comment states the conditions that make that
  safe — no shell, no SQL, httpx does the parameter encoding — so that a future
  tool building a command by interpolation is visibly out of contract rather
  than silently covered.

Ten tests added. The `origins` validator changes a tool's input schema, so
`tool-hashes.json` was regenerated.
