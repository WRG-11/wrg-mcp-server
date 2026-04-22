"""Tests for the expanded MCP tool surface.

Each new tool has three test shapes:
  - happy path: subprocess stub returns ok; tool passes right args
  - error path: subprocess stub returns non-zero; tool surfaces the error
  - mutation guard (for state-changing tools): without
    ``WRG_MCP_ALLOW_MUTATIONS=1`` the tool refuses without spawning anything
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from wrg_mcp_server import local_tools as lt


# ─── fake CLI harness ────────────────────────────────────────────────────


class _FakeCall:
    """Record invocations and return canned results from ``_run_cli``."""

    def __init__(self, responses: list[dict[str, Any]] | dict[str, Any]) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self._responses = responses if isinstance(responses, list) else [responses]
        self._cursor = 0

    async def __call__(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((args, kwargs))
        if not self._responses:
            return {"ok": True, "exit_code": 0, "output": ""}
        if self._cursor < len(self._responses):
            resp = self._responses[self._cursor]
            self._cursor += 1
        else:
            resp = self._responses[-1]
        return resp


def _get_tools():
    """Register tools on a fresh FastMCP and return them by name."""
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=9999)
    return {t.name: t for t in server._tool_manager._tools.values()}


async def _call(tool_name: str, **kwargs: Any) -> dict[str, Any]:
    """Invoke a registered tool by name with kwargs."""
    tools = _get_tools()
    tool = tools[tool_name]
    return await tool.fn(**kwargs)


# ─── mutations guard helper ──────────────────────────────────────────────


def test_mutations_allowed_env_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WRG_MCP_ALLOW_MUTATIONS", raising=False)
    assert lt._mutations_allowed() is False
    for truthy in ("1", "true", "yes", "on"):
        monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", truthy)
        assert lt._mutations_allowed() is True
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "0")
    assert lt._mutations_allowed() is False


# ─── memory_search with --limit ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_search_passes_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": ["hit"]})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("memory_search", query="auth", limit=5)
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "search" in args
    assert "auth" in args
    assert "--limit" in args
    assert "5" in args


@pytest.mark.asyncio
async def test_memory_search_default_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": []})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("memory_search", query="auth")
    args = fake.calls[0][0]
    # Default limit of 10 is passed explicitly
    assert "--limit" in args
    assert "10" in args


# ─── memory_set mutation guard + ttl_seconds ─────────────────────────────


@pytest.mark.asyncio
async def test_memory_set_refused_without_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WRG_MCP_ALLOW_MUTATIONS", raising=False)
    called = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", called)
    result = await _call("memory_set", key="k", value="v")
    assert result["ok"] is False
    assert "mutation" in result["error"].lower() or "allow" in result["error"].lower()
    assert called.calls == []  # subprocess never spawned


@pytest.mark.asyncio
async def test_memory_set_allowed_with_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "1")
    fake = _FakeCall({"ok": True, "exit_code": 0})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("memory_set", key="k", value="v")
    assert result["ok"] is True
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_memory_set_passes_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "1")
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("memory_set", key="k", value="v", ttl_seconds=3600)
    args = fake.calls[0][0]
    assert "--ttl" in args
    # TTL in the memory CLI is in hours; 3600s rounds to 1h
    assert "1" in args


# ─── vault_audit ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vault_audit_composes_list_and_expiring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Responses: 1st = full list, 2nd = expiring within warn_days,
    #            3rd = stale (older than stale_days, computed client-side)
    full_list = [
        {"name": "api_key", "category": "general", "updated_at": "2026-01-01T00:00:00Z",
         "expires_at": "2026-05-01T00:00:00Z"},
        {"name": "db_pw", "category": "general", "updated_at": "2024-01-01T00:00:00Z",
         "expires_at": None},
    ]
    expiring = [
        {"name": "api_key", "category": "general",
         "expires_at": "2026-05-01T00:00:00Z"},
    ]
    fake = _FakeCall([
        {"ok": True, "exit_code": 0, "output": full_list},
        {"ok": True, "exit_code": 0, "output": expiring},
    ])
    monkeypatch.setattr(lt, "_run_cli", fake)

    result = await _call("vault_audit", warn_days=14, stale_days=365)
    assert result["ok"] is True
    assert result["total"] == 2
    assert result["expiring_soon"] == ["api_key"]
    # db_pw has no expires_at and updated_at is > stale_days old
    assert "db_pw" in result["stale"]
    # Two invocations: list, expiring
    assert len(fake.calls) == 2
    list_args, expiring_args = fake.calls[0][0], fake.calls[1][0]
    assert "list" in list_args and "--json" in list_args
    assert "expiring" in expiring_args and "14" in expiring_args


@pytest.mark.asyncio
async def test_vault_audit_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": False, "exit_code": 1, "stderr": "master key missing"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("vault_audit")
    assert result["ok"] is False
    assert "master key" in result.get("error", "")


# ─── scheduler_task_list ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scheduler_task_list_happy(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": "TASK  SOURCE  CMD\na  hardcoded  x y"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("scheduler_task_list")
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "task-list" in args


@pytest.mark.asyncio
async def test_scheduler_task_list_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": False, "exit_code": 2, "stderr": "boom"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("scheduler_task_list")
    assert result["ok"] is False


# ─── scheduler_tick_dry_run ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scheduler_tick_dry_run_parses_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    due = [{"task": "pulse-check", "next_run": "2026-04-22T09:00:00+00:00"}]
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": due})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("scheduler_tick_dry_run")
    assert result["ok"] is True
    assert result["due"] == due
    args = fake.calls[0][0]
    # Runs a small Python snippet that imports get_due_tasks
    assert any("get_due_tasks" in str(a) for a in args)


@pytest.mark.asyncio
async def test_scheduler_tick_dry_run_handles_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": []})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("scheduler_tick_dry_run")
    assert result["ok"] is True
    assert result["due"] == []


# ─── pipeline_run mutation guard + partial_ok ────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_run_refused_without_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WRG_MCP_ALLOW_MUTATIONS", raising=False)
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("pipeline_run", name="health_check")
    assert result["ok"] is False
    assert "mutation" in result["error"].lower() or "allow" in result["error"].lower()
    assert fake.calls == []


@pytest.mark.asyncio
async def test_pipeline_run_dry_allowed_without_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dry runs don't have side effects, so they bypass the guard."""
    monkeypatch.delenv("WRG_MCP_ALLOW_MUTATIONS", raising=False)
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": "Pipeline OK"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("pipeline_run", name="health_check", dry=True)
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "--dry" in args


