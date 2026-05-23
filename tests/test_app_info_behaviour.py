"""Behavioural coverage for the `app_info` MCP tool.

Closes the §6 "behavioural tests for app_info" deferred item from
docs/decisions/MCP_TOOL_AUDIT_2026_04_25.md (PR #295). app_info
previously had only registration-existence coverage in
test_local_tools.py::test_register_local_tools_adds_tools — this file
adds real value-correctness, error-path, and envelope-shape assertions
against the live registry (no mocks; behavioural-by-design).

Audit §1 row 2 promises: success → {ok: True, ...}; not-found →
{ok: False, error}. These tests pin both branches.
"""

from __future__ import annotations

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


# Monorepo-bound test guard: these tests require the WRG monorepo
# (apps/wrg_governance/.../registry.json + apps/wrg_mcp_server/pyproject.toml)
# to be present. In the standalone wrg-mcp-server PyPI repo / GitHub CI,
# the registry doesn't exist, so app_info("wrg_mcp_server") returns
# ok=False and these tests skip cleanly instead of failing.
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
async def test_app_info_envelope_first_key_is_ok() -> None:
    """The {ok, ...} envelope convention requires `ok` to be the first
    field — same shape audit §3.1 calls out as the ~88% standard, and
    the same convention used by the connector_status fix in 018dd82."""
    result = await _call("app_info", name="wrg_mcp_server")
    assert list(result.keys())[0] == "ok", (
        f"app_info envelope first key must be 'ok', got: "
        f"{list(result.keys())[:3]}..."
    )


# ── success path: real registry fixture ──────────────────────────────


@requires_monorepo
@pytest.mark.asyncio
async def test_app_info_known_app_returns_full_envelope() -> None:
    """A real, registered app returns {ok: True} with every documented
    field present. Fixture: `wrg_mcp_server` itself — guaranteed to
    exist (this test runs from inside that app) and pinned in
    apps/app_registry/.../registry.json.

    Behavioural-by-design: uses live registry.json + live pyproject.toml
    so a contract drift in either source surfaces here, not just at
    runtime in production."""
    result = await _call("app_info", name="wrg_mcp_server")
    assert result["ok"] is True
    # Every field documented in the source contract (local_tools.py:251-261)
    # must be present — a missing key is a contract regression.
    expected_keys = {
        "ok", "name", "registry", "version", "description",
        "dependencies", "requires_python", "test_files", "last_commit",
    }
    assert expected_keys.issubset(set(result.keys())), (
        f"Missing contract keys: {expected_keys - set(result.keys())}"
    )
    assert result["name"] == "wrg_mcp_server"
    # Registry entry must be a dict mirroring the registry.json row.
    assert isinstance(result["registry"], dict)
    assert result["registry"].get("name") == "wrg_mcp_server"


@requires_monorepo
@pytest.mark.asyncio
async def test_app_info_pyproject_metadata_populated() -> None:
    """pyproject.toml-derived fields must be real values, not the
    "unknown"/empty fallbacks. wrg_mcp_server has a published pyproject
    so version and description are guaranteed populated — if these come
    back as fallbacks, _read_pyproject() is broken or pyproject.toml
    drifted."""
    result = await _call("app_info", name="wrg_mcp_server")
    assert result["ok"] is True
    assert result["version"] != "unknown", (
        "version fell back to 'unknown' — _read_pyproject failed or "
        "pyproject.toml lost its [project].version key"
    )
    assert result["description"] != "", (
        "description fell back to empty — pyproject.toml lost its "
        "[project].description key"
    )
    assert isinstance(result["dependencies"], list)
    assert isinstance(result["requires_python"], str)


@requires_monorepo
@pytest.mark.asyncio
async def test_app_info_test_files_count_matches_filesystem() -> None:
    """test_files count must match what _count_tests sees on disk
    (test_*.py files under apps/<name>/tests/). A drift here means
    _count_tests is miscounting (recursion bug, glob-pattern change,
    etc.) — surfaces immediately rather than during a future test
    coverage audit."""
    result = await _call("app_info", name="wrg_mcp_server")
    assert result["ok"] is True
    assert isinstance(result["test_files"], int)
    # We're inside wrg_mcp_server's test suite right now; there must be
    # at least the file containing this test. Asserting a strict lower
    # bound (≥ 1) is enough — exact count would couple this test to the
    # rest of the suite and create churn.
    assert result["test_files"] >= 1, (
        f"test_files={result['test_files']} but this very file is one "
        f"of them — _count_tests glob is broken"
    )


@requires_monorepo
@pytest.mark.asyncio
async def test_app_info_last_commit_is_string() -> None:
    """last_commit must always be a string — never None, never raised.
    _last_commit catches all exceptions and returns 'unknown' on
    failure, so the contract is "always a string". Pinning this so a
    future refactor doesn't accidentally let the exception escape."""
    result = await _call("app_info", name="wrg_mcp_server")
    assert result["ok"] is True
    assert isinstance(result["last_commit"], str)
    assert result["last_commit"] != ""


# ── error path: not-found ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_app_info_unknown_name_returns_structured_error() -> None:
    """Unknown app name returns {ok: False, error: <message>} per
    audit §1 row 2 promise. Critically: must NOT raise — MCP tools
    return structured errors so Claude can read them, never raise."""
    bogus = "definitely-not-an-app-zz9-plural-z-alpha"
    result = await _call("app_info", name=bogus)
    assert result["ok"] is False
    assert "error" in result
    assert isinstance(result["error"], str)
    # Error must mention the bad name so the caller can correlate it
    # to their input — a generic "not found" loses information.
    assert bogus in result["error"], (
        f"error should reference the queried name {bogus!r}, "
        f"got: {result['error']!r}"
    )


@pytest.mark.asyncio
async def test_app_info_empty_name_returns_structured_error() -> None:
    """Empty-string name doesn't match any registry entry, so the
    not-found path runs. Tests that the empty-input edge case stays on
    the structured-error contract (no crash, no IndexError, no None)."""
    result = await _call("app_info", name="")
    assert result["ok"] is False
    assert "error" in result
    assert isinstance(result["error"], str)
