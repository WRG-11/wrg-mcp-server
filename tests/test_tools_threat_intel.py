"""Tests for ``wrg_mcp_server.tools.threat_intel``.

Strategy:
  * Library-missing path — clear ``wrg_threat_intel.*`` from ``sys.modules``
    so register-time import fails. Tool returns the missing-lib envelope.
  * Happy path — inject minimal fake ``wrg_threat_intel.*`` modules with
    stub functions returning canned dataclass-like objects. Register
    builds tools that call those stubs.

We never touch the real ``wrg_threat_intel`` package.
"""
from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

# ── shared helpers ──────────────────────────────────────────────────────


def _get_tools() -> dict[str, Any]:
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=9999)
    return {t.name: t for t in server._tool_manager._tools.values()}


@dataclass(frozen=True)
class _FakeSubdomain:
    fqdn: str
    apex: str
    source: str
    ip: str | None = None
    first_seen: str | None = None
    issuer: str | None = None
    not_before: str | None = None
    not_after: str | None = None


@dataclass(frozen=True)
class _FakeASN:
    ip: str
    asn: int | None = None
    netname: str = ""
    country: str = ""
    maintainer: str = ""
    description: str = ""
    prefix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ip": self.ip,
            "asn": self.asn,
            "netname": self.netname,
            "country": self.country,
            "maintainer": self.maintainer,
            "description": self.description,
            "prefix": self.prefix,
        }


@dataclass(frozen=True)
class _FakeVictim:
    name: str
    group: str = ""
    discovery_date: str = ""
    url: str = ""
    country: str = ""
    sector: str = ""
    description: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "group": self.group,
            "discovery_date": self.discovery_date,
            "url": self.url,
            "country": self.country,
            "sector": self.sector,
            "description": self.description,
            "source": self.source,
        }


@dataclass(frozen=True)
class _FakeBrandMatch:
    query: str
    candidate: str
    score: float
    mode: str
    matched: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "candidate": self.candidate,
            "score": self.score,
            "mode": self.mode,
            "matched": self.matched,
        }


_THREAT_MODULES = (
    "wrg_threat_intel",
    "wrg_threat_intel.feeds",
    "wrg_threat_intel.feeds.ddw_aggregator",
    "wrg_threat_intel.feeds.ransomware_live",
    "wrg_threat_intel.matching",
    "wrg_threat_intel.matching.brand",
    "wrg_threat_intel.recon",
    "wrg_threat_intel.recon.passive",
    "wrg_threat_intel.recon.passive.ct_log",
    "wrg_threat_intel.recon.passive.dns",
    "wrg_threat_intel.recon.passive.rdap",
)


