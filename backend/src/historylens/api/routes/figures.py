import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from historylens.api.schemas.figures import (
    FigureCreate,
    FigureListResponse,
    FigureResponse,
    FigureUpdate,
)
from historylens.db.engine import get_session
from historylens.db.repositories.figures import FigureRepository

router = APIRouter(prefix="/figures", tags=["figures"])


@router.get("", response_model=FigureListResponse)
async def list_figures(
    offset: int = 0,
    limit: int = 50,
    search: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    repo = FigureRepository(session)
    if search:
        items = await repo.search(search, offset=offset, limit=limit)
    else:
        items = await repo.list(offset=offset, limit=limit)
    total = await repo.count()
    return FigureListResponse(
        items=[FigureResponse.model_validate(f) for f in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{figure_id}", response_model=FigureResponse)
async def get_figure(figure_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    repo = FigureRepository(session)
    figure = await repo.get(figure_id)
    if not figure:
        raise HTTPException(status_code=404, detail="Figure not found")
    return FigureResponse.model_validate(figure)


@router.post("", response_model=FigureResponse, status_code=201)
async def create_figure(data: FigureCreate, session: AsyncSession = Depends(get_session)):
    repo = FigureRepository(session)
    figure = await repo.create(**data.model_dump(exclude_none=True))
    await session.commit()
    return FigureResponse.model_validate(figure)


@router.put("/{figure_id}", response_model=FigureResponse)
async def update_figure(
    figure_id: uuid.UUID,
    data: FigureUpdate,
    session: AsyncSession = Depends(get_session),
):
    repo = FigureRepository(session)
    figure = await repo.update(figure_id, **data.model_dump(exclude_none=True))
    if not figure:
        raise HTTPException(status_code=404, detail="Figure not found")
    await session.commit()
    return FigureResponse.model_validate(figure)


@router.delete("/{figure_id}", status_code=204)
async def delete_figure(figure_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    repo = FigureRepository(session)
    deleted = await repo.delete(figure_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Figure not found")
    await session.commit()
