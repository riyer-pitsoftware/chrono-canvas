from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.db.repositories.figures import FigureRepository
from chronocanvas.db.repositories.images import ImageRepository
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.db.repositories.validations import ValidationRepository


async def get_figure_repo(session: AsyncSession = None):
    return FigureRepository(session)


async def get_request_repo(session: AsyncSession = None):
    return RequestRepository(session)


async def get_image_repo(session: AsyncSession = None):
    return ImageRepository(session)


async def get_validation_repo(session: AsyncSession = None):
    return ValidationRepository(session)
