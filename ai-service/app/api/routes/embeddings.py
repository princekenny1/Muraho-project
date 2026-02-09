"""
Embeddings API — Content indexing endpoints.

Called by Payload CMS webhooks when content is published/updated/deleted.
Generates embeddings and stores them in pgvector.
"""

import logging
import uuid
import httpx

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from app.models.schemas import EmbedRequest, EmbedResponse
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Index Content (called by CMS triggerEmbedding hook) ──────

class IndexContentRequest(BaseModel):
    """Simplified request from Payload CMS hook."""
    contentId: str
    contentType: str
    operation: str = "update"  # create, update, delete


@router.post("/index-content")
async def index_content(body: IndexContentRequest, request: Request):
    """
    Called by the CMS triggerEmbedding hook when content is published.

    1. Fetches the full content from Payload CMS
    2. Extracts text from all text fields and blocks
    3. Chunks the text into 512-token segments
    4. Generates embeddings and stores in pgvector
    """
    embedding_service = request.app.state.embedding_service

    # Handle deletes
    if body.operation == "delete":
        deleted = await embedding_service.delete_by_source(body.contentId)
        return {"status": "deleted", "chunks_removed": deleted}

    # Fetch content from Payload CMS
    payload_url = settings.APP_SERVER_URL
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{payload_url}/{body.contentType}/{body.contentId}",
                params={"depth": 2},
            )
            if resp.status_code != 200:
                logger.warning(f"Could not fetch {body.contentType}/{body.contentId}: {resp.status_code}")
                return {"status": "skipped", "reason": f"CMS returned {resp.status_code}"}
            content = resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch content from CMS: {e}")
        raise HTTPException(status_code=502, detail="Could not reach CMS")

    # Extract text from content
    text_parts = _extract_text(content, body.contentType)
    full_text = "\n\n".join(text_parts)

    if not full_text.strip():
        return {"status": "skipped", "reason": "no text content found"}

    # Chunk the text (512 tokens ≈ 2000 chars, with 50-token overlap)
    chunks_data = _chunk_text(
        text=full_text,
        source_id=body.contentId,
        source_type=body.contentType,
        content=content,
        chunk_size=2000,
        overlap=200,
    )

    # Generate embeddings and store
    try:
        success, errors = await embedding_service.store_chunks(chunks_data)
        logger.info(
            f"Indexed {body.contentType}/{body.contentId}: "
            f"{success} chunks embedded, {len(errors)} errors"
        )
        return {
            "status": "indexed",
            "content_id": body.contentId,
            "content_type": body.contentType,
            "chunks_created": success,
            "errors": errors,
        }
    except Exception as e:
        logger.error(f"Embedding storage failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _extract_text(content: dict, content_type: str) -> list[str]:
    """Extract all text from a Payload document based on its type."""
    parts = []

    # Common text fields
    for field in ["title", "name", "summary", "description", "introduction", "content", "biography"]:
        if content.get(field) and isinstance(content[field], str):
            parts.append(content[field])

    # Rich text (Lexical JSON → plain text)
    for field in ["body", "richText", "fullText"]:
        val = content.get(field)
        if isinstance(val, dict) and val.get("root"):
            parts.append(_lexical_to_text(val))
        elif isinstance(val, str):
            parts.append(val)

    # Story blocks
    for block in content.get("storyBlocks", content.get("blocks", [])):
        if isinstance(block, dict):
            for bf in ["text", "content", "quote", "transcript", "caption"]:
                if block.get(bf) and isinstance(block[bf], str):
                    parts.append(block[bf])
                elif isinstance(block.get(bf), dict):
                    parts.append(_lexical_to_text(block[bf]))

    # Museum panels (embedded blocks)
    for block in content.get("blocks", []):
        if isinstance(block, dict) and block.get("content"):
            c = block["content"]
            if isinstance(c, dict) and c.get("text"):
                parts.append(c["text"] if isinstance(c["text"], str) else _lexical_to_text(c["text"]))

    # Documentary chapters
    for ch in content.get("chapters", []):
        if isinstance(ch, dict):
            for f in ["title", "description", "transcript"]:
                if ch.get(f) and isinstance(ch[f], str):
                    parts.append(ch[f])

    return [p for p in parts if p.strip()]


def _lexical_to_text(lexical: dict) -> str:
    """Recursively extract plain text from Lexical editor JSON."""
    if not isinstance(lexical, dict):
        return str(lexical) if lexical else ""

    parts = []
    if lexical.get("text"):
        parts.append(lexical["text"])

    for child in lexical.get("children", []):
        parts.append(_lexical_to_text(child))

    root = lexical.get("root")
    if root:
        parts.append(_lexical_to_text(root))

    return " ".join(parts).strip()


def _chunk_text(
    text: str,
    source_id: str,
    source_type: str,
    content: dict,
    chunk_size: int = 2000,
    overlap: int = 200,
) -> list[dict]:
    """Split text into overlapping chunks for embedding."""
    if len(text) <= chunk_size:
        return [{
            "chunk_id": f"{source_id}-0",
            "text": text,
            "source_id": source_id,
            "source_type": source_type,
            "language": content.get("language", "en"),
            "sensitivity": content.get("sensitivityLevel", "standard"),
            "location_id": _resolve_id(content.get("location")),
            "museum_id": _resolve_id(content.get("museum")),
            "route_id": _resolve_id(content.get("route")),
            "tags": content.get("tags", []),
        }]

    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end]

        # Try to break at a sentence boundary
        if end < len(text):
            last_period = chunk_text.rfind(". ")
            if last_period > chunk_size * 0.5:
                end = start + last_period + 2
                chunk_text = text[start:end]

        chunks.append({
            "chunk_id": f"{source_id}-{idx}",
            "text": chunk_text.strip(),
            "source_id": source_id,
            "source_type": source_type,
            "language": content.get("language", "en"),
            "sensitivity": content.get("sensitivityLevel", "standard"),
            "location_id": _resolve_id(content.get("location")),
            "museum_id": _resolve_id(content.get("museum")),
            "route_id": _resolve_id(content.get("route")),
            "tags": content.get("tags", []),
        })

        start = end - overlap
        idx += 1

    return chunks


