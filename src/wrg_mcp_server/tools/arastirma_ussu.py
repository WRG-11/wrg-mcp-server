"""Araştırma Üssü integration tools for MCP.

Exposes doc_search, memory_search, web_search and full agent query
from the arastirma-ussu project (D:\\dev\\arastirma-ussu).
Requires: pip install -e D:\\dev\\arastirma-ussu
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP


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
