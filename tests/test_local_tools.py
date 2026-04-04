"""Tests for local WRG tool wrappers."""

from __future__ import annotations

import asyncio
import json
import sys
from unittest.mock import AsyncMock, patch

import pytest

from wrg_mcp_server.local_tools import _run_cli, register_local_tools, _REPO_ROOT


# ── _run_cli unit tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_cli_success() -> None:
    """Successful command returns ok=True and parsed output."""
    result = await _run_cli(sys.executable, "-c", "print('hello')")
    assert result["ok"] is True
    assert result["exit_code"] == 0
    assert result["output"] == "hello"


@pytest.mark.asyncio
async def test_run_cli_json_output() -> None:
    """JSON stdout is parsed into structured output."""
    code = 'import json; print(json.dumps({"key": "val"}))'
    result = await _run_cli(sys.executable, "-c", code)
    assert result["ok"] is True
    assert result["output"] == {"key": "val"}


@pytest.mark.asyncio
async def test_run_cli_nonzero_exit() -> None:
    """Non-zero exit code returns ok=False."""
    result = await _run_cli(sys.executable, "-c", "raise SystemExit(1)")
    assert result["ok"] is False
    assert result["exit_code"] == 1


@pytest.mark.asyncio
async def test_run_cli_stderr_captured() -> None:
    """Stderr is captured in the result."""
    code = "import sys; print('err', file=sys.stderr)"
    result = await _run_cli(sys.executable, "-c", code)
    assert "stderr" in result
    assert "err" in result["stderr"]


@pytest.mark.asyncio
async def test_run_cli_command_not_found() -> None:
    """Missing command returns structured error."""
    result = await _run_cli("__nonexistent_binary_xyz__")
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_run_cli_timeout() -> None:
    """Command that exceeds timeout returns error."""
    result = await _run_cli(
        sys.executable, "-c", "import time; time.sleep(10)",
        timeout=0.5,
    )
    assert result["ok"] is False
    assert "timed out" in result["error"].lower()


# ── register_local_tools ──────────────────────────────────────────


def test_register_local_tools_adds_tools() -> None:
    """All expected tools are registered on the FastMCP instance."""
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=9999)

    # FastMCP stores tools internally; list them via the _tool_manager
    # The server should have both remote (site/pulseboard) and local tools
    tool_names = set()
    for tool in server._tool_manager._tools.values():
        tool_names.add(tool.name)

    # Local tools
    expected_local = {
        "app_list", "app_info",
        "governance_run",
        "research_history", "research_report", "research_scan", "research_watch",
        "pulse_check",
        "memory_get", "memory_set", "memory_list", "memory_search",
        "pipeline_list", "pipeline_show", "pipeline_run",
        "release_check",
    }
    # Remote tools
    expected_remote = {
        "connector_status",
        "site_health", "site_get", "site_post",
        "pulseboard_health", "pulseboard_list_repos",
        "pulseboard_add_repo", "pulseboard_delete_repo", "pulseboard_get_pulse",
    }

    for name in expected_local:
        assert name in tool_names, f"Local tool '{name}' not registered"
    for name in expected_remote:
        assert name in tool_names, f"Remote tool '{name}' not registered"


def test_repo_root_exists() -> None:
    """_REPO_ROOT points to the actual WRG monorepo root."""
    assert _REPO_ROOT.exists()
    assert (_REPO_ROOT / "CLAUDE.md").exists()
