"""Operator-facing MCP prompt templates for WRG state surfacing.

Prompts (slash-command friendly) tell Claude *how* to assemble a coherent
state snapshot from existing WRG MCP tools + repo files, rather than
hard-coding a static snapshot that would drift wave-by-wave. The prompt
body is a meta-instruction; Claude executes it via the tools it already
has (Read/Glob/Grep/Bash for git + the other ``@mcp.tool()`` callables).

Prompts exposed:

* ``wrg-status`` -- concise operational state snapshot covering active
  wave + 7-agent topology (A+B+C+D+E+F+G) + W cohort 9-member sentinels
  + capability gaps (4 sustainability + 5 visual disinfo + 6
  observability) + DR posture (3-tier) + pattern catalog graduation
  status + open queue.

* ``wrg-investigate-actor`` -- actor lookup workflow: profile YAML +
  recent incidents + linked Sigma rules + MITRE TTP histogram.

* ``wrg-pattern-codify`` -- 3-vaka graduation check + Pattern 26-32
  precedent scan + codify verdict (CANDIDATE / GRADUATE / DEFER).

* ``wrg-sigma-write`` -- Sigma rule template draft for a MITRE technique:
  logsource recommendation + detection skeleton + WRG corpus cross-ref.

Two register families (Option B -- semantic separation):
* ``register_status_prompts`` -- state snapshot prompts (read-only survey)
* ``register_workflow_prompts`` -- operator action recipe prompts

Sister pattern to ``register_*_tools`` modules; FastMCP treats
``@mcp.prompt()`` and ``@mcp.tool()`` as separate registration channels.

Test surface: all ``*_body()`` functions exposed at module level so unit
tests can assert content without invoking the MCP machinery.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def wrg_status_body() -> str:
    """Return the meta-instruction text used by the ``wrg-status`` prompt.

    Exposed at module level (not nested inside ``register_status_prompts``)
    so unit tests can import + assert content. The body is intentionally
    a *workflow recipe*, not a static snapshot -- Claude pulls live state
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


def wrg_investigate_actor_body(actor_slug: str) -> str:
    """Return the meta-instruction text used by the ``wrg-investigate-actor`` prompt."""
    return (
        f"Investigate actor '{actor_slug}' using the WRG corpus, Sigma rules, and MITRE TTPs.\n"
        "\n"
        "Workflow:\n"
        "\n"
        "1. **Actor profile**:\n"
        f"   - Read `apps/wrg_threat_intel/src/wrg_threat_intel/breach/data/actors/{actor_slug}.yaml`.\n"
        "   - Extract: display_name, status, motivation, modus_operandi, sophistication,\n"
        "     first_seen, target_sectors_preferred, ttps_mitre, references.\n"
        "   - If file missing: report 'actor not in WRG corpus' and stop.\n"
        "\n"
        "2. **Recent incidents** (up to 3 most recent):\n"
        "   - Glob `apps/wrg_threat_intel/src/wrg_threat_intel/breach/data/incidents/*.yaml`.\n"
        f"   - Filter incidents where `actor_id: {actor_slug}` (or aliases from profile).\n"
        "   - Extract: incident_id, title, date, breach_type, affected_count, source_url.\n"
        "\n"
        "3. **Sigma rules**:\n"
        "   - Grep for `actor_id: {actor_slug}` in\n"
        "     `apps/wrg_threat_intel/src/wrg_threat_intel/breach/sigma/`.\n"
        "   - Report rule count and rule titles. If zero: note gap.\n"
        "\n"
        "4. **MITRE TTP histogram**:\n"
        "   - From ttps_mitre in the actor profile, group by tactic where possible.\n"
        "   - List each TTP ID with a one-line description (from MITRE ATT&CK knowledge).\n"
        "\n"
        "5. **Compose summary**:\n"
        "   - Profile block + 3 most recent incidents + Sigma rule count + TTP list.\n"
        "   - Flag any ACUTE gaps (no Sigma coverage, no recent incidents, unknown origin).\n"
        "\n"
        "Output: structured markdown, ASCII only, < 80 lines. Bold ACUTE gaps."
    )


