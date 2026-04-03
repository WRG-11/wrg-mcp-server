from __future__ import annotations

import pytest

from wrg_mcp_server.config import AppConfig, ConfigError


def test_app_config_reads_service_blocks() -> None:
    env = {
        "WRG_SITE_BASE_URL": "https://site.example.com/",
        "WRG_SITE_TOKEN": "abc123",
        "WRG_PULSEBOARD_BASE_URL": "https://pulse.example.com",
        "WRG_PULSEBOARD_SESSION_COOKIE": "session=test",
    }

    cfg = AppConfig.from_env(env)

    assert cfg.site is not None
    assert cfg.site.base_url == "https://site.example.com"
    assert cfg.site.build_headers()["Authorization"] == "Bearer abc123"
    assert cfg.pulseboard is not None
    assert cfg.pulseboard.build_headers()["Cookie"] == "session=test"


def test_invalid_headers_json_raises() -> None:
    env = {
        "WRG_SITE_BASE_URL": "https://site.example.com",
        "WRG_SITE_EXTRA_HEADERS": "not-json",
    }

    with pytest.raises(ConfigError):
        AppConfig.from_env(env)
