from typing import Any

from chronocanvas.redis_client import publish_progress


class ProgressPublisher:
    """Thin wrapper around Redis pub/sub for pipeline progress events."""

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        await publish_progress(channel, payload)

    async def publish_agent(self, channel: str, agent: str, status: Any) -> None:
        await self.publish(channel, {
            "status": status,
            "agent": agent,
            "message": f"Running {agent}...",
        })

    async def publish_terminal(self, channel: str, *, failed: bool) -> None:
        await self.publish(channel, {
            "status": "failed" if failed else "completed",
            "message": "Generation complete",
        })
