"""Edge-case tests for wrg_mcp_server.config."""

from __future__ import annotations

import pytest

from wrg_mcp_server.config import (
    AppConfig,
    ConfigError,
    ServiceConfig,
    _parse_bool,
    _parse_float,
    _parse_headers_json,
)


# ─── _parse_bool ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw", ["1", "true", "True", "YES", "on"])
def test_parse_bool_truthy_values(raw: str) -> None:
    assert _parse_bool(raw, default=False) is True


@pytest.mark.parametrize("raw", ["0", "false", "False", "NO", "off"])
def test_parse_bool_falsy_values(raw: str) -> None:
    assert _parse_bool(raw, default=True) is False


def test_parse_bool_none_uses_default() -> None:
    assert _parse_bool(None, default=True) is True
    assert _parse_bool(None, default=False) is False


def test_parse_bool_invalid_raises() -> None:
    with pytest.raises(ConfigError, match="Invalid boolean"):
        _parse_bool("maybe", default=False)


# ─── _parse_float ────────────────────────────────────────────────────────────

def test_parse_float_returns_default_for_blank() -> None:
    assert _parse_float(None, default=12.5, key="X") == 12.5
    assert _parse_float("   ", default=12.5, key="X") == 12.5


def test_parse_float_parses_numeric_string() -> None:
    assert _parse_float("3.14", default=0.0, key="X") == 3.14


def test_parse_float_rejects_non_numeric() -> None:
    with pytest.raises(ConfigError, match="must be a number"):
        _parse_float("not-a-number", default=1.0, key="WRG_TIMEOUT")


def test_parse_float_rejects_zero_or_negative() -> None:
    with pytest.raises(ConfigError, match="must be > 0"):
        _parse_float("0", default=1.0, key="WRG_TIMEOUT")
    with pytest.raises(ConfigError, match="must be > 0"):
        _parse_float("-5", default=1.0, key="WRG_TIMEOUT")


# ─── _parse_headers_json ────────────────────────────────────────────────────

def test_parse_headers_json_blank_returns_empty() -> None:
    assert _parse_headers_json(None, key="X") == {}
    assert _parse_headers_json("", key="X") == {}
    assert _parse_headers_json("   ", key="X") == {}


def test_parse_headers_json_valid_object() -> None:
    out = _parse_headers_json('{"X-Custom": "abc"}', key="X")
    assert out == {"X-Custom": "abc"}


def test_parse_headers_json_invalid_json_raises() -> None:
    with pytest.raises(ConfigError, match="valid JSON object"):
        _parse_headers_json("{not-json", key="X")


def test_parse_headers_json_array_raises() -> None:
    with pytest.raises(ConfigError, match="must be a JSON object"):
        _parse_headers_json('["a", "b"]', key="X")


def test_parse_headers_json_non_string_value_raises() -> None:
    with pytest.raises(ConfigError, match="values must be strings"):
        _parse_headers_json('{"X-Foo": 42}', key="X")


# ─── AppConfig.from_env edge cases ───────────────────────────────────────────

def test_from_env_no_base_url_returns_none_service() -> None:
    cfg = AppConfig.from_env({})
    assert cfg.site is None
    assert cfg.pulseboard is None


def test_from_env_blank_base_url_treated_as_unset() -> None:
    cfg = AppConfig.from_env({"WRG_SITE_BASE_URL": "   "})
    assert cfg.site is None


def test_from_env_per_service_timeout_overrides_default() -> None:
    cfg = AppConfig.from_env(
        {
            "WRG_SITE_BASE_URL": "https://site.example.com",
            "WRG_HTTP_TIMEOUT_SECONDS": "10",
            "WRG_SITE_TIMEOUT_SECONDS": "5",
        }
    )
    assert cfg.site is not None
    assert cfg.site.timeout_seconds == 5.0


def test_from_env_default_timeout_propagates() -> None:
    cfg = AppConfig.from_env(
        {
            "WRG_SITE_BASE_URL": "https://site.example.com",
            "WRG_HTTP_TIMEOUT_SECONDS": "7",
        }
    )
    assert cfg.site.timeout_seconds == 7.0


def test_from_env_strips_trailing_slash_from_base_url() -> None:
    cfg = AppConfig.from_env({"WRG_SITE_BASE_URL": "https://api.example.com////"})
    assert cfg.site.base_url == "https://api.example.com"


def test_from_env_custom_auth_header_and_scheme() -> None:
    cfg = AppConfig.from_env(
        {
            "WRG_SITE_BASE_URL": "https://api.example.com",
            "WRG_SITE_TOKEN": "abc",
            "WRG_SITE_AUTH_HEADER": "X-API-Key",
            "WRG_SITE_AUTH_SCHEME": "",
        }
    )
    headers = cfg.site.build_headers()
    assert headers == {"X-API-Key": "abc"}


def test_from_env_extra_headers_merge_into_build_headers() -> None:
    cfg = AppConfig.from_env(
        {
            "WRG_SITE_BASE_URL": "https://api.example.com",
            "WRG_SITE_EXTRA_HEADERS": '{"X-Trace": "demo"}',
            "WRG_SITE_TOKEN": "tok",
            "WRG_SITE_SESSION_COOKIE": "s=1",
        }
    )
    headers = cfg.site.build_headers()
    assert headers["X-Trace"] == "demo"
    assert headers["Authorization"] == "Bearer tok"
    assert headers["Cookie"] == "s=1"


def test_from_env_empty_token_treated_as_unset() -> None:
    cfg = AppConfig.from_env(
        {
            "WRG_SITE_BASE_URL": "https://api.example.com",
            "WRG_SITE_TOKEN": "   ",
        }
    )
    assert cfg.site.token is None
    assert "Authorization" not in cfg.site.build_headers()


def test_from_env_verify_tls_false() -> None:
    cfg = AppConfig.from_env(
        {
            "WRG_SITE_BASE_URL": "https://api.example.com",
            "WRG_HTTP_VERIFY_TLS": "false",
        }
    )
    assert cfg.site.verify_tls is False


# ─── ServiceConfig.build_headers ────────────────────────────────────────────

def test_service_config_build_headers_minimal() -> None:
    svc = ServiceConfig(
        base_url="http://x",
        token=None,
        auth_header="Authorization",
        auth_scheme="Bearer",
        session_cookie=None,
        extra_headers={},
        timeout_seconds=10.0,
        verify_tls=True,
    )
    assert svc.build_headers() == {}