def _resolve_id(value) -> str | None:
    """Resolve a Payload relation field to its ID string."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("id")
    return None


@router.post("/embed", response_model=EmbedResponse)
async def embed_content(body: EmbedRequest, request: Request):
    """
    Generate embeddings for content chunks and store in pgvector.

    Called by CMS webhook on content publish/update.
    Chunks should be pre-split by the CMS hook before calling this endpoint.
    """
    embedding_service = request.app.state.embedding_service

    chunks = [
        {
            "chunk_id": c.chunk_id,
            "text": c.text,
            "source_id": c.metadata.source_id,
            "source_type": c.metadata.source_type,
            "language": c.metadata.language,
            "sensitivity": c.metadata.sensitivity_level,
            "location_id": c.metadata.location_id,
            "museum_id": c.metadata.museum_id,
            "route_id": c.metadata.route_id,
            "tags": c.metadata.tags,
        }
        for c in body.chunks
    ]

    try:
        success, errors = await embedding_service.store_chunks(chunks)
        return EmbedResponse(
            embedded_count=success,
            failed_count=len(errors),
            errors=errors,
        )
    except Exception as e:
        logger.error(f"Embedding error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/embed/{source_id}")
async def delete_embeddings(source_id: str, request: Request):
    """
    Delete all embeddings for a source (when content is unpublished/deleted).
    """
    embedding_service = request.app.state.embedding_service

    try:
        deleted = await embedding_service.delete_by_source(source_id)
        return {"deleted_count": deleted, "source_id": source_id}
    except Exception as e:
        logger.error(f"Delete embeddings error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed/search")
async def search_embeddings(
    query: str,
    source_type: str | None = None,
    location_id: str | None = None,
    museum_id: str | None = None,
    limit: int = 10,
    request: Request = None,
):
    """
    Debug endpoint: search embeddings directly.
    Useful for testing retrieval quality.
    """
    embedding_service = request.app.state.embedding_service

    filters = {}
    if source_type:
        filters["source_type"] = source_type
    if location_id:
        filters["location_id"] = location_id
    if museum_id:
        filters["museum_id"] = museum_id

    results = await embedding_service.search(
        query=query,
        filters=filters,
        limit=limit,
    )

    return {
        "query": query,
        "results_count": len(results),
        "results": results,
    }
