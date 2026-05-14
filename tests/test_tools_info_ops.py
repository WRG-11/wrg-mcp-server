"""Tests for ``wrg_mcp_server.tools.info_ops``.

Coverage strategy:
  * **Library-missing path** — purge ``wrg_threat_intel`` from sys.modules,
    invoke the tool, expect the missing-lib envelope.
  * **Happy path** — when ``wrg_threat_intel`` is actually installed in the
    dev env, exercise the real corpus: ``modus=info-ops`` must yield the
    ``russia_nexus_info_ops`` actor; ``modus=double-extortion`` must yield
    multiple ransomware actors.
  * **Validation** — unknown ``modus`` returns an error envelope with the
    list of valid values; unknown ``actor_id`` returns an error envelope
    with available actors for the supplied modus.
  * **Include flags** — ``include_sigma=False`` / ``include_incidents=False``
    drop those fields from each actor entry; counts go to zero.
"""
from __future__ import annotations

import sys
from typing import Any

import pytest


def _get_tools() -> dict[str, Any]:
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=9999)
    return {t.name: t for t in server._tool_manager._tools.values()}


def _purge_threat_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block ``wrg_threat_intel`` imports so the next ``import`` raises."""
    for mod in list(sys.modules):
        if mod == "wrg_threat_intel" or mod.startswith("wrg_threat_intel."):
            monkeypatch.delitem(sys.modules, mod, raising=False)
    for mod in (
        "wrg_threat_intel",
        "wrg_threat_intel.breach",
        "wrg_threat_intel.breach.corpus",
        "wrg_threat_intel.breach.sigma",
        "wrg_threat_intel.breach.sigma.rule_builder",
        "wrg_threat_intel.breach.types",
    ):
        monkeypatch.setitem(sys.modules, mod, None)


def _wrg_threat_intel_available() -> bool:
    try:
        import wrg_threat_intel  # noqa: F401

        return True
    except ImportError:
        return False


_HAS_LIB = _wrg_threat_intel_available()


class TestInfoOpsMissingLib:
    def test_missing_lib_envelope(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _purge_threat_modules(monkeypatch)
        # Re-import the tools module under poisoned sys.modules so the
        # try/except ImportError branch runs.
        monkeypatch.delitem(
            sys.modules, "wrg_mcp_server.tools.info_ops", raising=False
        )
        tools = _get_tools()
        result = tools["info_ops_detect"].fn()
        assert result == {
            "ok": False,
            "error": "wrg_threat_intel not installed",
            "tool": "info_ops_detect",
        }


@pytest.mark.skipif(
    not _HAS_LIB, reason="wrg_threat_intel not installed in this env"
)
class TestInfoOpsHappyPath:
    def test_default_info_ops_returns_russia_nexus(self) -> None:
        tools = _get_tools()
        result = tools["info_ops_detect"].fn()
        assert result["ok"] is True
        assert result["modus"] == "info-ops"
        actor_ids = [a["id"] for a in result["matched_actors"]]
        assert "russia_nexus_info_ops" in actor_ids
        assert result["actor_count"] >= 1
        assert result["sigma_rule_count"] >= 1
        assert "summary" in result

    def test_actor_entry_shape(self) -> None:
        tools = _get_tools()
        result = tools["info_ops_detect"].fn()
        russia = next(
            a for a in result["matched_actors"] if a["id"] == "russia_nexus_info_ops"
        )
        # Required keys per the tool contract.
        for key in (
            "display_name",
            "aliases",
            "status",
            "modus_operandi",
            "sophistication",
            "ttps_mitre",
            "origin_hints",
            "incidents",
            "sigma_rules",
        ):
            assert key in russia, f"missing key: {key}"
        assert "info-ops" in russia["modus_operandi"]

    def test_actor_id_override_returns_single_actor(self) -> None:
        tools = _get_tools()
        result = tools["info_ops_detect"].fn(actor_id="russia_nexus_info_ops")
        assert result["ok"] is True
        assert result["actor_count"] == 1
        assert result["matched_actors"][0]["id"] == "russia_nexus_info_ops"

    def test_unknown_actor_id_returns_error_with_available_list(self) -> None:
        tools = _get_tools()
        result = tools["info_ops_detect"].fn(actor_id="does_not_exist")
        assert result["ok"] is False
        assert "unknown actor_id" in result["error"]
        assert "available_actors_for_modus" in result
        assert "russia_nexus_info_ops" in result["available_actors_for_modus"]

    def test_unknown_modus_returns_error_with_valid_values(self) -> None:
        tools = _get_tools()
        result = tools["info_ops_detect"].fn(modus="not-a-real-modus")
        assert result["ok"] is False
        assert "unknown modus_operandi" in result["error"]
        assert "info-ops" in result["valid_values"]
        assert "double-extortion" in result["valid_values"]

    def test_double_extortion_modus_returns_ransomware_actors(self) -> None:
        tools = _get_tools()
        result = tools["info_ops_detect"].fn(modus="double-extortion")
        assert result["ok"] is True
        assert result["actor_count"] >= 1
        # Russia-nexus is info-ops only — must NOT appear here.
        actor_ids = [a["id"] for a in result["matched_actors"]]
        assert "russia_nexus_info_ops" not in actor_ids

    def test_include_flags_off_drops_fields_and_zeros_counts(self) -> None:
        tools = _get_tools()
        result = tools["info_ops_detect"].fn(
            include_sigma=False, include_incidents=False
        )
        assert result["ok"] is True
        assert result["sigma_rule_count"] == 0
        assert result["incident_count"] == 0
        for actor in result["matched_actors"]:
            assert "sigma_rules" not in actor
            assert "incidents" not in actor

    def test_mitre_technique_filter_matches_russia_nexus(self) -> None:
        tools = _get_tools()
        # T1585.001 is the INFO_OPS social-media accounts sub-technique
        # tagged on russia_nexus_info_ops in PR #35.
        result = tools["info_ops_detect"].fn(mitre_technique="T1585.001")
        assert result["ok"] is True
        assert result["technique_filter"] == "T1585.001"
        actor_ids = [a["id"] for a in result["matched_actors"]]
        assert "russia_nexus_info_ops" in actor_ids
        assert "T1585.001" in result["summary"]

    def test_mitre_technique_filter_unknown_returns_empty(self) -> None:
        tools = _get_tools()
        result = tools["info_ops_detect"].fn(mitre_technique="T9999.999")
        assert result["ok"] is True
        assert result["actor_count"] == 0
        assert result["matched_actors"] == []

    def test_mitre_technique_filter_combines_with_modus(self) -> None:
        tools = _get_tools()
        # Russia-nexus uses T1583 (Acquire Infrastructure parent), but
        # restricting to modus=double-extortion drops it because the
        # Russia-nexus actor is info-ops only.
        result = tools["info_ops_detect"].fn(
            modus="double-extortion", mitre_technique="T1583"
        )
        assert result["ok"] is True
        actor_ids = [a["id"] for a in result["matched_actors"]]
        assert "russia_nexus_info_ops" not in actor_ids
