"""Local WRG tool wrappers — subprocess-based CLI integration.

Each tool calls a WRG CLI command and returns structured output.
Designed for MCP consumption by Claude and other AI agents.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import partial
from pathlib import Path
from typing import Any

import anyio

from mcp.server.fastmcp import FastMCP

# Repo root: three levels up from this file (src/wrg_mcp_server/local_tools.py)
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _python() -> str:
    """Return the Python interpreter path."""
    return sys.executable or "python"


def _run_cli_sync(
    args: tuple[str, ...],
    timeout: float,
    cwd: str,
) -> dict[str, Any]:
    """Run a CLI command synchronously and return structured result.

    Uses subprocess.run instead of asyncio subprocess to avoid
    Windows event-loop pipe-blocking issues under anyio/MCP.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Command timed out after {timeout}s", "command": args[0]}
    except FileNotFoundError:
        return {"ok": False, "error": f"Command not found: {args[0]}", "command": args[0]}

    out = proc.stdout.decode("utf-8", errors="replace").strip()
    err = proc.stderr.decode("utf-8", errors="replace").strip()

    # Try to parse JSON output
    body: Any = out
    try:
        body = json.loads(out)
    except (json.JSONDecodeError, ValueError):
        pass

    result: dict[str, Any] = {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "output": body,
    }
    if err:
        result["stderr"] = err
    return result


