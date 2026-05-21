"""Operator-facing MCP prompt templates for WRG state surfacing.

Prompts (slash-command friendly) tell Claude *how* to assemble a coherent
state snapshot from existing WRG MCP tools + repo files, rather than
hard-coding a static snapshot that would drift wave-by-wave. The prompt
body is a meta-instruction; Claude executes it via the tools it already
has (Read/Glob/Grep/Bash for git + the other ``@mcp.tool()`` callables).

Prompts exposed:

* ``wrg-status`` — concise operational state snapshot covering active
  wave + 7-agent topology (A+B+C+D+E+F+G) + W cohort 9-member sentinels
  + capability gaps (4 sustainability + 5 visual disinfo + 6
  observability) + DR posture (3-tier) + pattern catalog graduation
  status + open queue.

Sister pattern to ``register_*_tools`` modules; FastMCP treats
``@mcp.prompt()`` and ``@mcp.tool()`` as separate registration channels.

R88-52+ "ucundan tut" PoC — first MCP prompt for WRG; Resources and
additional prompts (wrg-investigate-actor, wrg-incident-draft,
wrg-wave-orchestrate, wrg-pattern-codify, etc.) to follow incrementally.
See ``feedback_dr_posture_3_tier_hybrid_2026_05_21.md`` cross-link for
the broader MCP expansion roadmap discussion.

Test surface: ``wrg_status_body()`` exposed at module level so unit
tests can assert content without invoking the MCP machinery.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def wrg_status_body() -> str:
    """Return the meta-instruction text used by the ``wrg-status`` prompt.

    Exposed at module level (not nested inside ``register_status_prompts``)
    so unit tests can import + assert content. The body is intentionally
    a *workflow recipe*, not a static snapshot — Claude pulls live state
    each invocation, avoiding drift.
    """
    return (
        "Provide a concise WRG operational state snapshot as structured "
        "markdown. Pull live state from the repo + memory; do NOT rely on "
        "prior conversation context.\n"
        "\n"
        "Workflow:\n"
        "\n"
        "1. **Active wave + git state**:\n"
        "   - Run `git log --oneline -5` to identify recent activity.\n"
        "   - Identify current wave from CHANGELOG.md or commit subjects "
        "(R##-## prefix).\n"
        "   - Branch name via `git branch --show-current`.\n"
        "   - Report regression pass count from latest CHANGELOG.md entry "
        "(e.g. `218/218 PASS` marker).\n"
        "\n"
        "2. **7-Agent topology** (A+B+C+D+E+F+G):\n"
        "   - A operator: always present (user).\n"
        "   - For B/C/D/E/F/G: check `.agents/inbox/<X>/pending/` and "
        "`.agents/inbox/<X>/from-A/*.md` (excluding `*-done.md`). Empty "
        "= idle.\n"
        "   - Note any branch-preserve state (e.g. F deferred merge).\n"
        "\n"
        "3. **W cohort sentinels** (9-member as of R88-51):\n"
        "   - cov_drift, ai_runtime_cve_radar, dispatch_check, "
        "ransom_radar, pulseboard.\n"
        "   - feed_staleness, cadence_freshness, breach_disclosure.\n"
        "   - workflow_health (candidate, R88-52+).\n"
        "\n"
        "4. **Capability gaps** (ACUTE):\n"
        "   - gap 4 sustainability/maintenance -- see "
        "`feedback_maintenance_burden_growth_pattern_2026_05_20.md`.\n"
        "   - gap 5 visual disinfo -- see "
        "`feedback_multimodal_forensics_architecture_2026_05_21.md`.\n"
        "   - gap 6 observability/monitoring -- see "
        "`feedback_github_actions_billing_silent_ci_failure_2026_05_21.md`.\n"
        "\n"
        "5. **DR posture** (3-tier as of 2026-05-21):\n"
        "   - Tier 1 lokal `D:\\dev\\WinstonRedGuard`.\n"
        "   - Tier 2 GitHub push-only (Actions disabled $0, Dependabot $0).\n"
        "   - Tier 3 external HDD weekly Pazar 03:00 (`E:\\backups\\wrg\\`).\n"
        "   - Reference: `feedback_dr_posture_3_tier_hybrid_2026_05_21.md`.\n"
        "\n"
        "6. **Pattern catalog**:\n"
        "   - Total + FORMAL + CANDIDATE counts. Latest known: 32 total, "
        "26/27/28 FORMAL, 29-32 CANDIDATE.\n"
        "   - 3-criteria FORMAL graduation taxonomy: full-lifecycle (26) "
        "+ convergent Track A (27) + spec-adoption Track B (28).\n"
        "\n"
        "7. **Open queue** (top 3-5 pending):\n"
        "   - Read top Sessions entry in `MEMORY.md` for current pending "
        "list.\n"
        "   - Typical R88-52+ candidates: workflow_health_sentry W9 "
        "brief, T1 multi-modal forensics mini-suite, self-hosted runner.\n"
        "\n"
        "Output style: structured markdown with section headers, ASCII "
        "only. Highlight ACUTE items and last-24h activity with **bold**. "
        "Keep total output under ~60 lines (concise > exhaustive)."
    )


def register_status_prompts(mcp: FastMCP) -> None:
    """Register operator-facing state-snapshot prompts on the MCP server.

    Idempotent on import (decorator runs once per ``create_mcp_server``
    call). Sister to ``register_*_tools`` modules in this package.
    """

    @mcp.prompt(
        name="wrg-status",
        description=(
            "Compose a concise WRG operational state snapshot covering "
            "active wave, 7-agent topology, W cohort 9-member sentinels, "
            "capability gaps (4 sustainability + 5 visual disinfo + 6 "
            "observability), DR posture (3-tier), pattern catalog "
            "graduation status, and open queue. Use when the operator "
            "asks 'WRG state ne?', 'sun an ne durumda?', '/wrg-status', "
            "or before starting a new wave to refresh context."
        ),
    )
    def wrg_status() -> str:
        return wrg_status_body()
