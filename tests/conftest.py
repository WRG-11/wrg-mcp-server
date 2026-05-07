"""Shared test fixtures for wrg_mcp_server.

Provides fake module injection helpers for optional dependencies
(maigret, tradingagents, arastirma_ussu, yfinance, langchain_core)
that may not be installed in the test environment.
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest

APP_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
SRC_DIR = APP_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def install_fake_modules(
    monkeypatch: pytest.MonkeyPatch,
    stubs: dict[str, dict[str, Any]],
) -> None:
    """Inject fake modules into sys.modules so ``unittest.mock.patch()`` can
    resolve dotted paths to optional dependencies that aren't installed.

    Idempotent: skips modules already present in ``sys.modules``.
    Cleanup is automatic via monkeypatch.
    """
    for mod_path, attrs in stubs.items():
        if mod_path in sys.modules:
            continue
        fake = types.ModuleType(mod_path)
        for k, v in attrs.items():
            setattr(fake, k, v)
        monkeypatch.setitem(sys.modules, mod_path, fake)


# ── Stub catalogs ───────────────────────────────────────────────────────

STUBS_MAIGRET: dict[str, dict[str, Any]] = {
    "maigret": {},
}

STUBS_TRADINGAGENTS: dict[str, dict[str, Any]] = {
    "tradingagents": {},
    "tradingagents.default_config": {"DEFAULT_CONFIG": {}},
    "tradingagents.graph": {},
    "tradingagents.graph.trading_graph": {"TradingAgentsGraph": MagicMock},
    "yfinance": {"Ticker": MagicMock},
}

STUBS_ARASTIRMA_USSU: dict[str, dict[str, Any]] = {
    "arastirma_ussu": {},
    "arastirma_ussu.ingest": {},
    "arastirma_ussu.ingest.tool": {"doc_search": lambda *a, **kw: None},
    "arastirma_ussu.memory": {},
    "arastirma_ussu.memory.tool": {"memory_search": lambda *a, **kw: None},
    "arastirma_ussu.agent": {},
    "arastirma_ussu.agent.tools": {"web_search": lambda *a, **kw: None, "build_tool_registry": lambda *a, **kw: None},
    "arastirma_ussu.agent.graph": {"build_graph": lambda *a, **kw: None},
    "arastirma_ussu.agent.prompts": {"build_system_prompt": lambda *a, **kw: ""},
    "langchain_core": {},
    "langchain_core.messages": {"HumanMessage": MagicMock, "SystemMessage": MagicMock},
}


# ── Reusable fixtures ──────────────────────────────────────────────────

@pytest.fixture
def fake_maigret(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_modules(monkeypatch, STUBS_MAIGRET)


@pytest.fixture
def fake_tradingagents(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_modules(monkeypatch, STUBS_TRADINGAGENTS)


@pytest.fixture
def fake_arastirma_ussu(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_modules(monkeypatch, STUBS_ARASTIRMA_USSU)
