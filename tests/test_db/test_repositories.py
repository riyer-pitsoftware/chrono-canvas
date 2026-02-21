import pytest

from chronocanvas.db.repositories.figures import FigureRepository
from chronocanvas.db.repositories.requests import RequestRepository


@pytest.mark.asyncio
async def test_create_and_get_figure(db_session):
    repo = FigureRepository(db_session)
    figure = await repo.create(
        name="Test Figure",
        birth_year=1500,
        death_year=1560,
        nationality="Italian",
        occupation="Artist",
    )
    await db_session.flush()

    assert figure.id is not None
    assert figure.name == "Test Figure"

    fetched = await repo.get(figure.id)
    assert fetched is not None
    assert fetched.name == "Test Figure"


@pytest.mark.asyncio
async def test_list_figures(db_session):
    repo = FigureRepository(db_session)
    await repo.create(name="Figure A", nationality="Greek")
    await repo.create(name="Figure B", nationality="Roman")
    await db_session.flush()

    figures = await repo.list()
    assert len(figures) >= 2


@pytest.mark.asyncio
async def test_search_figures(db_session):
    repo = FigureRepository(db_session)
    await repo.create(name="Cleopatra VII", nationality="Egyptian")
    await repo.create(name="Julius Caesar", nationality="Roman")
    await db_session.flush()

    results = await repo.search("Cleopatra")
    assert len(results) == 1
    assert results[0].name == "Cleopatra VII"


@pytest.mark.asyncio
async def test_update_figure(db_session):
    repo = FigureRepository(db_session)
    figure = await repo.create(name="Old Name")
    await db_session.flush()

    updated = await repo.update(figure.id, name="New Name")
    assert updated is not None
    assert updated.name == "New Name"


@pytest.mark.asyncio
async def test_delete_figure(db_session):
    repo = FigureRepository(db_session)
    figure = await repo.create(name="To Delete")
    await db_session.flush()

    deleted = await repo.delete(figure.id)
    assert deleted is True

    fetched = await repo.get(figure.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_create_generation_request(db_session):
    repo = RequestRepository(db_session)
    request = await repo.create(
        input_text="Generate a portrait of Napoleon",
        status="pending",
    )
    await db_session.flush()

    assert request.id is not None
    assert request.input_text == "Generate a portrait of Napoleon"
    assert request.status == "pending"
