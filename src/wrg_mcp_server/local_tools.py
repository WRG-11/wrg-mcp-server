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

# Repo root: prefer WRG_REPO_ROOT env var, then walk up from this file.
# When installed from wheel (e.g. release gate), parents[4] won't be the
# monorepo so the env var or git-based fallback is needed.
def _find_repo_root() -> Path:
    env = os.environ.get("WRG_REPO_ROOT")
    if env:
        return Path(env)
    # Walk up from file location (works for editable installs / dev)
    candidate = Path(__file__).resolve().parents[4]
    if (candidate / "apps").is_dir() and (candidate / "CLAUDE.md").is_file():
        return candidate
    # Walk up from cwd as last resort
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "apps").is_dir() and (parent / "CLAUDE.md").is_file():
            return parent
    return candidate  # best guess

_REPO_ROOT = _find_repo_root()
_APPS_DIR = _REPO_ROOT / "apps"

# Apps whose src/ directories need explicit PYTHONPATH (not installed in current Python)
_NEEDS_PYTHONPATH: dict[str, str] = {}  # populated lazily


def _python() -> str:
    """Return the Python interpreter path."""
    return sys.executable or "python"


def _app_src_path(app_name: str) -> Path:
    """Return the src/ directory for an app."""
    return _APPS_DIR / app_name / "src"


def _build_env(app_name: str | None = None) -> dict[str, str]:
    """Build environment dict with PYTHONPATH for uninstalled apps."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if app_name:
        src = _app_src_path(app_name)
        if src.is_dir():
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{src}{os.pathsep}{existing}" if existing else str(src)
    return env


def _run_cli_sync(
    args: tuple[str, ...],
    timeout: float,
    cwd: str,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run a CLI command synchronously and return structured result.

    Uses subprocess.run instead of asyncio subprocess to avoid
    Windows event-loop pipe-blocking issues under anyio/MCP.
    """
    run_env = env or {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=run_env,
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
    app_name: str | None = None,
) -> dict[str, Any]:
    """Run a CLI command via anyio thread (works under anyio event loop)."""
    work_dir = cwd or str(_REPO_ROOT)
    env = _build_env(app_name)
    return await anyio.to_thread.run_sync(
        partial(_run_cli_sync, args, timeout, work_dir, env),
    )


def _read_registry() -> list[dict[str, Any]]:
    """Read app registry directly from registry.json (no subprocess needed)."""
    reg_path = _APPS_DIR / "app_registry" / "src" / "app_registry" / "data" / "registry.json"
    if not reg_path.exists():
        return []
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    return data.get("apps", [])


def _read_pyproject(app_name: str) -> dict[str, Any]:
    """Read pyproject.toml for an app and return parsed TOML dict."""
    pyproject = _APPS_DIR / app_name / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            return {}
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))


def _count_tests(app_name: str) -> int:
    """Count test files under an app's tests/ directory."""
    tests_dir = _APPS_DIR / app_name / "tests"
    if not tests_dir.is_dir():
        return 0
    return sum(1 for f in tests_dir.rglob("test_*.py"))


def _last_commit(app_name: str) -> str:
    """Get the last git commit touching an app directory."""
    app_path = _APPS_DIR / app_name
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%h %s (%cr)", "--", str(app_path)],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            timeout=10,
        )
        return proc.stdout.decode("utf-8", errors="replace").strip() or "no commits"
    except Exception:
        return "unknown"


