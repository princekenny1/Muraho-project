"""
Muraho Rwanda — Self-Hosted AI Microservice
============================================
FastAPI service running on the GPU server.
Handles: RAG queries, embedding generation, audio transcription.
All processing is local — zero external API calls.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.routes import ask_rwanda, embeddings, transcription, health, tts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load models. Shutdown: cleanup."""
    setup_logging()

    # Import here to avoid circular deps
    from app.services.llm_router import LLMRouter
    from app.services.embedding_service import EmbeddingService

    # Initialize services as app state
    app.state.llm_router = LLMRouter()
    app.state.embedding_service = EmbeddingService()

    await app.state.llm_router.initialize()
    await app.state.embedding_service.initialize()

    yield

    # Cleanup
    await app.state.llm_router.shutdown()
    await app.state.embedding_service.shutdown()


app = FastAPI(
    title="Muraho Rwanda AI Service",
    description="Self-hosted AI for cultural storytelling. Data never leaves the infrastructure.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — only allow requests from our app server (internal network)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(health.router, tags=["Health"])
app.include_router(ask_rwanda.router, prefix="/api/v1", tags=["Ask Rwanda"])
app.include_router(embeddings.router, prefix="/api/v1", tags=["Embeddings"])
app.include_router(transcription.router, prefix="/api/v1", tags=["Transcription"])
app.include_router(tts.router, prefix="/api/v1", tags=["TTS"])
