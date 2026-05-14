"""INFO_OPS detection state MCP tool wrapping ``wrg_threat_intel`` corpus.

R50 wave addition: surfaces the R49 Phase 9 INFO_OPS chain (enum + corpus +
Sigma rules) through the MCP server so external orchestrators (Claude
Code, IDEs, downstream pipelines) can query current detection state
without re-implementing the breach loaders.

Single tool exposed:

* ``info_ops_detect`` — filter the actor corpus by modus_operandi
  (default ``info-ops``), enrich each match with linked incidents and
  generated Sigma rule metadata.

The tool degrades gracefully when ``wrg_threat_intel`` is not installed
(returns ``{"ok": False, "error": "wrg_threat_intel not installed"}``).

Pasif-only kuralı: lookup against statically loaded corpus + rule
generation; no live scan / network / authentication action.
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP


def _missing_lib_envelope(tool: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "wrg_threat_intel not installed",
        "tool": tool,
    }


def register_info_ops_tools(mcp: FastMCP) -> None:
    try:
        from wrg_threat_intel.breach.corpus import load_actors, load_incidents
        from wrg_threat_intel.breach.sigma.rule_builder import build_actor_rules
        from wrg_threat_intel.breach.types import ModusOperandi

        _HAS_LIB = True
    except ImportError:
        _HAS_LIB = False

    @mcp.tool()
    def info_ops_detect(
        modus: str = "info-ops",
        actor_id: str | None = None,
        include_sigma: bool = True,
        include_incidents: bool = True,
    ) -> dict[str, Any]:
        """Query the INFO_OPS actor corpus + linked detection state.

        Filters the corpus by ``modus_operandi`` (default ``info-ops`` — the
        R49 first-class enum value) and optionally enriches each match with
        linked incident IDs and the Sigma rules currently emitted by
        ``build_actor_rules``. Pasif lookup; no live detection.

        Args:
            modus: ModusOperandi enum value. Defaults to ``"info-ops"``.
                Accepts any valid value: ``"extortion-only"``,
                ``"double-extortion"``, ``"triple-extortion"``,
                ``"supply-chain"``, ``"info-ops"``. Case-sensitive.
            actor_id: When set, overrides the modus filter and returns only
                the named actor's detection state (e.g.
                ``"russia_nexus_info_ops"``).
            include_sigma: When True, generate Sigma rules per matched
                actor via ``build_actor_rules`` and include title / id /
                level / status / tags for each rule.
            include_incidents: When True, include each matched actor's
                incident IDs with severity + announcement date.

        Returns:
            ``{"ok": True, "modus": ..., "matched_actors": [...],
            "actor_count": N, "sigma_rule_count": N, "incident_count": N,
            "summary": str}`` on success.
            ``{"ok": False, "error": ..., "valid_values": [...]}`` when the
            modus value is unknown.
            ``{"ok": False, "error": ..., "available_actors_for_modus":
            [...]}`` when a non-existent ``actor_id`` is supplied.
        """
        if not _HAS_LIB:
            return _missing_lib_envelope("info_ops_detect")

        try:
            modus_enum = ModusOperandi(modus)
        except ValueError:
            return {
                "ok": False,
                "error": f"unknown modus_operandi value: {modus!r}",
                "valid_values": [m.value for m in ModusOperandi],
            }

        actors = load_actors()
        incidents = load_incidents() if include_incidents else []

        if actor_id is not None:
            actor = actors.get(actor_id)
            if actor is None:
                return {
                    "ok": False,
                    "error": f"unknown actor_id: {actor_id!r}",
                    "available_actors_for_modus": [
                        aid
                        for aid, a in actors.items()
                        if modus_enum in a.modus_operandi
                    ],
                }
            matched = {actor_id: actor}
        else:
            matched = {
                aid: a
                for aid, a in actors.items()
                if modus_enum in a.modus_operandi
            }

        result_actors: list[dict[str, Any]] = []
        total_sigma = 0
        total_incidents = 0

        for aid in sorted(matched):
            actor = matched[aid]
            entry: dict[str, Any] = {
                "id": aid,
                "display_name": actor.display_name,
                "aliases": list(actor.aliases),
                "status": actor.status,
                "modus_operandi": [m.value for m in actor.modus_operandi],
                "sophistication": actor.sophistication.value,
                "ttps_mitre": list(actor.ttps_mitre),
                "origin_hints": list(actor.origin_hints),
            }

            if include_incidents:
                actor_incidents = [
                    {
                        "id": inc.id,
                        "victim_brand_id": inc.victim.brand_id,
                        "severity": inc.severity.value,
                        "first_announcement": (
                            inc.timeline_first_announcement.isoformat()
                            if inc.timeline_first_announcement
                            else None
                        ),
                        "ai_assisted": inc.ai_assisted,
                    }
                    for inc in incidents
                    if inc.actor_id == aid
                ]
                entry["incidents"] = actor_incidents
                total_incidents += len(actor_incidents)

            if include_sigma:
                rules = build_actor_rules(aid, actors=actors, incidents=incidents)
                entry["sigma_rules"] = [
                    {
                        "title": rule.title,
                        "id": str(rule.id),
                        "level": rule.level,
                        "status": rule.status,
                        "tags": list(rule.tags),
                    }
                    for rule in rules
                ]
                total_sigma += len(rules)

            result_actors.append(entry)

        return {
            "ok": True,
            "modus": modus,
            "actor_filter": actor_id,
            "matched_actors": result_actors,
            "actor_count": len(result_actors),
            "sigma_rule_count": total_sigma,
            "incident_count": total_incidents,
            "summary": (
                f"{len(result_actors)} actor(s) with modus={modus}; "
                f"{total_sigma} Sigma rule(s); {total_incidents} incident(s)"
            ),
        }
