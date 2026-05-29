## Finding: ARCH-003 — «Not Found» Anti-Pattern: Heuristiken statt leerer Antworten

**Severity:** medium
**Status:** open
**Server:** swisstopo-mcp
**Check-Reference:** ARCH-003
**PDF-Reference:** Sec 2.2
**Check-Status:** partial

### Observed Behavior
geocoding returns the bare string 'Keine Ergebnisse gefunden.'; no match_type or suggestions.

### Expected Behavior
Empty results should carry match_type and an actionable note (term refinement or fuzzy suggestions).

### Evidence
- OEREB tools return actionable 'not found' messages with next steps (oereb.py:84-88, 124-125)

Gaps:
- Geocoding returns the bare string 'Keine Ergebnisse gefunden.' (geocoding.py:53) — classic empty-result anti-pattern
- No match_type field and no fuzzy/suggestion fallback for empty results

### Risk Description
Bare 'no results' encourages LLM hallucination or premature abort.

### Remediation
Return a structured note with match_type=none and a hint (e.g. suggest broadening the query or checking spelling) for empty geocode/search results.

### Effort Estimate
S (<1d)
