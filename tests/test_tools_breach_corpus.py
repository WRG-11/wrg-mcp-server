"""Tests for ``wrg_mcp_server.tools.breach_corpus`` (R88-52b MCP tool family).

Scaffold-cross-validation discipline (sister R88-49c precedent — hotfix
``0af87ad9`` 1st canonical catch). The brief's 4 endpoints
(``breach_search`` / ``breach_recent`` / ``breach_by_actor`` /
``breach_by_sector``) ship in B's R88-52b stream; this test driver
lands **before** B merges and is guarded by a module-level import
``skipif`` so the suite remains green pre-B-merge and auto-activates
on B's merge.

If post-B-merge any of these assertions FAIL the failure is an
operational signal — escalate to A per the R88-49c precedent (spec
gap → hotfix or B re-ship). If all 10 PASS clean, the §15.14
``wait_for_b_finalize`` 5th-realisation cycle closes cleanly.

Coverage strategy mirrors sister ``test_tools_info_ops.py``:

* **Library-missing path** — purge ``wrg_threat_intel`` from
  ``sys.modules``, re-import the tools module, expect the missing-lib
  envelope (``ok=False`` + ``error`` + ``tool`` keys).
* **Happy path** — when ``wrg_threat_intel`` is installed in the dev
  env (35 actors + 26 incidents per `load_actors` / `load_incidents`
  smoke), exercise each endpoint over the real corpus.
* **Discovery** — ``server.list_tools()`` exposes all four endpoints
  by name; ``register_breach_corpus_tools`` is the public entry.
* **Schema** — return envelope shape (``ok`` / ``count`` /
  ``incidents``) is the contract for downstream MCP consumers.
"""
from __future__ import annotations

import asyncio
import sys
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Module-level import guard (sister R88-49c import-guard realisation)
# ---------------------------------------------------------------------------


try:  # pragma: no cover - import guard
    from wrg_mcp_server.tools.breach_corpus import (
        register_breach_corpus_tools,
    )

    _HAS_BREACH_CORPUS = True
except ImportError:  # pragma: no cover - skip path
    register_breach_corpus_tools = None  # type: ignore[assignment,misc]
    _HAS_BREACH_CORPUS = False


pytestmark = pytest.mark.skipif(
    not _HAS_BREACH_CORPUS,
    reason=(
        "breach_corpus module not yet shipped "
        "(R88-52b pending; wait_for_b_finalize import-guard fallback — "
        "auto-activates on B merge)"
    ),
)


# ---------------------------------------------------------------------------
# Helpers (mirror sister test_tools_info_ops convention)
# ---------------------------------------------------------------------------


def _get_tools() -> dict[str, Any]:
    """Return name → tool dict from a fresh MCP server instance."""
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=9998)
    return {t.name: t for t in server._tool_manager._tools.values()}


def _list_tool_names_via_async_api() -> set[str]:
    """List tool names via the public ``server.list_tools()`` async API.

    Sister status_prompt test convention — exercises the FastMCP
    discovery path the way external MCP clients would.
    """
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=8099)
    tools = asyncio.run(server.list_tools())
    return {t.name for t in tools}


