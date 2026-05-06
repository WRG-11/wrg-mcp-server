"""Tests for local WRG tool wrappers."""

from __future__ import annotations

import json
import sys

import pytest

from wrg_mcp_server.local_tools import (
    _REPO_ROOT,
    _build_env,
    _count_tests,
    _last_commit,
    _read_pyproject,
    _read_registry,
    _run_cli,
    register_local_tools,
)

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


@pytest.mark.asyncio
async def test_run_cli_with_app_name_sets_pythonpath() -> None:
    """app_name parameter adds the app's src/ to PYTHONPATH."""
    code = "import os; print(os.environ.get('PYTHONPATH', ''))"
    result = await _run_cli(
        sys.executable, "-c", code,
        app_name="pulse_core",
    )
    assert result["ok"] is True
    assert "pulse_core" in str(result["output"])


# ── Helper function tests ────────────────────────────────────────


def test_read_registry() -> None:
    """Registry returns a non-empty list of app dicts."""
    apps = _read_registry()
    assert len(apps) > 0
    assert all("name" in a for a in apps)
    assert all("status" in a for a in apps)


def test_read_pyproject() -> None:
    """Can parse a real pyproject.toml from the monorepo."""
    data = _read_pyproject("wrg_mcp_server")
    assert "project" in data
    assert data["project"]["name"] == "wrg_mcp_server"


def test_read_pyproject_missing() -> None:
    """Missing app returns empty dict, no crash."""
    data = _read_pyproject("__nonexistent_app__")
    assert data == {}


def test_count_tests() -> None:
    """Count test files for a real app."""
    count = _count_tests("wrg_mcp_server")
    assert count >= 1  # at least this test file


def test_count_tests_missing() -> None:
    """Missing app returns 0."""
    assert _count_tests("__nonexistent__") == 0


def test_last_commit() -> None:
    """Last commit returns a non-empty string for a real app."""
    commit = _last_commit("wrg_mcp_server")
    assert commit != ""
    assert commit != "unknown"


def test_build_env_without_app() -> None:
    """Without app_name, env has standard keys."""
    env = _build_env()
    assert "PYTHONIOENCODING" in env
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_build_env_with_app() -> None:
    """With app_name, PYTHONPATH includes the app's src/."""
    env = _build_env("pulse_core")
    assert "PYTHONPATH" in env
    assert "pulse_core" in env["PYTHONPATH"]


# ── register_local_tools ──────────────────────────────────────────


def test_register_local_tools_adds_tools() -> None:
    """All expected tools are registered on the FastMCP instance."""
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=9999)

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
    if (_REPO_ROOT / "CLAUDE.md").exists():
        assert (_REPO_ROOT / "apps").is_dir()
