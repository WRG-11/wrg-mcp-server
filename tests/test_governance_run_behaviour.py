"""Behavioural coverage for the `governance_run` MCP tool.

Closes another §1-rollup smoke-only entry from
docs/decisions/MCP_TOOL_AUDIT_2026_04_25.md. governance_run wraps
`python -m governance_check.cli check --repo-root <root>` via
_run_cli, with optional per-app post-filtering of stdout. This file
adds CLI-arg-construction, failure-passthrough, app-filter, and
envelope-shape assertions.

Mirrors PR #298 (research_* mock-fixture pattern) — live subprocess
into governance_check.cli would be flaky/slow; mocking _run_cli via
_FakeCall asserts the meaningful contract (right args, right
filtering) without depending on governance_check's runtime state.
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


# ── default invocation ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_governance_run_default_builds_check_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default invocation (no app arg) must build:
    `python -m governance_check.cli check --repo-root <root>` with
    app_name="governance_check" and timeout=120.0. Pinning so a
    refactor can't drop --repo-root or rename the subcommand."""
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": ""})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("governance_run")
    args = fake.calls[0][0]
    kwargs = fake.calls[0][1]
    assert "-m" in args
    assert "governance_check.cli" in args
    assert "check" in args
    assert "--repo-root" in args
    assert kwargs.get("app_name") == "governance_check"
    # 120s timeout for governance scans is the documented contract.
    assert kwargs.get("timeout") == 120.0


@pytest.mark.asyncio
async def test_governance_run_envelope_first_key_is_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Envelope shape consistency (audit §3.1) — _run_cli result is
    passed through, so first key must be `ok` (matches _run_cli's
    own return shape)."""
    monkeypatch.setattr(
        lt, "_run_cli",
        _FakeCall({"ok": True, "exit_code": 0, "output": ""}),
    )
    result = await _call("governance_run")
    assert list(result.keys())[0] == "ok"


# ── failure passthrough ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_governance_run_failure_passes_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When _run_cli reports ok=False (e.g. governance_check found
    violations and exited non-zero, or process-level failure), the
    tool MUST surface the failure dict as-is. The app-filter branch
    is gated on `result.get("ok")` so failure paths never get
    silently filtered."""
    failure = {
        "ok": False,
        "exit_code": 1,
        "stderr": "governance violations found",
    }
    monkeypatch.setattr(lt, "_run_cli", _FakeCall(failure))
    result = await _call("governance_run", app="some_app")
    # MUST be the exact failure dict — no filtering, no wrapping.
    assert result == failure


# ── app-filter behaviour ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_governance_run_with_app_filters_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `app` is given AND output is a string AND ok=True, the
    tool filters output to lines containing `app` OR starting with
    "governance". Pinning the filter logic so a refactor can't
    silently change the filter predicate."""
    raw_output = (
        "governance: starting check\n"
        "wrg_memory: 3 issues\n"
        "wrg_devguard: 1 issue\n"
        "wrg_pipeline: 0 issues\n"
        "governance: complete\n"
    )
    monkeypatch.setattr(
        lt, "_run_cli",
        _FakeCall({"ok": True, "exit_code": 0, "output": raw_output}),
    )
    result = await _call("governance_run", app="wrg_memory")
    # Filter must keep "wrg_memory" line + both "governance" lines,
    # drop the wrg_devguard / wrg_pipeline lines.
    out_lines = result["output"].splitlines()
    assert any("wrg_memory" in line for line in out_lines)
    assert any(line.startswith("governance") for line in out_lines)
    assert not any("wrg_devguard" in line for line in out_lines)
    assert not any("wrg_pipeline" in line for line in out_lines)


@pytest.mark.asyncio
async def test_governance_run_with_app_no_match_keeps_full_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If filter produces zero matches, source falls back to the
    unfiltered output (`result["output"] = "\\n".join(filtered) if
    filtered else result["output"]`). Without this, asking about an
    unknown app would return empty output, which is worse than
    returning the full unfiltered run."""
    raw_output = "wrg_memory: 3 issues\nwrg_devguard: 1 issue\n"
    monkeypatch.setattr(
        lt, "_run_cli",
        _FakeCall({"ok": True, "exit_code": 0, "output": raw_output}),
    )
    result = await _call("governance_run", app="nonexistent_app_zz9")
    # No "governance" prefix lines, no "nonexistent_app_zz9"
    # match → filter is empty → fallback to full output.
    assert result["output"] == raw_output


# ── empty-string app == "all" semantic ──────────────────────────────


@pytest.mark.asyncio
async def test_governance_run_empty_string_app_skips_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty-string `app` must be treated as falsy → no filter
    applied. Source guards filtering with `if app and ...` so an
    empty string takes the no-filter path. Pinning this so the
    default value behaviour can't silently flip to "filter on empty
    string matches everything"."""
    raw_output = "wrg_memory: 3 issues\nwrg_devguard: 1 issue\n"
    monkeypatch.setattr(
        lt, "_run_cli",
        _FakeCall({"ok": True, "exit_code": 0, "output": raw_output}),
    )
    result_default = await _call("governance_run")  # no app arg
    result_empty = await _call("governance_run", app="")  # explicit empty
    # Both must return raw output unchanged — filter not applied.
    assert result_default["output"] == raw_output
    assert result_empty["output"] == raw_output
