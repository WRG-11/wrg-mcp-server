# wrg_mcp_server

> **Status: Scaffold** — app structure created, implementation pending.

MCP (Model Context Protocol) server for WinstonRedGuard. Exposes WRG tools and data as MCP resources so Claude and other MCP-compatible AI agents can interact with the monorepo programmatically.

## Planned Features

- MCP protocol implementation (stdio/SSE transport)
- Tool exposure — governance check, pulse status, app registry queries
- Resource exposure — app metadata, pipeline status, memory store
- Claude Desktop / Claude Code integration
- Authentication and access control

## Run

```bash
wrg-mcp-server
```
