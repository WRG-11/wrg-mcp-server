"""Edge-case tests for wrg_mcp_server.http_utils."""

from __future__ import annotations

import httpx
import pytest

from wrg_mcp_server.http_utils import (
    _truncate_text,
    build_url,
    normalize_relative_path,
    parse_response,
)

# ─── normalize_relative_path ─────────────────────────────────────────────────

def test_normalize_empty_returns_root() -> None:
    assert normalize_relative_path("") == "/"
    assert normalize_relative_path("   ") == "/"


def test_normalize_adds_leading_slash() -> None:
    assert normalize_relative_path("repos") == "/repos"
    assert normalize_relative_path("repos/123") == "/repos/123"


def test_normalize_passes_through_absolute_path() -> None:
    assert normalize_relative_path("/health") == "/health"


def test_normalize_rejects_url_with_scheme() -> None:
    with pytest.raises(ValueError, match="Absolute URLs"):
        normalize_relative_path("https://evil.example.com/x")
    with pytest.raises(ValueError, match="Absolute URLs"):
        normalize_relative_path("http://x")


def test_normalize_rejects_protocol_relative() -> None:
    with pytest.raises(ValueError, match="must not start with //"):
        normalize_relative_path("//evil.example.com")


# ─── build_url ──────────────────────────────────────────────────────────────

def test_build_url_with_no_query() -> None:
    assert build_url("https://api.example.com", "/health") == "https://api.example.com/health"


def test_build_url_strips_base_trailing_slash() -> None:
    assert build_url("https://api.example.com/", "/repos") == "https://api.example.com/repos"


def test_build_url_skips_none_query_values() -> None:
    url = build_url(
        "https://api.example.com",
        "/repos",
        query={"a": "1", "b": None, "c": "3"},
    )
    assert "a=1" in url
    assert "c=3" in url
    assert "b=" not in url


def test_build_url_coerces_non_string_query_values() -> None:
    url = build_url(
        "https://api.example.com",
        "/repos",
        query={"limit": 25, "active": True},
    )
    assert "limit=25" in url
    assert "active=True" in url


def test_build_url_empty_path_becomes_root() -> None:
    assert build_url("https://api.example.com", "") == "https://api.example.com/"


# ─── parse_response ──────────────────────────────────────────────────────────

def test_parse_response_non_json_returns_text_body() -> None:
    req = httpx.Request("GET", "https://api.example.com/page")
    resp = httpx.Response(
        200,
        request=req,
        headers={"content-type": "text/html"},
        text="<html>hi</html>",
    )
    out = parse_response(resp)
    assert out["body"] == "<html>hi</html>"
    assert out["content_type"] == "text/html"


def test_parse_response_json_content_type_parses_body() -> None:
    req = httpx.Request("GET", "https://api.example.com/x")
    resp = httpx.Response(
        200,
        request=req,
        headers={"content-type": "application/json; charset=utf-8"},
        json={"foo": "bar"},
    )
    out = parse_response(resp)
    assert out["body"] == {"foo": "bar"}


def test_parse_response_error_status_marks_not_ok() -> None:
    req = httpx.Request("GET", "https://api.example.com/x")
    resp = httpx.Response(
        500,
        request=req,
        headers={"content-type": "text/plain"},
        text="boom",
    )
    out = parse_response(resp)
    assert out["ok"] is False
    assert out["status_code"] == 500
    assert out["body"] == "boom"


def test_parse_response_truncates_long_body() -> None:
    big = "x" * 5000
    req = httpx.Request("GET", "https://api.example.com/x")
    resp = httpx.Response(
        200,
        request=req,
        headers={"content-type": "text/plain"},
        text=big,
    )
    out = parse_response(resp)
    assert out["body"].endswith("...(truncated)")
    assert len(out["body"]) < len(big) + 50


# ─── _truncate_text ──────────────────────────────────────────────────────────

def test_truncate_text_short_passthrough() -> None:
    assert _truncate_text("abc") == "abc"


def test_truncate_text_long_clamped() -> None:
    out = _truncate_text("a" * 10_000, max_chars=100)
    assert out.endswith("...(truncated)")
    assert out.startswith("a" * 100)