async def _run_cli(
    *args: str,
    timeout: float = 60.0,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Run a CLI command via anyio thread (works under anyio event loop)."""
    work_dir = cwd or str(_REPO_ROOT)
    return await anyio.to_thread.run_sync(
        partial(_run_cli_sync, args, timeout, work_dir),
    )


def register_local_tools(mcp: FastMCP) -> None:
    """Register all local WRG tools on the given FastMCP server."""

    py = _python()

    # ── app_registry ──────────────────────────────────────────────

    @mcp.tool()
    async def app_list() -> dict[str, Any]:
        """List all WRG apps with their status and tier."""
        return await _run_cli(py, "-m", "app_registry.cli", "list")

    @mcp.tool()
    async def app_info(app_name: str) -> dict[str, Any]:
        """Get detailed info about a specific WRG app (JSON)."""
        return await _run_cli(py, "-m", "app_registry.cli", "show", app_name)

    # ── governance_check ──────────────────────────────────────────

    @mcp.tool()
    async def governance_run() -> dict[str, Any]:
        """Run the 55-gate governance check across all WRG apps."""
        return await _run_cli(py, "-m", "governance_check.cli", "check", timeout=120.0)

    # ── research_motor ────────────────────────────────────────────

    @mcp.tool()
    async def research_history() -> dict[str, Any]:
        """List recent research_motor runs (JSON)."""
        return await _run_cli(py, "-m", "research_motor.cli", "history", "--json")

    @mcp.tool()
    async def research_report(run_id: str) -> dict[str, Any]:
        """Get the report for a specific research_motor run (JSON)."""
        return await _run_cli(py, "-m", "research_motor.cli", "report", "--run", run_id, "--json")

    @mcp.tool()
    async def research_scan(input_file: str) -> dict[str, Any]:
        """Run research_motor scan on a JSON input file. Returns candidates."""
        return await _run_cli(
            py, "-m", "research_motor.cli", "scan", "--input", input_file, "--json",
            timeout=120.0,
        )

    @mcp.tool()
    async def research_watch(preset: str = "default") -> dict[str, Any]:
        """Run research_motor watch with a preset. Fetches, scores, decides in one pass."""
        return await _run_cli(
            py, "-m", "research_motor.cli", "watch", "--preset", preset, "--json",
            timeout=180.0,
        )

    # ── wrg_pulse ─────────────────────────────────────────────────

    @mcp.tool()
    async def pulse_check() -> dict[str, Any]:
        """Check WRG system health — all apps, governance, pipelines (JSON)."""
        return await _run_cli(
            py, "-m", "wrg_pulse.cli", "check", "--json",
            "--repo-root", str(_REPO_ROOT),
        )

    # ── wrg_memory ───────────────────────────────────────��────────

    @mcp.tool()
    async def memory_get(key: str) -> dict[str, Any]:
        """Get a value from WRG cross-app memory store."""
        return await _run_cli(py, "-m", "wrg_memory.cli", "get", key)

    @mcp.tool()
    async def memory_set(key: str, value: str, app: str = "", category: str = "") -> dict[str, Any]:
        """Set a value in WRG cross-app memory store."""
        args = [py, "-m", "wrg_memory.cli", "set", key, value]
        if app:
            args.extend(["--app", app])
        if category:
            args.extend(["--cat", category])
        return await _run_cli(*args)

    @mcp.tool()
    async def memory_list(app: str = "", category: str = "", prefix: str = "") -> dict[str, Any]:
        """List entries in WRG memory store, with optional filters."""
        args = [py, "-m", "wrg_memory.cli", "list"]
        if app:
            args.extend(["--app", app])
        if category:
            args.extend(["--cat", category])
        if prefix:
            args.extend(["--prefix", prefix])
        return await _run_cli(*args)

    @mcp.tool()
    async def memory_search(query: str) -> dict[str, Any]:
        """Search WRG memory store by keyword."""
        return await _run_cli(py, "-m", "wrg_memory.cli", "search", query)

    # ── instinct pipeline (via instinct-mcp package) ───────────────

    from instinct.store import InstinctStore, project_fingerprint

    _instinct = InstinctStore()

    @mcp.tool()
    async def instinct_observe(
        pattern: str, category: str = "sequence",
        source: str = "", project: str = "",
    ) -> dict[str, Any]:
        """Record a pattern observation. Increments confidence if already seen.

        Categories: sequence (A->B tool flow), preference (user choice),
        fix_pattern (recurring fix). Example: 'seq:governance_run->pipeline_list'
        """
        proj = project or project_fingerprint()
        return await anyio.to_thread.run_sync(
            partial(_instinct.observe, pattern, category=category, source=source, project=proj),
        )

    @mcp.tool()
    async def instinct_list(
        min_confidence: int = 1, category: str = "",
    ) -> dict[str, Any]:
        """List observed instincts, optionally filtered by minimum confidence or category."""
        entries = await anyio.to_thread.run_sync(
            partial(_instinct.list, min_confidence=min_confidence, category=category or None),
        )
        return {"instincts": entries, "count": len(entries)}

    @mcp.tool()
    async def instinct_suggest(project: str = "") -> dict[str, Any]:
        """Get mature instincts (confidence >= 5) as suggestions."""
        entries = await anyio.to_thread.run_sync(
            partial(_instinct.suggest, project=project or None),
        )
        return {"suggestions": entries, "count": len(entries)}

    @mcp.tool()
    async def instinct_consolidate() -> dict[str, Any]:
        """Auto-promote instincts: confidence>=5 becomes mature, >=10 becomes rule."""
        return await anyio.to_thread.run_sync(_instinct.consolidate)

    # ── wrg_pipeline ──────────────────────────────────────────────

    @mcp.tool()
    async def pipeline_list() -> dict[str, Any]:
        """List all registered WRG pipelines."""
        return await _run_cli(py, "-m", "wrg_pipeline.cli", "list")

    @mcp.tool()
    async def pipeline_show(name: str) -> dict[str, Any]:
        """Show DAG structure for a WRG pipeline."""
        return await _run_cli(py, "-m", "wrg_pipeline.cli", "show", name)

    @mcp.tool()
    async def pipeline_run(name: str, dry: bool = False) -> dict[str, Any]:
        """Run a WRG pipeline. Use dry=True for a dry-run without side effects."""
        args = [py, "-m", "wrg_pipeline.cli", "run", name]
        if dry:
            args.append("--dry")
        return await _run_cli(*args, timeout=300.0)

    # ── release gate ───���──────────────────────────────────────────

    @mcp.tool()
    async def release_check(app_name: str = "") -> dict[str, Any]:
        """Run the WRG release gate (wheel build + smoke + pytest).

        Pass app_name for a single app, or leave empty for all apps.
        """
        ps_script = str(_REPO_ROOT / "tools" / "release_check.ps1")
        args = ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_script]
        if app_name:
            args.extend(["-App", app_name])
        else:
            args.append("-All")
        return await _run_cli(*args, timeout=600.0)
