"""HTTP utility helpers."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

import httpx


def normalize_relative_path(path: str) -> str:
    """Normalize user path and reject absolute/unsafe input."""
    clean = path.strip()
    if not clean:
        return "/"
    if "://" in clean:
        raise ValueError("Absolute URLs are not allowed; provide a relative path.")
    if clean.startswith("//"):
        raise ValueError("Path must not start with //.")
    if not clean.startswith("/"):
        clean = f"/{clean}"
    return clean


def build_url(base_url: str, path: str, query: Mapping[str, Any] | None = None) -> str:
    """Build a final URL from base and safe relative path."""
    normalized = normalize_relative_path(path)
    parsed = urlparse(normalized)
    if parsed.scheme or parsed.netloc:
        raise ValueError("Path must be relative.")

    absolute = urljoin(f"{base_url.rstrip('/')}/", parsed.path.lstrip("/"))

    merged: dict[str, str] = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if query:
        for key, value in query.items():
            if value is None:
                continue
            merged[str(key)] = str(value)
    if not merged:
        return absolute
    return f"{absolute}?{urlencode(merged)}"


def parse_response(response: httpx.Response) -> dict[str, Any]:
    """Parse response body in a tool-friendly format."""
    content_type = response.headers.get("content-type", "")
    body: Any
    if "application/json" in content_type.lower():
        try:
            body = response.json()
        except ValueError:
            body = _truncate_text(response.text)
    else:
        body = _truncate_text(response.text)

    return {
        "ok": response.is_success,
        "status_code": response.status_code,
        "url": str(response.url),
        "content_type": content_type,
        "body": body,
    }


def _truncate_text(value: str, max_chars: int = 4000) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}...(truncated)"
