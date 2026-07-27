## Finding: SEC-018 — Input-Validation an Tool-Boundaries (Pydantic strict / Zod)

**Severity:** high
**Status:** closed
**Server:** swisstopo-mcp
**Check-Reference:** SEC-018
**PDF-Reference:** Sec 3 / Sec 4 (Defense-in-Depth)

### Observed Behavior
The tool boundary itself is strict and this was verified at runtime, not only by grep. All 23 tools take a single Pydantic model parameter, and every one of those models declares `model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)` — `geocoding.py:19` and `:41`, `rest_api.py:40`, `:54`, `:75`, `:84`, `:92`, `:96`, `:100`, `stac.py:19` and `:32`, `wmts.py:29`, `height.py:28` and `:42`, `oereb.py:49` and `:61`, `coords.py:181`, `geodata.py:158` and `:199`, `openplz.py:247`, `:257`, `:304`. Whitelist patterns are centralised and positively anchored (`src/swisstopo_mcp/api_client.py:39-43`).

Three deviations keep this off pass:

1. **The shared `SwissPointInput` base model declares no `model_config`** (`src/swisstopo_mcp/coords.py:77-108`). Runtime-verified: `SwissPointInput(lat=47.0, lon=8.0, evil="x")` is accepted, `SwissPointInput(lat="47.0", lon="8.0")` coerces strings to floats, and `SwissPointInput.model_config == {}`. The tool surface is safe today only because all five subclasses re-declare the config (`height.py:28`, `rest_api.py:54`, `:92`, `:96`, `oereb.py:49`).
2. **Three `sr` arguments are unbounded integers forwarded into upstream query params.** `sr: int = Field(default=4326, ...)` with no `ge`/`le`, no `Literal` and no validator at `geocoding.py:36` (GeocodeInput), `geocoding.py:46` (ReverseGeocodeInput) and `rest_api.py:89` (GetFeatureInput); the values reach the upstream request at `geocoding.py:95`, `geocoding.py:132` and `rest_api.py:368`. The helper written for exactly this, `validate_sr()` at `api_client.py:345-352`, is dead code — no call site anywhere in `src/`. By contrast `HeightInput`, `ElevationProfileInput` and `IdentifyInput` do guard `sr` via `check_deprecated_sr` (`height.py:37`, `height.py:71`, `rest_api.py:70`).
3. **Several string fields have no `max_length`.** `IdentifyInput.layers` (`rest_api.py:56-61`) and `FindFeaturesInput.layer` / `search_field` (`rest_api.py:78`, `:80`) carry `min_length` and a pattern but no upper bound, so an arbitrarily long comma-separated layer string passes validation into the upstream query string.

### Expected Behavior
- All tool arguments have schema validation
- Numeric fields carry `ge`/`le` constraints — no unbounded range
- String fields carry `min_length`/`max_length` and ideally a `pattern`
- Patterns are whitelist-based, not blacklist-based
- With Pydantic: `strict=True` and `extra="forbid"` set explicitly
- Validation errors surface as `isError` in the tool result, not as a server crash
- Tests cover edge cases: over-long strings, out-of-range numbers, unknown fields

### Evidence
- Strict config on every tool-boundary model: `geocoding.py:19`, `:41`, `rest_api.py:40`, `:54`, `:75`, `:84`, `:92`, `:96`, `:100`, `stac.py:19`, `:32`, `wmts.py:29`, `height.py:28`, `:42`, `oereb.py:49`, `:61`, `coords.py:181`, `geodata.py:158`, `:199`, `openplz.py:247`, `:257`, `:304`
- Runtime-verified against the installed package: `HeightInput(lat=47.0, lon=8.0, evil='x')` rejected; `HeightInput(lat='47.0', lon='8.0')` rejected; `IdentifyInput(..., evil=1)` rejected; `ConvertCoordinatesInput(easting='8.5', northing='47.4')` rejected
- Centralised whitelist patterns: `src/swisstopo_mcp/api_client.py:39-43` (TEXT_PATTERN, ID_PATTERN, COORDS_PATTERN, LANG_PATTERN, CANTON_PATTERN), applied at `geocoding.py:21-27`, `rest_api.py:42-48`, `rest_api.py:78-81`, `oereb.py:63-73`, `height.py:44-52`
- `ConvertCoordinatesInput` is well bounded: `coords.py:181` plus the range/axis-swap validator at `coords.py:202-227` against `coords.py:48-49`
- Missing config on the shared base: `src/swisstopo_mcp/coords.py:77-108`; runtime-verified `SwissPointInput(lat=47.0, lon=8.0, evil='x')` ACCEPTED and `SwissPointInput.model_config == {}`
- Unbounded `sr`: `geocoding.py:36`, `geocoding.py:46`, `rest_api.py:89`; reaching upstream at `geocoding.py:95`, `geocoding.py:132`, `rest_api.py:368`; unused validator at `api_client.py:345-352`
- Missing `max_length`: `rest_api.py:56-61`, `rest_api.py:78`, `rest_api.py:80`

