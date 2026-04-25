from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

REPO_ROOT = Path(__file__).resolve().parents[3]
WRG_MCP_SRC = Path(__file__).resolve().parents[1] / "src"
if str(WRG_MCP_SRC) not in sys.path:
    sys.path.insert(0, str(WRG_MCP_SRC))
loaded_wrg = sys.modules.get("wrg_mcp_server")
if loaded_wrg is not None:
    loaded_path = Path(getattr(loaded_wrg, "__file__", "")).resolve()
    if WRG_MCP_SRC.resolve() not in loaded_path.parents:
        for module_name in list(sys.modules):
            if module_name == "wrg_mcp_server" or module_name.startswith("wrg_mcp_server."):
                del sys.modules[module_name]

RM_SRC = REPO_ROOT / "apps" / "research_motor" / "src"
if str(RM_SRC) not in sys.path:
    sys.path.insert(0, str(RM_SRC))

from httpx import ASGITransport, AsyncClient

from research_motor.api import create_app
from research_motor.api.service import ScanService
from research_motor.storage import RunStore
from wrg_mcp_server import server as mcp_server
from wrg_mcp_server.tools import research_motor_api as rm_tools


def _get_tools() -> dict[str, object]:
    server = mcp_server.create_mcp_server(host="127.0.0.1", port=9999)
    return {tool.name: tool for tool in server._tool_manager._tools.values()}


def _service() -> ScanService:
    root = Path("build") / "rm-api-mcp-test-roots" / uuid4().hex
    return ScanService(store=RunStore(app_root=root))


@pytest.mark.asyncio
async def test_research_motor_api_tools_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service()
    app = create_app(api_key="secret", scan_service=service)

    def _client(*, timeout):
        return AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            timeout=timeout,
        )

    monkeypatch.setenv("WRG_RM_API_BASE_URL", "http://testserver")
    monkeypatch.setenv("WRG_RM_API_KEY", "secret")
    monkeypatch.setattr(rm_tools, "_make_client", _client)
    tools = _get_tools()

    try:
        health = await tools["research_motor_healthz"].fn()
        created = await tools["research_motor_scan_create"].fn(target="example.com", mode="domain")
        result = await tools["research_motor_scan_get"].fn(scan_id=created["body"]["scan_id"])
    finally:
        service.close()

    assert health["ok"] is True
    assert 200 <= health["status_code"] < 300
    assert health["body"] == {"ok": True, "service": "research_motor", "version": "v1"}

    assert created["ok"] is True
    assert 200 <= created["status_code"] < 300
    assert list(created.keys())[0] == "ok"
    assert created["body"]["scan_id"].startswith("api_")
    assert created["body"]["status"] == "scored"

    assert result["ok"] is True
    assert 200 <= result["status_code"] < 300
    assert result["body"]["scan_id"] == created["body"]["scan_id"]
    assert result["body"]["target"] == "example.com"
    assert result["body"]["mode"] == "domain"
    assert result["body"]["scoring"]["candidate_count"] >= 1


@pytest.mark.asyncio
async def test_research_motor_scan_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WRG_RM_API_KEY", raising=False)
    tools = _get_tools()

    result = await tools["research_motor_scan_create"].fn(target="alice", mode="username")

    assert result == {
        "ok": False,
        "error": "WRG_RM_API_KEY is required for research_motor API scan tools",
    }
    assert list(result.keys())[0] == "ok"


@pytest.mark.asyncio
async def test_research_motor_scan_get_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WRG_RM_API_KEY", raising=False)
    tools = _get_tools()

    result = await tools["research_motor_scan_get"].fn(scan_id="api_abc")

    assert result == {
        "ok": False,
        "error": "WRG_RM_API_KEY is required for research_motor API scan tools",
    }


@pytest.mark.asyncio
async def test_research_motor_request_returns_envelope_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-2xx HTTP responses surface as {ok: False, status_code, body, error} — no raise."""
    service = _service()
    app = create_app(api_key="secret", scan_service=service)

    def _client(*, timeout):
        return AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            timeout=timeout,
        )

    monkeypatch.setenv("WRG_RM_API_BASE_URL", "http://testserver")
    monkeypatch.setenv("WRG_RM_API_KEY", "secret")
    monkeypatch.setattr(rm_tools, "_make_client", _client)
    tools = _get_tools()

    try:
        result = await tools["research_motor_scan_get"].fn(scan_id="api_does_not_exist")
    finally:
        service.close()

    assert result["ok"] is False
    assert result["status_code"] == 404
    assert "error" in result
    assert "HTTP 404" in result["error"]
    assert list(result.keys())[0] == "ok"


def test_research_motor_api_tools_registered() -> None:
    tools = _get_tools()
    for name in (
        "research_motor_healthz",
        "research_motor_scan_create",
        "research_motor_scan_get",
    ):
        assert name in tools
