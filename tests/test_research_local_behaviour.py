"""Behavioural coverage for the 4 research_motor local MCP tools.

Closes the §6 "behavioural tests for research_history / research_report
/ research_scan / research_watch" deferred item from
docs/decisions/MCP_TOOL_AUDIT_2026_04_25.md (PR #295).

These 4 tools all wrap `_run_cli` (subprocess calls into
research_motor.cli) — so behavioural coverage means asserting the tool
BUILDS the right CLI args + handles the response correctly, not that
research_motor actually runs (live subprocess would be flaky/slow).

Mirrors the established pattern in test_new_tools.py (`_FakeCall` +
monkeypatch) rather than test_app_info_behaviour.py's live-fixture
approach — the choice depends on what the tool wraps.
"""

from __future__ import annotations

from typing import Any

import pytest

from wrg_mcp_server import local_tools as lt


# ── shared harness (mirrors test_new_tools.py:23-55) ─────────────────


class _FakeCall:
    """Record invocations and return canned _run_cli results."""

    def __init__(
        self,
        responses: list[dict[str, Any]] | dict[str, Any],
    ) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self._responses = (
            responses if isinstance(responses, list) else [responses]
        )
        self._cursor = 0

    async def __call__(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((args, kwargs))
        if self._cursor < len(self._responses):
            resp = self._responses[self._cursor]
            self._cursor += 1
        else:
            resp = self._responses[-1]
        return resp


def _get_tool(name: str):
    """Register tools on a fresh FastMCP and return the named tool."""
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=9999)
    tools = {t.name: t for t in server._tool_manager._tools.values()}
    return tools[name]


async def _call(tool_name: str, **kwargs: Any) -> dict[str, Any]:
    """Invoke a registered tool by name with kwargs."""
    return await _get_tool(tool_name).fn(**kwargs)


# ── research_history (no params) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_research_history_passes_history_json_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """research_history must invoke `research_motor.cli history --json`.
    Pinning these CLI args here so a future refactor can't silently
    drop --json (which would break Claude's JSON parsing) or change the
    subcommand name."""
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": []})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("research_history")
    args = fake.calls[0][0]
    assert "history" in args, f"missing 'history' subcommand in {args}"
    assert "--json" in args, f"missing '--json' flag in {args}"
    # app_name kwarg drives PYTHONPATH for the subprocess; if this is
    # ever lost, research_motor.cli won't be importable.
    assert fake.calls[0][1].get("app_name") == "research_motor"


@pytest.mark.asyncio
async def test_research_history_passes_through_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """research_history is a passthrough — when _run_cli reports
    ok=False, the tool MUST surface that as-is so callers can read
    the structured error. Hiding it would break the {ok, ...}
    contract for callers."""
    failure = {"ok": False, "exit_code": 2, "stderr": "boom"}
    monkeypatch.setattr(lt, "_run_cli", _FakeCall(failure))
    result = await _call("research_history")
    assert result == failure


@pytest.mark.asyncio
async def test_research_history_envelope_first_key_is_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Envelope shape consistency (audit §3.1)."""
    monkeypatch.setattr(
        lt, "_run_cli",
        _FakeCall({"ok": True, "exit_code": 0, "output": []}),
    )
    result = await _call("research_history")
    assert list(result.keys())[0] == "ok"


# ── research_report (run_id arg) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_research_report_passes_run_id_to_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """research_report must thread run_id through to `--run <id>`.
    Pinning this so any signature drift (e.g. someone renames the
    parameter to `id` or `report_id`) breaks loudly."""
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": {}})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("research_report", run_id="run-abc-123")
    args = fake.calls[0][0]
    assert "report" in args
    assert "--run" in args
    assert "run-abc-123" in args
    assert "--json" in args


@pytest.mark.asyncio
async def test_research_report_passes_through_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = {"ok": False, "exit_code": 1, "stderr": "no such run"}
    monkeypatch.setattr(lt, "_run_cli", _FakeCall(failure))
    result = await _call("research_report", run_id="nope")
    assert result == failure


@pytest.mark.asyncio
async def test_research_report_envelope_first_key_is_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        lt, "_run_cli",
        _FakeCall({"ok": True, "exit_code": 0, "output": {}}),
    )
    result = await _call("research_report", run_id="any")
    assert list(result.keys())[0] == "ok"


# ── research_scan (query arg, longer timeout) ────────────────────────


@pytest.mark.asyncio
async def test_research_scan_passes_query_to_input_arg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """research_scan threads `query` into `--input <query>`. The
    parameter name is misleading — it's actually a JSON-input file
    path or query string per the docstring — but the CLI flag name
    `--input` is the contract pinned here."""
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": []})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("research_scan", query="targets.json")
    args = fake.calls[0][0]
    assert "scan" in args
    assert "--input" in args
    assert "targets.json" in args
    assert "--json" in args


@pytest.mark.asyncio
async def test_research_scan_passes_through_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = {"ok": False, "exit_code": 1, "stderr": "bad input"}
    monkeypatch.setattr(lt, "_run_cli", _FakeCall(failure))
    result = await _call("research_scan", query="x")
    assert result == failure


@pytest.mark.asyncio
async def test_research_scan_envelope_first_key_is_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        lt, "_run_cli",
        _FakeCall({"ok": True, "exit_code": 0, "output": []}),
    )
    result = await _call("research_scan", query="x")
    assert list(result.keys())[0] == "ok"


# ── research_watch (preset arg with default, longest timeout) ────────


@pytest.mark.asyncio
async def test_research_watch_passes_preset_to_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """research_watch threads `preset` into `--preset <name>` and
    defaults to 'default' when not given. Both branches matter — the
    default value is part of the public contract."""
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": {}})
    monkeypatch.setattr(lt, "_run_cli", fake)
    # explicit preset
    await _call("research_watch", preset="custom")
    args = fake.calls[0][0]
    assert "watch" in args
    assert "--preset" in args
    assert "custom" in args
    assert "--json" in args
    # default preset (second invocation)
    await _call("research_watch")
    args2 = fake.calls[1][0]
    assert "default" in args2


@pytest.mark.asyncio
async def test_research_watch_passes_through_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = {"ok": False, "exit_code": 3, "stderr": "preset missing"}
    monkeypatch.setattr(lt, "_run_cli", _FakeCall(failure))
    result = await _call("research_watch", preset="bogus")
    assert result == failure


@pytest.mark.asyncio
async def test_research_watch_envelope_first_key_is_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        lt, "_run_cli",
        _FakeCall({"ok": True, "exit_code": 0, "output": {}}),
    )
    result = await _call("research_watch")
    assert list(result.keys())[0] == "ok"
