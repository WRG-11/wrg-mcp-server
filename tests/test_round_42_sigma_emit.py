"""Round 42 — ai_fingerprint_sigma_emit MCP tool tests.

R40 shipped wrg_ai_fingerprint_sigma; R42 exposes its ``emit`` step
as a Claude-callable MCP tool so the Phase 9.4 R4 chain
(scan → emit → validate) is reachable end-to-end via MCP.

Five shapes per R39 standard:
  - input_file happy path
  - scan_json happy path (temp-file materialisation)
  - both args → ok=False error envelope
  - neither args → ok=False error envelope
  - CLI error → envelope pass-through
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from wrg_mcp_server import local_tools as lt


# ─── helpers ────────────────────────────────────────────────────────────


class _FakeCall:
    """Record invocations and return canned results from ``_run_cli``."""

    def __init__(self, responses: list[dict[str, Any]] | dict[str, Any]) -> None:
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


def _get_tool(name: str) -> Any:
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=9999)
    tools = {t.name: t for t in server._tool_manager._tools.values()}
    return tools[name]


async def _call(name: str, **kwargs: Any) -> dict[str, Any]:
    tool = _get_tool(name)
    return await tool.fn(**kwargs)


# ─── ai_fingerprint_sigma_emit ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_sigma_emit_input_file_happy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall(
        {"ok": True, "exit_code": 0, "output": "title: stub-rule\n"}
    )
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call(
        "ai_fingerprint_sigma_emit", input_file="scan.json"
    )

    assert result["ok"] is True
    assert "title: stub-rule" in str(result["output"])
    args = fake.calls[0][0]
    assert "wrg_ai_fingerprint_sigma" in args
    assert "emit" in args
    assert "scan.json" in args
    assert "--stdout" in args
    # No --date when date_override omitted.
    assert "--date" not in args


@pytest.mark.asyncio
async def test_sigma_emit_scan_json_happy_writes_tempfile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall(
        {"ok": True, "exit_code": 0, "output": "title: stub-rule\n"}
    )
    monkeypatch.setattr(lt, "_run_cli", fake)
    payload: list[dict[str, Any]] = [
        {"file": "a.py", "score": 0.9, "detectors": ["ai_signature"]}
    ]
    result = await _call("ai_fingerprint_sigma_emit", scan_json=payload)

    assert result["ok"] is True
    args = fake.calls[0][0]
    # The positional input arg is the temp-file path; it must exist
    # at call time and be passed by string, but cleaned up afterwards.
    # We can't snapshot the path easily, but it must end with .json
    # and not be the literal placeholder.
    input_arg = args[args.index("emit") + 1]
    assert input_arg.endswith(".json")
    assert input_arg != "scan.json"
    # Temp file must be cleaned up after the call returns.
    assert not Path(input_arg).exists()


@pytest.mark.asyncio
async def test_sigma_emit_scan_json_tempfile_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _capture(*args: Any, **kwargs: Any) -> dict[str, Any]:
        # Read tempfile content before the wrapper cleans it up.
        input_path = args[args.index("emit") + 1]
        captured["path"] = input_path
        captured["content"] = Path(input_path).read_text(encoding="utf-8")
        return {"ok": True, "exit_code": 0, "output": "title: stub\n"}

    monkeypatch.setattr(lt, "_run_cli", _capture)
    payload = [{"file": "x.py", "score": 0.5}]
    await _call("ai_fingerprint_sigma_emit", scan_json=payload)

    assert json.loads(captured["content"]) == payload


@pytest.mark.asyncio
async def test_sigma_emit_both_args_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call(
        "ai_fingerprint_sigma_emit",
        scan_json=[{"file": "a.py"}],
        input_file="scan.json",
    )

    assert result["ok"] is False
    assert "not both" in result["error"]
    assert fake.calls == []  # subprocess must not be spawned


@pytest.mark.asyncio
async def test_sigma_emit_neither_args_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("ai_fingerprint_sigma_emit")

    assert result["ok"] is False
    assert "Provide either" in result["error"]
    assert fake.calls == []


@pytest.mark.asyncio
async def test_sigma_emit_date_override_threaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": ""})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call(
        "ai_fingerprint_sigma_emit",
        input_file="scan.json",
        date_override="2026-05-13",
    )

    args = fake.calls[0][0]
    assert "--date" in args
    assert "2026-05-13" in args


@pytest.mark.asyncio
async def test_sigma_emit_cli_error_envelope_passthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall(
        {
            "ok": False,
            "exit_code": 2,
            "stderr": "error: malformed scan JSON",
        }
    )
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call(
        "ai_fingerprint_sigma_emit", input_file="bad.json"
    )

    assert result["ok"] is False
    assert result["exit_code"] == 2
    assert "malformed" in result["stderr"]


@pytest.mark.asyncio
async def test_sigma_emit_uses_correct_app_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": ""})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("ai_fingerprint_sigma_emit", input_file="scan.json")

    kwargs = fake.calls[0][1]
    assert kwargs.get("app_name") == "wrg_ai_fingerprint_sigma"
    assert kwargs.get("timeout") == 120.0


def test_sigma_emit_registered_in_tool_manager() -> None:
    tool = _get_tool("ai_fingerprint_sigma_emit")
    assert tool is not None
    assert tool.name == "ai_fingerprint_sigma_emit"
