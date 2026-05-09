"""Tests for ``wrg_mcp_server.tools.ransom_radar``.

Same strategy as ``test_tools_threat_intel.py``: stub
``ransom_radar.orchestrator`` and ``wrg_threat_intel.store`` modules,
inject canned ``TickResult`` / ``Snapshot`` objects, verify wrapper output.
"""
from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest


def _get_tools() -> dict[str, Any]:
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=9999)
    return {t.name: t for t in server._tool_manager._tools.values()}


# ── fake dataclasses ────────────────────────────────────────────────────


@dataclass(frozen=True)
class _FakeLeakHit:
    brand_id: str
    brand_name: str = ""
    victim_name: str = ""
    victim_group: str = ""
    discovery_date: str = ""
    victim_country: str = ""
    victim_sector: str = ""
    confidence: float = 0.0
    match_kind: str = ""
    matched_value: str = ""
    victim_url: str = ""


@dataclass(frozen=True)
class _FakeTickResult:
    tick_at: str
    tier: str
    brand_count: int
    leak_hits: tuple[_FakeLeakHit, ...]
    attack_surfaces: tuple[Any, ...]
    snapshot_path: Any
    diff_summary: str


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
class _FakeSnapshot:
    snapshot_date: str
    victims: tuple[_FakeVictim, ...] = ()
    subdomains: tuple[Any, ...] = ()
    asn_records: tuple[Any, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


# ── module purge / stub helpers ─────────────────────────────────────────


_RR_MODULES = (
    "ransom_radar",
    "ransom_radar.orchestrator",
    "wrg_threat_intel",
    "wrg_threat_intel.store",
)


def _purge_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block both ``ransom_radar`` and ``wrg_threat_intel.store`` imports."""
    for mod in list(sys.modules):
        if (
            mod == "ransom_radar"
            or mod.startswith("ransom_radar.")
            or mod == "wrg_threat_intel"
            or mod.startswith("wrg_threat_intel.")
        ):
            monkeypatch.delitem(sys.modules, mod, raising=False)
    for mod in _RR_MODULES:
        monkeypatch.setitem(sys.modules, mod, None)


def _install_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tick_result: _FakeTickResult | None = None,
    latest: _FakeSnapshot | None = None,
    dates: list[str] | None = None,
    snapshots_by_date: dict[str, list[_FakeSnapshot]] | None = None,
) -> dict[str, MagicMock]:
    spies: dict[str, MagicMock] = {}

    def _make(mod_name: str, attrs: dict[str, Any]) -> None:
        mod = types.ModuleType(mod_name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        monkeypatch.setitem(sys.modules, mod_name, mod)

    spies["tick_tier"] = MagicMock(return_value=tick_result)
    _make("ransom_radar", {})
    _make("ransom_radar.orchestrator", {"tick_tier": spies["tick_tier"]})

    spies["latest_snapshot"] = MagicMock(return_value=latest)
    spies["list_dates"] = MagicMock(return_value=list(dates or []))

    def _load_snapshots(d: str, base_dir: Any = None) -> list[_FakeSnapshot]:
        return (snapshots_by_date or {}).get(d, [])

    spies["load_snapshots"] = MagicMock(side_effect=_load_snapshots)

    _make("wrg_threat_intel", {})
    _make(
        "wrg_threat_intel.store",
        {
            "latest_snapshot": spies["latest_snapshot"],
            "list_dates": spies["list_dates"],
            "load_snapshots": spies["load_snapshots"],
        },
    )

    return spies


# ── ransom_radar_tick ───────────────────────────────────────────────────


def test_tick_missing_lib(monkeypatch: pytest.MonkeyPatch) -> None:
    _purge_modules(monkeypatch)
    tools = _get_tools()
    result = tools["ransom_radar_tick"].fn(tier="T1")
    assert result["ok"] is False
    assert result["tool"] == "ransom_radar_tick"


def test_tick_invalid_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stubs(monkeypatch)
    tools = _get_tools()
    result = tools["ransom_radar_tick"].fn(tier="T9")
    assert result["ok"] is False
    assert "tier" in result["error"].lower()


def test_tick_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    hit = _FakeLeakHit(
        brand_id="arcelik",
        brand_name="Arçelik",
        victim_name="Arçelik A.Ş.",
        victim_group="thegentlemen",
        discovery_date="2026-05-09",
        confidence=0.92,
        match_kind="brand_name",
    )
    tick = _FakeTickResult(
        tick_at="2026-05-09T17:00:00+00:00",
        tier="T1",
        brand_count=30,
        leak_hits=(hit,),
        attack_surfaces=(),
        snapshot_path=tmp_path / "snap.json",
        diff_summary="added_victims=1",
    )
    spies = _install_stubs(monkeypatch, tick_result=tick)
    tools = _get_tools()

    result = tools["ransom_radar_tick"].fn(
        tier="T1",
        feed_limit=50,
        leak_threshold=0.9,
        group="thegentlemen",
        skip_attack_surface=True,
    )

    assert result["ok"] is True
    assert result["tier"] == "T1"
    assert result["brand_count"] == 30
    assert result["leak_hit_count"] == 1
    assert result["attack_surface_count"] == 0
    assert result["snapshot_path"] == str(tmp_path / "snap.json")
    assert result["diff_summary"] == "added_victims=1"
    assert result["leak_hits"][0]["brand_id"] == "arcelik"
    assert result["leak_hits"][0]["confidence"] == 0.92

    args, kwargs = spies["tick_tier"].call_args
    assert kwargs["tier"] == "T1"
    assert kwargs["feed_limit"] == 50
    assert kwargs["leak_threshold"] == 0.9
    assert kwargs["leak_group"] == "thegentlemen"
    assert kwargs["include_attack_surface"] is False
    assert kwargs["include_apex_resolve"] is True


def test_tick_no_snapshot_path(monkeypatch: pytest.MonkeyPatch) -> None:
    tick = _FakeTickResult(
        tick_at="2026-05-09T17:00:00+00:00",
        tier="T2",
        brand_count=70,
        leak_hits=(),
        attack_surfaces=(),
        snapshot_path=None,
        diff_summary="no_previous",
    )
    _install_stubs(monkeypatch, tick_result=tick)
    tools = _get_tools()

    result = tools["ransom_radar_tick"].fn(tier="T2")
    assert result["ok"] is True
    assert result["snapshot_path"] is None
    assert result["leak_hit_count"] == 0


def test_tick_with_base_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    tick = _FakeTickResult(
        tick_at="t",
        tier="T1",
        brand_count=1,
        leak_hits=(),
        attack_surfaces=(),
        snapshot_path=None,
        diff_summary="",
    )
    spies = _install_stubs(monkeypatch, tick_result=tick)
    tools = _get_tools()

    result = tools["ransom_radar_tick"].fn(tier="T1", base_dir=str(tmp_path))
    assert result["ok"] is True
    args, kwargs = spies["tick_tier"].call_args
    assert kwargs["base_dir"] is not None
    assert str(kwargs["base_dir"]) == str(tmp_path)


# ── ransom_radar_status ─────────────────────────────────────────────────


def test_status_missing_lib(monkeypatch: pytest.MonkeyPatch) -> None:
    _purge_modules(monkeypatch)
    tools = _get_tools()
    result = tools["ransom_radar_status"].fn()
    assert result["ok"] is False
    assert result["tool"] == "ransom_radar_status"


def test_status_no_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stubs(monkeypatch, latest=None)
    tools = _get_tools()
    result = tools["ransom_radar_status"].fn()
    assert result["ok"] is True
    assert result["snapshot"] is None
    assert "no snapshots" in result["message"]


def test_status_latest_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    snap = _FakeSnapshot(
        snapshot_date="2026-05-09",
        victims=(
            _FakeVictim(
                name="Arçelik",
                group="thegentlemen",
                discovery_date="2026-05-09",
                description="matched brand='arcelik' (brand_name, score=0.95)",
            ),
            _FakeVictim(name="Other"),
        ),
        metadata={"tier": "T1", "brand_count": 30},
    )
    _install_stubs(monkeypatch, latest=snap)
    tools = _get_tools()
    result = tools["ransom_radar_status"].fn()
    assert result["ok"] is True
    assert result["snapshot"]["snapshot_date"] == "2026-05-09"
    assert result["snapshot"]["victim_count"] == 2
    assert result["snapshot"]["metadata"]["tier"] == "T1"


def test_status_latest_brand_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    snap = _FakeSnapshot(
        snapshot_date="2026-05-09",
        victims=(
            _FakeVictim(
                name="Arçelik",
                description="matched brand='arcelik' (brand_name, score=0.95)",
            ),
            _FakeVictim(name="Other", description="matched brand='other' (...)"),
        ),
    )
    _install_stubs(monkeypatch, latest=snap)
    tools = _get_tools()
    result = tools["ransom_radar_status"].fn(brand="arcelik")
    assert result["ok"] is True
    assert result["snapshot"]["brand"] == "arcelik"
    assert result["snapshot"]["matched_count"] == 1
    assert result["snapshot"]["matched_victims"][0]["name"] == "Arçelik"


def test_status_last_n_no_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stubs(monkeypatch, dates=[])
    tools = _get_tools()
    result = tools["ransom_radar_status"].fn(last_n=5)
    assert result["ok"] is True
    assert result["snapshots"] == []


def test_status_last_n_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    snap_d1 = _FakeSnapshot(snapshot_date="2026-05-08", metadata={"tier": "T1"})
    snap_d2 = _FakeSnapshot(snapshot_date="2026-05-09", metadata={"tier": "T1"})
    spies = _install_stubs(
        monkeypatch,
        dates=["2026-05-08", "2026-05-09"],
        snapshots_by_date={
            "2026-05-08": [snap_d1],
            "2026-05-09": [snap_d2],
        },
    )
    tools = _get_tools()
    result = tools["ransom_radar_status"].fn(last_n=5)

    assert result["ok"] is True
    assert result["count"] == 2
    # Sorted reverse: newest first
    assert result["snapshots"][0]["snapshot_date"] == "2026-05-09"
    assert result["snapshots"][1]["snapshot_date"] == "2026-05-08"
    spies["list_dates"].assert_called_once()


def test_status_last_n_with_base_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    spies = _install_stubs(monkeypatch, dates=[])
    tools = _get_tools()
    tools["ransom_radar_status"].fn(last_n=3, base_dir=str(tmp_path))
    args, kwargs = spies["list_dates"].call_args
    assert str(kwargs["base_dir"]) == str(tmp_path)


# ── registration ────────────────────────────────────────────────────────


def test_ransom_radar_tools_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stubs(monkeypatch)
    tools = _get_tools()
    for name in ("ransom_radar_tick", "ransom_radar_status"):
        assert name in tools


def test_ransom_radar_tools_registered_when_lib_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _purge_modules(monkeypatch)
    tools = _get_tools()
    for name in ("ransom_radar_tick", "ransom_radar_status"):
        assert name in tools