def register_local_tools(mcp: FastMCP) -> None:
    """Register all local WRG tools on the given FastMCP server."""

    py = _python()
    repo_root = str(_REPO_ROOT)

    # ── app_registry ──────────────────────────────────────────────

    @mcp.tool()
    async def app_list() -> dict[str, Any]:
        """List all WRG apps with their status, class, and tier.

        Returns structured data from registry.json — no subprocess needed.
        """
        apps = await anyio.to_thread.run_sync(_read_registry)
        summary = []
        for a in apps:
            summary.append({
                "name": a["name"],
                "status": a.get("status", "unknown"),
                "class": a.get("class", ""),
                "primary_role": a.get("primary_role", ""),
            })
        active = sum(1 for a in apps if a.get("status") == "active")
        return {
            "ok": True,
            "apps": summary,
            "total": len(apps),
            "active": active,
        }

    @mcp.tool()
    async def app_info(name: str) -> dict[str, Any]:
        """Get detailed info about a specific WRG app.

        Includes: registry entry, pyproject.toml metadata, test count, last commit.
        """
        def _gather() -> dict[str, Any]:
            # Registry entry
            apps = _read_registry()
            entry = next((a for a in apps if a["name"] == name), None)
            if entry is None:
                return {"ok": False, "error": f"App not found: {name}"}

            # pyproject.toml
            pyproject = _read_pyproject(name)
            project_meta = pyproject.get("project", {})

            # Test count
            test_count = _count_tests(name)

            # Last commit
            commit = _last_commit(name)

            return {
                "ok": True,
                "name": name,
                "registry": entry,
                "version": project_meta.get("version", "unknown"),
                "description": project_meta.get("description", ""),
                "dependencies": project_meta.get("dependencies", []),
                "requires_python": project_meta.get("requires-python", ""),
                "test_files": test_count,
                "last_commit": commit,
            }

        return await anyio.to_thread.run_sync(_gather)

    # ── governance_check ──────────────────────────────────────────

    @mcp.tool()
    async def governance_run(app: str = "") -> dict[str, Any]:
        """Run the governance check across WRG apps.

        Pass app name to check a single app, or leave empty for all.
        Returns structured governance results.
        """
        args = [py, "-m", "governance_check.cli", "check",
                "--repo-root", repo_root]
        result = await _run_cli(*args, timeout=120.0,
                                app_name="governance_check")
        if app and result.get("ok") and isinstance(result.get("output"), str):
            # Filter output for the specific app
            lines = result["output"].splitlines()
            filtered = [l for l in lines if app in l or l.startswith("governance")]
            result["output"] = "\n".join(filtered) if filtered else result["output"]
        return result

    # ── release gate ──────────────────────────────────────────────

    @mcp.tool()
    async def release_check(app_name: str = "") -> dict[str, Any]:
        """Run the WRG release gate (wheel build + smoke + pytest).

        Pass app_name for a single app, or leave empty for all apps.
        """
        ps_script = str(_REPO_ROOT / "tools" / "release_check.ps1")
        args = ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", ps_script]
        if app_name:
            args.extend(["-App", app_name])
        else:
            args.append("-All")
        return await _run_cli(*args, timeout=600.0)

    # ── wrg_pipeline ──────────────────────────────────────────────

    @mcp.tool()
    async def pipeline_list() -> dict[str, Any]:
        """List all registered WRG pipelines."""
        return await _run_cli(py, "-m", "wrg_pipeline.cli", "list",
                              app_name="wrg_pipeline")

    @mcp.tool()
    async def pipeline_show(name: str) -> dict[str, Any]:
        """Show DAG structure for a WRG pipeline."""
        return await _run_cli(py, "-m", "wrg_pipeline.cli", "show", name,
                              app_name="wrg_pipeline")

    @mcp.tool()
    async def pipeline_run(name: str, dry: bool = False) -> dict[str, Any]:
        """Run a WRG pipeline. Use dry=True for a dry-run without side effects."""
        args = [py, "-m", "wrg_pipeline.cli", "run", name]
        if dry:
            args.append("--dry")
        return await _run_cli(*args, timeout=300.0, app_name="wrg_pipeline")

    # ── pulse_core ────────────────────────────────────────────────

    @mcp.tool()
    async def pulse_check() -> dict[str, Any]:
        """Check WRG system health — all apps, governance, pipelines (JSON)."""
        return await _run_cli(
            py, "-m", "pulse_core.pulse_cli", "check", "--json",
            "--repo-root", repo_root,
            app_name="pulse_core",
        )

    # ── wrg_memory ────────────────────────────────────────────────

    @mcp.tool()
    async def memory_get(key: str) -> dict[str, Any]:
        """Get a value from WRG cross-app memory store."""
        return await _run_cli(py, "-m", "wrg_memory.cli", "get", key,
                              app_name="wrg_memory")

    @mcp.tool()
    async def memory_set(key: str, value: str, app: str = "",
                         category: str = "") -> dict[str, Any]:
        """Set a value in WRG cross-app memory store."""
        args = [py, "-m", "wrg_memory.cli", "set", key, value]
        if app:
            args.extend(["--app", app])
        if category:
            args.extend(["--cat", category])
        return await _run_cli(*args, app_name="wrg_memory")

    @mcp.tool()
    async def memory_list(app: str = "", category: str = "",
                          prefix: str = "") -> dict[str, Any]:
        """List entries in WRG memory store, with optional filters."""
        args = [py, "-m", "wrg_memory.cli", "list"]
        if app:
            args.extend(["--app", app])
        if category:
            args.extend(["--cat", category])
        if prefix:
            args.extend(["--prefix", prefix])
        return await _run_cli(*args, app_name="wrg_memory")

    @mcp.tool()
    async def memory_search(query: str) -> dict[str, Any]:
        """Search WRG memory store by keyword."""
        return await _run_cli(py, "-m", "wrg_memory.cli", "search", query,
                              app_name="wrg_memory")

    # ── research_motor ────────────────────────────────────────────

    @mcp.tool()
    async def research_history() -> dict[str, Any]:
        """List recent research_motor runs (JSON)."""
        return await _run_cli(py, "-m", "research_motor.cli", "history", "--json",
                              app_name="research_motor")

    @mcp.tool()
    async def research_report(run_id: str) -> dict[str, Any]:
        """Get the report for a specific research_motor run (JSON)."""
        return await _run_cli(py, "-m", "research_motor.cli", "report",
                              "--run", run_id, "--json",
                              app_name="research_motor")

    @mcp.tool()
    async def research_scan(query: str) -> dict[str, Any]:
        """Run research_motor scan on a JSON input file. Returns candidates."""
        return await _run_cli(
            py, "-m", "research_motor.cli", "scan",
            "--input", query, "--json",
            timeout=120.0, app_name="research_motor",
        )

    @mcp.tool()
    async def research_watch(preset: str = "default") -> dict[str, Any]:
        """Run research_motor watch with a preset.

        Fetches, scores, decides in one pass.
        """
        return await _run_cli(
            py, "-m", "research_motor.cli", "watch",
            "--preset", preset, "--json",
            timeout=180.0, app_name="research_motor",
        )
