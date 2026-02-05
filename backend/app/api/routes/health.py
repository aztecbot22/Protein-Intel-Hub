from fastapi import APIRouter

from app.services.http_client import cache_stats


router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/health/metrics")
def metrics() -> dict:
    return {"status": "ok", "cache": cache_stats()}
