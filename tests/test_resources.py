"""Smoke + content tests for the R88-52d corpus MCP resources.

3 Resources added to wrg_mcp_server (1st Resource layer; sister to today's
prompts.py ship). Test surface covers:

* Body content invariants — corpus_stats keys + pattern_lookup known/
  unknown + recent_breaches schema.
* ASCII-only discipline matches sister convention.
* Server registration smoke — create_mcp_server succeeds with resources
  registered alongside existing tools.
* Resource discovery — registered resources reachable via FastMCP's
  internal resource manager (URIs ``wrg://corpus-stats`` +
  ``wrg://breaches/recent`` static; ``wrg://patterns/{pattern_id}``
  templated).
"""
from __future__ import annotations

import asyncio
import json

from wrg_mcp_server.server import create_mcp_server
from wrg_mcp_server.tools.resources import (
    corpus_stats_body,
    pattern_lookup_body,
    recent_breaches_body,
)


def test_corpus_stats_body_returns_expected_keys() -> None:
    body = corpus_stats_body()
    doc = json.loads(body)
    assert doc["ok"] is True
    for key in (
        "incident_count",
        "actor_count",
        "pattern_count_total",
        "pattern_count_formal",
        "pattern_count_candidate",
        "w_cohort_count",
        "w_cohort_members",
        "capability_gaps_acute",
        "source_note",
    ):
        assert key in doc, f"missing required key: {key}"
    # Counts should be non-negative ints
    assert doc["incident_count"] >= 0
    assert doc["actor_count"] >= 0
    assert doc["pattern_count_total"] >= 1
    # W cohort should list 9 known sentinels
    assert doc["w_cohort_count"] == len(doc["w_cohort_members"])
    assert doc["w_cohort_count"] >= 8
    for member in (
        "cov_drift_sentry",
        "ai_runtime_cve_radar",
        "feed_staleness_sentry",
        "breach_disclosure_sentry",
    ):
        assert member in doc["w_cohort_members"], f"missing W cohort: {member}"
    # Capability gaps include ACUTE 4/5/6
    gap_ids = {g["id"] for g in doc["capability_gaps_acute"]}
    assert {4, 5, 6}.issubset(gap_ids), f"missing ACUTE gap ids; got {gap_ids}"


def test_corpus_stats_body_ascii_only() -> None:
    # ASCII-only discipline matches sister convention
    corpus_stats_body().encode("ascii")


def test_pattern_lookup_known_id_returns_structured() -> None:
    # Pattern 26 FORMAL sister 4-vaka cluster (R88-48e ship)
    body = pattern_lookup_body("26")
    doc = json.loads(body)
    assert doc["ok"] is True
    assert doc["id"] == "26"
    assert doc["graduation"] == "FORMAL"
    assert "title" in doc
    assert "agents_md_section" in doc
    assert "vaka_count" in doc
    assert "sister_applications" in doc
    # Pattern 26 specific sisters
    sisters = doc["sister_applications"]
    assert any("cross_app_type_contract" in s for s in sisters)


def test_pattern_lookup_normalizes_prefix() -> None:
    # Accept "Pattern 26" or "pattern-26" variants
    for variant in ("Pattern 26", "pattern-26", "p26", "26"):
        body = pattern_lookup_body(variant)
        doc = json.loads(body)
        assert doc["ok"] is True, f"variant '{variant}' failed: {doc}"
        assert doc["id"] == "26"


def test_pattern_lookup_unknown_id_returns_envelope() -> None:
    body = pattern_lookup_body("999")
    doc = json.loads(body)
    assert doc["ok"] is False
    assert "not found" in doc["error"]
    assert "available_ids" in doc
    assert "26" in doc["available_ids"]
    assert "27" in doc["available_ids"]


def test_pattern_lookup_empty_id_returns_envelope() -> None:
    body = pattern_lookup_body("xyz")  # no digits
    doc = json.loads(body)
    assert doc["ok"] is False
    assert "at least one digit" in doc["error"]


def test_recent_breaches_body_returns_list() -> None:
    body = recent_breaches_body()
    doc = json.loads(body)
    assert doc["ok"] is True
    assert doc["cutoff_days"] == 30
    assert "incident_count" in doc
    assert "incidents" in doc
    assert isinstance(doc["incidents"], list)
    # Each incident should have the expected fields
    for inc in doc["incidents"]:
        for key in (
            "id",
            "actor_id",
            "victim_display_name",
            "victim_sector",
            "severity",
            "status",
            "latest_timeline_date",
        ):
            assert key in inc, f"incident missing field {key}: {inc}"


def test_recent_breaches_body_ascii_only() -> None:
    recent_breaches_body().encode("ascii")


def test_create_server_with_resources_registered() -> None:
    """Server construction succeeds with all 3 resources registered."""
    server = create_mcp_server(host="127.0.0.1", port=8099)
    assert server is not None


def test_corpus_resources_discoverable_static() -> None:
    """Static URI resources are listed by FastMCP."""
    server = create_mcp_server(host="127.0.0.1", port=8099)
    resources = asyncio.run(server.list_resources())
    uris = {str(r.uri) for r in resources}
    assert any("wrg://corpus-stats" in u for u in uris), \
        f"wrg://corpus-stats not registered; have {uris}"
    assert any("wrg://breaches/recent" in u for u in uris), \
        f"wrg://breaches/recent not registered; have {uris}"


def test_corpus_resources_template_discoverable() -> None:
    """Templated URI resources (with {param}) are exposed via list_resource_templates."""
    server = create_mcp_server(host="127.0.0.1", port=8099)
    templates = asyncio.run(server.list_resource_templates())
    uri_patterns = {str(t.uriTemplate) for t in templates}
    assert any("wrg://patterns/" in u for u in uri_patterns), \
        f"wrg://patterns/{{id}} template not registered; have {uri_patterns}"
