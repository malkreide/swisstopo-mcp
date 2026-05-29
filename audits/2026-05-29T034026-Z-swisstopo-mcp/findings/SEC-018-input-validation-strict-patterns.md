## Finding: SEC-018 — Input-Validation an Tool-Boundaries (Pydantic strict / Zod)

**Severity:** high
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** SEC-018
**PDF-Reference:** Sec 3 / Sec 4 (Defense-in-Depth)
**Check-Status:** partial

### Observed Behavior
All inputs are Pydantic v2 models with extra='forbid' and ge/le + min/max bounds. Missing strict=True and whitelist patterns on free-text fields.

### Expected Behavior
strict=True to stop coercion; whitelist 'pattern' on free-text args.

### Evidence
- All tool inputs are Pydantic models with extra='forbid' (geocoding/rest_api/stac/height/oereb)
- Numeric ranges bounded (ge/le): limit 1-50, lat 45.8-47.9, lon 5.9-10.5, zoom 1-13, tolerance 0-200
- String fields bounded: min_length/max_length (e.g. search_text 2-200)

Gaps:
- model_config does not set strict=True — Pydantic coercion is allowed ('1' -> 1)
- Free-text fields (search_text, layer, search_field, topics) have no whitelist 'pattern' constraint

### Risk Description
Type coercion can mask bugs; unconstrained free-text widens the injection/encoding surface (low given downstream is HTTP query params).

### Remediation
Add strict=True to each model_config and add conservative regex patterns to search_text/layer/search_field/topics.

### Effort Estimate
S (<1d)
