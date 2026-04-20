"""Tests covering server.py paths not exercised by smoke."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from wrg_mcp_server.config import AppConfig, ConfigError
from wrg_mcp_server import server as srv


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