@pytest.mark.asyncio
async def test_pipeline_run_partial_ok_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "1")
    fake = _FakeCall({"ok": True, "exit_code": 2, "output": "partial"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("pipeline_run", name="health_check", partial_ok=True)
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "--partial-ok-exit-2" in args


# ─── research_scan_summary ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_research_scan_summary_returns_latest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history = [
        {"run_id": "watch_20260422_060003", "ts": "2026-04-22T06:00:03",
         "candidates": 279, "status": "reported"},
        {"run_id": "watch_20260421_060003", "ts": "2026-04-21T06:00:03",
         "candidates": 250, "status": "reported"},
    ]
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": history})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("research_scan_summary")
    assert result["ok"] is True
    assert result["latest"]["run_id"] == "watch_20260422_060003"
    assert result["latest"]["candidates"] == 279


@pytest.mark.asyncio
async def test_research_scan_summary_empty_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": []})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("research_scan_summary")
    assert result["ok"] is True
    assert result["latest"] is None


@pytest.mark.asyncio
async def test_research_scan_summary_cli_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": False, "exit_code": 1, "stderr": "db locked"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("research_scan_summary")
    assert result["ok"] is False


# ─── registration ────────────────────────────────────────────────────────


def test_new_tools_registered() -> None:
    tools = _get_tools()
    for name in (
        "vault_audit",
        "scheduler_task_list",
        "scheduler_tick_dry_run",
        "research_scan_summary",
    ):
        assert name in tools, f"expected tool {name!r} to be registered"
