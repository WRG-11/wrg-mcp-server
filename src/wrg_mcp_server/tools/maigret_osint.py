"""Maigret OSINT integration tools for MCP.

Exposes username-based OSINT reconnaissance from Maigret
(github.com/soxoj/maigret) — searches 3000+ sites for accounts.
Requires: pip install maigret
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


def register_maigret_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def maigret_search(username: str, top_sites: int = 100) -> dict[str, Any]:
        """Search for a username across thousands of websites using Maigret OSINT tool.
        Returns list of found accounts with URLs, site names, and tags.
        Useful for digital footprint analysis, person reconnaissance, and
        account discovery across social media, forums, and services.

        Args:
            username: Username to search (e.g. "johndoe")
            top_sites: Number of top sites to check (default 100, max 3000+)

        Requires: pip install maigret. Runs 30-120s depending on top_sites.
        """
        try:
            import maigret as _check  # noqa: F401
        except ImportError:
            return {"ok": False, "error": "maigret not installed. Run: pip install maigret"}

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            cmd = [
                "maigret", username,
                "--top-sites", str(top_sites),
                "-J", "simple",
                "--folderoutput", tmpdir,
                "--no-color",
                "--no-progressbar",
                "--timeout", "15",
                "-n", "10",
            ]

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=180, encoding="utf-8", errors="replace",
                )
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": "maigret timed out after 180s", "username": username}
            except FileNotFoundError:
                return {"ok": False, "error": "maigret CLI not found in PATH"}

            # Find the JSON report
            json_files = list(Path(tmpdir).glob("report_*_simple.json"))
            if not json_files:
                # Try stderr for error info
                return {
                    "ok": False,
                    "error": "no report generated",
                    "stderr": result.stderr[:500] if result.stderr else "",
                    "username": username,
                }

            try:
                report = json.loads(json_files[0].read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                return {"ok": False, "error": f"failed to parse report: {e}"}

            # Extract found accounts
            accounts = []
            tags_set = set()
            for site_name, data in report.items():
                status = data.get("status", {})
                if status.get("status") == "Claimed":
                    account = {
                        "site": site_name,
                        "url": status.get("url", ""),
                        "tags": status.get("tags", []),
                    }
                    # Add extracted IDs if any
                    ids = status.get("ids", {})
                    if ids:
                        account["ids"] = ids
                    accounts.append(account)
                    tags_set.update(status.get("tags", []))

            return {
                "ok": True,
                "username": username,
                "accounts_found": len(accounts),
                "sites_checked": top_sites,
                "accounts": accounts,
                "tags": sorted(tags_set),
                "summary": _build_summary(username, accounts),
            }


def _build_summary(username: str, accounts: list[dict]) -> str:
    if not accounts:
        return f"No accounts found for username '{username}'."
    sites = ", ".join(a["site"] for a in accounts[:10])
    extra = f" and {len(accounts) - 10} more" if len(accounts) > 10 else ""
    return f"Found {len(accounts)} accounts for '{username}': {sites}{extra}."