def _purge_threat_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block ``wrg_threat_intel`` imports so the next ``import`` raises."""
    for mod in list(sys.modules):
        if mod == "wrg_threat_intel" or mod.startswith("wrg_threat_intel."):
            monkeypatch.delitem(sys.modules, mod, raising=False)
    for mod in (
        "wrg_threat_intel",
        "wrg_threat_intel.breach",
        "wrg_threat_intel.breach.corpus",
        "wrg_threat_intel.breach.types",
    ):
        monkeypatch.setitem(sys.modules, mod, None)


def _wrg_threat_intel_available() -> bool:
    try:
        import wrg_threat_intel  # noqa: F401

        return True
    except ImportError:
        return False


_HAS_LIB = _wrg_threat_intel_available()


# ---------------------------------------------------------------------------
# Test cases (10)
# ---------------------------------------------------------------------------


def test_case01_register_function_exists() -> None:
    """``register_breach_corpus_tools`` is a callable public entry point.

    Sister convention: ``register_<family>_tools(mcp: FastMCP) -> None``.
    The presence of this name on the module is the registration contract
    consumed by ``server.py``.
    """
    assert callable(register_breach_corpus_tools)


def test_case02_create_server_with_breach_corpus() -> None:
    """``create_mcp_server`` boots cleanly with the breach_corpus family registered.

    No exception during registration is the smoke contract — any
    import-time or registration-time failure would surface here.
    """
    from wrg_mcp_server.server import create_mcp_server

    server = create_mcp_server(host="127.0.0.1", port=8099)
    assert server is not None


def test_case03_breach_search_tool_discoverable() -> None:
    """``breach_search`` is exposed via the async ``list_tools`` discovery API."""
    names = _list_tool_names_via_async_api()
    assert "breach_search" in names, (
        f"breach_search not registered; have {sorted(names)[:20]}..."
    )


def test_case04_breach_recent_tool_discoverable() -> None:
    """``breach_recent`` is exposed via the async ``list_tools`` discovery API."""
    names = _list_tool_names_via_async_api()
    assert "breach_recent" in names, (
        f"breach_recent not registered; have {sorted(names)[:20]}..."
    )


def test_case05_breach_by_actor_tool_discoverable() -> None:
    """``breach_by_actor`` is exposed via the async ``list_tools`` discovery API."""
    names = _list_tool_names_via_async_api()
    assert "breach_by_actor" in names, (
        f"breach_by_actor not registered; have {sorted(names)[:20]}..."
    )


def test_case06_breach_by_sector_tool_discoverable() -> None:
    """``breach_by_sector`` is exposed via the async ``list_tools`` discovery API."""
    names = _list_tool_names_via_async_api()
    assert "breach_by_sector" in names, (
        f"breach_by_sector not registered; have {sorted(names)[:20]}..."
    )


def test_case07_breach_search_returns_envelope_on_missing_lib(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``wrg_threat_intel`` is unavailable, ``breach_search`` returns the
    missing-lib envelope (``ok=False`` + ``error`` + ``tool`` keys).

    Sister info_ops convention: graceful degradation envelope keyed by
    the tool name so downstream MCP consumers can detect/route the
    missing-dep state.
    """
    _purge_threat_modules(monkeypatch)
    # Force re-import of the tools module so its top-level try/except
    # ImportError branch executes against the poisoned sys.modules.
    monkeypatch.delitem(
        sys.modules, "wrg_mcp_server.tools.breach_corpus", raising=False
    )
    tools = _get_tools()
    result = tools["breach_search"].fn()
    assert isinstance(result, dict)
    assert result.get("ok") is False
    assert "wrg_threat_intel" in result.get("error", "")
    assert result.get("tool") == "breach_search"


@pytest.mark.skipif(
    not _HAS_LIB, reason="wrg_threat_intel not installed in this env"
)
def test_case08_breach_recent_default_days_param() -> None:
    """``breach_recent`` accepts the default ``days=30`` and returns a typed envelope.

    The contract is: no args ⇒ last 30 days of incidents, capped at the
    default ``limit``. Envelope must carry ``ok`` + ``count`` + ``incidents``;
    the count is corpus-state-dependent but ``incidents`` must be a list.
    """
    tools = _get_tools()
    result = tools["breach_recent"].fn()
    assert isinstance(result, dict)
    assert result.get("ok") is True
    assert "count" in result
    assert isinstance(result["count"], int)
    assert isinstance(result.get("incidents"), list)
    assert result["count"] == len(result["incidents"])


@pytest.mark.skipif(
    not _HAS_LIB, reason="wrg_threat_intel not installed in this env"
)
def test_case09_breach_by_actor_unknown_slug_envelope() -> None:
    """Unknown ``actor_slug`` returns a typed envelope (no exception).

    Contract: lookup failures degrade to a structured envelope (either
    ``ok=True`` with ``count=0`` empty list, or ``ok=False`` with a
    typed ``error`` describing the unknown slug). Either shape is
    acceptable; an unhandled exception is not.
    """
    tools = _get_tools()
    result = tools["breach_by_actor"].fn(actor_slug="does-not-exist-actor-slug-xyz")
    assert isinstance(result, dict)
    assert "ok" in result
    # Implementation may return ok=True+empty OR ok=False+error.
    if result["ok"] is True:
        assert result.get("count", 0) == 0
        assert result.get("incidents", []) == []
    else:
        assert "error" in result


@pytest.mark.skipif(
    not _HAS_LIB, reason="wrg_threat_intel not installed in this env"
)
def test_case10_breach_search_filter_combine_semantics() -> None:
    """Filter parameters compose monotonically — narrower filters never
    grow the result set.

    Invariant: ``|unfiltered| >= |sector-filtered| >= |sector + year-from
    filtered|``. The exact AND/OR semantics across filters are an
    operator decision (see brief Open Questions §3); this test only
    asserts the monotonic narrowing property which any sensible
    combination semantics must preserve.
    """
    tools = _get_tools()
    unfiltered = tools["breach_search"].fn(limit=500)
    sector_filtered = tools["breach_search"].fn(sector="finance", limit=500)
    sector_year_filtered = tools["breach_search"].fn(
        sector="finance", year_from=2025, limit=500
    )
    assert unfiltered["ok"] is True
    assert sector_filtered["ok"] is True
    assert sector_year_filtered["ok"] is True
    assert unfiltered["count"] >= sector_filtered["count"]
    assert sector_filtered["count"] >= sector_year_filtered["count"]
