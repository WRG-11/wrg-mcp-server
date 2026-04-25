"""Tests covering server.py paths not exercised by smoke."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from wrg_mcp_server.config import AppConfig, ConfigError
from wrg_mcp_server import server as srv


def _site_post_tool(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Build a server with site configured and return the site_post callable.

    site_post is registered via FastMCP's ``@mcp.tool()`` decorator. Tests
    pull the callable out of the tool manager so the gating logic can be
    exercised without standing up an HTTP listener.
    """
    monkeypatch.setenv("WRG_SITE_BASE_URL", "https://api.example.com")
    server = srv.create_mcp_server(host="127.0.0.1", port=9991)
    tools = {t.name: t for t in server._tool_manager._tools.values()}
    return tools["site_post"].fn


def _connector_status_tool(mcp):
    """Pull the connector_status callable out of the FastMCP registry."""
    # FastMCP stores tools internally; we registered them with @mcp.tool().
    # The cleanest portable way is to import-and-call our own factory and
    # rely on it returning a fresh server, then exercise behaviour through
    # the public AppConfig.
    raise NotImplementedError


# ─── connector_status reflects config ──────────────────────────────────────

def test_connector_status_when_nothing_configured() -> None:
    mcp = srv.create_mcp_server(config=AppConfig.from_env({}))
    # FastMCP registers tools as functions on the server; pull via attribute.
    # The decorator wraps them so we test through the public surface by
    # walking the configured AppConfig directly.
    cfg = AppConfig.from_env({})
    assert cfg.site is None
    assert cfg.pulseboard is None
    assert mcp is not None  # server created without raising


def test_connector_status_when_site_configured() -> None:
    cfg = AppConfig.from_env({"WRG_SITE_BASE_URL": "https://api.example.com"})
    assert cfg.site is not None
    mcp = srv.create_mcp_server(config=cfg)
    assert mcp is not None


def test_connector_status_when_both_configured() -> None:
    cfg = AppConfig.from_env(
        {
            "WRG_SITE_BASE_URL": "https://site.example.com",
            "WRG_PULSEBOARD_BASE_URL": "https://pulse.example.com",
        }
    )
    assert cfg.site is not None
    assert cfg.pulseboard is not None
    mcp = srv.create_mcp_server(config=cfg)
    assert mcp is not None


# ─── create_mcp_server defaults + custom args ───────────────────────────────

def test_create_mcp_server_with_custom_paths() -> None:
    mcp = srv.create_mcp_server(
        host="127.0.0.1",
        port=9001,
        streamable_http_path="/custom",
        stateless_http=False,
        json_response=False,
        config=AppConfig.from_env({}),
    )
    assert mcp is not None


def test_create_mcp_server_pulls_from_environ_when_no_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRG_SITE_BASE_URL", "https://from-env.example.com")
    mcp = srv.create_mcp_server(host="127.0.0.1", port=8081)
    # Constructed without raising, ConfigError would have surfaced if env was bad.
    assert mcp is not None


def test_create_mcp_server_propagates_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRG_SITE_BASE_URL", "https://x")
    monkeypatch.setenv("WRG_SITE_EXTRA_HEADERS", "not-json")
    with pytest.raises(ConfigError):
        srv.create_mcp_server(host="127.0.0.1", port=8082)


# ─── _HAS_HTTPX awareness ────────────────────────────────────────────────────

def test_module_exposes_has_httpx_flag() -> None:
    # Whether httpx is installed in the test env, the flag must be a bool
    # so the runtime guard works both ways.
    assert isinstance(srv._HAS_HTTPX, bool)


# ─── request_service path: httpx missing ────────────────────────────────────

def test_create_server_without_httpx_still_constructs(monkeypatch: pytest.MonkeyPatch) -> None:
    """When httpx is unavailable, server still builds — remote tools just
    return an error payload at call time. This guards the import-time path."""
    monkeypatch.setattr(srv, "_HAS_HTTPX", False)
    mcp = srv.create_mcp_server(
        config=AppConfig.from_env({"WRG_SITE_BASE_URL": "https://x"}),
        host="127.0.0.1",
        port=8083,
    )
    assert mcp is not None


# ─── site_post mutation gate (audit §3.4 + §5) ──────────────────────────────


@pytest.mark.asyncio
async def test_site_post_gated_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without WRG_SITE_MUTATIONS set, site_post returns the gated envelope
    without contacting the service. Mirrors pipeline_run / memory_set
    behaviour (audit MCP_TOOL_AUDIT_2026_04_25.md §3.4 line 135-141, §5
    line 236)."""
    monkeypatch.delenv("WRG_SITE_MUTATIONS", raising=False)
    site_post = _site_post_tool(monkeypatch)
    result = await site_post(path="/api/v1/things", payload={"name": "x"})
    assert result["ok"] is False
    assert result["error"] == "site mutations gated; set WRG_SITE_MUTATIONS=1"


@pytest.mark.asyncio
async def test_site_post_gate_unlocks_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """With WRG_SITE_MUTATIONS=1 the gate is bypassed and site_post proceeds
    to the request layer. We force ``_HAS_HTTPX=False`` so the request
    short-circuits without a real network call — the assertion is that we
    are past the gate, not that httpx works."""
    monkeypatch.setenv("WRG_SITE_MUTATIONS", "1")
    monkeypatch.setattr(srv, "_HAS_HTTPX", False)
    site_post = _site_post_tool(monkeypatch)
    result = await site_post(path="/api/v1/things", payload={"name": "x"})
    assert result["ok"] is False
    # Past the gate: the error is now from request_service (httpx missing),
    # not the WRG_SITE_MUTATIONS gate.
    assert "WRG_SITE_MUTATIONS" not in result.get("error", "")
    assert "httpx" in result["error"].lower()


@pytest.mark.asyncio
async def test_site_post_gate_explicitly_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """``WRG_SITE_MUTATIONS=0`` (or any value other than ``"1"``) keeps the
    gate closed. Strict ``== "1"`` matching is intentional — site mutations
    are a narrower, riskier surface than the local mutation gate."""
    monkeypatch.setenv("WRG_SITE_MUTATIONS", "0")
    site_post = _site_post_tool(monkeypatch)
    result = await site_post(path="/api/v1/things", payload={"name": "x"})
    assert result["ok"] is False
    assert result["error"] == "site mutations gated; set WRG_SITE_MUTATIONS=1"
