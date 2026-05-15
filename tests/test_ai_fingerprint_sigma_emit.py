"""Unit coverage for the ai_fingerprint_sigma_emit MCP wrapper contract."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from wrg_mcp_server import local_tools as lt


pytestmark = pytest.mark.unit


def _get_tool(name: str) -> Any:
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=9999)
    tools = {t.name: t for t in server._tool_manager._tools.values()}
    return tools[name]


async def _call(name: str, **kwargs: Any) -> dict[str, Any]:
    tool = _get_tool(name)
    return await tool.fn(**kwargs)


async def _run_sigma_cli(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Return a subprocess-style envelope for the emit command.

    The release wheel for ``wrg_mcp_server`` does not install sibling apps,
    so the unit fake validates the wrapper's JSON temp-file handoff and
    returns the Sigma YAML shape produced by ``wrg_ai_fingerprint_sigma``.
    """
    argv = list(args)
    input_path = Path(str(argv[argv.index("emit") + 1]))
    try:
        scan = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "exit_code": 2,
            "output": "",
            "stderr": f"error: {exc}",
            "app_name": kwargs.get("app_name"),
        }
    if not isinstance(scan, list):
        return {
            "ok": False,
            "exit_code": 2,
            "output": "",
            "stderr": (
                "error: fingerprint scan output must be a JSON array "
                "of file results\n"
            ),
            "app_name": kwargs.get("app_name"),
        }
    first = scan[0]
    hit = first["hits"][0]
    date = "2026-05-16"
    if "--date" in argv:
        date = str(argv[argv.index("--date") + 1])
    output = f"""---
title: LLM prompt artifact in source code
id: 12345678-1234-5678-1234-567812345678
status: experimental
description: Aggregated from 1 fingerprint hit across 1 file.
references:
- https://attack.mitre.org/
author: WinstonRedGuard
date: {date}
logsource:
  category: code_review
  product: wrg_ai_fingerprint
detection:
  selection:
    detector: {hit["detector"]}
    evidence|contains:
    - {hit["evidence"]}
  condition: selection
falsepositives:
- Legitimate prompt-engineering tooling
level: high
tags:
- attack.t1027.005
- attack.t1059.001
- wrg.ai_fingerprint
"""
    envelope: dict[str, Any] = {"ok": True, "exit_code": 0, "output": output}
    envelope["app_name"] = kwargs.get("app_name")
    return envelope


def _valid_scan() -> list[dict[str, Any]]:
    return [
        {
            "path": "apps/example/security_tool.py",
            "score": 0.91,
            "hits": [
                {
                    "detector": "prompt_artifacts",
                    "line_start": 12,
                    "line_end": 12,
                    "evidence": "Core Judgment Rules:",
                    "confidence": 0.96,
                }
            ],
        }
    ]


@pytest.mark.asyncio
async def test_ai_fingerprint_sigma_emit_happy_path_emits_sigma_yaml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lt, "_run_cli", _run_sigma_cli)

    result = await _call(
        "ai_fingerprint_sigma_emit",
        scan_json=_valid_scan(),
        date_override="2026-05-16",
    )

    assert result["ok"] is True
    assert result["exit_code"] == 0
    assert result["app_name"] == "wrg_ai_fingerprint_sigma"
    assert "title: LLM prompt artifact in source code" in result["output"]
    assert "Core Judgment Rules:" in result["output"]


@pytest.mark.asyncio
async def test_ai_fingerprint_sigma_emit_malformed_signature_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lt, "_run_cli", _run_sigma_cli)

    result = await _call(
        "ai_fingerprint_sigma_emit",
        scan_json={"not": "a scan result list"},
    )

    assert result["ok"] is False
    assert result["exit_code"] == 2
    assert "error:" in result.get("stderr", "").lower()
    assert "json array" in result.get("stderr", "").lower()


@pytest.mark.asyncio
async def test_ai_fingerprint_sigma_emit_yaml_matches_sigma_schema_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lt, "_run_cli", _run_sigma_cli)

    result = await _call(
        "ai_fingerprint_sigma_emit",
        scan_json=_valid_scan(),
        date_override="2026-05-16",
    )

    output = result["output"]
    for field in (
        "title",
        "id",
        "status",
        "description",
        "logsource",
        "detection",
        "level",
    ):
        assert re.search(rf"(?m)^{field}:", output)
    assert re.search(
        r"(?m)^id: [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
        r"[0-9a-f]{4}-[0-9a-f]{12}$",
        output,
    )
    assert "status: experimental" in output
    assert "date: 2026-05-16" in output
    assert "  category: code_review" in output
    assert "  product: wrg_ai_fingerprint" in output
    assert "    detector: prompt_artifacts" in output
    assert "    - Core Judgment Rules:" in output
    assert "  condition: selection" in output
    assert "- attack.t1027.005" in output
    assert "- attack.t1059.001" in output
    assert "- wrg.ai_fingerprint" in output
