"""
Main agent orchestration.
"""

import asyncio
import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from typing import Any
import re

from config.settings import settings
from models.query import SearchQuery, SearchResult
from orchestration.react_loop import ReActLoop, ReActResult
from orchestration.tools import build_tool_registry
from persistence.asset_repository import AssetRepository
from utils.vision_answer import answer_with_images


log = structlog.get_logger()


class InferenceClient:
    """
    Phase 1: Decoupled LLM Inference Gateway.
    Communicates with vLLM, LiteLLM, or any OpenAI-compatible endpoint.
    """
    def __init__(self):
        # Fallback về OLLAMA_BASE_URL để tương thích ngược nếu chưa thiết lập Gateway
        raw_url = getattr(settings, "INFERENCE_BASE_URL", None) or settings.OLLAMA_BASE_URL
        self._base_url = str(raw_url or "").rstrip("/")
        self._model = getattr(settings, "INFERENCE_MODEL", getattr(settings, "OLLAMA_LLM_MODEL", "gpt-3.5-turbo"))

    async def chat(self, system: str, user: str, max_tokens: int = 800) -> str:
        try:
            async with httpx.AsyncClient(timeout=getattr(settings, "LLM_TIMEOUT", 800.0)) as client:
                payload = {
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.1,
                }
                # Gọi tới LiteLLM / vLLM gateway (Chuẩn cấu trúc OpenAI API)
                resp = await client.post(f"{self._base_url}/v1/chat/completions", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except asyncio.TimeoutError:
            log.warning("inference.timeout", model=self._model)
            raise
        except httpx.TimeoutException:
            log.warning("inference.httpx_timeout", model=self._model)
            raise asyncio.TimeoutError(f"Inference service timed out")
        except (httpx.ConnectError, httpx.NetworkError) as e:
            log.error("inference.connection_error", error=str(e))
            raise ConnectionError(f"LLM service unreachable: {str(e)}")
        except httpx.HTTPStatusError as e:
            log.error("inference.http_error", status=e.response.status_code, text=e.response.text)
            if e.response.status_code == 503:
                raise ConnectionError("LLM service unavailable")
            raise RuntimeError(f"Inference error {e.response.status_code}")
        except Exception as e:
            log.exception("inference.unexpected_error", error=str(e))
            raise

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

# Trỏ Alias tạm thời để các tools/plugins nếu có import OllamaLLM cũ không bị gãy
OllamaLLM = InferenceClient


class Agent:
    """
    Agent điều phối (Orchestrator) chính của hệ thống.
    Kết nối với phân hệ MyGPT BA Suite (Pipeline 9 Agents) thông qua SKILL.md.
    
    Chức năng chính:
    - Vận hành vòng lặp ReAct để giải quyết các yêu cầu nghiệp vụ phức tạp.
    - Gọi các công cụ (Tools) chuyên biệt: Search, GraphQuery, JiraTaskWriter.
    - Hỗ trợ 4-Layer Structured Output: Đảm bảo output JSON chuẩn schema để tránh ảo giác.
    - Tích hợp Vision pipeline: Giải thích diagram, screenshot từ Confluence/Jira.
    - Truyền ID nhất quán (intake_id, design_ref) xuyên suốt chuỗi 9 Agents.
    """
    def __init__(self, session: AsyncSession, user_id: str):
        """
        Initialize Agent with user context from the start.
        
        Args:
            session: AsyncSession for database access
            user_id: User ID for permission/context filtering
        """
        self._session = session
        self._user_id = user_id
        
        # Phase 1: Decoupled LLM
        self._llm = InferenceClient()
        
        # Phase 3: Dedicated RAG Service Base URL
        raw_rag_url = getattr(settings, "RAG_SERVICE_URL", None) or "http://rag-service:8000"
        self._rag_service_url = str(raw_rag_url or "").rstrip("/")
        
        log.info(
            "agent.initialized",
            user_id=user_id,
        )

    async def ask(self, question: str, on_thought: Any | None = None, on_token: Any | None = None) -> dict:
        """
        Process a question through the ReAct agent pipeline.
        
        Args:
            question: User's question
            on_thought: Optional callback for each agent thought
            on_token: Optional callback for each answer token
            
        Returns:
            Dictionary with answer, sources, and metadata
            
        Raises:
            asyncio.TimeoutError: If LLM processing times out
            ConnectionError: If LLM service is unavailable
        """
        # Build tools with user context
        tools = build_tool_registry(self._session, user_id=self._user_id)
        loop = ReActLoop(tools, max_iterations=settings.AGENT_MAX_STEPS)
        
        try:
            # Note: user_id is already in self, no need to pass again
            result: ReActResult = await loop.run(question, user_id=self._user_id, on_thought=on_thought, on_token=on_token)
        except asyncio.TimeoutError:
            # Re-raise to be caught by API endpoint
            raise
        except Exception as e:
            log.exception(
                "agent.ask_failed",
                user_id=self._user_id,
                question=question[:60],
                error_type=type(e).__name__,
            )
            raise
        finally:
            try:
                await loop.close()
            except Exception:
                pass

        sources = self._format_sources(result.sources)

        # Optional: run a final vision-aware answer pass if we have image assets for the retrieved chunks.
        # Captions are already injected into text, but vision can answer "explain this diagram/screenshot" more reliably.
        if settings.VISION_ENABLED and str(settings.OLLAMA_VISION_MODEL or "").strip():
            try:
                chunk_ids = [str(s.get("chunk_id") or "").strip() for s in (result.sources or []) if str(s.get("chunk_id") or "").strip()]
                chunk_ids = list(dict.fromkeys(chunk_ids))[:12]
                assets_by_chunk = await AssetRepository(self._session).assets_for_chunks(chunk_ids)

                picked: list[str] = []
                for cid in chunk_ids:
                    for a in (assets_by_chunk.get(cid) or []):
                        aid = str(a.get("asset_id") or "").strip()
                        if aid and aid not in picked:
                            picked.append(aid)
                        if len(picked) >= int(settings.VISION_MAX_IMAGES_PER_ANSWER or 2):
                            break
                    if len(picked) >= int(settings.VISION_MAX_IMAGES_PER_ANSWER or 2):
                        break

                async def _read_img(ap: Path) -> bytes | None:
                    try:
                        return await asyncio.to_thread(ap.read_bytes)
                    except Exception as e:
                        log.warning("agent.vision.read_failed", path=str(ap), error=str(e))
                        return None

                assets_dir = Path(settings.ASSETS_DIR or "assets")
                read_tasks = []
                
                # Collection logic (same as before but prepared for parallel)
                for cid in chunk_ids:
                    for a in (assets_by_chunk.get(cid) or []):
                        aid = str(a.get("asset_id") or "").strip()
                        if aid not in picked:
                            continue
                        rel = str(a.get("local_path") or "").strip().replace("\\", "/")
                        if rel:
                            read_tasks.append(_read_img(assets_dir / rel))

                # Parallel async read
                images_raw = await asyncio.gather(*read_tasks)
                images: list[bytes] = [b for b in images_raw if b]

                # Build a compact text context for the vision pass.
                blocks: list[str] = []
                for s in (result.sources or [])[:6]:
                    title = str(s.get("title") or "").strip()
                    content = str(s.get("content") or "").strip()
                    content = re.sub(r"\[\[ASSET_ID:[0-9a-fA-F-]{36}\]\]", "", content).strip()
                    if not content:
                        continue
                    blocks.append(f"TITLE: {title}\n{content[:1800]}".strip())
                vision_context = "\n\n---\n\n".join(blocks)[:12000]

                if images:
                    vision_out = await answer_with_images(question=question, context=vision_context, images=images)
                    if vision_out:
                        result.answer = vision_out
                        if "vision_answer" not in (result.used_tools or []):
                            result.used_tools.append("vision_answer")
            except Exception:
                pass

        log.info(
            "agent.ask.done",
            question=question[:60],
            iterations=len(result.steps),
            used_tools=result.used_tools,
            sources=len(sources),
        )

        return {
            "answer": result.answer,
            "sources": sources,
            "rewritten_query": result.rewritten_query or question,
            "agent_steps": self._format_steps(result.steps),
            "agent_plan": [{"step": p.step, "tool": p.tool, "reason": p.reason} for p in result.plan],
            "used_tools": result.used_tools,
        }

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        log.info("agent.search.delegated", q=query.raw, limit=query.limit, offset=query.offset)
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                payload = {
                    "raw": query.raw,
                    "effective": query.effective,
                    "limit": query.limit,
                    "offset": query.offset,
                    "user_id": query.user_id,
                    "entities": query.entities
                }
                # Ủy quyền toàn bộ RAG search + Reranking sang service chuyên biệt
                resp = await client.post(f"{self._rag_service_url}/search", json=payload)
                resp.raise_for_status()
                
                data = resp.json()
                results = data.get("results", [])
                return [SearchResult(**item) for item in results]
                
        except Exception as e:
            log.exception("agent.rag_service.failed", error=str(e))
            return []

    async def health(self) -> dict:
        llm_ok = await self._llm.is_available()
        return {
            "inference_gateway": "ok" if llm_ok else "unavailable",
            "inference_model": self._llm._model,
            "inference_url": self._llm._base_url,
            "embedding_model": settings.EMBEDDING_MODEL,
        }

    def _format_sources(self, raw_sources: list[dict]) -> list[dict]:
        seen: dict[str, dict] = {}
        for source in raw_sources:
            url = source.get("url") or source.get("document_id", "")
            if url and url not in seen:
                seen[url] = {
                    "title": source.get("title", "Untitled"),
                    "url": source.get("url", ""),
                    "source": source.get("source", ""),
                    "score": round(source.get("score", 0), 3),
                    "snippet": source.get("content", "")[:150],
                    "document_id": source.get("document_id", ""),
                    "chunk_id": source.get("chunk_id", ""),
                    "assets": source.get("assets") or [],
                }
        return list(seen.values())

    def _format_steps(self, steps) -> list[dict]:
        return [
            {
                "iteration": step.iteration,
                "thought": step.thought,
                "action": step.action,
                "action_input": step.action_input,
                "observation": step.observation[:300] if step.observation else "",
                "is_final": step.is_final,
            }
            for step in steps
        ]
