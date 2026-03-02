from fastapi import APIRouter

from chronocanvas.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "chronocanvas",
        "hackathon_mode": settings.hackathon_mode,
    }
