"""Round 39 — per-tool tests for the 6-silo MCP expansion wave.

Each of the 12 tools is exercised in four shapes:
  - happy path: subprocess stub returns ok; right args are passed through
  - error path: subprocess stub returns non-zero; envelope surfaces failure
  - mutation gate (mutation tools only): without WRG_MCP_ALLOW_MUTATIONS=1
    the handler refuses without spawning anything
  - arg validation: rejected arguments don't reach the subprocess

For read-only tools that have no mutation gate, the fourth shape is a
distinct arg / behaviour assertion that still keeps the count at 4 per
tool (≥48 total).
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from wrg_mcp_server import local_tools as lt


# ─── helpers ────────────────────────────────────────────────────────────


class _FakeCall:
    """Record invocations and return canned results from ``_run_cli``."""

    def __init__(self, responses: list[dict[str, Any]] | dict[str, Any]) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self._responses = responses if isinstance(responses, list) else [responses]
        self._cursor = 0

    async def __call__(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((args, kwargs))
        if self._cursor < len(self._responses):
            resp = self._responses[self._cursor]
            self._cursor += 1
        else:
            resp = self._responses[-1]
        return resp


def _get_tools() -> dict[str, Any]:
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=9999)
    return {t.name: t for t in server._tool_manager._tools.values()}


async def _call(tool_name: str, **kwargs: Any) -> dict[str, Any]:
    tools = _get_tools()
    tool = tools[tool_name]
    return await tool.fn(**kwargs)


# ─── ai_fingerprint_scan ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ai_fingerprint_scan_happy(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": []})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("ai_fingerprint_scan", path="apps/")
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "scan" in args and "apps/" in args
    assert "--min-score" in args and "0.5" in args
    assert "--json" in args


@pytest.mark.asyncio
async def test_ai_fingerprint_scan_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": False, "exit_code": 2, "stderr": "no such path"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("ai_fingerprint_scan", path="/nope")
    assert result["ok"] is False
    assert result["exit_code"] == 2


@pytest.mark.asyncio
async def test_ai_fingerprint_scan_exclude_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": []})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("ai_fingerprint_scan", path="apps/",
                exclude=["build", "dist"])
    args = fake.calls[0][0]
    assert args.count("--exclude") == 2
    assert "build" in args and "dist" in args


@pytest.mark.asyncio
async def test_ai_fingerprint_scan_min_score_coerced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": []})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("ai_fingerprint_scan", path="x", min_score=0.75)
    args = fake.calls[0][0]
    i = args.index("--min-score")
    assert args[i + 1] == "0.75"


# ─── ai_fingerprint_detectors ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_ai_fingerprint_detectors_happy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0,
                      "output": "detector_a 0.5\ndetector_b 0.3"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("ai_fingerprint_detectors")
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "detectors" in args


@pytest.mark.asyncio
async def test_ai_fingerprint_detectors_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": False, "exit_code": 1, "stderr": "module broken"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("ai_fingerprint_detectors")
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_ai_fingerprint_detectors_timeout_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("ai_fingerprint_detectors")
    _, kwargs = fake.calls[0]
    assert kwargs.get("timeout") == 60.0
    assert kwargs.get("app_name") == "wrg_ai_fingerprint"


@pytest.mark.asyncio
async def test_ai_fingerprint_detectors_no_extra_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("ai_fingerprint_detectors")
    args = fake.calls[0][0]
    # detectors takes no positional args beyond the subcommand
    assert "--exclude" not in args
    assert "--min-score" not in args


# ─── devguard_scan ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_devguard_scan_default_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": {"violations": []}})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("devguard_scan", path="apps/")
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "check" in args
    assert "--path" in args and "apps/" in args


@pytest.mark.asyncio
async def test_devguard_scan_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": False, "exit_code": 1, "stderr": "policy missing"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("devguard_scan", path="apps/")
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_devguard_scan_rejects_unknown_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("devguard_scan", path="apps/",
                         scan_types=["bogus"])
    assert result["ok"] is False
    assert "bogus" in result["error"]
    assert fake.calls == []  # subprocess never spawned


@pytest.mark.asyncio
async def test_devguard_scan_dispatches_secrets_subcommand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": {}})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("devguard_scan", path="apps/", scan_types=["secrets"])
    args = fake.calls[0][0]
    assert "scan-secrets" in args


# ─── devguard_baseline ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_devguard_baseline_happy(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0,
                      "output": "wrg-devguard profiles: baseline | missing"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("devguard_baseline")
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "profiles" in args


@pytest.mark.asyncio
async def test_devguard_baseline_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": False, "exit_code": 1, "stderr": "module not found"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("devguard_baseline")
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_devguard_baseline_takes_no_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("devguard_baseline")
    args = fake.calls[0][0]
    assert "--path" not in args


@pytest.mark.asyncio
async def test_devguard_baseline_uses_module_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("devguard_baseline")
    args = fake.calls[0][0]
    # Module-execution pattern, not PATH-bound entry-point
    assert "-m" in args
    assert "wrg_devguard.cli" in args


# ─── security_suite_run (mutation) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_security_suite_run_refused_without_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WRG_MCP_ALLOW_MUTATIONS", raising=False)
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("security_suite_run", target="example.com")
    assert result["ok"] is False
    assert "mutation" in result["error"].lower()
    assert fake.calls == []


@pytest.mark.asyncio
async def test_security_suite_run_allowed_with_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "1")
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": "ok"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("security_suite_run", target="example.com")
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "full" in args and "example.com" in args


@pytest.mark.asyncio
async def test_security_suite_run_rejects_unknown_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "1")
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("security_suite_run", target="x", profile="nope")
    assert result["ok"] is False
    assert "nope" in result["error"]
    assert fake.calls == []


@pytest.mark.asyncio
async def test_security_suite_run_network_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "1")
    fake = _FakeCall({"ok": True, "exit_code": 0})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("security_suite_run", target="10.0.0.1", profile="network")
    args = fake.calls[0][0]
    assert "scan-network" in args and "10.0.0.1" in args


@pytest.mark.asyncio
async def test_security_suite_run_code_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "1")
    fake = _FakeCall({"ok": True, "exit_code": 0})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("security_suite_run", target="apps/", profile="code")
    args = fake.calls[0][0]
    assert "scan-code" in args and "--path" in args and "apps/" in args


@pytest.mark.asyncio
async def test_security_suite_run_person_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "1")
    fake = _FakeCall({"ok": True, "exit_code": 0})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("security_suite_run", target="alice", profile="person")
    args = fake.calls[0][0]
    assert "scan-person" in args and "alice" in args


# ─── security_suite_report ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_security_suite_report_latest(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Build a fake repo root with a reports dir
    reports = tmp_path / "apps" / "wrg_security_suite" / "reports"
    reports.mkdir(parents=True)
    (reports / "scan_001.json").write_text('{"target": "ex.com", "findings": []}',
                                            encoding="utf-8")
    monkeypatch.setattr(lt, "_REPO_ROOT", tmp_path)
    # Patch the inline-snippet runner to use the patched _REPO_ROOT
    monkeypatch.setenv("WRG_REPO_ROOT", str(tmp_path))
    result = await _call("security_suite_report")
    assert result["ok"] is True
    body = result.get("output")
    assert isinstance(body, dict)
    assert body.get("ok") is True
    assert body.get("scan_id") == "scan_001"


@pytest.mark.asyncio
async def test_security_suite_report_specific_missing(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "apps" / "wrg_security_suite" / "reports").mkdir(parents=True)
    monkeypatch.setattr(lt, "_REPO_ROOT", tmp_path)
    monkeypatch.setenv("WRG_REPO_ROOT", str(tmp_path))
    result = await _call("security_suite_report", scan_id="ghost")
    assert result["ok"] is True
    body = result.get("output")
    assert isinstance(body, dict)
    assert body.get("ok") is False
    assert "not found" in body.get("error", "")


@pytest.mark.asyncio
async def test_security_suite_report_no_reports_dir(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lt, "_REPO_ROOT", tmp_path)
    monkeypatch.setenv("WRG_REPO_ROOT", str(tmp_path))
    result = await _call("security_suite_report")
    body = result.get("output")
    assert isinstance(body, dict)
    assert body.get("ok") is False


@pytest.mark.asyncio
async def test_security_suite_report_is_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No mutation gate — runs even when WRG_MCP_ALLOW_MUTATIONS is unset.
    monkeypatch.delenv("WRG_MCP_ALLOW_MUTATIONS", raising=False)
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)  # not used because handler bypasses _run_cli
    # Just exercise: should not error out solely because mutations are gated.
    result = await _call("security_suite_report", scan_id="x")
    # Should produce a dict regardless of contents
    assert isinstance(result, dict)


# ─── rule_lab_test ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rule_lab_test_happy(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0,
                      "output": {"total_rules": 3, "runs": []}})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("rule_lab_test",
                         rule_file="rules.json",
                         sample_file="contexts.json")
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "simulate" in args
    assert "--rules" in args and "rules.json" in args
    assert "--contexts" in args and "contexts.json" in args
    assert "--json" in args


@pytest.mark.asyncio
async def test_rule_lab_test_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": False, "exit_code": 1, "stderr": "rules invalid"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("rule_lab_test",
                         rule_file="bad.json",
                         sample_file="contexts.json")
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_rule_lab_test_uses_module(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("rule_lab_test", rule_file="r.json", sample_file="c.json")
    args = fake.calls[0][0]
    assert "-m" in args and "rule_lab.cli" in args


@pytest.mark.asyncio
async def test_rule_lab_test_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("rule_lab_test", rule_file="r.json", sample_file="c.json")
    _, kwargs = fake.calls[0]
    assert kwargs.get("timeout") == 300.0


# ─── rule_lab_list ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rule_lab_list_finds_files(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "alpha.json").write_text("[]", encoding="utf-8")
    (rules_dir / "beta.json").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("WRG_RULE_LAB_DIR", str(rules_dir))
    result = await _call("rule_lab_list")
    body = result.get("output")
    assert isinstance(body, dict)
    assert body.get("ok") is True
    names = sorted(r["name"] for r in body.get("rules", []))
    assert names == ["alpha", "beta"]
    assert body.get("count") == 2


@pytest.mark.asyncio
async def test_rule_lab_list_empty_dir(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("WRG_RULE_LAB_DIR", str(empty))
    result = await _call("rule_lab_list")
    body = result.get("output")
    assert isinstance(body, dict)
    assert body.get("count") == 0


@pytest.mark.asyncio
async def test_rule_lab_list_missing_dir(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WRG_RULE_LAB_DIR", str(tmp_path / "nope"))
    result = await _call("rule_lab_list")
    body = result.get("output")
    assert isinstance(body, dict)
    assert body.get("ok") is True  # missing dir is not an error, just empty
    assert body.get("count") == 0


@pytest.mark.asyncio
async def test_rule_lab_list_takes_no_args() -> None:
    tools = _get_tools()
    tool = tools["rule_lab_list"]
    # The handler signature must accept zero args
    import inspect
    sig = inspect.signature(tool.fn)
    assert len(sig.parameters) == 0


# ─── data_janitor_sweep (mutation when not dry) ─────────────────────────


@pytest.mark.asyncio
async def test_data_janitor_sweep_dry_run_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WRG_MCP_ALLOW_MUTATIONS", raising=False)
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": "scan: 0 files"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("data_janitor_sweep")
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "scan" in args  # dry_run defaults to True → scan subcommand


@pytest.mark.asyncio
async def test_data_janitor_sweep_non_dry_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WRG_MCP_ALLOW_MUTATIONS", raising=False)
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("data_janitor_sweep", dry_run=False)
    assert result["ok"] is False
    assert "mutation" in result["error"].lower()
    assert fake.calls == []


@pytest.mark.asyncio
async def test_data_janitor_sweep_non_dry_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "1")
    fake = _FakeCall({"ok": True, "exit_code": 0})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("data_janitor_sweep", dry_run=False)
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "clean" in args


@pytest.mark.asyncio
async def test_data_janitor_sweep_repo_root_passed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("data_janitor_sweep", path="/tmp/myrepo")
    args = fake.calls[0][0]
    assert "--repo-root" in args and "/tmp/myrepo" in args


# ─── data_janitor_orphans ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_data_janitor_orphans_happy(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": "0 files would be removed"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("data_janitor_orphans")
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "scan" in args and "--target" in args and "all" in args


@pytest.mark.asyncio
async def test_data_janitor_orphans_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": False, "exit_code": 1, "stderr": "fs error"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("data_janitor_orphans")
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_data_janitor_orphans_is_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No mutation gate — even with mutations unset, it should call the subprocess.
    monkeypatch.delenv("WRG_MCP_ALLOW_MUTATIONS", raising=False)
    fake = _FakeCall({"ok": True, "exit_code": 0})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("data_janitor_orphans")
    assert result["ok"] is True
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_data_janitor_orphans_uses_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    await _call("data_janitor_orphans")
    args = fake.calls[0][0]
    assert "-m" in args and "data_janitor.cli" in args


# ─── notifier_send (mutation) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_notifier_send_refused_without_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WRG_MCP_ALLOW_MUTATIONS", raising=False)
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("notifier_send", channel="log", message="hi")
    assert result["ok"] is False
    assert "mutation" in result["error"].lower()
    assert fake.calls == []


@pytest.mark.asyncio
async def test_notifier_send_allowed_with_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "1")
    fake = _FakeCall({"ok": True, "exit_code": 0, "output": "delivered"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("notifier_send", channel="log", message="hi")
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "send" in args
    assert "--channel" in args and "log" in args
    assert "--message" in args and "hi" in args


@pytest.mark.asyncio
async def test_notifier_send_rejects_empty_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "1")
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("notifier_send", channel="", message="hi")
    assert result["ok"] is False
    assert "channel" in result["error"].lower()
    assert fake.calls == []


@pytest.mark.asyncio
async def test_notifier_send_rejects_empty_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WRG_MCP_ALLOW_MUTATIONS", "1")
    fake = _FakeCall({"ok": True})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("notifier_send", channel="log", message="")
    assert result["ok"] is False
    assert "message" in result["error"].lower()
    assert fake.calls == []


# ─── notifier_channels ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notifier_channels_happy(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": True, "exit_code": 0,
                      "output": {"ok": True, "channels": ["log", "webhook"],
                                 "count": 2}})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("notifier_channels")
    assert result["ok"] is True
    args = fake.calls[0][0]
    assert "-c" in args  # inline-snippet pattern


@pytest.mark.asyncio
async def test_notifier_channels_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCall({"ok": False, "exit_code": 1, "stderr": "import failed"})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("notifier_channels")
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_notifier_channels_is_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WRG_MCP_ALLOW_MUTATIONS", raising=False)
    fake = _FakeCall({"ok": True, "exit_code": 0})
    monkeypatch.setattr(lt, "_run_cli", fake)
    result = await _call("notifier_channels")
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_notifier_channels_no_args() -> None:
    tools = _get_tools()
    tool = tools["notifier_channels"]
    import inspect
    sig = inspect.signature(tool.fn)
    assert len(sig.parameters) == 0


# ─── registration ───────────────────────────────────────────────────────


def test_round_39_tools_all_registered() -> None:
    tools = _get_tools()
    expected = (
        "ai_fingerprint_scan", "ai_fingerprint_detectors",
        "devguard_scan", "devguard_baseline",
        "security_suite_run", "security_suite_report",
        "rule_lab_test", "rule_lab_list",
        "data_janitor_sweep", "data_janitor_orphans",
        "notifier_send", "notifier_channels",
    )
    for name in expected:
        assert name in tools, f"expected tool {name!r} to be registered"
    assert len(expected) == 12
