from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

from mcp.server.fastmcp import FastMCP

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_TIMEOUT_SECONDS = 30.0


def register_research_motor_api_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def research_motor_healthz() -> dict[str, Any]:
        """Check the research_motor HTTP API health endpoint."""
        return await _request("GET", "/v1/healthz", require_api_key=False)

    @mcp.tool()
    async def research_motor_scan_create(target: str, mode: str) -> dict[str, Any]:
        """Create a research_motor HTTP API scan and return its scan_id."""
        return await _request(
            "POST",
            "/v1/scan",
            payload={"target": target, "mode": mode},
            require_api_key=True,
        )

    @mcp.tool()
    async def research_motor_scan_get(scan_id: str) -> dict[str, Any]:
        """Fetch a research_motor HTTP API scan result, including scoring."""
        return await _request("GET", f"/v1/scan/{scan_id}", require_api_key=True)


async def _request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    require_api_key: bool,
) -> dict[str, Any]:
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx is required for research_motor HTTP API tools") from exc

    api_key = os.environ.get("WRG_RM_API_KEY", "")
    if require_api_key and not api_key:
        raise RuntimeError("WRG_RM_API_KEY is required for research_motor API scan tools")

    headers = {"X-API-Key": api_key} if api_key else {}
    timeout = httpx.Timeout(_timeout_seconds())
    async with _make_client(timeout=timeout) as client:
        response = await client.request(
            method,
            _url(path),
            headers=headers,
            json=payload,
        )
    if response.is_success:
        return _response_body(response)
    body = _response_body(response)
    raise RuntimeError(f"research_motor API {method} {path} failed: HTTP {response.status_code}: {body!r}")


def _url(path: str) -> str:
    base_url = os.environ.get("WRG_RM_API_BASE_URL", DEFAULT_BASE_URL)
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def _timeout_seconds() -> float:
    raw = os.environ.get("WRG_RM_API_TIMEOUT_SECONDS", "")
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        parsed = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    return parsed if parsed > 0 else DEFAULT_TIMEOUT_SECONDS


def _response_body(response: Any) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type.lower():
        return response.json()
    return {"text": response.text}


def _make_client(*, timeout: Any) -> Any:
    import httpx

    return httpx.AsyncClient(timeout=timeout, follow_redirects=True)