def wrg_pattern_codify_body(observation: str) -> str:
    """Return the meta-instruction text used by the ``wrg-pattern-codify`` prompt."""
    return (
        f"Evaluate whether the following observation meets WRG pattern graduation criteria:\n"
        f"\n"
        f"Observation: {observation}\n"
        "\n"
        "Workflow:\n"
        "\n"
        "1. **3-vaka check** (minimum threshold):\n"
        "   - Has this pattern been observed in at least 3 independent cases?\n"
        "   - List evidence: case slug + date + brief description for each.\n"
        "   - If < 3 vaka: verdict = DEFER (note how many remain needed).\n"
        "\n"
        "2. **Precedent scan** (Pattern 26-32 emsal catalog):\n"
        "   - Pattern 26: baseline + strict 2-mode + acknowledged whitelist lifecycle.\n"
        "   - Pattern 27 Track A: convergent-validation (independent agents reach same impl).\n"
        "   - Pattern 28 Track B: spec-adoption (agent follows external spec unprompted).\n"
        "   - Pattern 29: evidence-erasure / AI inpainting laundering forensics.\n"
        "   - Pattern 30: silent CI/CD failure observability gap.\n"
        "   - Pattern 31: billing single point of failure (cost/ops fragility).\n"
        "   - Pattern 32: deferred-merge sub-pattern (agent race condition with A operator).\n"
        "   - Does the observation extend, sister, or duplicate an existing pattern?\n"
        "   - Check AGENTS.md section 15.6+ for full catalog.\n"
        "\n"
        "3. **FORMAL graduation track** (3-criteria taxonomy):\n"
        "   - Track A (convergent): same impl reached by 2+ independent agents/waves.\n"
        "   - Track B (spec-adoption): agent follows external spec without explicit brief.\n"
        "   - Full-lifecycle: all 4 stages (seedling -> CANDIDATE -> MATURE -> FORMAL).\n"
        "   - Which track applies (if any)?\n"
        "\n"
        "4. **Codify verdict**:\n"
        "   - CANDIDATE: 3+ vaka, clear pattern anatomy, not yet FORMAL.\n"
        "   - GRADUATE / FORMAL: meets graduation track criteria.\n"
        "   - DEFER: < 3 vaka or observation is noise / already covered.\n"
        "   - Suggest a pattern name and one-line anatomy summary.\n"
        "\n"
        "Output: structured markdown, ASCII only. Lead with verdict in bold."
    )


