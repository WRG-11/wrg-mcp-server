"""FastMCP server definition for WinstonRedGuard.

Exposes both remote HTTP tools (site/PulseBoard) and local CLI tools
(research_motor, governance_check, app_registry, pulse_core, wrg_memory,
wrg_pipeline, release_check).
"""

from __future__ import annotations

import os
from typing import Any, Mapping

from mcp.server.fastmcp import FastMCP

from wrg_mcp_server.config import AppConfig, ConfigError, ServiceConfig
from wrg_mcp_server.local_tools import register_local_tools
from wrg_mcp_server.tools.arastirma_ussu import register_arastirma_ussu_tools
from wrg_mcp_server.tools.research_motor_api import register_research_motor_api_tools
from wrg_mcp_server.tools.trading_agents import register_trading_agents_tools

# httpx is optional — only needed for remote tools (site/pulseboard)
try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


def create_mcp_server(
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
    streamable_http_path: str = "/mcp",
    stateless_http: bool = True,
    json_response: bool = True,
    config: AppConfig | None = None,
) -> FastMCP:
    cfg = config or AppConfig.from_env(os.environ)

    mcp = FastMCP(
        "WinstonRedGuard",
        instructions=(
            "WRG MCP server — exposes the full WinstonRedGuard monorepo.\n"
            "Local tools: app_list, app_info, governance_run, research_*, "
            "pulse_check, memory_*, pipeline_*, release_check.\n"
            "HTTP API tools: research_motor_scan_create, research_motor_scan_get, research_motor_healthz.\n"
            "Arastirma Ussu tools: arastirma_ask, arastirma_doc_search, arastirma_web_search, arastirma_memory_search.\n"
            "Trading tools: trading_analyze (full multi-agent), trading_quick_signal (fast RSI/price).\n"
            "Remote tools: site_* (company site APIs), pulseboard_* (GitHub health dashboard).\n"
            "Use connector_status to check which remote services are configured."
        ),
        host=host,
        port=port,
        streamable_http_path=streamable_http_path,
        stateless_http=stateless_http,
        json_response=json_response,
    )

    async def request_service(
        service: ServiceConfig,
        *,
        method: str,
        path: str,
        query: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not _HAS_HTTPX:
            return {"ok": False, "error": "httpx not installed — remote tools unavailable"}
        from wrg_mcp_server.http_utils import build_url, parse_response
        url = build_url(service.base_url, path, query=query)
        headers = service.build_headers()
        timeout = httpx.Timeout(service.timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout,
            verify=service.verify_tls,
            follow_redirects=True,
        ) as client:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=payload,
            )
        return parse_response(response)

    def require_service(service: ServiceConfig | None, env_key: str) -> ServiceConfig:
        if service is None:
            raise ConfigError(
                f"Service is not configured. Set `{env_key}` for this tool family."
            )
        return service

    @mcp.tool()
    def connector_status() -> dict[str, Any]:
        """Show connector configuration status (without secrets)."""
        return {
            "ok": True,
            "httpx_available": _HAS_HTTPX,
            "site_configured": cfg.site is not None,
            "site_base_url": cfg.site.base_url if cfg.site else None,
            "pulseboard_configured": cfg.pulseboard is not None,
            "pulseboard_base_url": cfg.pulseboard.base_url if cfg.pulseboard else None,
        }

    @mcp.tool()
    async def site_health(path: str = "/health") -> dict[str, Any]:
        """Check the WinstonRedGuard live site's health endpoint to verify the public-facing service is reachable. Use when the user asks 'is the site up?', 'check site status', 'site healthcheck', or before composing a site_post call that depends on the live API. Returns the site's health JSON plus HTTP status code."""
        service = require_service(cfg.site, "WRG_SITE_BASE_URL")
        return await request_service(service, method="GET", path=path)

    @mcp.tool()
    async def site_get(
        path: str = "/",
        query: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Read a WinstonRedGuard live site API endpoint with optional query params.

        Use when the user asks "fetch from site", "read the site API", "check
        this public endpoint", or before site_post when you need current
        server state. Use site_health for reachability checks and site_post for
        writes. Returns the site's response body plus HTTP metadata in the
        parse_response shape: {ok, status_code, url, content_type, body}.
        """
        service = require_service(cfg.site, "WRG_SITE_BASE_URL")
        return await request_service(
            service,
            method="GET",
            path=path,
            query=query,
        )

    @mcp.tool()
    async def site_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON POST payload to a WinstonRedGuard live site endpoint.

        MUTATION (gated): site_post performs a network write against the
        configured site service, so it requires ``WRG_SITE_MUTATIONS=1`` in
        the server env. When the gate is unset (or any value other than
        ``"1"``) the tool returns the envelope
        ``{"ok": False, "error": "site mutations gated; set WRG_SITE_MUTATIONS=1"}``
        without contacting the service. This mirrors the pipeline_run /
        memory_set gating pattern (audit
        ``docs/decisions/MCP_TOOL_AUDIT_2026_04_25.md`` §3.4 + §5).

        Use when the user asks to "post to site", "create a site entry",
        "submit to the site API", or wants to push data to the WRG public
        API. Use site_get for reads. When the gate is unlocked the tool
        returns the site's response body (typically ``{ok, data}``) plus
        HTTP status code.
        """
        if os.environ.get("WRG_SITE_MUTATIONS") != "1":
            return {
                "ok": False,
                "error": "site mutations gated; set WRG_SITE_MUTATIONS=1",
            }
        service = require_service(cfg.site, "WRG_SITE_BASE_URL")
        return await request_service(
            service,
            method="POST",
            path=path,
            payload=payload,
        )

    @mcp.tool()
    async def pulseboard_health(path: str = "/health") -> dict[str, Any]:
        """Check the PulseBoard repo-health dashboard service for reachability.

        Use when the user asks 'is pulseboard up?', 'pulseboard status', or
        before calling pulseboard_list_repos / pulseboard_add_repo on a
        possibly-unreachable instance. Returns health JSON plus HTTP status
        code.

        SOFT-DEPRECATED (2026-04-25): PulseBoard service is Railway-dormant
        per docs/decisions and PR #252. Tool still functional if
        WRG_PULSEBOARD_BASE_URL points to a live instance, but agents should
        deprioritize PulseBoard recommendations until re-eval 2026-10-24. See
        project_pulseboard.md.
        """
        service = require_service(cfg.pulseboard, "WRG_PULSEBOARD_BASE_URL")
        return await request_service(service, method="GET", path=path)

    @mcp.tool()
    async def pulseboard_list_repos() -> dict[str, Any]:
        """List repos from PulseBoard (`GET /repos`).

        SOFT-DEPRECATED (2026-04-25): PulseBoard service is Railway-dormant
        per docs/decisions and PR #252. Tool still functional if
        WRG_PULSEBOARD_BASE_URL points to a live instance, but agents should
        deprioritize PulseBoard recommendations until re-eval 2026-10-24. See
        project_pulseboard.md.
        """
        service = require_service(cfg.pulseboard, "WRG_PULSEBOARD_BASE_URL")
        return await request_service(service, method="GET", path="/repos")

    @mcp.tool()
    async def pulseboard_add_repo(owner: str, name: str) -> dict[str, Any]:
        """Add a repo in PulseBoard (`POST /repos`).

        SOFT-DEPRECATED (2026-04-25): PulseBoard service is Railway-dormant
        per docs/decisions and PR #252. Tool still functional if
        WRG_PULSEBOARD_BASE_URL points to a live instance, but agents should
        deprioritize PulseBoard recommendations until re-eval 2026-10-24. See
        project_pulseboard.md.
        """
        service = require_service(cfg.pulseboard, "WRG_PULSEBOARD_BASE_URL")
        return await request_service(
            service,
            method="POST",
            path="/repos",
            payload={"owner": owner, "name": name},
        )

    @mcp.tool()
    async def pulseboard_delete_repo(repo_id: int) -> dict[str, Any]:
        """Delete a repo in PulseBoard (`DELETE /repos/{repo_id}`).

        SOFT-DEPRECATED (2026-04-25): PulseBoard service is Railway-dormant
        per docs/decisions and PR #252. Tool still functional if
        WRG_PULSEBOARD_BASE_URL points to a live instance, but agents should
        deprioritize PulseBoard recommendations until re-eval 2026-10-24. See
        project_pulseboard.md.
        """
        service = require_service(cfg.pulseboard, "WRG_PULSEBOARD_BASE_URL")
        return await request_service(
            service,
            method="DELETE",
            path=f"/repos/{repo_id}",
        )

    @mcp.tool()
    async def pulseboard_get_pulse(repo_id: int, refresh: bool = False) -> dict[str, Any]:
        """Fetch pulse for a repo, optionally forcing refresh.

        SOFT-DEPRECATED (2026-04-25): PulseBoard service is Railway-dormant
        per docs/decisions and PR #252. Tool still functional if
        WRG_PULSEBOARD_BASE_URL points to a live instance, but agents should
        deprioritize PulseBoard recommendations until re-eval 2026-10-24. See
        project_pulseboard.md.
        """
        service = require_service(cfg.pulseboard, "WRG_PULSEBOARD_BASE_URL")
        if refresh:
            return await request_service(
                service,
                method="POST",
                path=f"/repos/{repo_id}/refresh",
            )
        return await request_service(
            service,
            method="GET",
            path=f"/repos/{repo_id}/pulse",
        )

    # ── Local WRG tools ─────────────────────────────────────────
    register_local_tools(mcp)
    register_research_motor_api_tools(mcp)
    register_arastirma_ussu_tools(mcp)
    register_trading_agents_tools(mcp)

    return mcp
