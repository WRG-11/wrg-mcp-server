<!-- mcp-name: io.github.yakuphanycl/wrg-mcp-server -->

# wrg_mcp_server

[![PyPI](https://img.shields.io/pypi/v/wrg-mcp-server?label=PyPI&color=34D058&style=flat-square)](https://pypi.org/project/wrg-mcp-server/)
[![MCP Registry](https://img.shields.io/badge/MCP%20Registry-live-3b82f6?style=flat-square)](https://registry.modelcontextprotocol.io/v0/servers?search=wrg-mcp-server)

MCP (Model Context Protocol) server exposing the WinstonRedGuard monorepo to Claude and other MCP-compatible AI agents. Built on `FastMCP` — registers tools from every active WRG app so an agent can inspect the repo, run pipelines, query memory, and call remote services without shelling out.

**Published:**
- PyPI: [`wrg-mcp-server`](https://pypi.org/project/wrg-mcp-server/) (v1.0.0, 2026-04-24)
- MCP Registry: [`io.github.yakuphanycl/wrg-mcp-server`](https://registry.modelcontextprotocol.io/v0/servers?search=wrg-mcp-server) (status: `active`, 2026-04-24)

## Transports

```bash
wrg-mcp-server --transport stdio              # Claude Desktop / Claude Code
wrg-mcp-server --transport streamable-http    # default HTTP (recommended)
wrg-mcp-server --transport sse                # legacy HTTP
```

Flags: `--host 0.0.0.0` · `--port 8080` · `--mcp-path /mcp`

## Install

```bash
cd apps/wrg_mcp_server
pip install -e .             # core: MCP + local tools only
pip install -e ".[remote]"   # adds httpx for site_* / pulseboard_* tools
pip install -e ".[dev]"      # pytest + pytest-asyncio
```

## Tools exposed

### Local (subprocess-backed, always available)

| Tool | What it does |
|---|---|
| `connector_status` | Report which remote services are configured |
| `app_list`, `app_info` | Query `app_registry/data/registry.json` |
| `governance_run` | Execute `governance_check` across one or all apps |
| `release_check` | Run the `tools/release_check.ps1` gate |
| `pipeline_list`, `pipeline_show`, `pipeline_run` | `wrg_pipeline` DAG operations |
| `pulse_check` | Invoke `wrg-pulse check` |
| `memory_get`, `memory_set`, `memory_list`, `memory_search` | `wrg_memory` key-value access |
| `research_history`, `research_report`, `research_scan`, `research_watch`, `research_scan_summary` | `research_motor` runs and artifacts |
| `vault_audit` | `wrg_vault` audit ledger inspection |
| `scheduler_task_list`, `scheduler_tick_dry_run` | `wrg_scheduler` inspection |

### Remote (HTTP, opt-in via env)

| Tool | Upstream |
|---|---|
| `site_health`, `site_get`, `site_post` | Company site API (`WRG_SITE_BASE_URL`) |
| `pulseboard_health`, `pulseboard_list_repos`, `pulseboard_add_repo`, `pulseboard_delete_repo`, `pulseboard_get_pulse` | `pulseboard` dashboard (`WRG_PULSEBOARD_BASE_URL`) |

Remote tools return `{"ok": false, "error": "httpx not installed — remote tools unavailable"}` when the `[remote]` extra is not installed.

## Environment

### Repo discovery

| Variable | Default | Purpose |
|---|---|---|
| `WRG_REPO_ROOT` | auto-detect (walk up until `apps/` + `CLAUDE.md`) | Required when installed from wheel outside the monorepo |

### Mutation gate (default: off)

State-changing tools (`memory_set`, `pipeline_run`) refuse to execute unless:

```bash
WRG_MCP_ALLOW_MUTATIONS=1
```

This prevents an MCP client from silently writing memory or launching pipelines on a read-only connection.

### Remote service config

Per service (`SITE` / `PULSEBOARD`), prefix with `WRG_<SERVICE>_`:

| Variable | Default | Purpose |
|---|---|---|
| `*_BASE_URL` | — | Enables the service (unset = service disabled) |
| `*_TOKEN` | — | Bearer token for `Authorization` header |
| `*_AUTH_HEADER` | `Authorization` | Override header name |
| `*_AUTH_SCHEME` | `Bearer` | Override token scheme |
| `*_SESSION_COOKIE` | — | Optional `Cookie` header |
| `*_EXTRA_HEADERS` | — | JSON object of extra headers |
| `*_TIMEOUT_SECONDS` | `WRG_HTTP_TIMEOUT_SECONDS` (20.0) | Per-request timeout |
| `*_VERIFY_TLS` | `WRG_HTTP_VERIFY_TLS` (true) | TLS verification |

## Claude Code / Claude Desktop integration

Add to your MCP client config:

```json
{
  "mcpServers": {
    "wrg": {
      "command": "wrg-mcp-server",
      "args": ["--transport", "stdio"],
      "env": {
        "WRG_REPO_ROOT": "D:\\dev\\WinstonRedGuard",
        "WRG_MCP_ALLOW_MUTATIONS": "0"
      }
    }
  }
}
```

## Architecture

```
FastMCP server
├── server.py            — tool registration, remote HTTP dispatch
├── config.py            — ServiceConfig / AppConfig from env (frozen dataclasses)
├── http_utils.py        — URL builder, response parser
├── local_tools.py       — subprocess wrappers for WRG CLIs (~20 tools)
└── cli.py               — argparse entry point
```

Local tools use `subprocess.run` with `stdin=DEVNULL` (not asyncio subprocess) — avoids a Windows pipe-blocking deadlock under anyio. Tool dispatch is wrapped in `anyio.to_thread.run_sync` so the MCP event loop stays responsive.

## Tests

```bash
pytest -q
```

## Status

Production — 1045 lines, covers every active WRG app, drives the `mcp__wrg__*` tools visible in connected Claude sessions.
