"""Breach-incident corpus query MCP tool family for the WRG threat intel catalog.

R88-52b wave addition: surfaces the ``wrg_threat_intel.breach.corpus`` loaders
as a query-friendly MCP surface so external orchestrators (Claude Desktop,
Claude Code, downstream pipelines) can ask for "recent ransomware incidents",
"sector=finance breaches", or "incidents linked to actor X" without
re-implementing the YAML walkers.

Four tools exposed:

* ``breach_search`` — full-text + structured filter combo (sector, year
  range, severity, free-text ``q`` matched against id / victim / notes /
  references).
* ``breach_recent`` — incidents whose earliest known timeline date falls
  within the last N days (default 30).
* ``breach_by_actor`` — every incident linked to a specific actor slug.
* ``breach_by_sector`` — every incident whose victim sector matches the
  given taxonomy slug.

Sister module: :mod:`wrg_mcp_server.tools.info_ops` — register/envelope/
docstring convention is birebir copied from the R50 1st tool family so the
two tool surfaces compose cleanly. Pasif lookup only; the corpus is loaded
statically from packaged YAML — no live scan / network / authentication.

Graceful degradation: if ``wrg_threat_intel`` cannot be imported (e.g.
the package is not installed in the active env), each tool returns the
canonical missing-lib envelope so client code can branch on ``ok=False``
without crashing.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP


def _missing_lib_envelope(tool: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "wrg_threat_intel not installed",
        "tool": tool,
    }


def _incident_year_safe(inc: Any) -> int | None:
    """Return the earliest known year for an incident, or ``None`` if unknown.

    Mirrors ``wrg_threat_intel.breach.corpus._incident_year`` but does not
    raise — the tool surface prefers a soft drop ("incident has no
    datable timeline") over a hard ``CorpusError`` since the corpus YAML
    may include legacy entries lacking every timeline field.
    """
    for candidate in (
        inc.timeline_first_announcement,
        inc.timeline_deadline,
        inc.timeline_public_leak,
    ):
        if candidate is not None:
            return candidate.year
    head = inc.id.split("-", 1)[0]
    try:
        return int(head)
    except ValueError:
        return None


def _earliest_timeline_date(inc: Any) -> date | None:
    """Earliest known timeline date for an incident (announcement -> deadline -> public leak)."""
    for candidate in (
        inc.timeline_first_announcement,
        inc.timeline_deadline,
        inc.timeline_public_leak,
    ):
        if candidate is not None:
            return candidate
    return None


def _serialize_incident(inc: Any) -> dict[str, Any]:
    """Render a BreachIncident dataclass to the MCP envelope shape (ASCII-only)."""
    return {
        "id": inc.id,
        "actor_id": inc.actor_id,
        "victim_brand_id": inc.victim.brand_id,
        "victim_display_name": inc.victim.display_name,
        "sector": inc.victim.sector,
        "country": inc.victim.country,
        "size_tier": inc.victim.size_tier,
        "status": inc.status.value,
        "severity": inc.severity.value,
        "root_cause": inc.root_cause.value,
        "first_announcement": (
            inc.timeline_first_announcement.isoformat()
            if inc.timeline_first_announcement
            else None
        ),
        "deadline": (
            inc.timeline_deadline.isoformat() if inc.timeline_deadline else None
        ),
        "public_leak": (
            inc.timeline_public_leak.isoformat() if inc.timeline_public_leak else None
        ),
        "exfil_data_types": list(inc.exfil_data_types),
        "estimated_records": inc.estimated_records,
        "estimated_size_gb": inc.estimated_size_gb,
        "ai_assisted": inc.ai_assisted,
        "ai_role": inc.ai_role.value if inc.ai_role else None,
        "ai_model_family": inc.ai_model_family,
        "references_count": len(inc.references),
        "notes": inc.notes,
    }


def _matches_query(inc: Any, q: str) -> bool:
    """Case-insensitive substring match against id / actor / victim / notes / refs."""
    needle = q.lower()
    haystacks = (
        inc.id,
        inc.actor_id,
        inc.victim.brand_id,
        inc.victim.display_name,
        inc.victim.sector,
        inc.victim.country,
        inc.notes,
        " ".join(inc.references),
        " ".join(inc.exfil_data_types),
    )
    return any(needle in (s or "").lower() for s in haystacks)


def register_breach_corpus_tools(mcp: FastMCP) -> None:
    """Register the breach-incident corpus query tool family on an MCP server.

    Sister to :func:`wrg_mcp_server.tools.info_ops.register_info_ops_tools`;
    idempotent on repeated ``create_mcp_server`` calls because FastMCP
    handles decorator re-registration. The import is tucked inside the
    function body so a missing ``wrg_threat_intel`` install only fails the
    tool's runtime path, not the server bootstrap.
    """
    try:
        from wrg_threat_intel.breach.corpus import filter_incidents, load_incidents
        from wrg_threat_intel.breach.types import Severity

        _HAS_LIB = True
    except ImportError:
        _HAS_LIB = False

    @mcp.tool()
    def breach_search(
        q: str = "",
        sector: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Full-text + structured filter search across the WRG breach incident corpus.

        Use when the operator asks "incidents matching X", "ransomware in
        2024-2025 finance sector", "high-severity supply-chain breaches",
        or wants to scan the corpus by a combination of free-text and
        structured filters. For single-axis filters prefer the dedicated
        helpers (``breach_recent`` / ``breach_by_actor`` / ``breach_by_sector``)
        which return a more focused envelope.

        Args:
            q: Case-insensitive substring matched against incident id,
                actor_id, victim brand_id / display_name / sector / country,
                notes, references, and exfil_data_types. Empty string skips
                the text filter.
            sector: When set, restricts to incidents whose ``victim.sector``
                equals this taxonomy slug (e.g. ``"finance"``,
                ``"healthcare"``). Exact match.
            year_from: Inclusive lower bound on the earliest known timeline
                date (or year parsed from the incident id when no timeline
                date is set).
            year_to: Inclusive upper bound on the earliest known timeline
                date. May equal ``year_from`` for single-year queries.
            severity: One of ``"info"`` / ``"low"`` / ``"medium"`` /
                ``"high"`` (lowercase). Unknown values return an error
                envelope with the list of valid values.
            limit: Cap on the number of incidents returned. Defaults to 50;
                pass a higher value for full-corpus scans.

        Returns:
            ``{"ok": True, "count": N, "incidents": [...], "filters": {...},
            "truncated": bool}`` on success. ``incidents`` is sorted by id
            ascending (matching the corpus loader). ``truncated`` is True
            when the unfiltered match count exceeded ``limit``.
            ``{"ok": False, "error": ..., "valid_values": [...]}`` when
            ``severity`` is malformed.
        """
        if not _HAS_LIB:
            return _missing_lib_envelope("breach_search")

        if severity is not None:
            try:
                Severity(severity)
            except ValueError:
                return {
                    "ok": False,
                    "error": f"unknown severity value: {severity!r}",
                    "valid_values": [s.value for s in Severity],
                }

        # First-pass structured filter via corpus helper (actor/sector/etc).
        pool = filter_incidents(sector=sector)

        # Tool-side post-filters: year-range + severity + free-text. Brief's
        # year_from / year_to needs range semantics, but filter_incidents
        # only supports a single year — so we layer the range here.
        def _in_year_range(inc: Any) -> bool:
            if year_from is None and year_to is None:
                return True
            year = _incident_year_safe(inc)
            if year is None:
                return False
            if year_from is not None and year < year_from:
                return False
            if year_to is not None and year > year_to:
                return False
            return True

        def _matches_severity(inc: Any) -> bool:
            return severity is None or inc.severity.value == severity

        def _matches_text(inc: Any) -> bool:
            return not q or _matches_query(inc, q)

        filtered = [
            inc
            for inc in pool
            if _in_year_range(inc) and _matches_severity(inc) and _matches_text(inc)
        ]

        truncated = len(filtered) > limit
        clipped = filtered[:limit] if truncated else filtered

        return {
            "ok": True,
            "count": len(clipped),
            "total_matches": len(filtered),
            "truncated": truncated,
            "filters": {
                "q": q,
                "sector": sector,
                "year_from": year_from,
                "year_to": year_to,
                "severity": severity,
                "limit": limit,
            },
            "incidents": [_serialize_incident(inc) for inc in clipped],
        }

    @mcp.tool()
    def breach_recent(days: int = 30, limit: int = 50) -> dict[str, Any]:
        """Recent incidents whose earliest timeline date falls within the last N days.

        Use when the operator asks "what happened this week", "recent
        breaches", "last 30 days incidents", or before composing an
        ``arastirma_ask`` query that needs fresh corpus context. The
        earliest-known timeline rule mirrors ``breach_search``: first
        announcement -> deadline -> public leak; incidents lacking every
        timeline date are excluded.

        Args:
            days: Lookback window in days. Defaults to 30. Pass ``7`` for
                weekly cadence, ``365`` for annual.
            limit: Cap on the number of incidents returned. Defaults to 50.

        Returns:
            ``{"ok": True, "count": N, "window_days": days, "cutoff":
            "YYYY-MM-DD", "incidents": [...], "truncated": bool}``. The
            ``incidents`` list is sorted by earliest-timeline date
            descending (newest first).
        """
        if not _HAS_LIB:
            return _missing_lib_envelope("breach_recent")

        if days <= 0:
            return {
                "ok": False,
                "error": f"days must be a positive integer, got {days}",
            }

        cutoff = date.today() - timedelta(days=days)
        pool = load_incidents()

        def _is_recent(inc: Any) -> bool:
            earliest = _earliest_timeline_date(inc)
            return earliest is not None and earliest >= cutoff

        recent = [inc for inc in pool if _is_recent(inc)]
        recent.sort(
            key=lambda inc: _earliest_timeline_date(inc) or date.min,
            reverse=True,
        )

        truncated = len(recent) > limit
        clipped = recent[:limit] if truncated else recent

        return {
            "ok": True,
            "count": len(clipped),
            "total_matches": len(recent),
            "window_days": days,
            "cutoff": cutoff.isoformat(),
            "truncated": truncated,
            "incidents": [_serialize_incident(inc) for inc in clipped],
        }

    @mcp.tool()
    def breach_by_actor(actor_slug: str, limit: int = 50) -> dict[str, Any]:
        """All incidents linked to a specific actor by slug.

        Use when the operator asks "what has actor X done", "TeamPCP
        incidents", "Lapsus$ targets", or wants a single-actor pivot view.
        Returns an empty list when the actor slug is unknown rather than
        raising — the loader's actor catalog is the authoritative source
        of truth for valid slugs; this tool does not echo unknown-slug
        errors because incidents may legitimately reference actors that
        have not yet been profiled.

        Args:
            actor_slug: The ``ActorProfile.id`` value. Corpus convention
                is underscore-separated (e.g. ``"teampcp_unc6780"``,
                ``"russia_nexus_info_ops"``, ``"lapsus"``). Exact match,
                case-sensitive.
            limit: Cap on the number of incidents returned. Defaults to 50.

        Returns:
            ``{"ok": True, "actor_slug": ..., "count": N, "incidents":
            [...], "truncated": bool}``. The ``incidents`` list is sorted
            by earliest-timeline date descending (newest first).
        """
        if not _HAS_LIB:
            return _missing_lib_envelope("breach_by_actor")

        matched = filter_incidents(actor_id=actor_slug)
        matched.sort(
            key=lambda inc: _earliest_timeline_date(inc) or date.min,
            reverse=True,
        )

        truncated = len(matched) > limit
        clipped = matched[:limit] if truncated else matched

        return {
            "ok": True,
            "actor_slug": actor_slug,
            "count": len(clipped),
            "total_matches": len(matched),
            "truncated": truncated,
            "incidents": [_serialize_incident(inc) for inc in clipped],
        }

    @mcp.tool()
    def breach_by_sector(sector: str, limit: int = 50) -> dict[str, Any]:
        """All incidents whose victim sector matches the given taxonomy slug.

        Use when the operator asks "finance sector breaches", "healthcare
        ransomware", "incidents in <sector>", or wants a sector-level
        pivot for dashboard / executive-summary composition. Exact match
        on ``BreachVictim.sector``; mismatched casing or trailing
        whitespace returns an empty list.

        Args:
            sector: Sector taxonomy slug (e.g. ``"finance"``,
                ``"healthcare"``, ``"manufacturing"``, ``"government"``).
                Exact match, case-sensitive.
            limit: Cap on the number of incidents returned. Defaults to 50.

        Returns:
            ``{"ok": True, "sector": ..., "count": N, "incidents": [...],
            "truncated": bool}``. The ``incidents`` list is sorted by
            earliest-timeline date descending (newest first).
        """
        if not _HAS_LIB:
            return _missing_lib_envelope("breach_by_sector")

        matched = filter_incidents(sector=sector)
        matched.sort(
            key=lambda inc: _earliest_timeline_date(inc) or date.min,
            reverse=True,
        )

        truncated = len(matched) > limit
        clipped = matched[:limit] if truncated else matched

        return {
            "ok": True,
            "sector": sector,
            "count": len(clipped),
            "total_matches": len(matched),
            "truncated": truncated,
            "incidents": [_serialize_incident(inc) for inc in clipped],
        }
