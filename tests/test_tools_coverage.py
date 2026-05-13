"""Coverage tests for MCP tool modules: polymarket, trading_agents, arastirma_ussu, maigret_osint, research_platform.

Tests helper/utility functions directly and exercises ImportError paths
for tool functions that depend on external packages.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# polymarket helpers
# ---------------------------------------------------------------------------


class TestPolymarketHelpers:
    def test_build_signal_basic(self):
        from wrg_mcp_server.tools.polymarket import _build_signal
        record = {
            "question": "Will BTC hit 100k?",
            "endDate": "2026-12-31",
            "volume24hr": 12345.67,
            "volume": 999999.0,
            "outcomes": '["Yes","No"]',
            "outcomePrices": '["0.72","0.28"]',
            "slug": "btc-100k",
            "active": True,
            "closed": False,
        }
        result = _build_signal(record, "btc-100k")
        assert result["ok"] is True
        assert result["question"] == "Will BTC hit 100k?"
        assert result["volume_24h_usd"] == 12345.67
        assert len(result["outcomes"]) == 2
        assert result["outcomes"][0]["name"] == "Yes"
        assert result["outcomes"][0]["price"] == 0.72
        assert result["lean"]["outcome"] == "Yes"
        assert result["lean"]["margin_over_50_50"] == 0.22

    def test_build_signal_empty_outcomes(self):
        from wrg_mcp_server.tools.polymarket import _build_signal
        record = {"question": "Q?", "outcomes": [], "outcomePrices": []}
        result = _build_signal(record, "test")
        assert result["ok"] is True
        assert result["outcomes"] == []
        assert result["lean"]["outcome"] == "?"
        assert result["lean"]["margin_over_50_50"] == 0.0

    def test_zip_outcomes_json_strings(self):
        from wrg_mcp_server.tools.polymarket import _zip_outcomes
        outcomes = _zip_outcomes('["Yes","No"]', '["0.65","0.35"]')
        assert len(outcomes) == 2
        assert outcomes[0]["name"] == "Yes"
        assert outcomes[0]["price"] == 0.65
        assert outcomes[1]["name"] == "No"

    def test_zip_outcomes_list_input(self):
        from wrg_mcp_server.tools.polymarket import _zip_outcomes
        outcomes = _zip_outcomes(["A", "B", "C"], [0.5, 0.3, 0.2])
        assert len(outcomes) == 3
        assert outcomes[2]["name"] == "C"
        assert outcomes[2]["price"] == 0.2

    def test_zip_outcomes_mismatched_lengths(self):
        from wrg_mcp_server.tools.polymarket import _zip_outcomes
        outcomes = _zip_outcomes(["Yes", "No"], [0.7])
        assert outcomes[1]["price"] == 0.0

    def test_zip_outcomes_invalid_price(self):
        from wrg_mcp_server.tools.polymarket import _zip_outcomes
        outcomes = _zip_outcomes(["Yes"], ["invalid"])
        assert outcomes[0]["price"] == 0.0

    def test_coerce_list_from_list(self):
        from wrg_mcp_server.tools.polymarket import _coerce_list
        assert _coerce_list([1, 2, 3]) == [1, 2, 3]

    def test_coerce_list_from_json_string(self):
        from wrg_mcp_server.tools.polymarket import _coerce_list
        assert _coerce_list('["a","b"]') == ["a", "b"]

    def test_coerce_list_invalid_string(self):
        from wrg_mcp_server.tools.polymarket import _coerce_list
        assert _coerce_list("not json") == []

    def test_coerce_list_non_list_json(self):
        from wrg_mcp_server.tools.polymarket import _coerce_list
        assert _coerce_list('{"key": "val"}') == []

    def test_coerce_list_other_type(self):
        from wrg_mcp_server.tools.polymarket import _coerce_list
        assert _coerce_list(42) == []

    def test_compute_lean(self):
        from wrg_mcp_server.tools.polymarket import _compute_lean
        outcomes = [
            {"name": "Yes", "price": 0.8},
            {"name": "No", "price": 0.2},
        ]
        name, margin = _compute_lean(outcomes)
        assert name == "Yes"
        assert margin == pytest.approx(0.3)

    def test_compute_lean_empty(self):
        from wrg_mcp_server.tools.polymarket import _compute_lean
        name, margin = _compute_lean([])
        assert name == "?"
        assert margin == 0.0


# ---------------------------------------------------------------------------
# polymarket tool — httpx error path
# ---------------------------------------------------------------------------


class TestPolymarketTool:
    def _register(self):
        from wrg_mcp_server.tools.polymarket import register_polymarket_tools
        mcp = MagicMock()
        tools = {}

        def capture_tool():
            def dec(fn):
                tools[fn.__name__] = fn
                return fn
            return dec
        mcp.tool = capture_tool
        register_polymarket_tools(mcp)
        return tools

    @pytest.mark.asyncio
    async def test_httpx_error(self):
        import httpx
        tools = self._register()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tools["polymarket_event_signal"]("nonexistent-slug")
        assert result["ok"] is False
        assert "failed" in result["error"]

    @pytest.mark.asyncio
    async def test_httpx_success(self):
        tools = self._register()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{
            "question": "Test?",
            "slug": "test",
            "outcomes": ["Yes", "No"],
            "outcomePrices": ["0.6", "0.4"],
            "volume24hr": 1000,
            "volume": 50000,
            "active": True,
            "closed": False,
        }]
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tools["polymarket_event_signal"]("test")
        assert result["ok"] is True
        assert result["question"] == "Test?"

    @pytest.mark.asyncio
    async def test_empty_response(self):
        tools = self._register()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = []
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tools["polymarket_event_signal"]("missing")
        assert result["ok"] is False
        assert "no market found" in result["error"]

    @pytest.mark.asyncio
    async def test_condition_id_param(self):
        tools = self._register()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{"question": "Q?", "outcomes": [], "outcomePrices": []}]
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await tools["polymarket_event_signal"]("0xabc123")
        assert result["ok"] is True
        # Should have used condition_ids param
        call_kwargs = mock_client.get.call_args
        assert "condition_ids" in str(call_kwargs)


# ---------------------------------------------------------------------------
# trading_agents — ImportError paths (packages not installed)
# ---------------------------------------------------------------------------


class TestTradingAgentsTool:
    @pytest.fixture(autouse=True)
    def _setup(self, fake_tradingagents: None) -> None:
        pass

    def _register(self):
        from wrg_mcp_server.tools.trading_agents import register_trading_agents_tools
        mcp = MagicMock()
        tools = {}

        def capture_tool():
            def dec(fn):
                tools[fn.__name__] = fn
                return fn
            return dec
        mcp.tool = capture_tool
        register_trading_agents_tools(mcp)
        return tools

    @pytest.mark.asyncio
    async def test_trading_analyze_success(self):
        tools = self._register()
        mock_graph = MagicMock()
        mock_graph.propagate.return_value = (None, {"action": "BUY", "confidence": 0.8})
        with patch("tradingagents.graph.trading_graph.TradingAgentsGraph", return_value=mock_graph):
            result = await tools["trading_analyze"]("NVDA", provider="ollama")
        assert result["ok"] is True
        assert result["ticker"] == "NVDA"
        assert result["decision"]["action"] == "BUY"

    @pytest.mark.asyncio
    async def test_trading_analyze_exception(self):
        tools = self._register()
        with patch("tradingagents.graph.trading_graph.TradingAgentsGraph", side_effect=RuntimeError("connection refused")):
            result = await tools["trading_analyze"]("NVDA")
        assert result["ok"] is False
        assert "connection refused" in result["error"]

    @pytest.mark.asyncio
    async def test_trading_analyze_providers(self):
        tools = self._register()
        mock_graph = MagicMock()
        mock_graph.propagate.return_value = (None, {"action": "HOLD"})
        for provider in ("openai", "anthropic", "google"):
            with patch("tradingagents.graph.trading_graph.TradingAgentsGraph", return_value=mock_graph):
                result = await tools["trading_analyze"]("AAPL", provider=provider)
            assert result["ok"] is True
            assert result["provider"] == provider

    @pytest.mark.asyncio
    async def test_trading_quick_signal_success(self):
        np = pytest.importorskip("numpy")
        pd = pytest.importorskip("pandas")
        tools = self._register()
        dates = pd.date_range("2026-01-01", periods=20)
        hist = pd.DataFrame({
            "Close": np.linspace(100, 120, 20),
            "Volume": [1000000] * 20,
        }, index=dates)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist
        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await tools["trading_quick_signal"]("AAPL")
        assert result["ok"] is True
        assert result["ticker"] == "AAPL"
        assert "price" in result
        assert "rsi_14" in result

    @pytest.mark.asyncio
    async def test_trading_quick_signal_empty(self):
        pd = pytest.importorskip("pandas")
        tools = self._register()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = await tools["trading_quick_signal"]("FAKE")
        assert result["ok"] is False
        assert "No data" in result["error"]


# ---------------------------------------------------------------------------
# arastirma_ussu — ImportError paths (packages not installed)
# ---------------------------------------------------------------------------


class TestArastirmaUssuTool:
    @pytest.fixture(autouse=True)
    def _setup(self, fake_arastirma_ussu: None) -> None:
        pass

    def _register(self):
        from wrg_mcp_server.tools.arastirma_ussu import register_arastirma_ussu_tools
        mcp = MagicMock()
        tools = {}

        def capture_tool():
            def dec(fn):
                tools[fn.__name__] = fn
                return fn
            return dec
        mcp.tool = capture_tool
        register_arastirma_ussu_tools(mcp)
        return tools

    @pytest.mark.asyncio
    async def test_doc_search_success(self):
        tools = self._register()
        with patch("arastirma_ussu.ingest.tool.doc_search", return_value="Found: relevant docs"):
            result = await tools["arastirma_doc_search"]("test query")
        assert result["ok"] is True
        assert "relevant docs" in result["result"]

    @pytest.mark.asyncio
    async def test_doc_search_exception(self):
        tools = self._register()
        with patch("arastirma_ussu.ingest.tool.doc_search", side_effect=RuntimeError("qdrant down")):
            result = await tools["arastirma_doc_search"]("test query")
        assert result["ok"] is False
        assert "qdrant down" in result["error"]

    @pytest.mark.asyncio
    async def test_memory_search_success(self):
        tools = self._register()
        with patch("arastirma_ussu.memory.tool.memory_search", return_value="past answer"):
            result = await tools["arastirma_memory_search"]("test query")
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_memory_search_exception(self):
        tools = self._register()
        with patch("arastirma_ussu.memory.tool.memory_search", side_effect=RuntimeError("fail")):
            result = await tools["arastirma_memory_search"]("test query")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_web_search_success(self):
        tools = self._register()
        with patch("arastirma_ussu.agent.tools.web_search", return_value="web results here"):
            result = await tools["arastirma_web_search"]("test query")
        assert result["ok"] is True
        assert "web results" in result["result"]

    @pytest.mark.asyncio
    async def test_web_search_exception(self):
        tools = self._register()
        with patch("arastirma_ussu.agent.tools.web_search", side_effect=RuntimeError("network")):
            result = await tools["arastirma_web_search"]("test query")
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_ask_success(self):
        tools = self._register()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "final_answer": "The answer is 42",
            "iteration": 2,
            "last_action": "web_search",
        }
        with patch("arastirma_ussu.agent.graph.build_graph", return_value=mock_graph), \
             patch("arastirma_ussu.agent.tools.build_tool_registry", return_value=MagicMock()), \
             patch("arastirma_ussu.agent.prompts.build_system_prompt", return_value="sys"):
            result = await tools["arastirma_ask"]("what is AI?")
        assert result["ok"] is True
        assert result["answer"] == "The answer is 42"

    @pytest.mark.asyncio
    async def test_ask_exception(self):
        tools = self._register()
        with patch("arastirma_ussu.agent.graph.build_graph", side_effect=RuntimeError("ollama down")):
            result = await tools["arastirma_ask"]("what is AI?")
        assert result["ok"] is False
        assert "ollama down" in result["error"]

    @pytest.mark.asyncio
    async def test_health_all_modules_stubbed(self):
        """Health probe: with fake_arastirma_ussu fixture all import probes
        should report available; Ollama/Qdrant probes report 'reachable: false'
        on a clean dev box without those services (no exception)."""
        tools = self._register()
        result = await tools["arastirma_health"]()
        assert result["ok"] is True
        assert "arastirma_ussu" in result["checks"]
        assert result["checks"]["arastirma_ussu"]["available"] is True
        assert result["checks"]["layer55_eval"]["available"] is True
        # Ollama + Qdrant are real HTTP probes; just assert shape, not reachability.
        assert "reachable" in result["checks"]["ollama"]
        assert "reachable" in result["checks"]["qdrant"]
        assert result["summary"].endswith("/9 healthy")

    @pytest.mark.asyncio
    async def test_eval_skeleton_returns_nan_without_judge(self):
        """arastirma_eval no-judge path returns the all-nan JudgeResult."""
        import math
        from dataclasses import dataclass

        @dataclass
        class _StubResult:
            faithfulness: float = math.nan
            answer_relevancy: float = math.nan
            context_recall: float = math.nan
            raw: dict = None  # type: ignore[assignment]

            def __post_init__(self) -> None:
                if self.raw is None:
                    self.raw = {"reason": "no llm provided"}

            @property
            def overall(self) -> float:
                return math.nan

            def is_passing(self, threshold: float = 0.7) -> bool:
                return False

        tools = self._register()
        with patch("arastirma_ussu.eval.evaluate_answer", return_value=_StubResult()):
            result = await tools["arastirma_eval"]("q", "a", ["c"])
        assert result["ok"] is True
        assert math.isnan(result["faithfulness"])
        assert math.isnan(result["overall"])
        assert result["is_passing"] is False
        assert result["raw"]["reason"] == "no llm provided"

    @pytest.mark.asyncio
    async def test_eval_import_error_message(self):
        """When arastirma_ussu.eval can't import, the wrapper relays a
        clear hint about installing the package."""
        tools = self._register()
        with patch("arastirma_ussu.eval.evaluate_answer", side_effect=ImportError("ragas missing")):
            result = await tools["arastirma_eval"]("q", "a", ["c"])
        assert result["ok"] is False
        assert "ragas missing" in result["error"]


# ---------------------------------------------------------------------------
# maigret_osint — helper + ImportError
# ---------------------------------------------------------------------------


class TestMaigretOsint:
    @pytest.fixture(autouse=True)
    def _setup(self, fake_maigret: None) -> None:
        pass

    def test_build_summary_no_accounts(self):
        from wrg_mcp_server.tools.maigret_osint import _build_summary
        result = _build_summary("john", [])
        assert "No accounts found" in result
        assert "john" in result

    def test_build_summary_few_accounts(self):
        from wrg_mcp_server.tools.maigret_osint import _build_summary
        accounts = [{"site": "GitHub"}, {"site": "Twitter"}]
        result = _build_summary("john", accounts)
        assert "2 accounts" in result
        assert "GitHub" in result

    def test_build_summary_many_accounts(self):
        from wrg_mcp_server.tools.maigret_osint import _build_summary
        accounts = [{"site": f"Site{i}"} for i in range(15)]
        result = _build_summary("john", accounts)
        assert "15 accounts" in result
        assert "5 more" in result

    def _register(self):
        from wrg_mcp_server.tools.maigret_osint import register_maigret_tools
        mcp = MagicMock()
        tools = {}

        def capture_tool():
            def dec(fn):
                tools[fn.__name__] = fn
                return fn
            return dec
        mcp.tool = capture_tool
        register_maigret_tools(mcp)
        return tools

    @pytest.mark.asyncio
    async def test_maigret_timeout(self):
        import subprocess
        tools = self._register()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("maigret", 180)):
            result = await tools["maigret_search"]("john")
        assert result["ok"] is False
        assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_maigret_not_found(self):
        tools = self._register()
        with patch("subprocess.run", side_effect=FileNotFoundError("maigret")):
            result = await tools["maigret_search"]("john")
        assert result["ok"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_maigret_no_report(self):
        tools = self._register()
        mock_result = MagicMock()
        mock_result.stderr = "some error"
        with patch("subprocess.run", return_value=mock_result):
            result = await tools["maigret_search"]("john")
        assert result["ok"] is False
        assert "no report" in result["error"]


# ---------------------------------------------------------------------------
# research_platform — helpers
# ---------------------------------------------------------------------------


class TestResearchPlatform:
    def test_detect_modes_osint(self):
        from wrg_mcp_server.tools.research_platform import _detect_modes
        modes = _detect_modes("kim bu kullanıcı?", "johndoe")
        assert "osint" in modes

    def test_detect_modes_rag(self):
        from wrg_mcp_server.tools.research_platform import _detect_modes
        modes = _detect_modes("proje dosyalarında ne var?", "")
        assert "rag" in modes

    def test_detect_modes_target_triggers_osint(self):
        from wrg_mcp_server.tools.research_platform import _detect_modes
        modes = _detect_modes("analyze this", "target.com")
        assert "osint" in modes

    def test_detect_modes_web_always_included(self):
        from wrg_mcp_server.tools.research_platform import _detect_modes
        modes = _detect_modes("some generic question", "")
        assert "web" in modes

    def test_build_research_summary_no_engines(self):
        from wrg_mcp_server.tools.research_platform import _build_research_summary
        result = _build_research_summary("q?", {}, [])
        assert "No research engines" in result

    def test_build_research_summary_osint(self):
        from wrg_mcp_server.tools.research_platform import _build_research_summary
        results = {"osint": {"candidates": 5, "top_score": 7.2, "scores": []}}
        result = _build_research_summary("q?", results, ["osint"])
        assert "OSINT: 5 candidate" in result

    def test_build_research_summary_rag(self):
        from wrg_mcp_server.tools.research_platform import _build_research_summary
        results = {"rag": {"result": "x" * 200, "source": "local_documents"}}
        result = _build_research_summary("q?", results, ["rag"])
        assert "RAG: 200 chars" in result

    def test_build_research_summary_web(self):
        from wrg_mcp_server.tools.research_platform import _build_research_summary
        results = {"web": {"result": "y" * 100, "source": "duckduckgo"}}
        result = _build_research_summary("q?", results, ["web"])
        assert "Web: 100 chars" in result

    def test_build_research_summary_patterns(self):
        from wrg_mcp_server.tools.research_platform import _build_research_summary
        results = {"patterns": {"similar_queries": 3, "matches": []}}
        result = _build_research_summary("q?", results, ["patterns"])
        assert "Patterns: 3 similar" in result

    def _register(self):
        from wrg_mcp_server.tools.research_platform import register_research_platform_tools
        mcp = MagicMock()
        tools = {}

        def capture_tool():
            def dec(fn):
                tools[fn.__name__] = fn
                return fn
            return dec
        mcp.tool = capture_tool
        register_research_platform_tools(mcp)
        return tools

    @pytest.mark.asyncio
    async def test_research_deep_all_imports_fail(self):
        tools = self._register()
        # research_motor, arastirma_ussu, instinct — all not available in test env
        result = await tools["research_deep"]("test question", "target.com")
        # Should still return but with errors
        assert "errors" in result or result["ok"] is False

    @pytest.mark.asyncio
    async def test_research_deep_auto_mode_no_target(self):
        tools = self._register()
        result = await tools["research_deep"]("some generic question", "")
        # web mode should be tried but fail (no arastirma_ussu)
        assert "errors" in result or result["ok"] is False

    @pytest.mark.asyncio
    async def test_research_deep_explicit_mode(self):
        tools = self._register()
        result = await tools["research_deep"]("test", "domain.com", mode="osint")
        assert "errors" in result or result["ok"] is False
