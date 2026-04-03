"""Environment-driven configuration for wrg_mcp_server."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping


class ConfigError(RuntimeError):
    """Raised when connector configuration is invalid."""


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"Invalid boolean value: {value!r}")


def _parse_float(value: str | None, *, default: float, key: str) -> float:
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ConfigError(f"{key} must be a number: {value!r}") from exc
    if parsed <= 0:
        raise ConfigError(f"{key} must be > 0: {value!r}")
    return parsed


def _parse_headers_json(raw: str | None, *, key: str) -> dict[str, str]:
    if raw is None or not raw.strip():
        return {}
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{key} must be valid JSON object") from exc

    if not isinstance(obj, dict):
        raise ConfigError(f"{key} must be a JSON object")

    out: dict[str, str] = {}
    for k, v in obj.items():
        if not isinstance(k, str):
            raise ConfigError(f"{key} keys must be strings")
        if not isinstance(v, str):
            raise ConfigError(f"{key} values must be strings")
        out[k] = v
    return out


@dataclass(frozen=True)
class ServiceConfig:
    """Configuration for one upstream service."""

    base_url: str
    token: str | None
    auth_header: str
    auth_scheme: str
    session_cookie: str | None
    extra_headers: dict[str, str]
    timeout_seconds: float
    verify_tls: bool

    def build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = dict(self.extra_headers)
        if self.token:
            token_value = f"{self.auth_scheme} {self.token}".strip()
            headers[self.auth_header] = token_value
        if self.session_cookie:
            headers["Cookie"] = self.session_cookie
        return headers


@dataclass(frozen=True)
class AppConfig:
    """Top-level connector configuration."""

    site: ServiceConfig | None
    pulseboard: ServiceConfig | None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AppConfig":
        default_timeout = _parse_float(
            env.get("WRG_HTTP_TIMEOUT_SECONDS"),
            default=20.0,
            key="WRG_HTTP_TIMEOUT_SECONDS",
        )
        default_verify_tls = _parse_bool(
            env.get("WRG_HTTP_VERIFY_TLS"),
            default=True,
        )

        site = _service_from_env(
            env=env,
            prefix="WRG_SITE",
            base_url=env.get("WRG_SITE_BASE_URL"),
            default_timeout=default_timeout,
            default_verify_tls=default_verify_tls,
        )
        pulseboard = _service_from_env(
            env=env,
            prefix="WRG_PULSEBOARD",
            base_url=env.get("WRG_PULSEBOARD_BASE_URL"),
            default_timeout=default_timeout,
            default_verify_tls=default_verify_tls,
        )
        return cls(site=site, pulseboard=pulseboard)


def _service_from_env(
    *,
    env: Mapping[str, str],
    prefix: str,
    base_url: str | None,
    default_timeout: float,
    default_verify_tls: bool,
) -> ServiceConfig | None:
    if base_url is None or not base_url.strip():
        return None

    timeout_seconds = _parse_float(
        env.get(f"{prefix}_TIMEOUT_SECONDS"),
        default=default_timeout,
        key=f"{prefix}_TIMEOUT_SECONDS",
    )
    verify_tls = _parse_bool(
        env.get(f"{prefix}_VERIFY_TLS"),
        default=default_verify_tls,
    )
    extra_headers = _parse_headers_json(
        env.get(f"{prefix}_EXTRA_HEADERS"),
        key=f"{prefix}_EXTRA_HEADERS",
    )
    auth_scheme = env.get(f"{prefix}_AUTH_SCHEME", "Bearer").strip()
    auth_header = env.get(f"{prefix}_AUTH_HEADER", "Authorization").strip()

    return ServiceConfig(
        base_url=base_url.rstrip("/"),
        token=(env.get(f"{prefix}_TOKEN") or "").strip() or None,
        auth_header=auth_header or "Authorization",
        auth_scheme=auth_scheme,
        session_cookie=(env.get(f"{prefix}_SESSION_COOKIE") or "").strip() or None,
        extra_headers=extra_headers,
        timeout_seconds=timeout_seconds,
        verify_tls=verify_tls,
    )
