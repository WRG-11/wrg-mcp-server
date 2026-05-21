"""Smoke + content tests for the wrg-status MCP prompt.

The first MCP prompt added to wrg_mcp_server (R88-52+ "ucundan tut"
ship). Test surface covers:

* Body content invariants — prompt instructs Claude through the WRG
  state-snapshot workflow (active wave, 7-agent topology, W cohort,
  capability gaps, DR posture, pattern catalog, open queue).
* Server registration smoke — ``create_mcp_server`` succeeds with the
  prompt registered alongside existing tools.
* Prompt discovery — registered prompt is reachable via FastMCP's
  internal prompt manager (name = ``wrg-status``).
"""
from __future__ import annotations

import asyncio

from wrg_mcp_server.server import create_mcp_server
from wrg_mcp_server.tools.prompts import wrg_status_body


def test_body_includes_required_sections() -> None:
    body = wrg_status_body()
    # Must mention each of the 7 numbered workflow steps
    for marker in (
        "1. **Active wave + git state**",
        "2. **7-Agent topology**",
        "3. **W cohort sentinels**",
        "4. **Capability gaps**",
        "5. **DR posture**",
        "6. **Pattern catalog**",
        "7. **Open queue**",
    ):
        assert marker in body, f"missing section marker: {marker}"


def test_body_references_canonical_memos() -> None:
    body = wrg_status_body()
    # Cross-link to the capability gap + DR memos must be preserved so
    # Claude knows where to pull live state from
    for memo in (
        "feedback_maintenance_burden_growth_pattern_2026_05_20.md",
        "feedback_multimodal_forensics_architecture_2026_05_21.md",
        "feedback_github_actions_billing_silent_ci_failure_2026_05_21.md",
        "feedback_dr_posture_3_tier_hybrid_2026_05_21.md",
    ):
        assert memo in body, f"missing memo cross-link: {memo}"


def test_body_lists_w_cohort_9_members() -> None:
    body = wrg_status_body()
    for member in (
        "cov_drift",
        "ai_runtime_cve_radar",
        "dispatch_check",
        "ransom_radar",
        "pulseboard",
        "feed_staleness",
        "cadence_freshness",
        "breach_disclosure",
        "workflow_health",
    ):
        assert member in body, f"missing W cohort member: {member}"


def test_body_mentions_3_acute_capability_gaps() -> None:
    body = wrg_status_body()
    assert "gap 4 sustainability" in body
    assert "gap 5 visual disinfo" in body
    assert "gap 6 observability" in body


def test_body_dr_posture_3_tier() -> None:
    body = wrg_status_body()
    assert "Tier 1 lokal" in body
    assert "Tier 2 GitHub" in body
    assert "Tier 3 external HDD" in body


def test_body_is_ascii() -> None:
    body = wrg_status_body()
    # ASCII-only discipline matches sister tool description style
    body.encode("ascii")


def test_create_server_with_status_prompt_registered() -> None:
    server = create_mcp_server(host="127.0.0.1", port=8099)
    assert server is not None


def test_wrg_status_prompt_discoverable() -> None:
    """FastMCP exposes registered prompts via list_prompts() (async API)."""
    server = create_mcp_server(host="127.0.0.1", port=8099)
    prompts = asyncio.run(server.list_prompts())
    names = {p.name for p in prompts}
    assert "wrg-status" in names, f"wrg-status not registered; have {names}"