def wrg_sigma_write_body(mitre_technique: str) -> str:
    """Return the meta-instruction text used by the ``wrg-sigma-write`` prompt."""
    return (
        f"Draft a Sigma rule skeleton for MITRE ATT&CK technique '{mitre_technique}'.\n"
        "\n"
        "Workflow:\n"
        "\n"
        "1. **Technique lookup**:\n"
        "   - Identify tactic(s) for '{mitre_technique}' from MITRE ATT&CK knowledge.\n"
        "   - Note the technique name, description, and typical data sources.\n"
        "\n"
        "2. **WRG corpus cross-reference**:\n"
        "   - Grep `apps/wrg_threat_intel/src/wrg_threat_intel/breach/data/actors/`\n"
        "     for actors using '{mitre_technique}' (field: ttps_mitre).\n"
        "   - Grep `apps/wrg_threat_intel/src/wrg_threat_intel/breach/sigma/`\n"
        "     for existing rules referencing '{mitre_technique}'.\n"
        "   - List: actors using this TTP, existing rule count.\n"
        "\n"
        "3. **Logsource recommendation**:\n"
        "   - Check `templates.py` TECHNIQUE_LOGSOURCE_MAP for the technique.\n"
        "   - Recommend: category + product. Note if technique falls back to\n"
        "     parent (e.g. T1021.001 -> T1021 parent) or DEFAULT_LOGSOURCE.\n"
        "\n"
        "4. **Rule skeleton**:\n"
        "   Draft a Sigma YAML skeleton with:\n"
        "   ```\n"
        "   title: Detect <technique name>\n"
        "   id: <uuid5 placeholder -- use WRG_SIGMA_NAMESPACE>\n"
        "   status: experimental\n"
        "   description: >\n"
        "     Detection for MITRE ATT&CK {mitre_technique}.\n"
        "   references: []\n"
        "   author: WRG Breach Intel\n"
        "   logsource:\n"
        "     category: <from step 3>\n"
        "     product: <from step 3>\n"
        "   detection:\n"
        "     selection:\n"
        "       # TODO: fill with real IOCs or behavioral indicators\n"
        "     condition: selection\n"
        "   falsepositives:\n"
        "     - Phase 6 v1 placeholder -- bind to a real pattern before deployment\n"
        "   level: medium\n"
        "   tags:\n"
        "     - attack.{mitre_technique_lower}\n"
        "   ```\n"
        "\n"
        "5. **Sister rule references**:\n"
        "   - List any existing WRG Sigma rules that share the same logsource.\n"
        "   - Note if this technique already has curated coverage in rule_builder.py.\n"
        "\n"
        "Output: the YAML skeleton + brief logsource rationale + sister rule list.\n"
        "ASCII only. Flag PLACEHOLDER_FP_WARNING if no curated pattern exists."
    )


def register_workflow_prompts(mcp: FastMCP) -> None:
    """Register operator workflow recipe prompts on the MCP server.

    Idempotent on import (decorator runs once per ``create_mcp_server``
    call). Sister to ``register_status_prompts`` -- semantic separation:
    status = read-only state survey; workflow = operator action recipes.
    """

    @mcp.prompt(
        name="wrg-investigate-actor",
        description=(
            "Investigate a threat actor using the WRG corpus. Pulls actor profile "
            "YAML, up to 3 recent incidents, linked Sigma rules, and MITRE TTP "
            "histogram. Use when the operator asks 'who is <actor>?', "
            "'investigate <actor>', '/wrg-investigate-actor <slug>', or before "
            "drafting a Sigma rule or incident report for a specific actor."
        ),
    )
    def wrg_investigate_actor(actor_slug: str) -> str:
        return wrg_investigate_actor_body(actor_slug)

    @mcp.prompt(
        name="wrg-pattern-codify",
        description=(
            "Evaluate an observation for WRG pattern graduation. Runs 3-vaka "
            "threshold check, scans Pattern 26-32 precedent catalog, applies "
            "3-criteria FORMAL taxonomy (Track A convergent / Track B spec-adoption "
            "/ full-lifecycle), and returns a verdict: CANDIDATE, FORMAL, or DEFER. "
            "Use when the operator asks 'should we codify this?', 'is this a pattern?', "
            "or '/wrg-pattern-codify <observation>'."
        ),
    )
    def wrg_pattern_codify(observation: str) -> str:
        return wrg_pattern_codify_body(observation)

    @mcp.prompt(
        name="wrg-sigma-write",
        description=(
            "Draft a Sigma rule skeleton for a MITRE ATT&CK technique. Looks up "
            "the technique, cross-references WRG corpus actors + existing rules, "
            "recommends logsource from the WRG TECHNIQUE_LOGSOURCE_MAP, and "
            "produces a YAML skeleton with WRG conventions (uuid5 namespace, "
            "falsepositives warning, attack tags). Use when the operator asks "
            "'write a sigma rule for T1234', '/wrg-sigma-write T1234', or "
            "after an actor investigation reveals a TTP gap."
        ),
    )
    def wrg_sigma_write(mitre_technique: str) -> str:
        return wrg_sigma_write_body(mitre_technique)


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
