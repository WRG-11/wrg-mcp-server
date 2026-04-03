from __future__ import annotations

from wrg_mcp_server import __version__
from wrg_mcp_server.server import create_mcp_server


def test_import_and_version() -> None:
    assert __version__ == "0.1.0"


def test_create_server() -> None:
    server = create_mcp_server(host="127.0.0.1", port=8099)
    assert server is not None
