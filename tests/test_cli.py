"""argparse + dispatch tests for wrg-mcp-server CLI."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from wrg_mcp_server import cli as mcp_cli


def _run(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["wrg-mcp-server", *argv])
    return mcp_cli.main()


# ─── argparse validation ──────────────────────────────────────────────────────

def test_invalid_transport_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, "--transport", "carrier-pigeon")
    assert exc.value.code == 2


def test_non_numeric_port_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, "--port", "not-a-port")
    assert exc.value.code == 2


# ─── happy paths ──────────────────────────────────────────────────────────────

def test_default_transport_invokes_streamable_http(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_server = MagicMock()
    with patch("wrg_mcp_server.server.create_mcp_server", return_value=fake_server) as factory:
        rc = _run(monkeypatch)
    assert rc == 0
    factory.assert_called_once()
    kwargs = factory.call_args.kwargs
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8080
    assert kwargs["streamable_http_path"] == "/mcp"
    fake_server.run.assert_called_once_with(transport="streamable-http")


def test_stdio_transport_routes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_server = MagicMock()
    with patch("wrg_mcp_server.server.create_mcp_server", return_value=fake_server):
        _run(monkeypatch, "--transport", "stdio")
    fake_server.run.assert_called_once_with(transport="stdio")


def test_sse_transport_routes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_server = MagicMock()
    with patch("wrg_mcp_server.server.create_mcp_server", return_value=fake_server):
        _run(monkeypatch, "--transport", "sse")
    fake_server.run.assert_called_once_with(transport="sse")


def test_custom_host_port_path_passed_to_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_server = MagicMock()
    with patch("wrg_mcp_server.server.create_mcp_server", return_value=fake_server) as factory:
        _run(
            monkeypatch,
            "--host",
            "127.0.0.1",
            "--port",
            "9100",
            "--mcp-path",
            "/custom",
        )
    kwargs = factory.call_args.kwargs
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 9100
    assert kwargs["streamable_http_path"] == "/custom"


def test_startup_banner_goes_to_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_server = MagicMock()
    with patch("wrg_mcp_server.server.create_mcp_server", return_value=fake_server):
        _run(monkeypatch, "--port", "8123")
    captured = capsys.readouterr()
    # Banner goes to stderr, not stdout, so stdio transport stays clean.
    assert captured.out == ""
    assert "wrg-mcp-server starting" in captured.err
    assert "port=8123" in captured.err
