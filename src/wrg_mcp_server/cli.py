"""CLI entrypoint for wrg_mcp_server.

Supports three transports:
  stdio             — for Claude Desktop / Claude Code integration
  streamable-http   — recommended HTTP transport (default)
  sse               — legacy HTTP transport
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="wrg-mcp-server",
        description="WinstonRedGuard MCP server",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="streamable-http",
        help="MCP transport (default: streamable-http)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    parser.add_argument("--mcp-path", default="/mcp", help="HTTP endpoint path (default: /mcp)")

    args = parser.parse_args()

    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(
        host=args.host,
        port=args.port,
        streamable_http_path=args.mcp_path,
    )

    print(
        f"wrg-mcp-server starting (transport={args.transport}, "
        f"host={args.host}, port={args.port})",
        file=sys.stderr,
    )
    server.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
