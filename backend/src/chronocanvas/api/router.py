from fastapi import APIRouter

from chronocanvas.api.routes import agents, export, faces, figures, generation, health, validation

api_router = APIRouter(prefix="/api")

api_router.include_router(health.router)
api_router.include_router(figures.router)
api_router.include_router(faces.router)
api_router.include_router(generation.router)
api_router.include_router(validation.router)
api_router.include_router(export.router)
api_router.include_router(agents.router)
