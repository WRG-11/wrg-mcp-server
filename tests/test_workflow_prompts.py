"""Smoke + content tests for the workflow MCP prompts (R88-52f).

Three prompts added alongside ``wrg-status``:
* ``wrg-investigate-actor``  — actor corpus lookup + incident + Sigma + MITRE TTPs
* ``wrg-pattern-codify``     — 3-vaka graduation check + Pattern 26-32 precedent scan
* ``wrg-sigma-write``        — Sigma rule skeleton for a MITRE technique

Test surface covers:
* Body content invariants — numbered workflow steps present
* Parameter substitution   — actor_slug / observation / mitre_technique injected
* ASCII-only discipline    — body encodes as ASCII without error
* Prompt discoverability   — ``create_mcp_server().list_prompts()`` includes all 4
* Server construction      — ``create_mcp_server()`` succeeds with workflow prompts
"""
from __future__ import annotations

import asyncio

from wrg_mcp_server.server import create_mcp_server
from wrg_mcp_server.tools.prompts import (
    wrg_investigate_actor_body,
    wrg_pattern_codify_body,
    wrg_sigma_write_body,
)

# ---------------------------------------------------------------------------
# wrg-investigate-actor
# ---------------------------------------------------------------------------


def test_investigate_actor_body_includes_workflow_sections() -> None:
    body = wrg_investigate_actor_body("akira")
    for marker in (
        "1. **Actor profile**",
        "2. **Recent incidents**",
        "3. **Sigma rules**",
        "4. **MITRE TTP histogram**",
        "5. **Compose summary**",
    ):
        assert marker in body, f"missing section: {marker}"


def test_investigate_actor_body_ascii_only() -> None:
    body = wrg_investigate_actor_body("akira")
    body.encode("ascii")


def test_investigate_actor_body_parameter_substitution() -> None:
    slug = "lockbit"
    body = wrg_investigate_actor_body(slug)
    assert slug in body, "actor_slug not injected into body"
    assert f"actors/{slug}.yaml" in body, "actor YAML path not substituted"


# ---------------------------------------------------------------------------
# wrg-pattern-codify
# ---------------------------------------------------------------------------


def test_pattern_codify_body_includes_workflow_sections() -> None:
    body = wrg_pattern_codify_body("agents converge on same helper pattern")
    for marker in (
        "1. **3-vaka check**",
        "2. **Precedent scan**",
        "3. **FORMAL graduation track**",
        "4. **Codify verdict**",
    ):
        assert marker in body, f"missing section: {marker}"


def test_pattern_codify_body_ascii_only() -> None:
    body = wrg_pattern_codify_body("test observation")
    body.encode("ascii")


def test_pattern_codify_body_parameter_substitution() -> None:
    obs = "billing silent failure pattern"
    body = wrg_pattern_codify_body(obs)
    assert obs in body, "observation not injected into body"


def test_pattern_codify_body_references_pattern_catalog() -> None:
    body = wrg_pattern_codify_body("x")
    for pattern_ref in ("Pattern 26", "Pattern 27", "Pattern 28", "Pattern 29",
                        "Pattern 30", "Pattern 31", "Pattern 32"):
        assert pattern_ref in body, f"missing precedent reference: {pattern_ref}"


def test_pattern_codify_body_mentions_graduation_tracks() -> None:
    body = wrg_pattern_codify_body("x")
    assert "Track A" in body
    assert "Track B" in body
    assert "CANDIDATE" in body
    assert "DEFER" in body


# ---------------------------------------------------------------------------
# wrg-sigma-write
# ---------------------------------------------------------------------------


def test_sigma_write_body_includes_workflow_sections() -> None:
    body = wrg_sigma_write_body("T1486")
    for marker in (
        "1. **Technique lookup**",
        "2. **WRG corpus cross-reference**",
        "3. **Logsource recommendation**",
        "4. **Rule skeleton**",
        "5. **Sister rule references**",
    ):
        assert marker in body, f"missing section: {marker}"


def test_sigma_write_body_ascii_only() -> None:
    body = wrg_sigma_write_body("T1486")
    body.encode("ascii")


def test_sigma_write_body_parameter_substitution() -> None:
    tid = "T1059.001"
    body = wrg_sigma_write_body(tid)
    assert tid in body, "mitre_technique not injected into body"


def test_sigma_write_body_references_wrg_conventions() -> None:
    body = wrg_sigma_write_body("T1078")
    assert "WRG_SIGMA_NAMESPACE" in body, "uuid5 namespace convention missing"
    assert "TECHNIQUE_LOGSOURCE_MAP" in body, "logsource map reference missing"
    assert "PLACEHOLDER_FP_WARNING" in body, "false-positive warning convention missing"


# ---------------------------------------------------------------------------
# Server construction + prompt discoverability
# ---------------------------------------------------------------------------


def test_create_server_with_workflow_prompts_registered() -> None:
    server = create_mcp_server(host="127.0.0.1", port=8099)
    assert server is not None


def test_all_four_prompts_discoverable() -> None:
    server = create_mcp_server(host="127.0.0.1", port=8099)
    prompts = asyncio.run(server.list_prompts())
    names = {p.name for p in prompts}
    for expected in ("wrg-status", "wrg-investigate-actor", "wrg-pattern-codify", "wrg-sigma-write"):
        assert expected in names, f"prompt not registered: {expected}; have {names}"
