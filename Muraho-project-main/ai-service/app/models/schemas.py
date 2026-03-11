"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


# ══════════════════════════════════════════════════════════
#  ASK RWANDA — RAG Chat
# ══════════════════════════════════════════════════════════

class QueryContext(BaseModel):
    """Current UI context sent with the query for location-aware responses."""

    current_page: str | None = Field(default=None, description="e.g. 'story:genocide-memorial-kigali'")
    museum_id: str | None = None
    route_id: str | None = None
    location_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class AskRwandaRequest(BaseModel):
    """User query to the Ask Rwanda AI assistant."""

    query: str = Field(..., max_length=2000, description="User's question")
    language: Literal["en", "fr", "rw", "auto"] = Field(
        default="auto",
        description="Query language. 'auto' for detection."
    )
    mode: Literal["standard", "personal_voices", "kid_friendly"] = Field(
        default="standard",
        description="AI tone/behavior mode"
    )
    context: QueryContext | None = None
    user_id: str | None = Field(default=None, description="For rate limiting")
    access_tier: Literal["free", "day_pass", "subscriber", "agency"] = "free"
    stream: bool = Field(default=True, description="Stream response tokens")
    # Passthrough fields from Payload endpoint
    messages: list[dict] | None = Field(default=None, description="Chat history from Payload")
    model: str | None = Field(default=None, description="Model override from Payload")
    temperature: float | None = Field(default=None, description="Temperature override")
    max_tokens: int | None = Field(default=None, description="Max tokens override")


class Source(BaseModel):
    """A cited source from the RAG pipeline."""

    source_id: str
    source_type: Literal["story", "testimony", "panel", "route_stop", "museum_info", "quote"]
    title: str
    excerpt: str = Field(description="Relevant excerpt from the source")
    similarity_score: float
    sensitivity_level: Literal["standard", "sensitive", "highly_sensitive"] = "standard"
    url: str | None = None


class RelatedContent(BaseModel):
    """Suggested related content to explore."""

    content_id: str
    content_type: str
    title: str
    thumbnail_url: str | None = None


class AskRwandaResponse(BaseModel):
    """Non-streaming response from Ask Rwanda."""

    answer: str
    sources: list[Source]
    language_detected: str
    language_response: str
    mode: str
    model_used: str
    related_content: list[RelatedContent] = []
    query_id: str
    processing_time_ms: int


# ══════════════════════════════════════════════════════════
#  EMBEDDINGS
# ══════════════════════════════════════════════════════════

class ChunkMetadata(BaseModel):
    """Metadata stored alongside each embedding in pgvector."""

    source_id: str
    source_type: str
    language: str = "en"
    location_id: str | None = None
    sensitivity_level: Literal["standard", "sensitive", "highly_sensitive"] = "standard"
    museum_id: str | None = None
    route_id: str | None = None
    tags: list[str] = []


class ContentChunk(BaseModel):
    """A single content chunk to embed."""

    chunk_id: str
    text: str
    metadata: ChunkMetadata


class EmbedRequest(BaseModel):
    """Request to generate embeddings for content chunks."""

    chunks: list[ContentChunk]
    # Simplified fields from Payload indexContent endpoint
    contentId: str | None = Field(default=None, description="Source content ID")
    contentType: str | None = Field(default=None, description="Source type")
    text: str | None = Field(default=None, description="Pre-extracted text")


class EmbedResponse(BaseModel):
    """Response after embedding generation."""

    embedded_count: int
    failed_count: int
    errors: list[str] = []


# ══════════════════════════════════════════════════════════
#  TRANSCRIPTION
# ══════════════════════════════════════════════════════════

class TranscribeRequest(BaseModel):
    """Request to transcribe audio file."""

    file_path: str = Field(description="Path to audio file on the server")
    source_id: str = Field(description="CMS content ID this audio belongs to")
    language_hint: str | None = Field(default=None, description="Expected language")
    auto_embed: bool = Field(default=True, description="Auto-generate embeddings after transcription")


class TranscriptSegment(BaseModel):
    """A timed segment of the transcription."""

    start: float
    end: float
    text: str
    language: str | None = None


class TranscribeResponse(BaseModel):
    """Transcription result."""

    transcript: str
    language_detected: str
    confidence: float
    duration_seconds: float
    segments: list[TranscriptSegment] = []
    chunks_embedded: int = 0


# ══════════════════════════════════════════════════════════
#  HEALTH
# ══════════════════════════════════════════════════════════

class ModelStatus(BaseModel):
    """Status of a loaded model."""

    loaded: bool
    name: str
    backend: str
    vram_mb: float | None = None


class GPUStatus(BaseModel):
    """GPU utilization info."""

    name: str
    vram_total_mb: float
    vram_used_mb: float
    utilization_percent: float
    temperature_c: float | None = None


class HealthResponse(BaseModel):
    """Service health status."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    uptime_seconds: float
    models: dict[str, ModelStatus]
    gpu: GPUStatus | None = None
    database: Literal["connected", "disconnected"]
    timestamp: datetime
