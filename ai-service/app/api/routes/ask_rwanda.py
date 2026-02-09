"""
Ask Rwanda API — The main RAG-powered chat endpoint.

Supports both streaming (SSE) and non-streaming responses.
"""

import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

from app.services.rag_pipeline import RAGPipeline
from app.models.schemas import AskRwandaRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ask")
@router.post("/ask-rwanda")
async def ask_rwanda(body: AskRwandaRequest, request: Request):
    """
    Ask Rwanda AI assistant.

    Accepts a question and returns an AI-generated response
    grounded in Muraho Rwanda's content library.

    Supports streaming (default) and non-streaming modes.
    """
    # Build the RAG pipeline from app-level services
    pipeline = RAGPipeline(
        llm_router=request.app.state.llm_router,
        embedding_service=request.app.state.embedding_service,
    )

    context = {}
    if body.context:
        context = body.context.model_dump(exclude_none=True)

    if body.stream:
        # Streaming response via Server-Sent Events
        async def event_stream():
            try:
                async for token in pipeline.process_query_stream(
                    query=body.query,
                    language=body.language,
                    mode=body.mode,
                    context=context,
                    access_tier=body.access_tier,
                ):
                    yield f"data: {token}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: [ERROR] An error occurred while generating the response.\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )
    else:
        # Non-streaming — return full response
        try:
            result = await pipeline.process_query(
                query=body.query,
                language=body.language,
                mode=body.mode,
                context=context,
                access_tier=body.access_tier,
            )
            return result
        except Exception as e:
            logger.error(f"Ask Rwanda error: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="An error occurred processing your question. Please try again.",
            )


@router.post("/ask-rwanda/feedback")
async def submit_feedback(
    query_id: str,
    helpful: bool,
    comment: str | None = None,
):
    """
    User feedback on AI responses.
    Used to improve the system and flag problematic responses.
    """
    logger.info(f"Feedback: query={query_id}, helpful={helpful}, comment={comment}")
    # TODO: Store in database for analysis
    return {"status": "received", "query_id": query_id}