Gaps:
- `SwissPointInput` (`coords.py:77`) omits `strict=True` / `extra="forbid"`; protection depends entirely on each subclass repeating it
- `GeocodeInput.sr`, `ReverseGeocodeInput.sr` and `GetFeatureInput.sr` are unconstrained ints passed to the upstream API; `validate_sr()` exists but is never called
- Several string fields lack `max_length` (`rest_api.py:56`, `:78`, `:80`)
- `tests/test_input_validation.py` covers patterns, strict mode and extra-field rejection for `GeocodeInput` / `GetFeatureInput` / `GetOerebExtractInput` but has no case asserting `SwissPointInput`'s own config, which is why the omission survived

### Risk Description
No tool is exposed through `SwissPointInput` directly today, so this is a latent regression rather than a live hole — but it is the exact failure mode the check calls out. The next point-based tool added to this server inherits from `SwissPointInput`, and if its author assumes the base class carries the strict config (a reasonable assumption for a shared base model), that tool silently ships with `extra="ignore"` and type coercion. Silent coercion of LLM-supplied strings to floats is the specific case that matters here: an LLM emitting `"47.0"` instead of `47.0` for a coordinate would be accepted rather than corrected, and the coercion has no range awareness — the coordinate-validation logic added at `coords.py:202-227` lives on a sibling model, not on the base.

The unbounded `sr` fields let the LLM forward an arbitrary integer into three upstream geo.admin.ch query strings. The upstream rejects unknown spatial-reference codes, so this is a garbage-in-error-out path rather than an injection vector — but it produces an upstream 4xx surfaced as a tool error instead of a clean local validation message, and it means the `sr=2056` correctness guard that three other tools apply is absent on these three. A purpose-built validator sits unused two files away, so the cost of not fixing this is unusually low-value.

The missing `max_length` on layer strings lets a very long comma-separated value reach the upstream URL. The practical outcome is an upstream 414 or a slow request, not a bypass — but it is unbounded input crossing a trust boundary, which the check requires bounding.

### Remediation
1. In `src/swisstopo_mcp/coords.py`, add the config to the shared base at line 77 so subclasses inherit it rather than each re-declaring it:

```python
class SwissPointInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)
    lat: float = Field(...)
    lon: float = Field(...)
```

The five subclasses (`height.py:28`, `rest_api.py:54`, `:92`, `:96`, `oereb.py:49`) can keep their declarations — Pydantic merges them — but the base must no longer depend on them.

2. Wire up the dead validator. In `geocoding.py:36`, `geocoding.py:46` and `rest_api.py:89`, replace the bare `sr: int = Field(default=4326, ...)` with a constrained field plus the existing helper:

```python
sr: int = Field(default=4326, description="...")

@field_validator("sr")
@classmethod
def _check_sr(cls, v: int) -> int:
    return validate_sr(v)   # api_client.py:345
```

Alternatively use `Literal[2056, 4326, 21781, 3857]` if the accepted set is genuinely closed — but then delete `validate_sr()` rather than leaving it dead.

3. Add `max_length` to `rest_api.py:56-61` (`layers`), `rest_api.py:78` (`layer`) and `rest_api.py:80` (`search_field`). A bound of 512 for the comma-separated `layers` and 128 for the two single-value fields is generous relative to real layer IDs.
4. Extend `tests/test_input_validation.py` with a case that asserts `SwissPointInput.model_config` contains `extra == "forbid"` and `strict is True`, and a case per fixed `sr` field asserting an out-of-set value raises. The base-model case is the one that would have caught this; add it so the next refactor does not reintroduce the gap.

All four items are one-line-to-few-line changes in files that already have the surrounding patterns in place.

### Effort Estimate
S (<1d)

---

### Remediation Status (2026-07-27, same PR as the audit)

**Partially closed.** The missing `model_config` on `SwissPointInput` was added
(`src/swisstopo_mcp/coords.py`), so the base class now enforces
`extra="forbid"` + `strict=True` instead of relying on every subclass to
re-declare it. Three regression tests cover it, including a subclass that
declares no config of its own.

**Still open:** `sr` remains an unbounded `int` on three models, and
`validate_sr()` in `api_client.py` remains dead code. Those predate this
change and are left for a dedicated remediation pass.

---

### Remediation Status (2026-07-27, follow-up PR)

**Now fully closed.** The base-model gap was fixed earlier; this pass closes the
remainder. `validate_sr()` is no longer dead code — it is wired into the three
`sr` fields via `field_validator`, so an arbitrary int is rejected instead of
being forwarded upstream. `max_length` bounds were added to `layers` (512),
`layer`, `search_field` and `feature_id` (128). 11 tests added, including the
base-model config assertions that would have caught the original gap.
