"""
TTS API — Self-hosted text-to-speech using Piper.
Fallback option for when ElevenLabs is not needed or for Kinyarwanda.
"""

import logging
import subprocess
import tempfile
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


class TTSRequest(BaseModel):
    text: str = Field(..., max_length=5000)
    language: str = Field(default="en", description="en, fr, or rw")
    voice: str | None = Field(default=None, description="Voice model name")


# Piper voice models per language
PIPER_VOICES = {
    "en": "en_US-lessac-medium",
    "fr": "fr_FR-siwis-medium",
    "rw": "en_US-lessac-medium",  # Fallback — no Kinyarwanda Piper model yet
}


@router.post("/tts")
async def text_to_speech(body: TTSRequest):
    """
    Generate speech from text using self-hosted Piper TTS.
    Returns raw MP3 audio bytes.
    """
    voice = body.voice or PIPER_VOICES.get(body.language, PIPER_VOICES["en"])

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        # Run Piper CLI
        process = subprocess.run(
            [
                "piper",
                "--model", voice,
                "--output_file", tmp_path,
            ],
            input=body.text,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if process.returncode != 0:
            logger.error(f"Piper TTS error: {process.stderr}")
            raise HTTPException(status_code=500, detail="TTS generation failed")

        # Convert WAV to MP3 using ffmpeg
        mp3_path = tmp_path.replace(".wav", ".mp3")
        subprocess.run(
            ["ffmpeg", "-i", tmp_path, "-codec:a", "libmp3lame", "-qscale:a", "4", mp3_path, "-y"],
            capture_output=True,
            timeout=30,
        )

        with open(mp3_path, "rb") as f:
            audio_data = f.read()

        # Cleanup
        for p in [tmp_path, mp3_path]:
            try:
                os.unlink(p)
            except:
                pass

        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={"Content-Length": str(len(audio_data))},
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="TTS generation timed out")
    except FileNotFoundError:
        # Piper not installed — return 503
        raise HTTPException(
            status_code=503,
            detail="Self-hosted TTS not available. Install Piper: pip install piper-tts",
        )
