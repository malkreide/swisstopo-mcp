# src/swisstopo_mcp/openplz.py
"""OpenPLZ API tools — the administrative address level (openplzapi.org/ch).

This module adds the layer that swisstopo geodata does *not* cover: the amtliche
administrative hierarchy **PLZ → Ort → Gemeinde → Bezirk → Kanton**. Its whole
point is the **BFS commune number** (``commune.key``): the official join key that
connects this server to ``swiss-statistics-mcp`` (BFS STAT-TAB) and
``zurich-opendata-mcp``. Every response that carries a commune therefore exposes
``bfs_commune_number`` as a named top-level field, never buried in a raw object.

Separate source, separate licence (see ``OPENPLZ_SOURCE`` / ``OPENPLZ_LICENSE``
in ``models.py``): the data are the official BFS municipal directory plus the
swisstopo street directory (both Swiss OGD, mandatory attribution), served
through the OpenPLZ API. Not to be conflated with the swisstopo geo.admin.ch OGD
attribution used by the other tools.

Architecture decision: **ARCH A (live-API-only)**. All required endpoints are
stable, fast and unauthenticated; no bulk dump is needed for a lookup connector.

Known findings from the live probe (2026-07-20) — see also CHANGELOG:

* **Abbreviation-vs-key trap:** path params are the numeric ``key``, not the
  canton abbreviation. ``/Cantons/ZH/Districts`` returns **HTTP 200 with ``[]``**,
  not an error. We resolve ``ZH`` → ``1`` server-side (via the authoritative
  ``/Cantons`` list) so users may write either, and an empty answer gets an
  explanatory ``note`` instead of silently reading as "does not exist".
* **Pagination cap:** list endpoints paginate with ``pageSize`` default 10 and a
  hard **maximum of 50** (``100`` → HTTP 400). Totals live in the
  ``x-total-count`` header. We iterate pages so ``find_commune`` returns *all*
  communes, not the first 10.
* **Empty ≠ absent:** an unknown PLZ (``?postalCode=9999``) also returns
  ``200 []``. Every empty result is reported with a note, never as bare nothing.
* **``historicalCode`` is not the join key:** for communes it differs from
  ``key`` (it is the historized-directory record id). The join key is the current
  ``key``; ``historicalCode`` is intentionally not surfaced as a top-level field.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from swisstopo_mcp.api_client import TEXT_PATTERN, handle_api_error, openplz_request
from swisstopo_mcp.logging_config import log_tool_call
from swisstopo_mcp.models import OPENPLZ_LICENSE, OPENPLZ_SOURCE, ToolResponse

# --- Pagination guards (live-probe finding: default 10, hard max 50) ----------
OPENPLZ_MAX_PAGE_SIZE = 50
OPENPLZ_MAX_RECORDS = 2000  # safety cap across paged fetches (largest canton ≪ this)

# --- BFS commune-number → canton block starts --------------------------------
#
# The OpenPLZ API has no endpoint to resolve a bare BFS commune number to its
# commune (no /Communes/{key}), and localities cannot be filtered by commune key.
# To resolve `bfs_number` we therefore derive the canton from the official BFS
# commune-number blocks — each canton owns a fixed, stable number range — then
# list that canton's communes and match the key exactly. The block starts below
# are the amtliche allocation (canton key in parentheses is the BFS canton
# number 1–26). This is a hint, not a source of truth: the result is verified
# against the live commune list, so a former/merged number simply degrades to an
# explanatory note rather than a wrong answer.
_CANTON_BFS_BLOCK_STARTS: tuple[tuple[int, str], ...] = (
    (1, "1"),      # ZH
    (301, "2"),    # BE
    (1001, "3"),   # LU
    (1201, "4"),   # UR
    (1301, "5"),   # SZ
    (1401, "6"),   # OW
    (1501, "7"),   # NW
    (1601, "8"),   # GL
    (1701, "9"),   # ZG
    (2001, "10"),  # FR
    (2401, "11"),  # SO
    (2701, "12"),  # BS
    (2761, "13"),  # BL
    (2901, "14"),  # SH
    (3001, "15"),  # AR
    (3101, "16"),  # AI
    (3201, "17"),  # SG
    (3501, "18"),  # GR
    (4001, "19"),  # AG
    (4401, "20"),  # TG
    (5001, "21"),  # TI
    (5401, "22"),  # VD
    (6001, "23"),  # VS
    (6401, "24"),  # NE
    (6601, "25"),  # GE
    (6701, "26"),  # JU
)


def _canton_key_for_bfs(bfs_number: int) -> str | None:
    """Return the canton key whose official BFS block contains ``bfs_number``."""
    chosen: str | None = None
    for start, key in _CANTON_BFS_BLOCK_STARTS:
        if bfs_number >= start:
            chosen = key
        else:
            break
    return chosen


# --- Canton abbreviation → key resolution (authoritative, cached) ------------
#
# Resolved from the live /Cantons list (26 rows) rather than hard-coded, so the
# mapping stays amtlich. Cached process-wide; tests reset it via
# `reset_canton_cache()`.
_canton_index: dict[str, str] | None = None


def reset_canton_cache() -> None:
    """Clear the cached canton abbreviation→key index (used by tests)."""
    global _canton_index
    _canton_index = None


async def _get_canton_index() -> dict[str, str]:
    """Return (and cache) an uppercase abbreviation → canton-key map."""
    global _canton_index
    if _canton_index is None:
        resp = await openplz_request("/Cantons")
        cantons = resp.json()
        _canton_index = {
            str(c["shortName"]).upper(): str(c["key"])
            for c in cantons
            if c.get("shortName") and c.get("key") is not None
        }
    return _canton_index


async def _resolve_canton_key(value: str) -> str:
    """Accept a canton abbreviation ('ZH') or a numeric key ('1') → key.

    Guards against the abbreviation-vs-key trap: an abbreviation used as a path
    param would silently yield ``[]``, so we translate it to the numeric key.
    """
    v = value.strip()
    if v.isdigit():
        return v
    index = await _get_canton_index()
    key = index.get(v.upper())
    if key is None:
        raise ValueError(
            f"Unbekanntes Kantonskürzel: {value!r}. Erwartet ein zweistelliges "
            f"Kürzel (z.B. 'ZH') oder eine Kantons-BFS-Nummer 1–26."
        )
    return key


# --- Paged fetch --------------------------------------------------------------


async def _fetch_all_pages(
    path: str, params: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]], int, bool]:
    """Fetch every page of a paginated list endpoint (pageSize=50).

    Returns ``(records, total_count, truncated)``. ``total_count`` comes from the
    ``x-total-count`` header; ``truncated`` is True if the safety cap stopped us
    before all pages were read.
    """
    query = dict(params or {})
    query["pageSize"] = OPENPLZ_MAX_PAGE_SIZE
    records: list[dict[str, Any]] = []
    total: int | None = None
    page = 1
    truncated = False
    while True:
        query["page"] = page
        resp = await openplz_request(path, query)
        batch = resp.json()
        if not isinstance(batch, list):
            break
        records.extend(batch)
        if total is None:
            try:
                total = int(resp.headers.get("x-total-count", len(batch)))
            except (TypeError, ValueError):
                total = len(batch)
        if not batch or len(records) >= total:
            break
        if len(records) >= OPENPLZ_MAX_RECORDS:
            truncated = True
            break
        page += 1
    return records, total if total is not None else len(records), truncated


# --- Record flattening (bfs_commune_number always top-level) ------------------


def _commune_fields(commune: dict[str, Any] | None) -> dict[str, Any]:
    c = commune or {}
    return {"commune_name": c.get("name"), "bfs_commune_number": c.get("key")}


def _district_fields(district: dict[str, Any] | None) -> dict[str, Any]:
    d = district or {}
    return {"district_name": d.get("name"), "district_number": d.get("key")}


def _canton_fields(canton: dict[str, Any] | None) -> dict[str, Any]:
    k = canton or {}
    return {
        "canton": k.get("shortName"),
        "canton_name": k.get("name"),
        "canton_number": k.get("key"),
    }


def _locality_record(loc: dict[str, Any]) -> dict[str, Any]:
    return {
        "postal_code": loc.get("postalCode"),
        "locality": loc.get("name"),
        **_commune_fields(loc.get("commune")),
        **_district_fields(loc.get("district")),
        **_canton_fields(loc.get("canton")),
    }


def _commune_record(com: dict[str, Any]) -> dict[str, Any]:
    # On the /Communes list the top-level object *is* the commune.
    return {
        "commune_name": com.get("name"),
        "bfs_commune_number": com.get("key"),
        **_district_fields(com.get("district")),
        **_canton_fields(com.get("canton")),
    }


def _address_record(a: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": a.get("name"),
        "postal_code": a.get("postalCode"),
        "locality": a.get("locality"),
        "status": a.get("status"),
        **_commune_fields(a.get("commune")),
        **_district_fields(a.get("district")),
        **_canton_fields(a.get("canton")),
    }


# --- Input models -------------------------------------------------------------


class LookupPostalCodeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    postal_code: str = Field(
        ...,
        pattern=r"^\d{4}$",
        description="Schweizer Postleitzahl (4-stellig, z.B. '8001').",
    )


class FindCommuneInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        pattern=TEXT_PATTERN,
        description="Gemeinde-/Ortsname (Vorwärts-Auflösung Name → BFS-Nummer).",
    )
    bfs_number: int | None = Field(
        default=None,
        ge=1,
        le=9999,
        description="BFS-Gemeindenummer (Rückwärts-Auflösung BFS-Nummer → Gemeinde).",
    )
    canton: str | None = Field(
        default=None,
        pattern=r"^([A-Za-z]{2}|\d{1,2})$",
        description="Kanton als Kürzel ('ZH') oder BFS-Nummer ('1'): listet dessen Gemeinden.",
    )
    district: str | None = Field(
        default=None,
        pattern=r"^\d{1,4}$",
        description="Bezirks-Schlüssel (numerisch, z.B. '109'): listet dessen Gemeinden.",
    )

    @model_validator(mode="after")
    def _exactly_one(self) -> FindCommuneInput:
        provided = [
            f
            for f, v in (
                ("name", self.name),
                ("bfs_number", self.bfs_number),
                ("canton", self.canton),
                ("district", self.district),
            )
            if v is not None
        ]
        if len(provided) != 1:
            raise ValueError(
                "Genau einen Parameter angeben: name | bfs_number | canton | district "
                f"(erhalten: {provided or 'keinen'})."
            )
        return self


class SearchAddressInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    query: str = Field(
        ...,
        min_length=2,
        max_length=100,
        pattern=TEXT_PATTERN,
        description="Suchbegriff (Strasse, Ort, PLZ) für die Volltextsuche.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=OPENPLZ_MAX_PAGE_SIZE,
        description="Maximale Trefferanzahl (1–50).",
    )


# --- Formatting helpers -------------------------------------------------------


def _format_localities(pc: str, records: list[dict[str, Any]]) -> str:
    if not records:
        return (
            f"Keine Ortschaft zur PLZ {pc} gefunden. Bei OpenPLZ liefert eine "
            f"unbekannte PLZ HTTP 200 mit leerer Liste — prüfe die 4-stellige "
            f"Schreibweise (z.B. '8001')."
        )
    lines = [
        f"**PLZ {pc}** — {len(records)} Ortschaft(en):",
        "",
        "| Ort | Gemeinde | BFS-Nr | Bezirk | Kanton |",
        "|-----|----------|--------|--------|--------|",
    ]
    for r in records:
        lines.append(
            f"| {r['locality']} | {r['commune_name']} | "
            f"**{r['bfs_commune_number']}** | {r['district_name']} | {r['canton']} |"
        )
    lines.append("")
    lines.append("_BFS-Nr = Join-Schlüssel zu BFS-Statistikdaten (swiss-statistics-mcp)._")
    return "\n".join(lines)


def _format_communes(title: str, records: list[dict[str, Any]], note: str = "") -> str:
    if not records:
        base = f"{title}: keine Gemeinden gefunden."
        return f"{base}\n\n{note}" if note else base
    lines = [
        f"**{title}** — {len(records)} Gemeinde(n):",
        "",
        "| Gemeinde | BFS-Nr | Bezirk | Kanton |",
        "|----------|--------|--------|--------|",
    ]
    for r in sorted(records, key=lambda x: str(x.get("commune_name") or "")):
        lines.append(
            f"| {r['commune_name']} | **{r['bfs_commune_number']}** | "
            f"{r.get('district_name') or '–'} | {r.get('canton') or '–'} |"
        )
    lines.append("")
    lines.append("_BFS-Nr = Join-Schlüssel zu BFS-Statistikdaten (swiss-statistics-mcp)._")
    if note:
        lines.append("")
        lines.append(f"_{note}_")
    return "\n".join(lines)


def _format_addresses(query: str, records: list[dict[str, Any]], total: int) -> str:
    if not records:
        return (
            f"Keine Treffer für «{query}». Versuche einen kürzeren oder "
            f"allgemeineren Suchbegriff."
        )
    shown = len(records)
    header = f"**Volltextsuche «{query}»** — {shown} von {total} Treffer(n) angezeigt:"
    lines = [header, "", "| Bezeichnung | PLZ | Ort | Gemeinde | BFS-Nr | Kanton |",
             "|-------------|-----|-----|----------|--------|--------|"]
    for r in records:
        lines.append(
            f"| {r.get('name') or '–'} | {r.get('postal_code') or '–'} | "
            f"{r.get('locality') or '–'} | {r.get('commune_name') or '–'} | "
            f"{r.get('bfs_commune_number') or '–'} | {r.get('canton') or '–'} |"
        )
    if total > shown:
        lines.append("")
        lines.append(f"_{total - shown} weitere Treffer nicht angezeigt (limit={shown})._")
    return "\n".join(lines)


# --- Handlers -----------------------------------------------------------------


@log_tool_call("lookup_postal_code")
async def lookup_postal_code(params: LookupPostalCodeInput) -> ToolResponse:
    """Resolve a Swiss postal code to locality, commune (+BFS number), district, canton."""
    try:
        resp = await openplz_request("/Localities", {"postalCode": params.postal_code})
        localities = resp.json()
        records = [_locality_record(loc) for loc in localities]
        return ToolResponse.ok(
            _format_localities(params.postal_code, records),
            records,
            match_type="exact" if records else "none",
            source=OPENPLZ_SOURCE,
            license=OPENPLZ_LICENSE,
        )
    except Exception as e:  # noqa: BLE001 — degrade gracefully
        return ToolResponse.error(
            handle_api_error(e, f"PLZ-Abfrage {params.postal_code}"), source=OPENPLZ_SOURCE
        )


async def _find_by_name(name: str) -> ToolResponse:
    resp = await openplz_request("/Localities", {"name": name})
    localities = resp.json()
    # A commune can back several localities — dedupe by BFS number.
    seen: dict[str, dict[str, Any]] = {}
    for loc in localities:
        rec = _locality_record(loc)
        bfs = rec.get("bfs_commune_number")
        if bfs and bfs not in seen:
            seen[bfs] = {
                "commune_name": rec["commune_name"],
                "bfs_commune_number": bfs,
                "district_name": rec["district_name"],
                "district_number": rec["district_number"],
                "canton": rec["canton"],
                "canton_name": rec["canton_name"],
                "canton_number": rec["canton_number"],
            }
    records = list(seen.values())
    return ToolResponse.ok(
        _format_communes(f"Gemeinde-Auflösung «{name}»", records),
        records,
        match_type="exact" if records else "none",
        source=OPENPLZ_SOURCE,
        license=OPENPLZ_LICENSE,
    )


async def _find_by_bfs(bfs_number: int) -> ToolResponse:
    canton_key = _canton_key_for_bfs(bfs_number)
    if canton_key is None:
        return ToolResponse.ok(
            _format_communes(
                f"BFS-Nummer {bfs_number}",
                [],
                note=f"BFS-Nummer {bfs_number} liegt ausserhalb der bekannten "
                f"Kantonsblöcke (1–6810).",
            ),
            [],
            match_type="none",
            source=OPENPLZ_SOURCE,
            license=OPENPLZ_LICENSE,
        )
    communes, _total, truncated = await _fetch_all_pages(f"/Cantons/{canton_key}/Communes")
    match = [c for c in communes if str(c.get("key")) == str(bfs_number)]
    records = [_commune_record(c) for c in match]
    note = ""
    if not records:
        note = (
            f"BFS-Nummer {bfs_number} wurde im (aus dem Nummernblock abgeleiteten) "
            f"Kanton {canton_key} nicht gefunden — evtl. eine fusionierte/ehemalige "
            f"Gemeinde oder eine ungültige Nummer."
        )
    elif truncated:
        note = "Hinweis: Gemeindeliste war sehr lang und wurde gekappt."
    return ToolResponse.ok(
        _format_communes(f"BFS-Nummer {bfs_number}", records, note=note),
        records,
        match_type="exact" if records else "none",
        source=OPENPLZ_SOURCE,
        license=OPENPLZ_LICENSE,
    )


async def _list_by_canton(canton: str) -> ToolResponse:
    canton_key = await _resolve_canton_key(canton)
    communes, total, truncated = await _fetch_all_pages(f"/Cantons/{canton_key}/Communes")
    records = [_commune_record(c) for c in communes]
    note = ""
    if not records:
        note = (
            f"Kanton {canton!r} → Schlüssel {canton_key} lieferte eine leere Liste. "
            f"Achtung: Pfad-Parameter ist die numerische BFS-Nummer, nicht das "
            f"Kürzel — die Auflösung erfolgte serverseitig."
        )
    elif truncated:
        note = f"Hinweis: nur die ersten {len(records)} von {total} Gemeinden gezeigt."
    return ToolResponse.ok(
        _format_communes(f"Gemeinden im Kanton {canton.upper()}", records, note=note),
        records,
        match_type="exact" if records else "none",
        source=OPENPLZ_SOURCE,
        license=OPENPLZ_LICENSE,
    )


async def _list_by_district(district: str) -> ToolResponse:
    communes, total, truncated = await _fetch_all_pages(f"/Districts/{district}/Communes")
    records = [_commune_record(c) for c in communes]
    note = ""
    if not records:
        note = (
            f"Bezirk {district!r} lieferte eine leere Liste. Der Pfad-Parameter ist "
            f"der numerische Bezirks-Schlüssel (z.B. '109' für den Bezirk Uster) — "
            f"eine leere Antwort bedeutet meist einen falschen Schlüssel."
        )
    elif truncated:
        note = f"Hinweis: nur die ersten {len(records)} von {total} Gemeinden gezeigt."
    return ToolResponse.ok(
        _format_communes(f"Gemeinden im Bezirk {district}", records, note=note),
        records,
        match_type="exact" if records else "none",
        source=OPENPLZ_SOURCE,
        license=OPENPLZ_LICENSE,
    )


@log_tool_call("find_commune")
async def find_commune(params: FindCommuneInput) -> ToolResponse:
    """Resolve a commune both directions (name↔BFS number) or list a unit's communes."""
    try:
        if params.name is not None:
            return await _find_by_name(params.name)
        if params.bfs_number is not None:
            return await _find_by_bfs(params.bfs_number)
        if params.canton is not None:
            return await _list_by_canton(params.canton)
        return await _list_by_district(str(params.district))
    except Exception as e:  # noqa: BLE001 — degrade gracefully
        return ToolResponse.error(handle_api_error(e, "Gemeinde-Auflösung"), source=OPENPLZ_SOURCE)


@log_tool_call("search_address")
async def search_address(params: SearchAddressInput) -> ToolResponse:
    """Full-text search over Swiss streets and localities (OpenPLZ FullTextSearch)."""
    try:
        resp = await openplz_request(
            "/FullTextSearch",
            {"searchTerm": params.query, "page": 1, "pageSize": params.limit},
        )
        results = resp.json()
        try:
            total = int(resp.headers.get("x-total-count", len(results)))
        except (TypeError, ValueError):
            total = len(results)
        records = [_address_record(a) for a in results][: params.limit]
        return ToolResponse.ok(
            _format_addresses(params.query, records, total),
            records,
            match_type="exact" if records else "none",
            source=OPENPLZ_SOURCE,
            license=OPENPLZ_LICENSE,
        )
    except Exception as e:  # noqa: BLE001 — degrade gracefully
        return ToolResponse.error(
            handle_api_error(e, f"Volltextsuche «{params.query}»"), source=OPENPLZ_SOURCE
        )
