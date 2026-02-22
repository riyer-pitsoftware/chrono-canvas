from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chronocanvas.api.schemas.figures import FigureResponse
from chronocanvas.db.engine import get_session
from chronocanvas.db.models.figure import Figure

router = APIRouter(prefix="/timeline", tags=["timeline"])


class TimelineFigureListResponse(BaseModel):
    items: list[FigureResponse]
    total: int
    year_min: int
    year_max: int


@router.get("/figures", response_model=TimelineFigureListResponse)
async def list_timeline_figures(
    year_min: int = -500,
    year_max: int = 1700,
    limit: int = 300,
    session: AsyncSession = Depends(get_session),
):
    """Return figures sorted by birth_year within the given year range."""
    stmt = (
        select(Figure)
        .where(Figure.birth_year.is_not(None))
        .where(Figure.birth_year >= year_min)
        .where(Figure.birth_year <= year_max)
        .order_by(Figure.birth_year)
        .limit(limit)
    )
    result = await session.execute(stmt)
    figures = result.scalars().all()
    items = [FigureResponse.model_validate(f) for f in figures]
    return TimelineFigureListResponse(
        items=items,
        total=len(items),
        year_min=year_min,
        year_max=year_max,
    )