def _purge_threat_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block ``wrg_threat_intel`` imports so the next ``import`` raises.

    Sets ``sys.modules[name] = None`` for every wrg_threat_intel submodule
    we touch; Python's import system treats a ``None`` entry as a poisoned
    cache and raises ``ModuleNotFoundError`` on access. This works even
    when the lib is editable-installed in the local dev env.
    """
    for mod in list(sys.modules):
        if mod == "wrg_threat_intel" or mod.startswith("wrg_threat_intel."):
            monkeypatch.delitem(sys.modules, mod, raising=False)
    for mod in _THREAT_MODULES:
        monkeypatch.setitem(sys.modules, mod, None)


def _install_threat_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    search_apex_result: list[_FakeSubdomain] | None = None,
    probe_patterns_result: list[_FakeSubdomain] | None = None,
    resolve_result: str | None = "10.0.0.1",
    lookup_ip_result: _FakeASN | None = None,
    get_group_victims_result: list[_FakeVictim] | None = None,
    get_recent_victims_result: list[_FakeVictim] | None = None,
    match_brand_result: list[_FakeBrandMatch] | None = None,
    parse_feed_result: list[_FakeVictim] | None = None,
) -> dict[str, MagicMock]:
    """Inject fake wrg_threat_intel modules into sys.modules.

    Returns a dict of MagicMock spies for the swapped functions so tests
    can inspect call args.
    """
    spies: dict[str, MagicMock] = {}

    def _make(mod_name: str, attrs: dict[str, Any]) -> None:
        mod = types.ModuleType(mod_name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        monkeypatch.setitem(sys.modules, mod_name, mod)

    # types-equivalent — only the dataclasses the lib actually uses
    _make(
        "wrg_threat_intel",
        {},
    )
    _make("wrg_threat_intel.feeds", {})
    _make("wrg_threat_intel.matching", {})
    _make("wrg_threat_intel.recon", {})
    _make("wrg_threat_intel.recon.passive", {})

    spies["search_apex"] = MagicMock(return_value=search_apex_result or [])
    _make(
        "wrg_threat_intel.recon.passive.ct_log",
        {"search_apex": spies["search_apex"]},
    )

    spies["probe_patterns"] = MagicMock(return_value=probe_patterns_result or [])
    spies["resolve"] = MagicMock(return_value=resolve_result)
    _make(
        "wrg_threat_intel.recon.passive.dns",
        {"probe_patterns": spies["probe_patterns"], "resolve": spies["resolve"]},
    )

    spies["lookup_ip"] = MagicMock(
        return_value=lookup_ip_result or _FakeASN(ip="10.0.0.1")
    )
    _make(
        "wrg_threat_intel.recon.passive.rdap",
        {"lookup_ip": spies["lookup_ip"]},
    )

    spies["get_group_victims"] = MagicMock(return_value=get_group_victims_result or [])
    spies["get_recent_victims"] = MagicMock(
        return_value=get_recent_victims_result or []
    )
    _make(
        "wrg_threat_intel.feeds.ransomware_live",
        {
            "get_group_victims": spies["get_group_victims"],
            "get_recent_victims": spies["get_recent_victims"],
        },
    )

    spies["match_brand"] = MagicMock(return_value=match_brand_result or [])
    _make(
        "wrg_threat_intel.matching.brand",
        {"match_brand": spies["match_brand"]},
    )

    spies["parse_feed"] = MagicMock(return_value=parse_feed_result or [])
    _make(
        "wrg_threat_intel.feeds.ddw_aggregator",
        {"parse_feed": spies["parse_feed"]},
    )

    return spies


# ── attack_surface_passive ──────────────────────────────────────────────


def test_attack_surface_passive_missing_lib(monkeypatch: pytest.MonkeyPatch) -> None:
    _purge_threat_modules(monkeypatch)
    tools = _get_tools()
    result = tools["attack_surface_passive"].fn(domain="arcelik.com")
    assert result["ok"] is False
    assert "wrg_threat_intel" in result["error"]
    assert result["tool"] == "attack_surface_passive"


def test_attack_surface_passive_happy_default_patterns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spies = _install_threat_stubs(
        monkeypatch,
        search_apex_result=[
            _FakeSubdomain(
                fqdn="vpn.arcelik.com",
                apex="arcelik.com",
                source="ct_log",
                first_seen="2026-01-01",
                issuer="Let's Encrypt",
            ),
        ],
        probe_patterns_result=[
            _FakeSubdomain(
                fqdn="jira.arcelik.com",
                apex="arcelik.com",
                source="dns_probe",
                ip="10.0.0.5",
            ),
        ],
        resolve_result="10.0.0.1",
        lookup_ip_result=_FakeASN(
            ip="10.0.0.1", asn=15169, netname="ARC-NET", country="TR"
        ),
    )
    tools = _get_tools()
    result = tools["attack_surface_passive"].fn(domain="arcelik.com")

    assert result["ok"] is True
    assert result["domain"] == "arcelik.com"
    assert "atlas" in result["patterns_used"]
    assert "vpn" in result["patterns_used"]
    assert len(result["ct_hits"]) == 1
    assert result["ct_hits"][0]["fqdn"] == "vpn.arcelik.com"
    assert result["ct_hits"][0]["issuer"] == "Let's Encrypt"
    assert len(result["live_subs"]) == 1
    assert result["live_subs"][0]["ip"] == "10.0.0.5"
    assert result["apex_ip"] == "10.0.0.1"
    assert result["asn"]["asn"] == 15169
    assert "1 CT hit" in result["summary"]

    spies["search_apex"].assert_called_once()
    spies["probe_patterns"].assert_called_once()
    spies["resolve"].assert_called_once_with("arcelik.com")
    spies["lookup_ip"].assert_called_once_with("10.0.0.1")


def test_attack_surface_passive_custom_patterns_no_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spies = _install_threat_stubs(
        monkeypatch,
        resolve_result=None,
    )
    tools = _get_tools()
    result = tools["attack_surface_passive"].fn(
        domain="example.com",
        patterns=["api", "admin"],
        include_apex_resolve=False,
    )

    assert result["ok"] is True
    assert result["patterns_used"] == ["api", "admin"]
    assert result["apex_ip"] is None
    assert result["asn"] is None
    spies["resolve"].assert_not_called()
    spies["lookup_ip"].assert_not_called()
    args, kwargs = spies["search_apex"].call_args
    assert args[0] == "example.com"
    assert kwargs["patterns"] == ["api", "admin"]


def test_attack_surface_passive_resolve_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spies = _install_threat_stubs(monkeypatch, resolve_result=None)
    tools = _get_tools()
    result = tools["attack_surface_passive"].fn(domain="dead.example")
    assert result["ok"] is True
    assert result["apex_ip"] is None
    assert result["asn"] is None
    spies["lookup_ip"].assert_not_called()


# ── ransomware_lookup ───────────────────────────────────────────────────


def test_ransomware_lookup_missing_lib(monkeypatch: pytest.MonkeyPatch) -> None:
    _purge_threat_modules(monkeypatch)
    tools = _get_tools()
    result = tools["ransomware_lookup"].fn(group="thegentlemen")
    assert result["ok"] is False
    assert result["tool"] == "ransomware_lookup"


def test_ransomware_lookup_requires_group_or_brand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_threat_stubs(monkeypatch)
    tools = _get_tools()
    result = tools["ransomware_lookup"].fn()
    assert result["ok"] is False
    assert "group" in result["error"] or "brand" in result["error"]


def test_ransomware_lookup_group_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    victims = [
        _FakeVictim(
            name="Acme Corp",
            group="thegentlemen",
            discovery_date="2026-05-01",
            country="TR",
            sector="manufacturing",
        ),
    ]
    spies = _install_threat_stubs(monkeypatch, get_group_victims_result=victims)
    tools = _get_tools()
    result = tools["ransomware_lookup"].fn(group="thegentlemen", limit=25)

    assert result["ok"] is True
    assert result["mode"] == "group"
    assert result["group"] == "thegentlemen"
    assert result["count"] == 1
    assert result["victims"][0]["name"] == "Acme Corp"
    spies["get_group_victims"].assert_called_once_with("thegentlemen", limit=25)


def test_ransomware_lookup_brand_mode_filters_recent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recent = [
        _FakeVictim(name="Arçelik A.Ş.", group="g1", discovery_date="2026-05-01"),
        _FakeVictim(name="Foo Co", group="g1", discovery_date="2026-05-02"),
        _FakeVictim(name="Beko AS", group="g2", discovery_date="2026-05-03"),
    ]
    matches = [
        _FakeBrandMatch(
            query="Arçelik",
            candidate="Arçelik A.Ş.",
            score=0.95,
            mode="fuzzy",
            matched=True,
        )
    ]
    spies = _install_threat_stubs(
        monkeypatch,
        get_recent_victims_result=recent,
        match_brand_result=matches,
    )
    tools = _get_tools()
    result = tools["ransomware_lookup"].fn(brand="Arçelik", threshold=0.7)

    assert result["ok"] is True
    assert result["mode"] == "brand"
    assert result["brand"] == "Arçelik"
    assert result["count"] == 1
    assert result["victims"][0]["name"] == "Arçelik A.Ş."
    assert result["matches"][0]["candidate"] == "Arçelik A.Ş."
    # Brand mode pulls extra (max(limit, 100))
    spies["get_recent_victims"].assert_called_once()
    args, kwargs = spies["get_recent_victims"].call_args
    assert kwargs["limit"] == 100


def test_ransomware_lookup_brand_no_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    recent = [_FakeVictim(name="Other Inc", group="g")]
    _install_threat_stubs(
        monkeypatch,
        get_recent_victims_result=recent,
        match_brand_result=[],
    )
    tools = _get_tools()
    result = tools["ransomware_lookup"].fn(brand="Nope")
    assert result["ok"] is True
    assert result["count"] == 0
    assert result["victims"] == []


# ── darkweb_brand_watch ─────────────────────────────────────────────────


def test_darkweb_brand_watch_missing_lib(monkeypatch: pytest.MonkeyPatch) -> None:
    _purge_threat_modules(monkeypatch)
    tools = _get_tools()
    result = tools["darkweb_brand_watch"].fn(brand="Foo", feed="<rss/>")
    assert result["ok"] is False
    assert result["tool"] == "darkweb_brand_watch"


def test_darkweb_brand_watch_invalid_format(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_threat_stubs(monkeypatch)
    tools = _get_tools()
    result = tools["darkweb_brand_watch"].fn(brand="Foo", feed="...", feed_format="xml")
    assert result["ok"] is False
    assert "feed_format" in result["error"]


def test_darkweb_brand_watch_rss_happy(monkeypatch: pytest.MonkeyPatch) -> None:
    victims = [
        _FakeVictim(name="Arçelik", group="lockbit", discovery_date="2026-05-01"),
        _FakeVictim(name="Other Co", group="lockbit", discovery_date="2026-05-02"),
    ]
    matches = [
        _FakeBrandMatch(
            query="Arçelik",
            candidate="Arçelik",
            score=1.0,
            mode="fuzzy",
            matched=True,
        )
    ]
    spies = _install_threat_stubs(
        monkeypatch,
        parse_feed_result=victims,
        match_brand_result=matches,
    )
    tools = _get_tools()
    raw = "<rss><channel><item><title>Arçelik claims</title></item></channel></rss>"
    result = tools["darkweb_brand_watch"].fn(brand="Arçelik", feed=raw, feed_format="rss")

    assert result["ok"] is True
    assert result["brand"] == "Arçelik"
    assert result["feed_format"] == "rss"
    assert result["feed_entries"] == 2
    assert result["count"] == 1
    assert result["victims"][0]["name"] == "Arçelik"
    spies["parse_feed"].assert_called_once_with(raw, format="rss")


def test_darkweb_brand_watch_json_format(monkeypatch: pytest.MonkeyPatch) -> None:
    spies = _install_threat_stubs(monkeypatch, parse_feed_result=[])
    tools = _get_tools()
    result = tools["darkweb_brand_watch"].fn(brand="X", feed="[]", feed_format="json")
    assert result["ok"] is True
    assert result["count"] == 0
    spies["parse_feed"].assert_called_once_with("[]", format="json")


# ── registration ────────────────────────────────────────────────────────


def test_threat_intel_tools_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_threat_stubs(monkeypatch)
    tools = _get_tools()
    for name in ("attack_surface_passive", "ransomware_lookup", "darkweb_brand_watch"):
        assert name in tools, f"{name} not registered"


def test_threat_intel_tools_registered_when_lib_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tools must register even without the lib — they just return error envelopes."""
    _purge_threat_modules(monkeypatch)
    tools = _get_tools()
    for name in ("attack_surface_passive", "ransomware_lookup", "darkweb_brand_watch"):
        assert name in tools
