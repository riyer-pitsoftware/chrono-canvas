from fastapi import APIRouter

from chronocanvas.api.routes import (
    admin,
    agents,
    conversation,
    eval_viewer,
    export,
    faces,
    figures,
    generation,
    health,
    memory,
    reference_images,
    timeline,
    validation,
    voice,
)

api_router = APIRouter(prefix="/api")

api_router.include_router(health.router)
api_router.include_router(figures.router)
api_router.include_router(timeline.router)
api_router.include_router(faces.router)
api_router.include_router(generation.router)
api_router.include_router(validation.router)
api_router.include_router(export.router)
api_router.include_router(agents.router)
api_router.include_router(admin.router)
api_router.include_router(memory.router)
api_router.include_router(eval_viewer.router)
api_router.include_router(reference_images.router)
api_router.include_router(voice.router)
api_router.include_router(conversation.router)
