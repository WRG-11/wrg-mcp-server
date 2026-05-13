"""Araştırma Üssü integration tools for MCP.

Exposes doc_search, memory_search, web_search and full agent query
from the arastirma-ussu project (D:\\dev\\arastirma-ussu).
Requires: pip install -e D:\\dev\\arastirma-ussu
"""

from __future__ import annotations

import importlib.util
import sys
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP


def _probe_import(module: str) -> dict[str, Any]:
    """Return ``{available, error}`` for a single dotted module path.

    Fast path: already-imported modules are considered available regardless
    of whether ``find_spec`` can locate them (test stubs injected via
    ``sys.modules`` without a proper ``__spec__`` would otherwise read as
    missing)."""
    if module in sys.modules:
        return {"available": True, "error": None}
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError) as e:
        return {"available": False, "error": f"{type(e).__name__}: {e}"}
    if spec is None:
        return {"available": False, "error": "module not found"}
    return {"available": True, "error": None}


def _probe_http(url: str, timeout: float = 2.0) -> dict[str, Any]:
    """Return ``{reachable, url, status?, error?}`` for a GET probe."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"reachable": True, "url": url, "status": resp.status}
    except Exception as e:
        return {"reachable": False, "url": url, "error": f"{type(e).__name__}: {e}"}


def register_arastirma_ussu_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def arastirma_doc_search(query: str) -> dict[str, Any]:
        """Search the Araştırma Üssü local document library (LlamaIndex + Qdrant).
        Returns matching document chunks for the given query.
        Requires: arastirma-ussu[layer2,layer3] installed + Qdrant running."""
        try:
            from arastirma_ussu.ingest.tool import doc_search
            result = doc_search(query)
            return {"ok": True, "result": result}
        except ImportError:
            return {"ok": False, "error": "arastirma-ussu not installed. Run: pip install -e D:\\dev\\arastirma-ussu"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    async def arastirma_memory_search(query: str) -> dict[str, Any]:
        """Search Araştırma Üssü conversation memory for relevant past Q&A pairs.
        Returns similar past questions and answers from Qdrant vector store.
        Requires: arastirma-ussu[layer3] installed + Qdrant running."""
        try:
            from arastirma_ussu.memory.tool import memory_search
            result = memory_search(query)
            return {"ok": True, "result": result}
        except ImportError:
            return {"ok": False, "error": "arastirma-ussu not installed"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    async def arastirma_web_search(query: str) -> dict[str, Any]:
        """Search the web via DuckDuckGo through Araştırma Üssü.
        Translates Turkish queries to English for better results.
        Requires: arastirma-ussu installed + internet access."""
        try:
            from arastirma_ussu.agent.tools import web_search
            result = web_search(query)
            return {"ok": True, "result": result}
        except ImportError:
            return {"ok": False, "error": "arastirma-ussu not installed"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    async def arastirma_ask(question: str) -> dict[str, Any]:
        """Ask the full Araştırma Üssü ReAct agent a question.
        Uses LangGraph + Ollama (qwen2.5:7b) with tool calling.
        Slow (~10-60s depending on complexity). Requires Ollama running.
        For simple searches prefer arastirma_doc_search or arastirma_web_search."""
        try:
            from arastirma_ussu.agent.graph import build_graph
            from arastirma_ussu.agent.prompts import build_system_prompt
            from arastirma_ussu.agent.tools import build_tool_registry
            from langchain_core.messages import HumanMessage, SystemMessage

            registry = build_tool_registry()
            system_prompt = build_system_prompt(registry)
            app = build_graph()

            result = app.invoke({
                "messages": [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=question),
                ],
                "iteration": 0,
                "max_iterations": 4,
                "last_action": "",
                "last_action_input": "",
                "last_observation": "",
                "final_answer": "",
                "error": "",
            })

            answer = result.get("final_answer") or result.get("error") or "Yanıt üretilemedi."
            return {
                "ok": True,
                "answer": answer,
                "iterations": result.get("iteration", 0),
                "tools_used": result.get("last_action", ""),
            }
        except ImportError as e:
            return {"ok": False, "error": f"Missing dependency: {e}. Run: pip install -e D:\\dev\\arastirma-ussu"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    async def arastirma_health() -> dict[str, Any]:
        """Cross-repo health probe for the arastirma-ussu integration.

        Checks per-layer module availability + Ollama/Qdrant reachability
        so callers can choose between arastirma_doc_search / arastirma_ask
        / arastirma_eval before paying the slow path. No external API
        calls — Ollama + Qdrant probes hit localhost only."""
        checks: dict[str, Any] = {
            "arastirma_ussu":     _probe_import("arastirma_ussu"),
            "layer1_agent":       _probe_import("arastirma_ussu.agent.graph"),
            "layer2_ingest":      _probe_import("arastirma_ussu.ingest.tool"),
            "layer3_memory":      _probe_import("arastirma_ussu.memory.tool"),
            "layer4_crew":        _probe_import("arastirma_ussu.crew"),
            "layer5_guards":      _probe_import("arastirma_ussu.guards.pipeline"),
            "layer55_eval":       _probe_import("arastirma_ussu.eval"),
            "ollama":             _probe_http("http://localhost:11434/api/tags"),
            "qdrant":             _probe_http("http://localhost:6333/healthz"),
        }
        healthy = sum(
            1 for v in checks.values()
            if v.get("available") or v.get("reachable")
        )
        total = len(checks)
        return {
            "ok": healthy > 0,
            "checks": checks,
            "summary": f"{healthy}/{total} healthy",
        }

    @mcp.tool()
    async def arastirma_eval(
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate a (question, answer, contexts) tuple using the
        arastirma-ussu Layer 5.5 RAGAS skeleton (faithfulness +
        answer_relevancy + context_recall).

        Skeleton mode (no judge LLM): returns all-nan JudgeResult to
        prove the contract. Real RAGAS execution requires
        ``arastirma-ussu[layer55]`` extras + a configured Ollama judge;
        that path is exercised via arastirma_ussu's own pytest
        ``experimental`` marker, not from MCP."""
        try:
            from arastirma_ussu.eval import evaluate_answer
            r = evaluate_answer(
                question, answer, list(contexts),
                ground_truth=ground_truth,
            )
            return {
                "ok": True,
                "faithfulness": r.faithfulness,
                "answer_relevancy": r.answer_relevancy,
                "context_recall": r.context_recall,
                "overall": r.overall,
                "is_passing": r.is_passing(),
                "raw": r.raw,
            }
        except ImportError as e:
            return {"ok": False, "error": f"{e}. Run: pip install -e D:\\dev\\arastirma-ussu"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
