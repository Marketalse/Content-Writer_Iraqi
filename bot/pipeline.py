"""Platform-aware analyst -> writer -> independent review -> bounded section revision."""
from dataclasses import dataclass, field
from time import monotonic

from llm import Result
from quality import Checked
from revision import Settings, execute


@dataclass
class Run:
    checked: Checked
    calls: list[Result] = field(default_factory=list)
    notes: str = ''
    elapsed_ms: float = 0.0
    timings: list[dict] = field(default_factory=list)

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)


async def run_pipeline(fmt: str, system: str, topic: str, angle: str,
                       *, settings: Settings | None = None,
                       verified_facts: tuple[tuple[str, str], ...] = ()) -> Run:
    start = monotonic()
    checked, session, notes = await execute(fmt, system, topic, angle, settings, verified_facts)
    return Run(checked, session.calls, notes, round((monotonic() - start) * 1000, 2), session.timings)
