# Contributing

`wrg-mcp-server` is a single-author, low-traffic project. Contributions are
welcome, but review time is limited and scope control matters.

## Before You Start

- Search existing issues and pull requests first.
- Open an issue before starting larger work or behavior changes.
- Small docs fixes and test-only fixes can go straight to PR.

## Triage Expectations

There is no guaranteed SLA. For small PRs, expect a best-effort review when the
maintainer is active. For larger proposals, an issue may sit until there is a
clear use case, reproduction, or maintainer need.

## Local Dev Setup

```bash
git clone https://github.com/WRG-11/wrg-mcp-server.git
cd wrg-mcp-server
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

## Bar for Accepting a PR

- Tests pass locally and in CI (28 test files, asyncio_mode = "auto").
- No scope creep: one problem per PR.
- Keep the diff at or below 200 LOC unless prearranged in an issue.
- Add or update tests when behavior changes.
- Update README or CHANGELOG only when the user-facing surface changes.
- Do not add dependencies without explaining why stdlib or the existing stack
  (mcp + optional httpx) is insufficient.

## Commit Messages

Use clear, concise commit messages. Conventional commit style is preferred:

- `feat(mcp): add new tool wrapper for X`
- `fix(transport): handle Y edge case`
- `docs: update install instructions`

## Tool Contract Discipline

This server brokers tool execution. Every `@mcp.tool()`-decorated function
must:

- Return the standard envelope: `{"ok": True, ...}` on success or
  `{"ok": False, "error": "...", ...}` on failure.
- Treat `WRG_MCP_ALLOW_MUTATIONS=1` as the mutation gate -- write operations
  refuse without it.
- Never persist potentially sensitive matched text (redact-by-design).

See the existing tools in `src/wrg_mcp_server/local_tools.py` and
`server.py` for canonical patterns.

## Security Issues

Do not open public issues for security vulnerabilities. Use GitHub Security
Advisories:

- https://github.com/WRG-11/wrg-mcp-server/security/advisories
