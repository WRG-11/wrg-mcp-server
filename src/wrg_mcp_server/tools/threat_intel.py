"""Threat-intelligence MCP tools wrapping ``wrg_threat_intel`` lib.

Three passive-only tools exposed:

* ``attack_surface_passive`` — CT log subdomain enumeration + DNS A-record
  probe + RDAP whois for the apex IP.
* ``ransomware_lookup`` — ransomware.live victim feed query (by group or
  brand).
* ``darkweb_brand_watch`` — Dark Web Informer-style RSS/JSON aggregator
  brand mention search.

All tools degrade gracefully when ``wrg_threat_intel`` is not installed:
they return ``{"ok": False, "error": "wrg_threat_intel not installed"}``.

Pasif-only kuralı: bu wrapper'lar lib API'sini çağırır; lib zaten yapısal
pasif (port scan / TLS handshake / banner grab yok).
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

DEFAULT_DNS_PATTERNS: tuple[str, ...] = (
    "atlas",
    "vpn",
    "jira",
    "confluence",
    "wiki",
    "dev",
    "intranet",
    "sso",
)


def _missing_lib_envelope(tool: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "wrg_threat_intel not installed",
        "tool": tool,
    }


def register_threat_intel_tools(mcp: FastMCP) -> None:
    try:
        from wrg_threat_intel.feeds.ddw_aggregator import parse_feed
        from wrg_threat_intel.feeds.ransomware_live import (
            get_group_victims,
            get_recent_victims,
        )
        from wrg_threat_intel.matching.brand import match_brand
        from wrg_threat_intel.recon.passive.ct_log import search_apex
        from wrg_threat_intel.recon.passive.dns import probe_patterns, resolve
        from wrg_threat_intel.recon.passive.rdap import lookup_ip

        _HAS_LIB = True
    except ImportError:
        _HAS_LIB = False

    @mcp.tool()
    def attack_surface_passive(
        domain: str,
        patterns: list[str] | None = None,
        include_apex_resolve: bool = True,
    ) -> dict[str, Any]:
        """Passive attack-surface scan: CT log subdomain enumeration + DNS A-record probe + RDAP whois.

        Use when investigating a brand's external footprint (Arçelik / Beko /
        Borusan ICS PoC pattern). No port scan, no TLS handshake, no banner
        grab — only crt.sh / DNS / RDAP queries.

        Args:
            domain: Apex domain (e.g. ``"arcelik.com"``).
            patterns: Optional subdomain labels to filter CT-log hits and
                probe via DNS. Defaults to a curated set
                (atlas, vpn, jira, confluence, wiki, dev, intranet, sso).
            include_apex_resolve: When True, resolve the apex to an IP and
                run RDAP whois for ASN / netname.

        Returns:
            ``{"ok": True, "domain": ..., "ct_hits": [...], "live_subs": [...],
            "apex_ip": ..., "asn": {...}, "patterns_used": [...]}``.
        """
        if not _HAS_LIB:
            return _missing_lib_envelope("attack_surface_passive")

        pats = list(patterns) if patterns else list(DEFAULT_DNS_PATTERNS)

        ct_subs = search_apex(domain, patterns=pats)
        live_subs = probe_patterns(domain, pats)

        apex_ip: str | None = None
        asn_payload: dict[str, Any] | None = None
        if include_apex_resolve:
            apex_ip = resolve(domain)
            if apex_ip is not None:
                asn = lookup_ip(apex_ip)
                asn_payload = dict(asn.to_dict())

        return {
            "ok": True,
            "domain": domain,
            "patterns_used": pats,
            "ct_hits": [
                {
                    "fqdn": s.fqdn,
                    "source": s.source,
                    "first_seen": s.first_seen,
                    "issuer": s.issuer,
                }
                for s in ct_subs
            ],
            "live_subs": [
                {"fqdn": s.fqdn, "ip": s.ip, "source": s.source}
                for s in live_subs
            ],
            "apex_ip": apex_ip,
            "asn": asn_payload,
            "summary": (
                f"{len(ct_subs)} CT hit(s), {len(live_subs)} live sub(s)"
                + (f" — apex {apex_ip}" if apex_ip else "")
            ),
        }

    @mcp.tool()
    def ransomware_lookup(
        group: str | None = None,
        brand: str | None = None,
        limit: int = 50,
        threshold: float = 0.7,
    ) -> dict[str, Any]:
        """Ransomware leak feed query (ransomware.live API).

        Either ``group`` (e.g. ``"thegentlemen"``) returns that group's recent
        victims, or ``brand`` runs a fuzzy-match against the cross-group
        recent-victim feed. At least one must be provided.

        Use when checking if a brand has been claimed by a RaaS group, or
        listing a group's recent victim activity.

        Args:
            group: Ransomware group name (lowercase recommended).
            brand: Brand display name to fuzzy-match (e.g. ``"Arçelik"``).
                Only used when ``group`` is None.
            limit: Max entries returned (default 50).
            threshold: Brand fuzzy-match score threshold (0.0-1.0).

        Returns:
            ``{"ok": True, "mode": "group"|"brand", "victims": [...], "count": N}``.
        """
        if not _HAS_LIB:
            return _missing_lib_envelope("ransomware_lookup")

        if group is None and brand is None:
            return {
                "ok": False,
                "error": "Either 'group' or 'brand' must be provided",
            }

        if group is not None:
            victims = get_group_victims(group, limit=limit)
            return {
                "ok": True,
                "mode": "group",
                "group": group,
                "count": len(victims),
                "victims": [v.to_dict() for v in victims],
            }

        # brand mode: cross-group recent + fuzzy match
        assert brand is not None  # narrowed by the early-return above
        recent = get_recent_victims(limit=max(limit, 100))
        candidates = [v.name for v in recent]
        matches = match_brand(brand, candidates, mode="fuzzy", threshold=threshold)
        matched_names = {m.candidate for m in matches}
        hits = [v for v in recent if v.name in matched_names][:limit]

        return {
            "ok": True,
            "mode": "brand",
            "brand": brand,
            "threshold": threshold,
            "count": len(hits),
            "victims": [v.to_dict() for v in hits],
            "matches": [m.to_dict() for m in matches],
        }

    @mcp.tool()
    def darkweb_brand_watch(
        brand: str,
        feed: str,
        feed_format: str = "rss",
        threshold: float = 0.7,
    ) -> dict[str, Any]:
        """Dark Web Informer-style aggregator feed query for brand mentions.

        Parses a raw RSS / JSON feed string and fuzzy-matches victim entries
        against the ``brand`` query. The feed body is provided directly
        (HTTP fetching is the caller's responsibility — keeps the wrapper
        I/O-pure and matches the lib's ``parse_feed`` shape).

        Use when monitoring a brand for leak chatter / data sale postings
        across DDW-aggregated feeds.

        Args:
            brand: Brand display name to match.
            feed: Raw feed body (RSS XML or JSON array).
            feed_format: ``"rss"`` (default) or ``"json"``.
            threshold: Fuzzy-match score threshold (0.0-1.0).

        Returns:
            ``{"ok": True, "brand": ..., "feed_format": ..., "count": N,
            "victims": [...], "matches": [...]}``.
        """
        if not _HAS_LIB:
            return _missing_lib_envelope("darkweb_brand_watch")

        if feed_format not in {"rss", "json"}:
            return {
                "ok": False,
                "error": f"feed_format must be rss|json (got {feed_format!r})",
            }

        victims = parse_feed(feed, format=feed_format)
        candidates = [v.name for v in victims]
        matches = match_brand(brand, candidates, mode="fuzzy", threshold=threshold)
        matched_names = {m.candidate for m in matches}
        hits = [v for v in victims if v.name in matched_names]

        return {
            "ok": True,
            "brand": brand,
            "feed_format": feed_format,
            "feed_entries": len(victims),
            "count": len(hits),
            "victims": [v.to_dict() for v in hits],
            "matches": [m.to_dict() for m in matches],
        }
