import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CostEntry:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    task_type: str


@dataclass
class CostTracker:
    entries: list[CostEntry] = field(default_factory=list)

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        task_type: str = "general",
    ) -> None:
        entry = CostEntry(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            task_type=task_type,
        )
        self.entries.append(entry)
        logger.info(f"LLM cost: {provider}/{model} ${cost:.6f} ({task_type})")

    @property
    def total_cost(self) -> float:
        return sum(e.cost for e in self.entries)

    @property
    def total_tokens(self) -> int:
        return sum(e.input_tokens + e.output_tokens for e in self.entries)

    def summary(self) -> dict:
        by_provider: dict[str, float] = {}
        for e in self.entries:
            by_provider[e.provider] = by_provider.get(e.provider, 0) + e.cost
        return {
            "total_cost": self.total_cost,
            "total_tokens": self.total_tokens,
            "by_provider": by_provider,
            "num_calls": len(self.entries),
        }
