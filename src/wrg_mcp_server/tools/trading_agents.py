"""TradingAgents integration tools for MCP.

Exposes multi-agent trading analysis from the TradingAgents framework
(github.com/TauricResearch/TradingAgents) as MCP tools.
Requires: pip install tradingagents
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP


def register_trading_agents_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def trading_analyze(ticker: str, date: str = "", provider: str = "ollama", model: str = "") -> dict[str, Any]:
        """Run a full multi-agent trading analysis for a stock ticker.
        Deploys Analyst Team (fundamentals, sentiment, news, technical),
        Researcher Team (bull vs bear debate), Trader, and Risk Management.
        Returns buy/hold/sell decision with reasoning.

        Args:
            ticker: Stock symbol (e.g. NVDA, AAPL, TSLA)
            date: Analysis date in YYYY-MM-DD format (default: today)
            provider: LLM provider — ollama (free/local), openai, anthropic, google
            model: Model name override (default: provider's default)

        Slow (~30-120s). Requires LLM API key or Ollama running locally.
        """
        try:
            from tradingagents.graph.trading_graph import TradingAgentsGraph
            from tradingagents.default_config import DEFAULT_CONFIG

            config = DEFAULT_CONFIG.copy()
            config["llm_provider"] = provider

            if provider == "ollama":
                config["deep_think_llm"] = model or "qwen2.5:7b"
                config["quick_think_llm"] = model or "qwen2.5:7b"
                config["backend_url"] = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            elif provider == "openai":
                config["deep_think_llm"] = model or "gpt-4o"
                config["quick_think_llm"] = model or "gpt-4o-mini"
            elif provider == "anthropic":
                config["deep_think_llm"] = model or "claude-sonnet-4-20250514"
                config["quick_think_llm"] = model or "claude-haiku-4-5-20251001"
            elif provider == "google":
                config["deep_think_llm"] = model or "gemini-2.0-flash"
                config["quick_think_llm"] = model or "gemini-2.0-flash"

            config["max_debate_rounds"] = 1
            config["max_risk_discuss_rounds"] = 1

            if not date:
                date = datetime.now().strftime("%Y-%m-%d")

            ta = TradingAgentsGraph(debug=False, config=config)
            _, decision = ta.propagate(ticker.upper(), date)

            return {
                "ok": True,
                "ticker": ticker.upper(),
                "date": date,
                "provider": provider,
                "decision": decision,
            }
        except ImportError:
            return {"ok": False, "error": "tradingagents not installed. Run: pip install tradingagents"}
        except Exception as e:
            return {"ok": False, "error": str(e), "ticker": ticker}

    @mcp.tool()
    async def trading_quick_signal(ticker: str) -> dict[str, Any]:
        """Get a quick technical signal for a stock ticker using yfinance data.
        Does NOT run the full multi-agent pipeline — just fetches latest
        price, volume, and basic indicators (RSI, MACD).
        Fast (~2-5s), no LLM needed.

        Args:
            ticker: Stock symbol (e.g. NVDA, AAPL, TSLA)
        """
        try:
            import yfinance as yf

            stock = yf.Ticker(ticker.upper())
            hist = stock.history(period="1mo")

            if hist.empty:
                return {"ok": False, "error": f"No data for {ticker}"}

            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest

            price = float(latest["Close"])
            change = float((latest["Close"] - prev["Close"]) / prev["Close"] * 100)
            volume = int(latest["Volume"])
            avg_volume = int(hist["Volume"].mean())

            # Simple RSI (14-period)
            delta = hist["Close"].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = float(100 - (100 / (1 + rs)).iloc[-1])

            # Simple signal
            if rsi < 30:
                signal = "OVERSOLD (potential BUY)"
            elif rsi > 70:
                signal = "OVERBOUGHT (potential SELL)"
            else:
                signal = "NEUTRAL (HOLD)"

            return {
                "ok": True,
                "ticker": ticker.upper(),
                "price": round(price, 2),
                "change_pct": round(change, 2),
                "volume": volume,
                "avg_volume": avg_volume,
                "volume_ratio": round(volume / avg_volume, 2) if avg_volume > 0 else 0,
                "rsi_14": round(rsi, 1),
                "signal": signal,
                "period": f"{hist.index[0].strftime('%Y-%m-%d')} to {hist.index[-1].strftime('%Y-%m-%d')}",
            }
        except ImportError:
            return {"ok": False, "error": "yfinance not installed. Run: pip install yfinance"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
