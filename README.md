<!-- mcp-name: io.github.WRG-11/wrg-mcp-server -->

# wrg-mcp-server

> 💡 **Found this useful?** ⭐ Star the repo (helps others find it) and subscribe to weekly detection-engineering writeups at [Detection Frontier](https://detection-frontier.kit.com/subscribe).

[![PyPI](https://img.shields.io/pypi/v/wrg-mcp-server?label=PyPI&color=34D058&style=flat-square)](https://pypi.org/project/wrg-mcp-server/)
[![Python](https://img.shields.io/pypi/pyversions/wrg-mcp-server)](https://pypi.org/project/wrg-mcp-server/)
[![CI](https://github.com/WRG-11/wrg-mcp-server/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/WRG-11/wrg-mcp-server/actions/workflows/ci.yml)
[![CodeQL](https://github.com/WRG-11/wrg-mcp-server/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/WRG-11/wrg-mcp-server/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![MCP Registry](https://img.shields.io/badge/MCP%20Registry-live-3b82f6?style=flat-square)](https://registry.modelcontextprotocol.io/v0/servers?search=wrg-mcp-server)

> **Give your AI agent direct access to a 60+ tool security & threat-intel stack via MCP — secret scanning, sigma rule generation, ransomware lookup, OSINT, deep research, and more.**

An MCP (Model Context Protocol) bridge that exposes the [WinstonRedGuard](https://github.com/WRG-11) AI security platform to Claude Code, Claude Desktop, Cursor, Codex, and any MCP-compatible AI agent.

## Why this exists

Modern AI coding agents (Claude, Cursor, Codex) excel at code generation but cannot directly:

- Scan a repo for leaked secrets, credentials, or PII patterns
- Look up ransomware groups, victims, and infrastructure by name
- Generate Sigma detection rules from observed incident data
- Run OSINT username probes across 3000+ sites
- Query a curated threat-intel actor corpus with MITRE ATT&CK mappings

This MCP server fills that gap. Drop it into your MCP client config and your agent gains 60+ tools spanning code security, threat intelligence, OSINT, research, and signal analysis — all without leaving the agent's context.

## Use cases

- **Secure-by-default coding workflows** — agent runs `devguard_scan` before every commit, catches API keys + PII patterns before they ship
- **Threat-intel queries during incident response** — "What's the latest LockBit infrastructure?" → agent calls `ransomware_lookup` + `darkweb_brand_watch` directly
- **Detection engineering with AI assistance** — `ai_fingerprint_sigma_emit` converts observed AI-generated code patterns into Sigma YAML rules
- **OSINT investigations** — `maigret_search` username probe across 3000+ sites; results flow back into the agent's reasoning context
- **Research automation** — `research_motor` HTTP API gives the agent persistent, queryable research jobs across domains

## Quick start

```bash
pip install wrg-mcp-server                 # core: 40+ local tools
pip install "wrg-mcp-server[remote]"       # adds httpx for site_* / pulseboard_* tools
```

Add to your Claude Code / Claude Desktop config:

```json
{
  "mcpServers": {
    "wrg": {
      "command": "wrg-mcp-server",
      "args": ["--transport", "stdio"],
      "env": {
        "WRG_MCP_ALLOW_MUTATIONS": "0"
      }
    }
  }
}
```

Restart your client. The agent now has access to `mcp__wrg__*` tools.

## How it compares

| Project | Surface | Tool count | Auth required | Best for |
|---|---|---|---|---|
| **wrg-mcp-server** | Security + threat-intel + OSINT + research | 60+ | Optional env per remote | Security/detection/threat-intel engineers + AI agents |
| [github-mcp-server](https://github.com/github/github-mcp-server) | GitHub API | ~30 | Required (PAT) | General GitHub workflow automation |
| [Filesystem MCP](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) | Local fs | ~10 | None | Generic file operations |
| [Playwright MCP](https://github.com/microsoft/playwright-mcp) | Browser automation | ~20 | None | Web scraping + UI testing |
| [Fetch MCP](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch) | HTTP fetch | ~5 | None | Simple URL → markdown extraction |

## When to reach for wrg-mcp-server

- You're a **security engineer**, **detection engineer**, or **threat-intel analyst** working with AI agents
- You want curated threat-intel + OSINT in your agent without manual tool-juggling
- You have (or can install) the WinstonRedGuard monorepo for the full feature set

## Where wrg-mcp-server loses today (honest delta)

- **Setup friction higher than generic MCP servers** — full feature set requires the WinstonRedGuard monorepo (private). Standalone install (no monorepo) gives ~40% of tools (OSINT + research + trading + polymarket all work without monorepo)
- **Windows-first** — primary dev environment is Windows 11 + WSL2; macOS/Linux supported but less battle-tested
- **Documentation density** — 60+ tools is a lot; in-depth per-tool docs live in source comments rather than separate pages
- **Newer than alternatives** — github-mcp-server, Filesystem, Playwright MCP all have larger communities and more battle-testing

## Transports

```bash
wrg-mcp-server --transport stdio              # Claude Desktop / Claude Code (recommended)
wrg-mcp-server --transport streamable-http    # HTTP for remote clients
wrg-mcp-server --transport sse                # legacy HTTP (SSE)
```

Flags: `--host 0.0.0.0` · `--port 8080` · `--mcp-path /mcp`

## Install (full options)

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

> **Note**: `[threat-intel]` extras were removed in v1.0.4 (PyPI rejects direct `file://` deps). Sister `wrg_threat_intel` + `ransom_radar` stay in the WRG monorepo for now; will re-add this extras group once they publish to PyPI.

## Tool surface

60+ tools organised across 8 categories. Detailed tables below — expand a section to view.

<details>
<summary><b>Local tools</b> (subprocess-backed; always available regardless of remote config)</summary>

### Core monorepo introspection

| Tool | What it does |
|---|---|
| `connector_status` | Report which remote services are configured |
| `app_list`, `app_info` | Query `app_registry/data/registry.json` |
| `governance_run` | Execute `governance_check` across one or all apps |
| `release_check` | Run the `tools/release_check.ps1` gate |
| `pipeline_list`, `pipeline_show`, `pipeline_run` | `wrg_pipeline` DAG operations |
| `pulse_check` | Invoke `wrg-pulse check` |
| `memory_get`, `memory_set`, `memory_list`, `memory_search` | `wrg_memory` key-value access |
| `vault_audit` | `wrg_vault` audit ledger inspection |
| `scheduler_task_list`, `scheduler_tick_dry_run` | `wrg_scheduler` inspection |

### Research

| Tool | What it does |
|---|---|
| `research_history`, `research_report`, `research_scan`, `research_watch`, `research_scan_summary` | `research_motor` runs and artifacts |
| `research_motor_healthz`, `research_motor_scan_create`, `research_motor_scan_get` | `research_motor` HTTP API v1 over localhost |

### Silo-app expansion (6 apps × 2 tools)

**AI fingerprint** (`wrg_ai_fingerprint`)

| Tool | What it does |
|---|---|
| `ai_fingerprint_scan` | Scan a path for AI-generated code signals; supports `min_score`, `exclude[]` |
| `ai_fingerprint_detectors` | List registered detectors and their weights |
| `ai_fingerprint_sigma_emit` | Convert fingerprint scan JSON into Sigma YAML rules |

**DevGuard** (`wrg_devguard`)

| Tool | What it does |
|---|---|
| `devguard_scan` | Run policy / secrets / crypto scans on a path; empty `scan_types` runs combined `check` |
| `devguard_baseline` | List configured policy profiles (baseline + strict) and presence |

**Security suite** (`wrg_security_suite`) — `security_suite_run` is mutation-gated

| Tool | What it does |
|---|---|
| `security_suite_run` | Run code / person / network / full scan (**mutation** — requires `WRG_MCP_ALLOW_MUTATIONS=1`) |
| `security_suite_report` | Read a scan report by `scan_id` (read-only) |

**Rule lab** (`rule_lab`)

| Tool | What it does |
|---|---|
| `rule_lab_test` | Simulate a rule set against sample contexts |
| `rule_lab_list` | List rule files under `$WRG_RULE_LAB_DIR` or `<repo>/.wrg/rules` |

**Data janitor** (`data_janitor`) — `data_janitor_sweep` mutation-gated when `dry_run=False`

| Tool | What it does |
|---|---|
| `data_janitor_sweep` | Scan or clean build artifacts (non-dry requires `WRG_MCP_ALLOW_MUTATIONS=1`) |
| `data_janitor_orphans` | Preview orphan / build-artifact targets (read-only) |

**Notifier** (`wrg_notifier3`) — `notifier_send` is mutation-gated

| Tool | What it does |
|---|---|
| `notifier_send` | Dispatch a message to a configured channel (**mutation** — requires `WRG_MCP_ALLOW_MUTATIONS=1`) |
| `notifier_channels` | Introspect available channel adapters (read-only) |

### INFO_OPS extension

| Tool | What it does |
|---|---|
| `info_ops_detect` | Query INFO_OPS actor corpus; enrich each match with linked incidents + Sigma rules; reverse-lookup via `mitre_technique` filter |

Example:

```python
info_ops_detect()  # all INFO_OPS actors + Sigma + incidents
info_ops_detect(actor_id="russia_nexus_info_ops")  # specific actor
info_ops_detect(mitre_technique="T1656")  # reverse lookup
```

</details>

<details>
<summary><b>OSINT + threat-intel</b> (mostly standalone — works without WRG monorepo)</summary>

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

</details>

<details>
<summary><b>Arastirma Ussu</b> (knowledge-base RAG; opt-in via env)</summary>

| Tool | What it does |
|---|---|
| `arastirma_ask` | Ask a question to the Arastirma Ussu knowledge base |
| `arastirma_doc_search` | Search documents in the knowledge base |
| `arastirma_web_search` | Web search through Arastirma Ussu |
| `arastirma_memory_search` | Search memory entries |

</details>

<details>
<summary><b>Trading + signals</b> (opt-in via env; works without WRG monorepo)</summary>

| Tool | What it does |
|---|---|
| `trading_analyze` | Full multi-agent trading analysis for a ticker |
| `trading_quick_signal` | Fast RSI/price signal for a ticker |
| `polymarket_event_signal` | Polymarket event signal analysis |
| `research_deep` | Deep research with AI research platform |

</details>

<details>
<summary><b>Remote HTTP services</b> (opt-in via env; requires <code>[remote]</code> extra)</summary>

| Tool | Upstream |
|---|---|
| `site_health`, `site_get`, `site_post` | Company site API (`WRG_SITE_BASE_URL`) |
| `pulseboard_health`, `pulseboard_list_repos`, `pulseboard_add_repo`, `pulseboard_delete_repo`, `pulseboard_get_pulse` | `pulseboard` dashboard (`WRG_PULSEBOARD_BASE_URL`) |

Remote tools return `{"ok": false, "error": "httpx not installed — remote tools unavailable"}` when `[remote]` extra is missing.

</details>

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

### research_motor HTTP API

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

- [`instinct-mcp`](https://pypi.org/project/instinct-mcp/) — Self-learning memory for AI coding agents
- [`wrg-devguard`](https://pypi.org/project/wrg-devguard/) — Developer-first AI safety: prompt-policy lint + secret scanning + log scanning with PII detection
- [`wrg-rule-lab`](https://pypi.org/project/wrg-rule-lab/) — Local-first deterministic rule evaluation engine (zero-dep, stdlib-only)
- [`ai-security-toolkit`](https://github.com/WRG-11/ai-security-toolkit) — Offensive + defensive AI/LLM security tools, labs, CTF writeups, research

Built by [WRG-11](https://github.com/WRG-11).

## Status

Production — covers every active WRG app, drives the `mcp__wrg__*` tools visible in connected Claude sessions.

## License

MIT. See [LICENSE](LICENSE).
