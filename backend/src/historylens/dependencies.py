from sqlalchemy.ext.asyncio import AsyncSession

from historylens.db.engine import get_session
from historylens.db.repositories.figures import FigureRepository
from historylens.db.repositories.images import ImageRepository
from historylens.db.repositories.requests import RequestRepository
from historylens.db.repositories.validations import ValidationRepository


async def get_figure_repo(session: AsyncSession = None):
    return FigureRepository(session)


async def get_request_repo(session: AsyncSession = None):
    return RequestRepository(session)


async def get_image_repo(session: AsyncSession = None):
    return ImageRepository(session)


async def get_validation_repo(session: AsyncSession = None):
    return ValidationRepository(session)
