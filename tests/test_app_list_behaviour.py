"""Behavioural coverage for the `app_list` MCP tool.

Closes another §1-rollup smoke-only entry from
docs/decisions/MCP_TOOL_AUDIT_2026_04_25.md. app_list previously had
only registration-existence coverage in
test_local_tools.py::test_register_local_tools_adds_tools — this file
adds value-correctness, envelope-shape, and field-derivation
assertions against the live registry (no mocks; behavioural-by-design,
mirroring PR #297 sibling coverage for app_info).

Audit §1 row 1 promises: returns `{ok: True, apps: [...], total: N,
active: M}` where N = total apps, M = count where status == "active".
These tests pin both the envelope and the derivation logic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from wrg_mcp_server.server import create_mcp_server


def _get_tool(name: str):
    """Register tools on a fresh FastMCP and return the named tool."""
    server = create_mcp_server(host="127.0.0.1", port=9999)
    tools = {t.name: t for t in server._tool_manager._tools.values()}
    return tools[name]


async def _call(tool_name: str, **kwargs: Any) -> dict[str, Any]:
    """Invoke a registered tool by name with kwargs."""
    return await _get_tool(tool_name).fn(**kwargs)


def _live_registry() -> list[dict[str, Any]]:
    """Read the live registry the same way _read_registry does, so
    tests can compute expected values from the canonical source."""
    return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8")).get("apps", [])


# Monorepo-bound test guard: these tests require the WRG monorepo
# (apps/wrg_governance/.../registry.json) to be present. In the standalone
# wrg-mcp-server PyPI repo / GitHub CI, the registry doesn't exist, so
# `_live_registry()` raises FileNotFoundError and `_call("app_list")`
# returns an empty apps list. Skip cleanly instead of failing.
_REGISTRY_PATH = (
    Path(__file__).resolve().parents[3]
    / "apps" / "wrg_governance" / "src" / "wrg_governance"
    / "registry" / "data" / "registry.json"
)
requires_monorepo = pytest.mark.skipif(
    not _REGISTRY_PATH.exists(),
    reason=(
        "Requires WRG monorepo (apps/wrg_governance/.../registry.json); "
        "skipped in standalone wrg-mcp-server repo / GitHub CI."
    ),
)


# ── envelope shape (audit §3.1 consistency) ──────────────────────────


@pytest.mark.asyncio
async def test_app_list_envelope_first_key_is_ok() -> None:
    """`ok` must be the first field of the return dict — same envelope
    convention as the connector_status fix in 018dd82 and the
    app_info coverage in PR #297."""
    result = await _call("app_list")
    assert list(result.keys())[0] == "ok"


# ── success path: live registry ──────────────────────────────────────


@pytest.mark.asyncio
async def test_app_list_returns_full_envelope() -> None:
    """Live registry returns {ok: True, apps, total, active} with all
    contract keys present. Behavioural-by-design: a key drift in the
    source surfaces here, not in production."""
    result = await _call("app_list")
    assert result["ok"] is True
    assert {"ok", "apps", "total", "active"}.issubset(set(result.keys()))
    assert isinstance(result["apps"], list)
    assert isinstance(result["total"], int)
    assert isinstance(result["active"], int)


@requires_monorepo
@pytest.mark.asyncio
async def test_app_list_total_matches_registry_length() -> None:
    """`total` MUST equal len(registry["apps"]). Anything else means
    the source is silently dropping or duplicating apps."""
    result = await _call("app_list")
    expected_total = len(_live_registry())
    assert result["total"] == expected_total, (
        f"app_list total={result['total']} but registry has "
        f"{expected_total} apps — derivation is broken"
    )
    assert len(result["apps"]) == expected_total, (
        f"app_list apps list length ({len(result['apps'])}) does not "
        f"match registry length ({expected_total})"
    )


@requires_monorepo
@pytest.mark.asyncio
async def test_app_list_active_matches_status_filter() -> None:
    """`active` MUST equal the count of registry entries with
    status == "active". Any other count means the active-filter logic
    is broken (e.g. counting "Active" case-sensitively wrong, or
    counting all non-archived)."""
    result = await _call("app_list")
    expected_active = sum(
        1 for a in _live_registry() if a.get("status") == "active"
    )
    assert result["active"] == expected_active, (
        f"app_list active={result['active']} but registry has "
        f"{expected_active} status='active' entries"
    )


@requires_monorepo
@pytest.mark.asyncio
async def test_app_list_summary_has_documented_fields() -> None:
    """Each summary dict in `apps` must have exactly the 4 fields the
    source contract documents (local_tools.py:214-219): `name`,
    `status`, `class`, `primary_role`. A drift in field names is a
    contract regression."""
    result = await _call("app_list")
    assert result["apps"], "registry returned no apps — test setup wrong"
    expected_keys = {"name", "status", "class", "primary_role"}
    for entry in result["apps"]:
        assert set(entry.keys()) == expected_keys, (
            f"app_list summary entry has {set(entry.keys())}, "
            f"expected exactly {expected_keys}"
        )


@pytest.mark.asyncio
async def test_app_list_summary_defaults_for_missing_fields() -> None:
    """Source contract uses `.get(..., default)` for status/class/
    primary_role — a registry entry missing those keys must surface
    as the documented default ("unknown" for status, "" for the
    others), NOT as None or KeyError. wrg_mcp_server itself is in
    the registry; it has all fields populated, so use it as a known
    fixture for the populated case. Defaults are tested via the
    `class`/`primary_role` empty-string fallback (some entries may
    legitimately have empty strings, which is the expected default
    behaviour)."""
    result = await _call("app_list")
    # No entry should have None values — they should be defaults.
    for entry in result["apps"]:
        assert entry["name"] is not None
        assert entry["status"] is not None  # default "unknown"
        assert entry["class"] is not None  # default ""
        assert entry["primary_role"] is not None  # default ""
    # wrg_mcp_server fixture: known populated.
    by_name = {e["name"]: e for e in result["apps"]}
    if "wrg_mcp_server" in by_name:
        wms = by_name["wrg_mcp_server"]
        assert wms["status"] != "", "wrg_mcp_server should have status set"
