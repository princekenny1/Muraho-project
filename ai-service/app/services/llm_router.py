"""
LLM Router — Routes queries to the appropriate self-hosted model.

Strategy:
  - Simple/factual queries → Mistral 7B (fast, low VRAM)
  - Complex/sensitive queries → Mixtral 8×7B (stronger reasoning)
  - Both served via OpenAI-compatible API (works with Ollama and vLLM)

The router uses a lightweight classifier to decide which model handles each query.
"""

import logging
import time
from typing import AsyncGenerator

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


# Query complexity signals that trigger the heavy model
HEAVY_MODEL_SIGNALS = [
    # Genocide/memorial-related — needs stronger reasoning + safety
    "genocide", "tutsi", "hutu", "memorial", "testimony", "survivor",
    "murambi", "nyamata", "ntarama", "bisesero", "gisozi",
    # Complex reasoning
    "compare", "contrast", "analyze", "explain why", "relationship between",
    "significance of", "impact of", "how did", "what caused",
    # Multi-source synthesis
    "tell me everything", "comprehensive", "full history", "overview of",
    # Personal voices mode content
    "personal story", "witness", "account", "experience",
]


class LLMRouter:
    """
    Routes queries to Mistral 7B (fast) or Mixtral 8×7B (heavy).
    Both backends expose the same OpenAI-compatible chat completions API.
    """

    def __init__(self):
        self.client: AsyncOpenAI | None = None
        self.model_fast = settings.LLM_MODEL_FAST
        self.model_heavy = settings.LLM_MODEL_HEAVY

    async def initialize(self):
        """Connect to the LLM backend (Ollama or vLLM)."""
        self.client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key="not-needed",  # Self-hosted, no API key required
        )
        logger.info(
            f"LLM Router initialized: backend={settings.LLM_BACKEND}, "
            f"url={settings.LLM_BASE_URL}, "
            f"fast={self.model_fast}, heavy={self.model_heavy}"
        )

        # Verify connectivity
        try:
            models = await self.client.models.list()
            available = [m.id for m in models.data]
            logger.info(f"Available models: {available}")
        except Exception as e:
            logger.warning(f"Could not list models (backend may still be loading): {e}")

    async def shutdown(self):
        """Cleanup."""
        if self.client:
            await self.client.close()

    def classify_query(self, query: str, mode: str) -> str:
        """
        Decide which model handles this query.

        Returns model name: either the fast or heavy model.
        """
        query_lower = query.lower()

        # Personal Voices mode always uses heavy model (sensitivity)
        if mode == "personal_voices":
            return self.model_heavy

        # Check for complexity signals
        for signal in HEAVY_MODEL_SIGNALS:
            if signal in query_lower:
                return self.model_heavy

        # Long queries tend to be more complex
        if len(query.split()) > 40:
            return self.model_heavy

        # Default to fast model
        return self.model_fast

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        mode: str = "standard",
        model_override: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """
        Non-streaming generation. Returns the full response.
        """
        model = model_override or self.classify_query(user_message, mode)
        temp = temperature or (
            settings.LLM_TEMPERATURE_CREATIVE
            if mode == "kid_friendly"
            else settings.LLM_TEMPERATURE
        )

        start = time.monotonic()

        response = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temp,
            max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
            top_p=settings.LLM_TOP_P,
            stream=False,
        )

        elapsed_ms = int((time.monotonic() - start) * 1000)

        return {
            "content": response.choices[0].message.content,
            "model": model,
            "tokens_used": response.usage.total_tokens if response.usage else 0,
            "processing_time_ms": elapsed_ms,
        }

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        mode: str = "standard",
        model_override: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming generation. Yields tokens as they're generated.
        Used for the Ask Rwanda chat interface (real-time feel).
        """
        model = model_override or self.classify_query(user_message, mode)
        temp = temperature or (
            settings.LLM_TEMPERATURE_CREATIVE
            if mode == "kid_friendly"
            else settings.LLM_TEMPERATURE
        )

        stream = await self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temp,
            max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
            top_p=settings.LLM_TOP_P,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
