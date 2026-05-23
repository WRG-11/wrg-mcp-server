<!-- mcp-name: io.github.WRG-11/wrg-mcp-server -->

# wrg_mcp_server

[![PyPI](https://img.shields.io/pypi/v/wrg-mcp-server?label=PyPI&color=34D058&style=flat-square)](https://pypi.org/project/wrg-mcp-server/)
[![Python](https://img.shields.io/pypi/pyversions/wrg-mcp-server)](https://pypi.org/project/wrg-mcp-server/)
[![CI](https://github.com/WRG-11/wrg-mcp-server/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/WRG-11/wrg-mcp-server/actions/workflows/ci.yml)
[![CodeQL](https://github.com/WRG-11/wrg-mcp-server/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/WRG-11/wrg-mcp-server/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![MCP Registry](https://img.shields.io/badge/MCP%20Registry-live-3b82f6?style=flat-square)](https://registry.modelcontextprotocol.io/v0/servers?search=wrg-mcp-server)

MCP (Model Context Protocol) server exposing the WinstonRedGuard monorepo to Claude and other MCP-compatible AI agents. Built on `FastMCP` — registers tools from every active WRG app so an agent can inspect the repo, run pipelines, query memory, and call remote services without shelling out.

**Published:**
- PyPI: [`wrg-mcp-server`](https://pypi.org/project/wrg-mcp-server/) (v1.0.5)
- MCP Registry: [`io.github.WRG-11/wrg-mcp-server`](https://registry.modelcontextprotocol.io/v0/servers?search=wrg-mcp-server) (status: `active`; re-submission pending for WRG-11 namespace migration)

## Transports

```bash
wrg-mcp-server --transport stdio              # Claude Desktop / Claude Code
wrg-mcp-server --transport streamable-http    # default HTTP (recommended)
wrg-mcp-server --transport sse                # legacy HTTP
```

Flags: `--host 0.0.0.0` · `--port 8080` · `--mcp-path /mcp`

## Install

```bash
pip install wrg-mcp-server                 # core: MCP + local tools only
pip install "wrg-mcp-server[remote]"       # adds httpx for site_* / pulseboard_* tools
pip install "wrg-mcp-server[dev]"          # pytest + pytest-asyncio
```

From source (standalone repo):

```bash
git clone https://github.com/WRG-11/wrg-mcp-server.git
cd wrg-mcp-server
pip install -e ".[dev]"
```

Note: `[threat-intel]` extras were removed in v1.0.4 (PyPI rejects direct `file://` deps). Sister `wrg_threat_intel` + `ransom_radar` stay in the WRG monorepo for now; will re-add this extras group once they publish to PyPI.

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
| `research_motor_healthz`, `research_motor_scan_create`, `research_motor_scan_get` | `research_motor` HTTP API v1 over localhost |
| `vault_audit` | `wrg_vault` audit ledger inspection |
| `scheduler_task_list`, `scheduler_tick_dry_run` | `wrg_scheduler` inspection |

#### Round 39 — silo-app expansion (6 apps × 2 tools = 12 tools)

**AI fingerprint** (`wrg_ai_fingerprint`)

| Tool | What it does |
|---|---|
| `ai_fingerprint_scan` | Scan a path for AI-generated code signals; supports `min_score`, `exclude[]` |
| `ai_fingerprint_detectors` | List registered detectors and their weights |
| `ai_fingerprint_sigma_emit` | Convert fingerprint scan JSON into Sigma YAML rules (R42 — `wrg_ai_fingerprint_sigma emit`; pass `input_file` *or* `scan_json`, optional `date_override`) |

**DevGuard** (`wrg_devguard`)

| Tool | What it does |
|---|---|
| `devguard_scan` | Run policy / secrets / crypto scans on a path; empty `scan_types` runs combined `check` |
| `devguard_baseline` | List configured policy profiles (baseline + strict) and presence |

**Security suite** (`wrg_security_suite`) — `security_suite_run` is mutation-gated

| Tool | What it does |
|---|---|
| `security_suite_run` | Run code / person / network / full scan (**mutation** — requires `WRG_MCP_ALLOW_MUTATIONS=1`) |
| `security_suite_report` | Read a scan report by `scan_id` from `apps/wrg_security_suite/reports/` (read-only) |

**Rule lab** (`rule_lab`)

| Tool | What it does |
|---|---|
| `rule_lab_test` | Simulate a rule set against sample contexts (`simulate --json`) |
| `rule_lab_list` | List rule files under `$WRG_RULE_LAB_DIR` or `<repo>/.wrg/rules` |

**Data janitor** (`data_janitor`) — `data_janitor_sweep` mutation-gated when `dry_run=False`

| Tool | What it does |
|---|---|
| `data_janitor_sweep` | Scan (dry-run) or clean build artifacts; non-dry requires `WRG_MCP_ALLOW_MUTATIONS=1` |
| `data_janitor_orphans` | Preview orphan / build-artifact targets (read-only) |

**Notifier** (`wrg_notifier3`) — `notifier_send` is mutation-gated

| Tool | What it does |
|---|---|
| `notifier_send` | Dispatch a message to a configured channel (**mutation** — requires `WRG_MCP_ALLOW_MUTATIONS=1`) |
| `notifier_channels` | Introspect available channel adapters (read-only) |

#### Round 50 — INFO_OPS extension

| Tool | What it does |
|---|---|
| `info_ops_detect` | Query INFO_OPS actor corpus (default `modus=info-ops`); enrich each match with linked incidents + Sigma rules; reverse-lookup via `mitre_technique` filter |

#### `info_ops_detect` usage

**Default — list all INFO_OPS actors with Sigma + incidents:**
```python
info_ops_detect()
# -> 3 actors (russia_nexus_info_ops, china_nexus_spamouflage, iran_nexus_apt35),
#    ~21 Sigma rules total, linked incidents per actor
```

**Specific actor lookup:**
```python
info_ops_detect(actor_id="russia_nexus_info_ops")
# -> single-actor detection state (Sigma rules + 2 incidents)
```

**Reverse-lookup — "which info-ops actors use T1656 Impersonation?":**
```python
info_ops_detect(mitre_technique="T1656")
# -> china_nexus_spamouflage + iran_nexus_apt35 (R52);
#    russia_nexus_info_ops excluded (uses T1078 Valid Accounts)
```

### Arastirma Ussu (opt-in via env)

| Tool | What it does |
|---|---|
| `arastirma_ask` | Ask a question to the Arastirma Ussu knowledge base |
| `arastirma_doc_search` | Search documents in the knowledge base |
| `arastirma_web_search` | Web search through Arastirma Ussu |
| `arastirma_memory_search` | Search memory entries |

### Trading (opt-in via env)

| Tool | What it does |
|---|---|
| `trading_analyze` | Full multi-agent trading analysis for a ticker |
| `trading_quick_signal` | Fast RSI/price signal for a ticker |

### OSINT

| Tool | What it does |
|---|---|
| `maigret_search` | Username search across 3000+ sites (Maigret) |

### Threat-intel (opt-in via `[threat-intel]` extra)

| Tool | What it does |
|---|---|
| `attack_surface_passive` | Passive attack surface reconnaissance |
| `ransomware_lookup` | Ransomware group/victim lookup |
| `darkweb_brand_watch` | Dark web brand mention monitoring |

### Ransom-radar

| Tool | What it does |
|---|---|
| `ransom_radar_tick` | Run a ransom-radar feed tick |
| `ransom_radar_status` | Check ransom-radar watchlist status |

### Other

| Tool | What it does |
|---|---|
| `polymarket_event_signal` | Polymarket event signal analysis |
| `research_deep` | Deep research with AI research platform |

### Remote (HTTP, opt-in via env)

| Tool | Upstream |
|---|---|
| `site_health`, `site_get`, `site_post` | Company site API (`WRG_SITE_BASE_URL`) |
| `pulseboard_health`, `pulseboard_list_repos`, `pulseboard_add_repo`, `pulseboard_delete_repo`, `pulseboard_get_pulse` | `pulseboard` dashboard (`WRG_PULSEBOARD_BASE_URL`) |

Remote tools return `{"ok": false, "error": "httpx not installed — remote tools unavailable"}` when the `[remote]` extra is not installed.

### research_motor HTTP API tools

Start the research_motor API separately, then point the MCP server at it:

```bash
cd apps/research_motor
pip install -e ".[api]"
set RESEARCH_MOTOR_API_KEY=replace-me
research-motor serve --host 127.0.0.1 --port 8080
```

Configure the MCP server environment:

```bash
set WRG_RM_API_BASE_URL=http://127.0.0.1:8080
set WRG_RM_API_KEY=replace-me
```

Example MCP tool payloads:

```json
{"target": "example.com", "mode": "domain"}
```

```json
{"scan_id": "sample-scan-abc123"}
```

## Environment

### Repo discovery

| Variable | Default | Purpose |
|---|---|---|
| `WRG_REPO_ROOT` | auto-detect (walk up until `apps/` + `CLAUDE.md`) | Required when installed from wheel outside the monorepo |

### Mutation gate (default: off)

State-changing tools (`memory_set`, `pipeline_run`, `security_suite_run`, `data_janitor_sweep` non-dry, `notifier_send`) refuse to execute unless:

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

## Sister WRG-11 packages

Part of the WRG-11 PyPI portfolio:

- [`instinct-mcp`](https://pypi.org/project/instinct-mcp/) -- MCP server for capturing recurring patterns into structured memory
- [`wrg-devguard`](https://pypi.org/project/wrg-devguard/) -- Developer-first AI safety: prompt-policy lint + secret scanning + log scanning with PII detection
- [`wrg-rule-lab`](https://pypi.org/project/wrg-rule-lab/) -- Local-first deterministic rule evaluation engine (zero-dep, stdlib-only)
- [`ai-security-toolkit`](https://github.com/WRG-11/ai-security-toolkit) -- Offensive + defensive AI/LLM security tools, labs, CTF writeups, research

Built by [WRG-11](https://github.com/WRG-11).

## Status

Production -- 1045 lines, covers every active WRG app, drives the `mcp__wrg__*` tools visible in connected Claude sessions.
