"""
RAG Pipeline — Retrieval-Augmented Generation for Ask Rwanda.

Full pipeline:
  1. Language detection + translation (if Kinyarwanda)
  2. Safety check (blocklist + pattern matching)
  3. Context assembly (page, mode, location)
  4. Hybrid retrieval (semantic + keyword)
  5. Source selection + deduplication
  6. System prompt construction (identity + tone + safety + location)
  7. LLM generation (streaming or full)
  8. Post-processing (citations, related content, safety filter)
"""

import logging
import time
import uuid
from typing import AsyncGenerator

from app.core.config import settings
from app.services.llm_router import LLMRouter
from app.services.embedding_service import EmbeddingService
from app.services.safety_service import SafetyService
from app.services.language_service import LanguageService
from app.prompts.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Orchestrates the full Ask Rwanda RAG flow.
    """

    def __init__(
        self,
        llm_router: LLMRouter,
        embedding_service: EmbeddingService,
    ):
        self.llm = llm_router
        self.embeddings = embedding_service
        self.safety = SafetyService()
        self.language = LanguageService()
        self.prompts = PromptBuilder()

    async def process_query(
        self,
        query: str,
        language: str = "auto",
        mode: str = "standard",
        context: dict | None = None,
        access_tier: str = "free",
    ) -> dict:
        """
        Full RAG pipeline — non-streaming response.

        Returns a complete response with answer, sources, and metadata.
        """
        query_id = str(uuid.uuid4())[:12]
        start = time.monotonic()
        context = context or {}

        # ── Step 1: Language Detection ────────────────────
        detected_lang = language
        search_query = query

        if language == "auto":
            detected_lang = self.language.detect(query)

        # If Kinyarwanda, translate to English for better retrieval
        if detected_lang == "rw":
            search_query = self.language.translate_to_english(query)
            logger.info(f"[{query_id}] Translated RW→EN: '{query[:50]}' → '{search_query[:50]}'")

        # ── Step 2: Safety Check ──────────────────────────
        safety_result = self.safety.check_query(query)
        if safety_result["blocked"]:
            return {
                "answer": safety_result["safe_response"],
                "sources": [],
                "language_detected": detected_lang,
                "language_response": detected_lang,
                "mode": mode,
                "model_used": "safety_filter",
                "related_content": [],
                "query_id": query_id,
                "processing_time_ms": int((time.monotonic() - start) * 1000),
            }

        # ── Step 3: Build Search Filters ──────────────────
        filters = self._build_filters(context, mode, access_tier)

        # ── Step 4: Hybrid Retrieval ──────────────────────
        # Semantic search (primary)
        semantic_results = await self.embeddings.search(
            query=search_query,
            filters=filters,
            limit=settings.VECTOR_SEARCH_LIMIT,
        )

        # Keyword fallback (if semantic results are low confidence)
        if not semantic_results or semantic_results[0]["similarity_score"] < 0.5:
            keyword_results = await self.embeddings.keyword_search(
                query=search_query,
                limit=10,
            )
            # Merge, preferring semantic results
            seen_ids = {r["chunk_id"] for r in semantic_results}
            for kr in keyword_results:
                if kr["chunk_id"] not in seen_ids:
                    semantic_results.append(kr)

        # ── Step 5: Select Top Sources ────────────────────
        sources = self._select_sources(
            semantic_results,
            limit=settings.VECTOR_RERANK_LIMIT,
        )

        # ── Step 6: Build System Prompt ───────────────────
        system_prompt = self.prompts.build(
            mode=mode,
            context=context,
            sources=sources,
            language=detected_lang,
        )

        # ── Step 7: Generate Response ─────────────────────
        # Construct the user message with retrieved context
        augmented_query = self._build_augmented_query(query, sources, detected_lang)

        llm_result = await self.llm.generate(
            system_prompt=system_prompt,
            user_message=augmented_query,
            mode=mode,
        )

        # ── Step 8: Post-Processing ───────────────────────
        answer = llm_result["content"]

        # Safety filter on output
        output_check = self.safety.check_output(answer)
        if output_check["flagged"]:
            answer = output_check["filtered_response"]

        elapsed_ms = int((time.monotonic() - start) * 1000)

        return {
            "answer": answer,
            "sources": [
                {
                    "source_id": s["source_id"],
                    "source_type": s["source_type"],
                    "title": s.get("title", s["source_id"]),
                    "excerpt": s["text"][:200],
                    "similarity_score": s["similarity_score"],
                    "sensitivity": s["sensitivity"],
                }
                for s in sources
            ],
            "language_detected": detected_lang,
            "language_response": detected_lang,
            "mode": mode,
            "model_used": llm_result["model"],
            "related_content": [],
            "query_id": query_id,
            "processing_time_ms": elapsed_ms,
        }

    async def process_query_stream(
        self,
        query: str,
        language: str = "auto",
        mode: str = "standard",
        context: dict | None = None,
        access_tier: str = "free",
    ) -> AsyncGenerator[str, None]:
        """
        Streaming RAG pipeline — yields tokens as they're generated.
        Retrieval happens upfront, then LLM streams the response.
        """
        context = context or {}

        # Steps 1-6 are identical to non-streaming
        detected_lang = language
        search_query = query

        if language == "auto":
            detected_lang = self.language.detect(query)

        if detected_lang == "rw":
            search_query = self.language.translate_to_english(query)

        safety_result = self.safety.check_query(query)
        if safety_result["blocked"]:
            yield safety_result["safe_response"]
            return

        filters = self._build_filters(context, mode, access_tier)
        semantic_results = await self.embeddings.search(query=search_query, filters=filters)

        if not semantic_results or semantic_results[0]["similarity_score"] < 0.5:
            keyword_results = await self.embeddings.keyword_search(query=search_query)
            seen_ids = {r["chunk_id"] for r in semantic_results}
            for kr in keyword_results:
                if kr["chunk_id"] not in seen_ids:
                    semantic_results.append(kr)

        sources = self._select_sources(semantic_results)

        system_prompt = self.prompts.build(
            mode=mode, context=context, sources=sources, language=detected_lang,
        )
        augmented_query = self._build_augmented_query(query, sources, detected_lang)

        # Stream from LLM
        async for token in self.llm.generate_stream(
            system_prompt=system_prompt,
            user_message=augmented_query,
            mode=mode,
        ):
            yield token

    # ── Helper Methods ────────────────────────────────────

    def _build_filters(self, context: dict, mode: str, access_tier: str) -> dict:
        """Build pgvector metadata filters from the query context."""
        filters = {}

        # Kid-friendly mode: exclude sensitive content
        if mode == "kid_friendly":
            filters["sensitivity"] = "standard"
        elif mode == "standard":
            filters["sensitivity"] = "sensitive"       # Include up to sensitive
        else:
            filters["sensitivity"] = "highly_sensitive" # Personal voices: include all

        # Location-scoped retrieval
        if context.get("museum_id"):
            filters["museum_id"] = context["museum_id"]
        if context.get("route_id"):
            filters["route_id"] = context["route_id"]
        if context.get("location_id"):
            filters["location_id"] = context["location_id"]

        return filters

    def _select_sources(self, results: list[dict], limit: int | None = None) -> list[dict]:
        """
        Select and deduplicate the best sources.
        Prefers diversity across source types.
        """
        limit = limit or settings.VECTOR_RERANK_LIMIT
        selected = []
        seen_sources = set()

        for result in results:
            source_key = result["source_id"]

            # Skip if we already have a chunk from this source
            if source_key in seen_sources and len(selected) < limit:
                continue

            seen_sources.add(source_key)
            selected.append(result)

            if len(selected) >= limit:
                break

        return selected

    def _build_augmented_query(
        self,
        original_query: str,
        sources: list[dict],
        language: str,
    ) -> str:
        """
        Build the augmented user message with retrieved context.
        """
        if not sources:
            return (
                f"Question: {original_query}\n\n"
                "Note: No relevant sources were found in the Muraho Rwanda content library. "
                "You MUST NOT use external or general knowledge to answer this question. "
                "Instead, politely let the user know that you don't have information about "
                "this topic in the platform's content library, and suggest they explore "
                "related content on the platform such as stories, museums, or routes. "
                "If the question is about Rwanda's heritage, suggest specific sections "
                "of the app they could visit to learn more."
            )

        context_parts = []
        for i, source in enumerate(sources, 1):
            context_parts.append(
                f"[Source {i} — {source['source_type']}]\n{source['text']}"
            )

        context_block = "\n\n".join(context_parts)

        return (
            f"RETRIEVED CONTEXT:\n{context_block}\n\n"
            f"---\n"
            f"USER QUESTION ({language}): {original_query}\n\n"
            f"Answer the question using ONLY the retrieved context above. "
            f"Do NOT use any external knowledge, general training data, or information "
            f"from outside the Muraho Rwanda content library. "
            f"Cite sources by number [Source N]. If the context doesn't contain "
            f"enough information, say so honestly and suggest the user explore "
            f"related content on the platform."
        )
