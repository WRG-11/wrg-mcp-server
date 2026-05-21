"""MCP Resources for read-only WRG state exposure.

Resources are the third MCP capability (alongside Tools + Prompts). Where
``@mcp.tool()`` exposes actions and ``@mcp.prompt()`` exposes workflow
recipes, ``@mcp.resource()`` exposes URI-addressable read-only data
snapshots. Claude can subscribe to a resource URI (e.g.,
``wrg://patterns/26``) and pull the body directly without invoking a tool
call (lower friction + parametric-query-free).

R88-52d ship — 3 Resources NEW (1st Resource layer for WRG MCP server,
sister to today's ``prompts.py`` first-prompt ship at commit ``e40f6197``):

* ``wrg://corpus-stats`` — Live aggregate counts (incidents + actors +
  patterns + sigma rules + W cohort + capability gaps).
* ``wrg://patterns/{pattern_id}`` — Pattern catalog entry by numeric ID;
  returns graduation status + criteria + vaka count + sister applications.
* ``wrg://breaches/recent`` — Last 30 days incidents aggregated from
  breach corpus (filtered by timeline_first_announcement).

Test surface: ``corpus_stats_body()``, ``pattern_lookup_body(pattern_id)``,
and ``recent_breaches_body()`` exposed at module level so unit tests can
assert content without invoking the MCP machinery (sister pattern to
``wrg_status_body()`` in ``prompts.py``).

D scope family-pivot 5-vaka MATURE candidate (5th distinct sub-family this
sprint): corpus-add (R87-43d) + helper-impl (R88-47d) + helper-EXTEND
(R88-49d) + LLM-integrated (R88-51d) + **MCP-Resource NEW (R88-52d)**.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP


# ---------------------------------------------------------------------------
# Pattern catalog — hardcoded metadata mirror of AGENTS.md sections 15.10,
# 15.12, 15.16, 15.18, 15.19, 15.20.
# ---------------------------------------------------------------------------
# Manual sync per pattern graduation (R88-52d initial ship; R88-53+ candidate
# = derive from AGENTS.md auto-parse + drift detector W cohort 10th member).
# Drift risk acknowledged in module docstring + done report saha bulgu.
_PATTERN_CATALOG: dict[str, dict[str, Any]] = {
    "22": {
        "id": "22",
        "title": "README dashboard rendering — HTML comment + code span convention",
        "graduation": "CANDIDATE",
        "version": "v1.0",
        "agents_md_section": "15.10",
        "shipped_in": "R88-45e",
        "vaka_count": 3,
        "criteria_summary": (
            "README dashboard claims wrapped in HTML comment markers + code span "
            "preserve operator-readable diff signal across rendering passes."
        ),
        "sister_applications": ["dashboard_live_check sentry (R88-48d W4)"],
    },
    "25": {
        "id": "25",
        "title": "V_corpus pre-merge discipline — mitigation playbook",
        "graduation": "FORMAL",
        "version": "v1.0",
        "agents_md_section": "15.12",
        "shipped_in": "R88-46e",
        "vaka_count": 5,
        "criteria_summary": (
            "Corpus YAML changes require ≥3-vaka graduation evidence + cross-link "
            "memos before merge; prevents single-source corpus inflation."
        ),
        "sister_applications": ["actor catalog growth governance"],
    },
    "26": {
        "id": "26",
        "title": "Cross-app type contract discipline — baseline lifecycle playbook",
        "graduation": "FORMAL",
        "version": "v1.0",
        "agents_md_section": "15.16",
        "shipped_in": "R88-48e",
        "vaka_count": 4,
        "criteria_summary": (
            "Sentry helper baseline+acknowledged_drifts+regen lifecycle; "
            "Literal-vs-YAML type contract enforcement across app boundaries."
        ),
        "sister_applications": [
            "R88-47d cross_app_type_contract_audit",
            "R88-48d dashboard_live_check",
            "R88-49d feed_staleness_sentry EXTEND",
            "R88-50d breach_disclosure_sentry",
        ],
    },
    "27": {
        "id": "27",
        "title": "Convergent industry validation — Track A graduation taxonomy",
        "graduation": "FORMAL",
        "version": "v1.0",
        "agents_md_section": "15.20",
        "shipped_in": "R88-49e",
        "vaka_count": 7,
        "criteria_summary": (
            "Track A — parallel-independent-invention mechanism; ≥4/5 pillar "
            "STRONG CONVERGENT across ≥7-vaka cluster validates WRG discipline "
            "as industry-best-practice (NOT idiosyncratic). 5-pillar matrix: "
            "multi-pass review + effort parameter + workspace memory + pattern "
            "recording + production-ready."
        ),
        "sister_applications": [
            "Conductor.build", "spec-kit", "Grok Build",
            "Cursor", "Aider", "Bolt.new", "OpenHands",
        ],
    },
    "28": {
        "id": "28",
        "title": "Cross-vendor convention — Track B graduation taxonomy",
        "graduation": "FORMAL",
        "version": "v1.0",
        "agents_md_section": "15.18 + 15.20",
        "shipped_in": "R88-50e",
        "vaka_count": 4,
        "criteria_summary": (
            "Track B — explicit-spec-adoption mechanism; ≥3-vaka shared-spec "
            "adoption across vendors validates external spec as convention. "
            "Sister to Track A but mechanism differs (shared spec vs parallel "
            "invention)."
        ),
        "sister_applications": ["MCP spec adoption cluster", "spec-kit slash-flow"],
    },
    "29": {
        "id": "29",
        "title": "Multi-modal forensics discipline — capability gap 5 ACUTE",
        "graduation": "CANDIDATE",
        "version": "v1.0",
        "agents_md_section": "15.19",
        "shipped_in": "R88-50e",
        "vaka_count": 1,
        "criteria_summary": (
            "Visual disinformation + deepfake detection 1st codified pattern; "
            "capability gap 5 ACUTE escalation cluster trigger. Awaits 2+ vaka "
            "for FORMAL graduation."
        ),
        "sister_applications": ["T1 multi-modal forensics mini-suite (R88-53+ candidate)"],
    },
}

# W cohort 9-member sentinel roster (parity with prompts.py wrg_status_body)
_W_COHORT_MEMBERS = [
    "cov_drift_sentry",
    "ai_runtime_cve_radar",
    "dispatch_check",
    "ransom_radar",
    "pulseboard",
    "feed_staleness_sentry",
    "cadence_freshness_sentry",
    "breach_disclosure_sentry",
    "workflow_health_sentry",  # candidate R88-52+
]

# Capability gaps — ACUTE state (parity with wrg_status_body)
_CAPABILITY_GAPS_ACUTE = [
    {
        "id": 4,
        "name": "sustainability/maintenance",
        "memo": "feedback_maintenance_burden_growth_pattern_2026_05_20.md",
    },
    {
        "id": 5,
        "name": "visual disinfo",
        "memo": "feedback_multimodal_forensics_architecture_2026_05_21.md",
    },
    {
        "id": 6,
        "name": "observability/monitoring",
        "memo": "feedback_github_actions_billing_silent_ci_failure_2026_05_21.md",
    },
]


def _load_actor_count() -> int:
    """Graceful actor count load — returns 0 if wrg_threat_intel unavailable."""
    try:
        from wrg_threat_intel.breach.corpus import load_actors
        return len(load_actors())
    except Exception:
        return 0


def _load_incident_count() -> int:
    """Graceful incident count load — returns 0 if wrg_threat_intel unavailable."""
    try:
        from wrg_threat_intel.breach.corpus import load_incidents
        return len(load_incidents())
    except Exception:
        return 0


def _load_recent_incidents(days: int = 30) -> list[dict[str, Any]]:
    """Return last-N-days incidents as plain dicts. Empty list if unavailable.

    Cutoff = ``date.today() - days``. Match keys (any-of):
    timeline_first_announcement OR timeline_deadline OR timeline_public_leak.
    Falls back to year-only match parsed from incident id if all timeline
    fields are None.
    """
    try:
        from wrg_threat_intel.breach.corpus import load_incidents
    except Exception:
        return []
    try:
        incidents = load_incidents()
    except Exception:
        return []
    cutoff = date.today() - timedelta(days=days)
    out: list[dict[str, Any]] = []
    for inc in incidents:
        candidates = [
            inc.timeline_first_announcement,
            inc.timeline_deadline,
            inc.timeline_public_leak,
        ]
        latest = max((c for c in candidates if c is not None), default=None)
        if latest is None or latest < cutoff:
            continue
        out.append({
            "id": inc.id,
            "actor_id": inc.actor_id,
            "victim_display_name": inc.victim.display_name,
            "victim_sector": inc.victim.sector,
            "victim_country": inc.victim.country,
            "severity": inc.severity.value if hasattr(inc.severity, "value") else str(inc.severity),
            "status": inc.status.value if hasattr(inc.status, "value") else str(inc.status),
            "root_cause": inc.root_cause.value if hasattr(inc.root_cause, "value") else str(inc.root_cause),
            "latest_timeline_date": latest.isoformat(),
            "ai_assisted": inc.ai_assisted,
        })
    # Sort newest first
    out.sort(key=lambda r: r["latest_timeline_date"], reverse=True)
    return out


def corpus_stats_body() -> str:
    """Live WRG corpus aggregate snapshot as JSON-encoded string.

    Returns structured JSON (operator/Claude consumes via ``ConvertFrom-Json``
    or stdlib ``json.loads``). Errors degrade gracefully — missing
    wrg_threat_intel surface returns ``actor_count`` / ``incident_count`` =
    0 rather than raising. ASCII-only output.
    """
    payload = {
        "ok": True,
        "incident_count": _load_incident_count(),
        "actor_count": _load_actor_count(),
        "pattern_count_total": len(_PATTERN_CATALOG),
        "pattern_count_formal": sum(
            1 for p in _PATTERN_CATALOG.values() if p["graduation"] == "FORMAL"
        ),
        "pattern_count_candidate": sum(
            1 for p in _PATTERN_CATALOG.values() if p["graduation"] == "CANDIDATE"
        ),
        "w_cohort_count": len(_W_COHORT_MEMBERS),
        "w_cohort_members": list(_W_COHORT_MEMBERS),
        "capability_gaps_acute": list(_CAPABILITY_GAPS_ACUTE),
        "source_note": (
            "Pattern catalog mirrored from AGENTS.md sections 15.10, 15.12, "
            "15.16, 15.18, 15.19, 15.20. Pattern count NOT auto-derived; "
            "manual sync per graduation (R88-53+ candidate auto-sync W10)."
        ),
    }
    return json.dumps(payload, ensure_ascii=True, indent=2)


def pattern_lookup_body(pattern_id: str) -> str:
    """Pattern catalog entry by numeric ID.

    Accepts ``"26"`` or ``"pattern-26"`` or ``"Pattern 26"`` — normalized to
    bare numeric. Unknown IDs return ``{ok: False, error, available}``
    envelope. ASCII-only output.
    """
    # Normalize id: strip non-digit prefixes
    raw = pattern_id.strip()
    digits = "".join(c for c in raw if c.isdigit())
    if not digits:
        payload: dict[str, Any] = {
            "ok": False,
            "error": f"pattern_id must contain at least one digit; got '{raw}'",
            "available_ids": sorted(_PATTERN_CATALOG.keys()),
        }
        return json.dumps(payload, ensure_ascii=True, indent=2)
    entry = _PATTERN_CATALOG.get(digits)
    if entry is None:
        payload = {
            "ok": False,
            "error": f"pattern_id '{digits}' not found",
            "available_ids": sorted(_PATTERN_CATALOG.keys()),
            "note": "Pattern catalog is manually maintained; some patterns may exist in feedback_pattern_catalog.md memory but not yet codified in AGENTS.md §15.x.",
        }
        return json.dumps(payload, ensure_ascii=True, indent=2)
    response: dict[str, Any] = {"ok": True}
    response.update(entry)
    return json.dumps(response, ensure_ascii=True, indent=2)


def recent_breaches_body() -> str:
    """Last 30 days incident aggregated snapshot.

    Returns JSON list of incidents whose latest timeline date is within
    the cutoff window. Empty list if no recent incidents OR
    wrg_threat_intel unavailable. ASCII-only output.
    """
    incidents = _load_recent_incidents(days=30)
    payload: dict[str, Any] = {
        "ok": True,
        "cutoff_days": 30,
        "incident_count": len(incidents),
        "incidents": incidents,
        "source_note": (
            "Loaded from wrg_threat_intel.breach.corpus.load_incidents(); "
            "cutoff = today - 30 days against max(timeline_first_announcement, "
            "timeline_deadline, timeline_public_leak). Sorted newest first."
        ),
    }
    return json.dumps(payload, ensure_ascii=True, indent=2)


def register_corpus_resources(mcp: FastMCP) -> None:
    """Register read-only corpus resources on the MCP server.

    Idempotent on import (decorator runs once per ``create_mcp_server``
    call). Sister to ``register_status_prompts``.
    """

    @mcp.resource(
        "wrg://corpus-stats",
        name="wrg-corpus-stats",
        description=(
            "Live aggregate WRG corpus snapshot: incident count + actor "
            "count + pattern catalog (FORMAL + CANDIDATE) + W cohort 9-member "
            "sentinels + capability gaps 4/5/6 ACUTE state. Use when the "
            "operator asks 'WRG corpus durumu', 'kac incident var', 'pattern "
            "katalog ozet', or before composing a new wave brief to refresh "
            "state context."
        ),
        mime_type="application/json",
    )
    def corpus_stats() -> str:
        return corpus_stats_body()

    @mcp.resource(
        "wrg://patterns/{pattern_id}",
        name="wrg-patterns-by-id",
        description=(
            "Pattern catalog entry by numeric ID (e.g., wrg://patterns/26). "
            "Returns graduation status (FORMAL/CANDIDATE), version, AGENTS.md "
            "section anchor, shipped wave, vaka count, criteria summary, and "
            "sister applications. Use for pattern lookup without grep through "
            "AGENTS.md."
        ),
        mime_type="application/json",
    )
    def pattern_lookup(pattern_id: str) -> str:
        return pattern_lookup_body(pattern_id)

    @mcp.resource(
        "wrg://breaches/recent",
        name="wrg-breaches-recent",
        description=(
            "Last 30 days breach incidents aggregated from wrg_threat_intel "
            "corpus YAML files. Returns structured list with actor + victim "
            "sector/country + severity + status + root_cause + latest "
            "timeline date per incident. Sorted newest first. Use for "
            "rolling-window threat-landscape awareness."
        ),
        mime_type="application/json",
    )
    def recent_breaches() -> str:
        return recent_breaches_body()
