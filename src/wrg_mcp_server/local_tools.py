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


def _mutations_allowed() -> bool:
    """Whether state-changing tools (memory_set, pipeline_run) may execute.

    Gated by ``WRG_MCP_ALLOW_MUTATIONS`` so an MCP session can't silently
    write to the user's memory store or kick off a pipeline unless the
    operator explicitly opted in.
    """
    raw = (os.environ.get("WRG_MCP_ALLOW_MUTATIONS") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _mutation_denied(tool: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": (
            f"{tool} is a mutation and WRG_MCP_ALLOW_MUTATIONS is not set. "
            "Set WRG_MCP_ALLOW_MUTATIONS=1 in the MCP server environment "
            "to allow state-changing tools."
        ),
    }


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
    reg_path = _APPS_DIR / "wrg_governance" / "src" / "wrg_governance" / "registry" / "data" / "registry.json"
    if not reg_path.exists():
        return []
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    return list(data.get("apps", []))


def _read_pyproject(app_name: str) -> dict[str, Any]:
    """Read pyproject.toml for an app and return parsed TOML dict."""
    pyproject = _APPS_DIR / app_name / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]  # Python 3.10 fallback for built-in tomllib
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
        args = [py, "-m", "wrg_governance.checks.cli", "check",
                "--repo-root", repo_root]
        result = await _run_cli(*args, timeout=120.0,
                                app_name="wrg_governance")
        if app and result.get("ok") and isinstance(result.get("output"), str):
            # Filter output for the specific app
            lines = result["output"].splitlines()
            filtered = [
                line for line in lines if app in line or line.startswith("governance")
            ]
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
        """List registered wrg_pipeline DAG names available in this WRG checkout.

        Use when the user asks "what pipelines exist?", "show pipeline
        registry", or before calling pipeline_show / pipeline_run and you need
        the exact pipeline name. Returns the standard _run_cli envelope:
        {ok, exit_code, output, stderr?}.
        """
        return await _run_cli(py, "-m", "wrg_pipeline.cli", "list",
                              app_name="wrg_pipeline")

    @mcp.tool()
    async def pipeline_show(name: str) -> dict[str, Any]:
        """Show the wrg_pipeline DAG structure for one named pipeline.

        Use when the user asks "what does this pipeline do?", "show pipeline
        steps", or before pipeline_run to inspect task order and dependencies.
        Use pipeline_list first if the pipeline name is unknown. Returns the
        standard _run_cli envelope: {ok, exit_code, output, stderr?}.
        """
        return await _run_cli(py, "-m", "wrg_pipeline.cli", "show", name,
                              app_name="wrg_pipeline")

    @mcp.tool()
    async def pipeline_run(
        name: str,
        dry: bool = False,
        partial_ok: bool = False,
    ) -> dict[str, Any]:
        """Run a WRG pipeline (LONG-RUNNING — can take minutes).

        MUTATION: a non-dry run spawns real subprocesses and may write to
        the filesystem, so it requires WRG_MCP_ALLOW_MUTATIONS=1 in the
        server env. ``dry=True`` bypasses the guard since no side effects
        occur. ``partial_ok=True`` passes ``--partial-ok-exit-2`` through
        so partial_success runs surface a distinct exit code.
        """
        if not dry and not _mutations_allowed():
            return _mutation_denied("pipeline_run")
        args = [py, "-m", "wrg_pipeline.cli", "run", name]
        if dry:
            args.append("--dry")
        if partial_ok:
            args.append("--partial-ok-exit-2")
        return await _run_cli(*args, timeout=300.0, app_name="wrg_pipeline")

    # ── pulse_core ────────────────────────────────────────────────

    @mcp.tool()
    async def pulse_check() -> dict[str, Any]:
        """Check WRG system health — all apps, governance, pipelines (JSON)."""
        return await _run_cli(
            py, "-m", "pulseboard.collectors.pulse_core.pulse_cli", "check", "--json",
            "--repo-root", repo_root,
            app_name="pulseboard",
        )

    # ── wrg_memory ────────────────────────────────────────────────

    @mcp.tool()
    async def memory_get(key: str) -> dict[str, Any]:
        """Read one key from the WRG cross-app memory store.

        Use when the user asks "what is stored for this key?", "retrieve WRG
        memory", or when a workflow needs a previously persisted value before
        deciding the next action. Use memory_list or memory_search when the
        exact key is unknown. Returns the standard _run_cli envelope:
        {ok, exit_code, output, stderr?}.
        """
        return await _run_cli(py, "-m", "wrg_memory.cli", "get", key,
                              app_name="wrg_memory")

    @mcp.tool()
    async def memory_set(key: str, value: str, app: str = "",
                         category: str = "",
                         ttl_seconds: int | None = None) -> dict[str, Any]:
        """Set a value in WRG cross-app memory store.

        MUTATION: requires WRG_MCP_ALLOW_MUTATIONS=1 in the server env.
        ``ttl_seconds`` is converted to hours (ceil) since the underlying
        store is hour-granular.
        """
        if not _mutations_allowed():
            return _mutation_denied("memory_set")
        args = [py, "-m", "wrg_memory.cli", "set", key, value]
        if app:
            args.extend(["--app", app])
        if category:
            args.extend(["--cat", category])
        if ttl_seconds is not None:
            import math
            ttl_hours = max(1, math.ceil(ttl_seconds / 3600))
            args.extend(["--ttl", str(ttl_hours)])
        return await _run_cli(*args, app_name="wrg_memory")

    @mcp.tool()
    async def memory_list(app: str = "", category: str = "",
                          prefix: str = "") -> dict[str, Any]:
        """List WRG cross-app memory store entries with optional filters.

        Use when the user asks "show memory entries", "list memory for this
        app/category", or when you need to discover keys before memory_get.
        Filter by app, category, or key prefix; use memory_search for keyword
        search across values. Returns the standard _run_cli envelope:
        {ok, exit_code, output, stderr?}.
        """
        args = [py, "-m", "wrg_memory.cli", "list"]
        if app:
            args.extend(["--app", app])
        if category:
            args.extend(["--cat", category])
        if prefix:
            args.extend(["--prefix", prefix])
        return await _run_cli(*args, app_name="wrg_memory")

    @mcp.tool()
    async def memory_search(query: str, limit: int = 10) -> dict[str, Any]:
        """Search WRG memory store by keyword.

        ``limit`` is passed as ``--limit N`` to the underlying CLI; older
        CLI versions ignore it, newer ones slice results server-side.
        """
        safe_limit = max(1, min(int(limit), 500))
        return await _run_cli(
            py, "-m", "wrg_memory.cli", "search", query,
            "--limit", str(safe_limit),
            app_name="wrg_memory",
        )

    # ── research_motor ────────────────────────────────────────────

    @mcp.tool()
    async def research_history() -> dict[str, Any]:
        """List recent research_motor local CLI runs as JSON history.

        Use when the user asks "what research scans ran recently?", "show
        research history", or before research_report when you need a run_id.
        This is the local CLI history surface; use research_motor_scan_get for
        HTTP API scan results. Returns the standard _run_cli envelope:
        {ok, exit_code, output, stderr?}.
        """
        return await _run_cli(py, "-m", "research_motor.cli", "history", "--json",
                              app_name="research_motor")

    @mcp.tool()
    async def research_report(run_id: str) -> dict[str, Any]:
        """Fetch one research_motor local CLI run report as JSON.

        Use when the user asks "show this research report", "open run
        details", or after research_history returns a run_id that needs
        inspection. This reads stored local research_motor output; use
        research_scan to create a new local scan. Returns the standard
        _run_cli envelope: {ok, exit_code, output, stderr?}.
        """
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

    @mcp.tool()
    async def research_scan_summary() -> dict[str, Any]:
        """Return the most recent research_motor watch summary.

        Wraps ``research history --json`` and surfaces the latest run so
        Claude can say "this morning's scan found 279 candidates" without
        parsing the full history.
        """
        result = await _run_cli(
            py, "-m", "research_motor.cli", "history", "--json",
            app_name="research_motor",
        )
        if not result.get("ok"):
            return result
        history = result.get("output") or []
        if not isinstance(history, list) or not history:
            return {"ok": True, "latest": None, "history_count": 0}
        return {
            "ok": True,
            "latest": history[0],
            "history_count": len(history),
        }

    # ── wrg_vault ─────────────────────────────────────────────────

    @mcp.tool()
    async def vault_audit(
        warn_days: int = 14,
        stale_days: int = 365,
    ) -> dict[str, Any]:
        """Audit the encrypted vault for expiring or stale secrets.

        Composes ``wrg-vault list --json`` and ``wrg-vault expiring --days N --json``
        into a single structured report:

            {
              "ok": True,
              "total": int,
              "expiring_soon": [name, ...],     # within ``warn_days``
              "stale":         [name, ...],     # updated_at older than ``stale_days``
              "details": {name: entry, ...},    # full vault entries
            }
        """
        py_exe = _python()
        all_resp = await _run_cli(
            py_exe, "-m", "wrg_vault.cli", "list", "--json",
            app_name="wrg_vault",
        )
        if not all_resp.get("ok"):
            return {
                "ok": False,
                "error": (all_resp.get("stderr") or "vault list failed").strip(),
            }
        exp_resp = await _run_cli(
            py_exe, "-m", "wrg_vault.cli", "expiring",
            "--days", str(int(warn_days)), "--json",
            app_name="wrg_vault",
        )
        if not exp_resp.get("ok"):
            return {
                "ok": False,
                "error": (exp_resp.get("stderr") or "vault expiring failed").strip(),
            }

        entries = all_resp.get("output") or []
        expiring = exp_resp.get("output") or []
        if not isinstance(entries, list):
            entries = []
        if not isinstance(expiring, list):
            expiring = []

        from datetime import datetime, timedelta, timezone

        stale_cutoff = datetime.now(timezone.utc) - timedelta(days=int(stale_days))

        def _updated_at(e: dict[str, Any]) -> datetime | None:
            raw = e.get("updated_at")
            if not isinstance(raw, str):
                return None
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        stale = [
            e["name"] for e in entries
            if isinstance(e, dict) and e.get("name")
            and ((ua := _updated_at(e)) is None or ua < stale_cutoff)
        ]

        return {
            "ok": True,
            "total": len(entries),
            "expiring_soon": [
                e["name"] for e in expiring
                if isinstance(e, dict) and e.get("name")
            ],
            "stale": stale,
            "details": {e["name"]: e for e in entries
                        if isinstance(e, dict) and e.get("name")},
            "warn_days": int(warn_days),
            "stale_days": int(stale_days),
        }

    # ── wrg_scheduler ─────────────────────────────────────────────

    @mcp.tool()
    async def scheduler_task_list() -> dict[str, Any]:
        """List all registered scheduler tasks (hardcoded + YAML merged view).

        Wraps ``wrg-schedule task-list`` and returns the raw output; the
        underlying CLI prints a ``TASK | SOURCE | CMD`` table.
        """
        return await _run_cli(
            py, "-m", "wrg_scheduler.cli", "task-list",
            app_name="wrg_scheduler",
        )

    @mcp.tool()
    async def scheduler_tick_dry_run() -> dict[str, Any]:
        """Preview which scheduled tasks would run RIGHT NOW.

        Read-only — calls ``wrg_scheduler.schedules.get_due_tasks`` via an
        inline Python snippet so Claude can see the tick's blast radius
        without executing anything.
        """
        snippet = (
            "import json, sys; "
            "from wrg_scheduler.schedules import get_due_tasks; "
            "sys.stdout.write(json.dumps(get_due_tasks()))"
        )
        result = await _run_cli(
            py, "-c", snippet,
            app_name="wrg_scheduler",
        )
        if not result.get("ok"):
            return result
        due = result.get("output")
        if not isinstance(due, list):
            due = []
        return {"ok": True, "due": due, "count": len(due)}

    # ── wrg_ai_fingerprint ────────────────────────────────────────
    # Round 39: MCP expansion wave — 6 silo app × 2 tool = 12 tools.
    # Convention: <app_short>_<verb>, async, _run_cli envelope,
    # mutation tools gated by WRG_MCP_ALLOW_MUTATIONS.

    @mcp.tool()
    async def ai_fingerprint_scan(
        path: str,
        min_score: float = 0.5,
        exclude: list[str] | None = None,
    ) -> dict[str, Any]:
        """Scan a path for AI-augmented code fingerprints.

        Use when the user asks "scan for AI-generated code", "is this
        LLM-written?", or before reviewing security-sensitive PRs. Returns
        the standard _run_cli envelope: {ok, exit_code, output, stderr?}.
        """
        args = [py, "-m", "wrg_ai_fingerprint", "scan", path,
                "--min-score", str(float(min_score)), "--json"]
        for ex in (exclude or []):
            args.extend(["--exclude", str(ex)])
        return await _run_cli(*args, timeout=300.0,
                              app_name="wrg_ai_fingerprint")

    @mcp.tool()
    async def ai_fingerprint_detectors() -> dict[str, Any]:
        """List registered AI-fingerprint detectors and their weights.

        Use when the user asks "what detectors are available?", "show
        fingerprint signals", or before ai_fingerprint_scan to understand
        what will be measured. Returns the standard _run_cli envelope:
        {ok, exit_code, output, stderr?}.
        """
        return await _run_cli(
            py, "-m", "wrg_ai_fingerprint", "detectors",
            timeout=60.0, app_name="wrg_ai_fingerprint",
        )

    # ── wrg_ai_fingerprint_sigma (R42) ────────────────────────────
    # R40 shipped wrg_ai_fingerprint_sigma; R42 exposes its emit step
    # as a Claude-callable MCP tool so the Phase 9.4 R4 chain
    # (scan → emit → validate) is reachable end-to-end via MCP.

    @mcp.tool()
    async def ai_fingerprint_sigma_emit(
        scan_json: list[dict[str, Any]] | None = None,
        input_file: str | None = None,
        date_override: str | None = None,
    ) -> dict[str, Any]:
        """Convert wrg_ai_fingerprint scan output into Sigma rule YAML.

        Use when the user asks "convert these fingerprint findings to
        Sigma", "emit detection rules from the scan", or after running
        ai_fingerprint_scan and wanting downstream SOC-pipeline deployable
        rules. Provide exactly one of ``scan_json`` (inline list of result
        dicts) or ``input_file`` (path to a JSON file). ``date_override``
        is optional (YYYY-MM-DD); when omitted the emitter picks its own
        default. Returns the standard _run_cli envelope; on success the
        ``output`` field carries the rendered Sigma YAML as text.
        """
        if scan_json is not None and input_file is not None:
            return {
                "ok": False,
                "error": "Provide either scan_json or input_file, not both",
            }
        if scan_json is None and input_file is None:
            return {
                "ok": False,
                "error": "Provide either scan_json or input_file",
            }

        tmp_path: Path | None = None
        try:
            if scan_json is not None:
                # _run_cli has no stdin pipe (subprocess.DEVNULL), so we
                # materialise inline JSON to a temp file and pass it as
                # the positional input.
                import tempfile
                fd, name = tempfile.mkstemp(
                    prefix="wrg_sigma_emit_", suffix=".json"
                )
                tmp_path = Path(name)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(scan_json, handle)
                except Exception:
                    tmp_path.unlink(missing_ok=True)
                    raise
                input_arg = str(tmp_path)
            else:
                # input_file is guaranteed non-None by the guard above.
                input_arg = str(input_file)

            args = [
                py, "-m", "wrg_ai_fingerprint_sigma", "emit",
                input_arg, "--stdout",
            ]
            if date_override:
                args.extend(["--date", date_override])

            return await _run_cli(
                *args, timeout=120.0,
                app_name="wrg_ai_fingerprint_sigma",
            )
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    # ── wrg_devguard ──────────────────────────────────────────────

    @mcp.tool()
    async def devguard_scan(
        path: str,
        scan_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run wrg_devguard policy / secrets / crypto scans on a path.

        Use when the user asks "scan this repo for policy violations",
        "check secrets / weak crypto", or before merging changes that
        touch security-sensitive code. Empty ``scan_types`` runs the
        combined ``check`` subcommand (lint-policy + scan-secrets).
        Supported types: ``secrets``, ``crypto``, ``credentials``,
        ``threat``, ``logs``, ``policy``. Returns the standard _run_cli
        envelope: {ok, exit_code, output, stderr?}.
        """
        types = list(scan_types or [])
        valid = {"secrets", "crypto", "credentials", "threat", "logs", "policy"}
        unknown = [t for t in types if t not in valid]
        if unknown:
            return {
                "ok": False,
                "error": f"unknown scan_types: {unknown}; expected subset of {sorted(valid)}",
            }
        if not types:
            args = [py, "-m", "wrg_devguard.cli", "check", "--path", path]
        else:
            # Single-subcommand dispatch keeps the envelope shape stable.
            t = types[0]
            sub = "lint-policy" if t == "policy" else f"scan-{t}"
            args = [py, "-m", "wrg_devguard.cli", sub, "--path", path]
        return await _run_cli(*args, timeout=300.0, app_name="wrg_devguard")

    @mcp.tool()
    async def devguard_baseline() -> dict[str, Any]:
        """List wrg_devguard policy profiles (baseline + strict) and presence.

        Use when the user asks "what devguard profiles exist?", "is the
        baseline policy in place?", or before devguard_scan to confirm a
        profile is configured. Wraps the ``profiles`` subcommand. Returns
        the standard _run_cli envelope: {ok, exit_code, output, stderr?}.
        """
        return await _run_cli(
            py, "-m", "wrg_devguard.cli", "profiles",
            timeout=60.0, app_name="wrg_devguard",
        )

    # ── wrg_security_suite ────────────────────────────────────────

    @mcp.tool()
    async def security_suite_run(
        target: str,
        profile: str = "default",
    ) -> dict[str, Any]:
        """Run a wrg_security_suite scan (MUTATION — performs network probes).

        MUTATION: spawns code/person/network scanners that may issue real
        network traffic and write report artifacts, so it requires
        WRG_MCP_ALLOW_MUTATIONS=1 in the server env. ``profile`` selects
        the subcommand: ``code`` → ``scan-code --path``, ``person`` →
        ``scan-person`` (target = username), ``network`` → ``scan-network``,
        ``full`` / ``default`` → ``full`` (all scanners).
        """
        if not _mutations_allowed():
            return _mutation_denied("security_suite_run")
        allowed = {"default", "full", "code", "person", "network"}
        if profile not in allowed:
            return {
                "ok": False,
                "error": f"unknown profile: {profile!r}; expected one of {sorted(allowed)}",
            }
        if profile == "code":
            args = [py, "-m", "wrg_security_suite.cli", "scan-code", "--path", target]
        elif profile == "person":
            args = [py, "-m", "wrg_security_suite.cli", "scan-person", target]
        elif profile == "network":
            args = [py, "-m", "wrg_security_suite.cli", "scan-network", target]
        else:
            args = [py, "-m", "wrg_security_suite.cli", "full", target]
        return await _run_cli(*args, timeout=600.0,
                              app_name="wrg_security_suite")

    @mcp.tool()
    async def security_suite_report(scan_id: str = "") -> dict[str, Any]:
        """Read a wrg_security_suite scan report by id (read-only).

        Use when the user asks "show that security scan report", "open
        results for scan X", or after security_suite_run completes and
        reports its scan_id. Empty ``scan_id`` returns the latest report.
        Reads from the suite's reports directory rooted at the repo, so
        no network or mutation occurs. Returns the standard _run_cli
        envelope: {ok, exit_code, output, stderr?}.
        """
        snippet = (
            "import json, os, sys; "
            "from pathlib import Path; "
            "root = Path(os.environ.get('WRG_REPO_ROOT') or '.'); "
            "rd = root / 'apps' / 'wrg_security_suite' / 'reports'; "
            "files = sorted(rd.glob('*.json')) if rd.is_dir() else []; "
            "scan_id = " + repr(scan_id) + "; "
            "target = (rd / (scan_id + '.json')) if scan_id else (files[-1] if files else None); "
            "out = {'ok': False, 'error': 'no reports'} if target is None "
            "else ({'ok': True, 'scan_id': target.stem, 'report': json.loads(target.read_text(encoding='utf-8'))} "
            "if target.exists() else {'ok': False, 'error': f'report not found: {target.name}'}); "
            "sys.stdout.write(json.dumps(out))"
        )
        env_root = {**os.environ, "WRG_REPO_ROOT": repo_root}
        return await anyio.to_thread.run_sync(
            partial(
                _run_cli_sync,
                (py, "-c", snippet),
                60.0,
                repo_root,
                {**env_root, "PYTHONIOENCODING": "utf-8",
                 "PYTHONDONTWRITEBYTECODE": "1"},
            ),
        )

    # ── rule_lab ──────────────────────────────────────────────────

    @mcp.tool()
    async def rule_lab_test(
        rule_file: str,
        sample_file: str,
    ) -> dict[str, Any]:
        """Simulate a rule_lab rule set against sample contexts.

        Use when the user asks "test these rules against this sample",
        "simulate rule firing", or while iterating on rule_lab JSON rule
        files. ``rule_file`` is a JSON rule list, ``sample_file`` is a
        JSON array of contexts. Returns the standard _run_cli envelope:
        {ok, exit_code, output, stderr?}.
        """
        return await _run_cli(
            py, "-m", "rule_lab.cli", "simulate",
            "--rules", rule_file,
            "--contexts", sample_file,
            "--json",
            timeout=300.0, app_name="rule_lab",
        )

    @mcp.tool()
    async def rule_lab_list() -> dict[str, Any]:
        """List rule_lab rule files discovered in the project rules directory.

        Use when the user asks "what rule files exist?", "list rule_lab
        rules", or before rule_lab_test when the exact rule path is
        unknown. Reads from ``$WRG_RULE_LAB_DIR`` or, if unset, from
        ``<repo>/.wrg/rules`` and ``apps/rule_lab/tests/fixtures``.
        Returns {ok, rules: [{path, name}], count}.
        """
        snippet = (
            "import json, os, sys; "
            "from pathlib import Path; "
            "root = Path(os.environ.get('WRG_REPO_ROOT') or '.'); "
            "env_dir = os.environ.get('WRG_RULE_LAB_DIR'); "
            "candidates = ([Path(env_dir)] if env_dir else "
            "[root / '.wrg' / 'rules', root / 'apps' / 'rule_lab' / 'tests' / 'fixtures']); "
            "found = []; "
            "[found.extend(sorted(p.rglob('*.json'))) for p in candidates if p.is_dir()]; "
            "rules = [{'path': str(f), 'name': f.stem} for f in found]; "
            "sys.stdout.write(json.dumps({'ok': True, 'rules': rules, 'count': len(rules)}))"
        )
        env_root = {**os.environ, "WRG_REPO_ROOT": repo_root,
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONDONTWRITEBYTECODE": "1"}
        return await anyio.to_thread.run_sync(
            partial(_run_cli_sync, (py, "-c", snippet), 30.0, repo_root, env_root),
        )

    # ── data_janitor ──────────────────────────────────────────────

    @mcp.tool()
    async def data_janitor_sweep(
        path: str = "",
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Sweep build artifacts via data_janitor.

        Read-only when ``dry_run=True`` (uses ``scan`` subcommand).
        MUTATION: ``dry_run=False`` invokes ``clean`` which removes
        files from disk and requires WRG_MCP_ALLOW_MUTATIONS=1 in the
        server env. Empty ``path`` defaults to the repo root.
        """
        if not dry_run and not _mutations_allowed():
            return _mutation_denied("data_janitor_sweep")
        sub = "scan" if dry_run else "clean"
        args = [py, "-m", "data_janitor.cli"]
        if path:
            args.extend(["--repo-root", path])
        args.extend([sub, "--target", "all"])
        return await _run_cli(*args, timeout=120.0, app_name="data_janitor")

    @mcp.tool()
    async def data_janitor_orphans() -> dict[str, Any]:
        """List orphan / build-artifact targets discovered by data_janitor (read-only).

        Use when the user asks "what cleanup targets exist?", "show
        orphan artifacts", or before data_janitor_sweep to preview the
        scope. Wraps ``data_janitor scan --target all`` (dry-run). Returns
        the standard _run_cli envelope: {ok, exit_code, output, stderr?}.
        """
        return await _run_cli(
            py, "-m", "data_janitor.cli", "scan", "--target", "all",
            timeout=60.0, app_name="data_janitor",
        )

    # ── wrg_notifier3 ─────────────────────────────────────────────

    @mcp.tool()
    async def notifier_send(
        channel: str,
        message: str,
    ) -> dict[str, Any]:
        """Send a notification through wrg_notifier3 (MUTATION — external send).

        MUTATION: dispatches to a real notification channel (e.g. log,
        webhook, email) and may trigger external side-effects, so it
        requires WRG_MCP_ALLOW_MUTATIONS=1 in the server env. ``channel``
        is the configured channel name; use ``notifier_channels`` to
        list available channels.
        """
        if not _mutations_allowed():
            return _mutation_denied("notifier_send")
        if not channel or not isinstance(channel, str):
            return {"ok": False, "error": "channel must be a non-empty string"}
        if not message or not isinstance(message, str):
            return {"ok": False, "error": "message must be a non-empty string"}
        return await _run_cli(
            py, "-m", "wrg_notifier3", "send",
            "--channel", channel,
            "--message", message,
            timeout=60.0, app_name="wrg_notifier3",
        )

    @mcp.tool()
    async def notifier_channels() -> dict[str, Any]:
        """List wrg_notifier3 channel adapters available in this checkout.

        Use when the user asks "which notifier channels are configured?",
        "show wrg_notifier3 adapters", or before notifier_send when the
        target channel is unknown. Read-only — introspects the channels
        module without sending anything. Returns {ok, channels: [str], count}.
        """
        snippet = (
            "import importlib, json, sys; "
            "names = []; "
            "candidates = ('wrg_notifier3.channels', 'wrg_notifier3.adapters', 'wrg_notifier3'); "
            "for modname in candidates:\n"
            "    try:\n"
            "        m = importlib.import_module(modname)\n"
            "    except ImportError:\n"
            "        continue\n"
            "    for attr in ('CHANNELS', 'ADAPTERS', 'channels', 'adapters'):\n"
            "        obj = getattr(m, attr, None)\n"
            "        if isinstance(obj, dict):\n"
            "            names = sorted(obj.keys())\n"
            "            break\n"
            "        if isinstance(obj, (list, tuple, set)):\n"
            "            names = sorted(str(x) for x in obj)\n"
            "            break\n"
            "    if names:\n"
            "        break\n"
            "sys.stdout.write(json.dumps({'ok': True, 'channels': names, 'count': len(names)}))"
        )
        return await _run_cli(
            py, "-c", snippet,
            timeout=30.0, app_name="wrg_notifier3",
        )
