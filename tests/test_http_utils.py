from __future__ import annotations

import httpx
import pytest

from wrg_mcp_server.http_utils import build_url, parse_response


def test_build_url_merges_query() -> None:
    url = build_url(
        "https://api.example.com",
        "/repos?x=1",
        query={"owner": "acme", "name": "pulseboard"},
    )
    assert url == "https://api.example.com/repos?x=1&owner=acme&name=pulseboard"


def test_build_url_rejects_absolute_path() -> None:
    with pytest.raises(ValueError):
        build_url("https://api.example.com", "https://evil.example.com/x")


def test_parse_response_json() -> None:
    req = httpx.Request("GET", "https://api.example.com/health")
    resp = httpx.Response(
        200,
        request=req,
        headers={"content-type": "application/json"},
        json={"status": "ok"},
    )
    out = parse_response(resp)
    assert out["ok"] is True
    assert out["body"] == {"status": "ok"}
