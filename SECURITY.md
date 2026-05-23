# Security Policy

## Supported Versions

Security fixes are applied to the latest release on `main`.

## Reporting a Vulnerability

Please do not report vulnerabilities in public issues.

Use GitHub Security Advisories:

- https://github.com/WRG-11/wrg-mcp-server/security/advisories

Include:

- A clear description of the issue
- Steps to reproduce
- Potential impact
- Suggested remediation (if available)

Special note for this project: `wrg-mcp-server` brokers tool execution from
AI agents to local CLIs. Vulnerabilities that allow argument injection,
mutation-gate bypass (`WRG_MCP_ALLOW_MUTATIONS`), credential leakage in tool
output, or remote service spoofing (`site_*`, `pulseboard_*`) are
particularly important.

We will acknowledge valid reports and work on a fix as quickly as possible.
