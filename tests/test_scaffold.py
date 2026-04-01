"""Scaffold tests for wrg_mcp_server."""


def test_import():
    """Verify package is importable."""
    import importlib
    mod = importlib.import_module("wrg_mcp_server")
    assert mod is not None
