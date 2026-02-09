"""
Configuration — loaded from environment variables.
Supports both Ollama (dev) and vLLM (production) backends.
"""

from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # ── Service ──────────────────────────────────────────
    APP_NAME: str = "Muraho AI Service"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Network ──────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
    APP_SERVER_URL: str = "http://localhost:3000"

    # ── LLM Backend ──────────────────────────────────────
    # Supports "ollama" (dev) or "vllm" (production)
    # Both expose OpenAI-compatible APIs — same code, different backend
    LLM_BACKEND: Literal["ollama", "vllm"] = "ollama"
    LLM_BASE_URL: str = "http://localhost:11434/v1"  # Ollama default

    # Model names (must match what's loaded in Ollama/vLLM)
    LLM_MODEL_FAST: str = "mistral"                   # Mistral 7B — 80% of queries
    LLM_MODEL_HEAVY: str = "mixtral"                   # Mixtral 8×7B — complex queries
    LLM_MODEL_DEFAULT: str = "mistral"                 # Fallback model

    # Generation parameters
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.3                       # Low for factual accuracy
    LLM_TEMPERATURE_CREATIVE: float = 0.7              # Higher for storytelling mode
    LLM_TOP_P: float = 0.9
    LLM_STREAM: bool = True                            # Streaming responses for chat UX

    # ── Embedding ────────────────────────────────────────
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_DEVICE: str = "cpu"                      # Runs on CPU, no GPU needed
    EMBEDDING_BATCH_SIZE: int = 32

    # ── Vector Search (pgvector) ─────────────────────────
    DATABASE_URL: str = "postgresql://muraho:muraho@localhost:5432/muraho"
    VECTOR_TABLE: str = "content_embeddings"
    VECTOR_SEARCH_LIMIT: int = 20                      # Retrieve top 20 candidates
    VECTOR_RERANK_LIMIT: int = 8                       # Return top 8 after re-ranking
    VECTOR_SIMILARITY_THRESHOLD: float = 0.3           # Minimum cosine similarity

    # ── Chunking ─────────────────────────────────────────
    CHUNK_SIZE: int = 512                              # Tokens per chunk
    CHUNK_OVERLAP: int = 50                            # Overlap between chunks

    # ── Transcription (Faster-Whisper) ───────────────────
    WHISPER_MODEL: str = "large-v3"
    WHISPER_DEVICE: str = "cuda"                       # GPU for transcription
    WHISPER_COMPUTE_TYPE: str = "float16"
    WHISPER_LANGUAGE: str | None = None                 # Auto-detect language

    # ── Translation (NLLB-200) ───────────────────────────
    TRANSLATION_MODEL: str = "facebook/nllb-200-distilled-600M"
    TRANSLATION_DEVICE: str = "cpu"
    SUPPORTED_LANGUAGES: list[str] = ["en", "fr", "rw"]

    # ── Safety ───────────────────────────────────────────
    SAFETY_BLOCKLIST_PATH: str = "app/prompts/blocklist.txt"
    SAFETY_MAX_QUERY_LENGTH: int = 2000                # Reject excessively long queries
    ENABLE_AUDIT_LOG: bool = True
    AUDIT_LOG_PATH: str = "/var/log/muraho/ai_audit.jsonl"

    # ── Rate Limiting ────────────────────────────────────
    RATE_LIMIT_FREE: int = 5                           # Queries per day (free tier)
    RATE_LIMIT_PAID: int = 100                         # Queries per day (paid tier)
    RATE_LIMIT_AGENCY: int = 500                       # Queries per day (agency tier)

    # ── Redis (caching + rate limiting) ──────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 3600                              # 1 hour cache for common queries

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
