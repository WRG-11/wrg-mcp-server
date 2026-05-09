"""ransom_radar MCP tools.

Two tools exposed:

* ``ransom_radar_tick`` — run a full tick (leak scan + attack surface +
  snapshot + diff) for a given watchlist tier. Wraps
  ``ransom_radar.orchestrator.tick_tier``.
* ``ransom_radar_status`` — read the latest snapshot(s) from the
  on-disk snapshot store, optionally filtered by brand id. Mirrors
  ``ransom-radar status`` / ``ransom-radar brief``.

Both tools degrade gracefully when ``ransom_radar`` (or the lib
``wrg_threat_intel`` it depends on) is not installed:
``{"ok": False, "error": "ransom_radar not installed"}``.

Pasif-only kuralı: tool'lar yalnızca ``ransom_radar.orchestrator`` /
``wrg_threat_intel.store`` API'lerini çağırır; bunlar yapısal pasif.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

VALID_TIERS: frozenset[str] = frozenset({"T1", "T2", "T3"})


def _missing_lib_envelope(tool: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "ransom_radar not installed",
        "tool": tool,
    }


def register_ransom_radar_tools(mcp: FastMCP) -> None:
    try:
        from ransom_radar.orchestrator import tick_tier
        from wrg_threat_intel.store import latest_snapshot, list_dates, load_snapshots

        _HAS_LIB = True
    except ImportError:
        _HAS_LIB = False

    @mcp.tool()
    def ransom_radar_tick(
        tier: str = "T1",
        feed_limit: int = 100,
        leak_threshold: float = 0.85,
        group: str | None = None,
        skip_attack_surface: bool = False,
        skip_apex_resolve: bool = False,
        base_dir: str | None = None,
    ) -> dict[str, Any]:
        """Run one ransom_radar tick: leak feed scan + attack-surface + snapshot + diff.

        Equivalent to ``ransom-radar tick --tier {tier}`` CLI. Persists a
        snapshot under ``base_dir`` (default ``~/.wrg/threat_intel/snapshots``)
        and computes a one-line diff summary against the previous snapshot.

        Args:
            tier: Watchlist tier (``"T1"``, ``"T2"``, or ``"T3"``).
            feed_limit: Max victims to fetch from the leak feed.
            leak_threshold: Brand-name fuzzy-match threshold (0.0-1.0).
            group: Scan victims of this specific ransomware group; if
                None, the cross-group recent-victim feed is used.
            skip_attack_surface: When True, skip CT log + DNS + RDAP scan.
            skip_apex_resolve: When True, skip apex IP resolve + RDAP whois.
            base_dir: Snapshot store base directory (path string).

        Returns:
            ``{"ok": True, "tick_at": ..., "tier": ..., "brand_count": ...,
            "leak_hit_count": ..., "attack_surface_count": ...,
            "snapshot_path": ..., "diff_summary": ..., "leak_hits": [...]}``.
        """
        if not _HAS_LIB:
            return _missing_lib_envelope("ransom_radar_tick")

        if tier not in VALID_TIERS:
            return {
                "ok": False,
                "error": f"tier must be one of {sorted(VALID_TIERS)} (got {tier!r})",
            }

        try:
            result = tick_tier(
                tier=tier,
                feed_limit=feed_limit,
                leak_threshold=leak_threshold,
                leak_group=group,
                include_attack_surface=not skip_attack_surface,
                include_apex_resolve=not skip_apex_resolve,
                base_dir=Path(base_dir) if base_dir else None,
            )
        except Exception as exc:  # pragma: no cover — defensive: surface any tick error
            return {"ok": False, "error": f"tick failed: {exc}", "tier": tier}

        return {
            "ok": True,
            "tick_at": result.tick_at,
            "tier": result.tier,
            "brand_count": result.brand_count,
            "leak_hit_count": len(result.leak_hits),
            "attack_surface_count": len(result.attack_surfaces),
            "snapshot_path": (
                str(result.snapshot_path) if result.snapshot_path else None
            ),
            "diff_summary": result.diff_summary,
            "leak_hits": [
                {
                    "brand_id": h.brand_id,
                    "victim_name": h.victim_name,
                    "victim_group": h.victim_group,
                    "discovery_date": h.discovery_date,
                    "match_kind": h.match_kind,
                    "confidence": h.confidence,
                }
                for h in result.leak_hits
            ],
        }

    @mcp.tool()
    def ransom_radar_status(
        brand: str | None = None,
        last_n: int = 1,
        base_dir: str | None = None,
    ) -> dict[str, Any]:
        """Read the latest ransom_radar snapshot(s), optionally filtered by brand.

        Equivalent to ``ransom-radar status`` (last_n=1) or
        ``ransom-radar brief --last N`` (last_n>1). Reads on-disk snapshots —
        does NOT trigger a fresh tick.

        Args:
            brand: Filter to victims attributed to this brand id. Match key
                comes from ``LeakHit.brand_id`` embedded in
                ``Victim.description`` as ``brand={id!r}``.
            last_n: Number of most recent snapshot dates to return
                (default 1). When 1, returns only the latest snapshot dict.
                When >1, returns a list under ``snapshots``.
            base_dir: Snapshot store base directory.

        Returns:
            ``{"ok": True, "snapshot": {...}}`` for last_n=1, or
            ``{"ok": True, "snapshots": [...]}`` for last_n>1.
        """
        if not _HAS_LIB:
            return _missing_lib_envelope("ransom_radar_status")

        bd = Path(base_dir) if base_dir else None

        if last_n <= 1:
            try:
                snap = latest_snapshot(base_dir=bd)
            except Exception as exc:  # pragma: no cover - defensive
                return {"ok": False, "error": str(exc)}

            if snap is None:
                return {
                    "ok": True,
                    "snapshot": None,
                    "message": "no snapshots yet — run ransom_radar_tick first",
                }

            return {
                "ok": True,
                "snapshot": _summarize_snapshot(snap, brand=brand),
            }

        # last_n > 1: list_dates + load_snapshots per date
        try:
            dates = list_dates(base_dir=bd)
        except Exception as exc:  # pragma: no cover - defensive
            return {"ok": False, "error": str(exc)}

        if not dates:
            return {"ok": True, "snapshots": [], "message": "no snapshots yet"}

        out: list[dict[str, Any]] = []
        for d in sorted(dates, reverse=True)[:last_n]:
            try:
                snaps = load_snapshots(d, base_dir=bd)
            except Exception:  # pragma: no cover - defensive
                continue
            for s in snaps:
                out.append(_summarize_snapshot(s, brand=brand))

        return {"ok": True, "snapshots": out, "count": len(out)}


def _summarize_snapshot(
    snap: Any,
    *,
    brand: str | None = None,
) -> dict[str, Any]:
    """Summarize a Snapshot to a JSON-friendly dict, optionally brand-filtered."""
    summary: dict[str, Any] = {
        "snapshot_date": snap.snapshot_date,
        "victim_count": len(snap.victims),
        "subdomain_count": len(snap.subdomains),
        "asn_count": len(snap.asn_records),
        "metadata": dict(snap.metadata) if snap.metadata else {},
    }

    if brand:
        token = f"brand={brand!r}"
        matched = [
            v.to_dict()
            for v in snap.victims
            if token in (v.description or "")
        ]
        summary["brand"] = brand
        summary["matched_victims"] = matched
        summary["matched_count"] = len(matched)

    return summary
