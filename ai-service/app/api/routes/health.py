"""
Health API — Service health, GPU status, and model availability.
"""

import time
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

_start_time = time.monotonic()


@router.get("/health")
async def health_check(request: Request):
    """
    Comprehensive health check.
    Reports: service status, loaded models, GPU utilization, DB connectivity.
    """
    status = "healthy"
    models = {}
    gpu = None
    db_status = "disconnected"

    # Check LLM backend
    try:
        llm = request.app.state.llm_router
        model_list = await llm.client.models.list()
        for m in model_list.data:
            models[m.id] = {
                "loaded": True,
                "name": m.id,
                "backend": settings.LLM_BACKEND,
                "vram_mb": None,
            }
    except Exception as e:
        status = "degraded"
        logger.warning(f"LLM health check failed: {e}")

    # Check GPU (nvidia-smi)
    try:
        import subprocess

        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            gpu = {
                "name": parts[0],
                "vram_total_mb": float(parts[1]),
                "vram_used_mb": float(parts[2]),
                "utilization_percent": float(parts[3]),
                "temperature_c": float(parts[4]) if len(parts) > 4 else None,
            }
    except Exception:
        pass  # GPU monitoring is optional

    # Check database
    try:
        pool = request.app.state.embedding_service.db_pool
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "connected"
    except Exception as e:
        status = "degraded"
        logger.warning(f"Database health check failed: {e}")

    return {
        "status": status,
        "version": "1.0.0",
        "uptime_seconds": round(time.monotonic() - _start_time, 1),
        "models": models,
        "gpu": gpu,
        "database": db_status,
        "backend": settings.LLM_BACKEND,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ping")
async def ping():
    """Simple liveness probe."""
    return {"pong": True}
