import pytest
from httpx import ASGITransport, AsyncClient

from chronocanvas.main import app


@pytest.mark.asyncio
async def test_list_agents():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        agent_names = [a["name"] for a in data["agents"]]
        assert "orchestrator" in agent_names
        assert "extraction" in agent_names
        assert "research" in agent_names
        assert "validation" in agent_names
        assert "export" in agent_names


@pytest.mark.asyncio
async def test_cost_summary():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/agents/costs")
        assert response.status_code == 200
        data = response.json()
        assert "total_cost" in data
        assert "total_tokens" in data
        assert "num_calls" in data
