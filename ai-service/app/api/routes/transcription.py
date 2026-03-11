"""
Transcription API — Audio to text using Faster-Whisper (self-hosted).

Runs on GPU as background jobs.
Supports: French, English, Kinyarwanda (with lower accuracy).
"""

import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import TranscribeRequest, TranscribeResponse
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Lazy-loaded Whisper model
_whisper_model = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        logger.info(f"Loading Whisper model: {settings.WHISPER_MODEL}")
        _whisper_model = WhisperModel(
            settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
        logger.info("Whisper model loaded")
    return _whisper_model


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(body: TranscribeRequest):
    """
    Transcribe an audio file using Faster-Whisper.

    The file must exist on the server filesystem (uploaded via CMS).
    Intended for background processing — not real-time.
    """
    import os

    if not os.path.exists(body.file_path):
        raise HTTPException(status_code=404, detail=f"Audio file not found: {body.file_path}")

    try:
        model = _get_whisper()

        segments, info = model.transcribe(
            body.file_path,
            language=body.language_hint,
            beam_size=5,
            vad_filter=True,  # Voice activity detection for cleaner output
        )

        # Collect all segments
        transcript_parts = []
        segment_list = []

        for segment in segments:
            transcript_parts.append(segment.text)
            segment_list.append({
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
                "language": info.language,
            })

        full_transcript = " ".join(transcript_parts).strip()

        return TranscribeResponse(
            transcript=full_transcript,
            language_detected=info.language,
            confidence=round(info.language_probability, 3),
            duration_seconds=round(info.duration, 2),
            segments=segment_list,
            chunks_embedded=0,  # Embedding happens in a separate step
        )

    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
