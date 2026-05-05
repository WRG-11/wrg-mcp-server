"""Polymarket prediction-market signal tool for MCP.

Lightweight bridge to Polymarket's public Gamma API
(https://gamma-api.polymarket.com) — fetches a single market's current
state and returns a structured signal: question, outcomes with implied
probabilities, volume, and a directional lean.

The full historical pipeline (markets + order events + trades) lives in
warproxxx/poly_data — that's the right tool for backtesting. This MCP
tool is the fast read for "what's the market saying right now?".

Bridge motivation: prediction-market consensus on macro / event-driven
catalysts is a useful complement to the equity signal already exposed by
trading_quick_signal. Together they cover both the "fundamentals" and
"crowd belief" axes a TradingAgents debate could weigh.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

GAMMA_API = "https://gamma-api.polymarket.com"


def register_polymarket_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def polymarket_event_signal(market: str) -> dict[str, Any]:
        """Fetch current state of a Polymarket prediction market by slug or id.

        Returns the question, end date, each outcome's implied probability
        (last trade price treated as P), 24h volume, and a directional
        "lean" — the favoured outcome plus its margin over a 50/50 prior.
        Fast (~1-2s, single REST call). No LLM needed.

        For the full historical event stream, see warproxxx/poly_data.

        Args:
            market: Polymarket slug (e.g. "will-bitcoin-hit-150k-in-2026")
                    or condition_id.
        """
        try:
            import httpx
        except ImportError:
            return {
                "ok": False,
                "error": "httpx not installed. Run: pip install 'wrg-mcp-server[remote]'",
            }

        params = {"slug": market} if not market.startswith("0x") else {"condition_ids": market}
        url = f"{GAMMA_API}/markets"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            return {"ok": False, "error": f"gamma-api request failed: {exc}", "market": market}

        if not data:
            return {"ok": False, "error": f"no market found for {market!r}", "market": market}

        record = data[0] if isinstance(data, list) else data
        return _build_signal(record, market)


def _build_signal(record: dict[str, Any], market_query: str) -> dict[str, Any]:
    question = record.get("question") or record.get("title") or "?"
    end_date = record.get("endDate") or record.get("end_date")
    volume_24h = float(record.get("volume24hr") or 0.0)
    volume_total = float(record.get("volume") or 0.0)

    outcomes_raw = record.get("outcomes") or []
    prices_raw = record.get("outcomePrices") or []
    outcomes = _zip_outcomes(outcomes_raw, prices_raw)

    lean_outcome, lean_margin = _compute_lean(outcomes)

    return {
        "ok": True,
        "market": market_query,
        "slug": record.get("slug"),
        "question": question,
        "end_date": end_date,
        "active": bool(record.get("active", False)),
        "closed": bool(record.get("closed", False)),
        "volume_24h_usd": round(volume_24h, 2),
        "volume_total_usd": round(volume_total, 2),
        "outcomes": outcomes,
        "lean": {
            "outcome": lean_outcome,
            "margin_over_50_50": round(lean_margin, 4),
        },
    }


def _zip_outcomes(outcomes_raw: Any, prices_raw: Any) -> list[dict[str, Any]]:
    names = _coerce_list(outcomes_raw)
    prices = _coerce_list(prices_raw)
    pairs: list[dict[str, Any]] = []
    for idx, name in enumerate(names):
        try:
            price = float(prices[idx]) if idx < len(prices) else 0.0
        except (TypeError, ValueError):
            price = 0.0
        pairs.append({
            "name": str(name),
            "price": round(price, 4),
            "implied_probability": round(price, 4),
        })
    return pairs


def _coerce_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Gamma API sometimes returns JSON-encoded strings: '["Yes","No"]'
        import json
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, TypeError):
            pass
    return []


def _compute_lean(outcomes: list[dict[str, Any]]) -> tuple[str, float]:
    if not outcomes:
        return "?", 0.0
    leader = max(outcomes, key=lambda o: o.get("price", 0.0))
    margin = float(leader.get("price", 0.0)) - 0.5
    return str(leader.get("name", "?")), margin
