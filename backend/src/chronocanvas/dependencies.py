from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.db.engine import get_session
from chronocanvas.db.repositories.figures import FigureRepository
from chronocanvas.db.repositories.images import ImageRepository
from chronocanvas.db.repositories.requests import RequestRepository
from chronocanvas.db.repositories.validations import ValidationRepository


async def get_figure_repo(session: AsyncSession = Depends(get_session)):
    return FigureRepository(session)


async def get_request_repo(session: AsyncSession = Depends(get_session)):
    return RequestRepository(session)


async def get_image_repo(session: AsyncSession = Depends(get_session)):
    return ImageRepository(session)


async def get_validation_repo(session: AsyncSession = Depends(get_session)):
    return ValidationRepository(session)
