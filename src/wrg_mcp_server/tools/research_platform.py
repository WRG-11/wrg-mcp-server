"""AI Research Platform — unified research tool combining multiple engines.

Orchestrates: araştırma_üssü (RAG) + research_motor (OSINT) + instinct (pattern learning)
into a single research pipeline that improves over time.
"""

from __future__ import annotations

import json
import time
from typing import Any

from mcp.server.fastmcp import FastMCP


def register_research_platform_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def research_deep(
        question: str,
        target: str = "",
        mode: str = "auto",
    ) -> dict[str, Any]:
        """Run a deep research pipeline combining multiple engines.
        Automatically selects the best research approach based on the question:
        - 'osint' mode: research_motor OSINT scan (for people, domains, IPs)
        - 'rag' mode: araştırma_üssü local document search + LLM reasoning
        - 'web' mode: araştırma_üssü web search via DuckDuckGo
        - 'auto' mode: tries all available engines and combines results

        Args:
            question: The research question to answer
            target: Optional target identifier (username, domain, ticker)
            mode: Research mode — auto, osint, rag, web

        Returns combined results from all engines with confidence scoring.
        Learns from patterns via instinct (when available).
        """
        start = time.time()
        results = {}
        errors = []

        # Determine mode
        if mode == "auto":
            modes = _detect_modes(question, target)
        else:
            modes = [mode]

        # 1. OSINT via research_motor
        if "osint" in modes and target:
            try:
                from research_motor.core.extract import extract_candidates
                from research_motor.core.normalize import normalize_sources
                from research_motor.core.score import score_candidates

                raw = [{
                    "id": f"research_{int(time.time())}",
                    "source_type": "unknown",
                    "title": f"Research: {question}",
                    "body": f"Target: {target}. Question: {question}",
                    "source_url": None,
                    "timestamp": None,
                    "metadata": {"target": target, "question": question},
                }]
                normalized = normalize_sources(raw)
                candidates = extract_candidates(normalized)
                scores = score_candidates(candidates, normalized)
                results["osint"] = {
                    "candidates": len(candidates),
                    "top_score": max((s.total_score for s in scores), default=0),
                    "scores": [s.to_dict() for s in scores[:5]],
                }
            except ImportError:
                errors.append("research_motor not available")
            except Exception as e:
                errors.append(f"osint error: {e}")

        # 2. RAG via araştırma_üssü
        if "rag" in modes:
            try:
                from arastirma_ussu.ingest.tool import doc_search
                result = doc_search(question)
                results["rag"] = {"result": result, "source": "local_documents"}
            except ImportError:
                errors.append("arastirma_ussu not available")
            except Exception as e:
                errors.append(f"rag error: {e}")

        # 3. Web search via araştırma_üssü
        if "web" in modes:
            try:
                from arastirma_ussu.agent.tools import web_search
                result = web_search(question)
                results["web"] = {"result": result, "source": "duckduckgo"}
            except ImportError:
                errors.append("arastirma_ussu web_search not available")
            except Exception as e:
                errors.append(f"web error: {e}")

        # 4. Pattern learning via instinct
        try:
            from instinct.store import MemoryStore  # type: ignore[attr-defined]
            store = MemoryStore()
            # Check if we've seen similar questions before
            similar = store.search(question, limit=3)
            if similar:
                results["patterns"] = {
                    "similar_queries": len(similar),
                    "matches": [{"query": s.key, "score": s.score} for s in similar],
                }
            # Save this query for future learning
            store.set(
                f"research:{int(time.time())}",
                json.dumps({"question": question, "target": target, "modes": modes}),
                tags=["research", mode],
            )
        except ImportError:
            pass  # instinct is optional — silently skip
        except Exception:
            pass  # pattern learning failure should never block research

        elapsed = time.time() - start
        engines_used = list(results.keys())

        return {
            "ok": len(results) > 0,
            "question": question,
            "target": target,
            "engines_used": engines_used,
            "results": results,
            "errors": errors if errors else None,
            "elapsed_seconds": round(elapsed, 2),
            "summary": _build_research_summary(question, results, engines_used),
        }


def _detect_modes(question: str, target: str) -> list[str]:
    """Auto-detect which research modes to use."""
    modes = []
    q = question.lower()

    # OSINT keywords
    osint_kw = ["kim", "who", "person", "user", "profile", "domain", "ip", "osint",
                "recon", "footprint", "dijital", "izle", "araştır"]
    if any(k in q for k in osint_kw) or target:
        modes.append("osint")

    # RAG keywords (local docs)
    rag_kw = ["belge", "document", "dosya", "file", "proje", "project", "kod", "code"]
    if any(k in q for k in rag_kw):
        modes.append("rag")

    # Web search — default fallback
    modes.append("web")

    return modes


def _build_research_summary(question: str, results: dict[str, Any], engines: list[str]) -> str:
    if not engines:
        return f"No research engines available for: {question}"

    parts = []
    if "osint" in results:
        n = results["osint"]["candidates"]
        parts.append(f"OSINT: {n} candidate(s) found")
    if "rag" in results:
        r = results["rag"]["result"]
        parts.append(f"RAG: {len(r)} chars from local docs")
    if "web" in results:
        r = results["web"]["result"]
        parts.append(f"Web: {len(r)} chars from DuckDuckGo")
    if "patterns" in results:
        n = results["patterns"]["similar_queries"]
        parts.append(f"Patterns: {n} similar past queries")

    return f"Research complete ({', '.join(engines)}): " + "; ".join(parts)
