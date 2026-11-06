"""Three-step pipeline: Analyst -> Writer -> Checker.

Analyst (Haiku): finds the audience pain and one objection for the topic and angle.
Writer (Sonnet): writes the format, with the analyst notes and the chosen angle.
Checker: the format validator (quality.py), then a Dialect Guard pass (Haiku).
Costs about 3 to 4 model calls per post; every call is recorded for cost tracking.
"""

from dataclasses import dataclass, field

from llm import FAST_MODEL, Result, generate
from quality import Checked, check, generate_checked, split_owner_note

ANALYST_SYSTEM = """أنت محلل جمهور. اقرأ الموضوع والزاوية، وأعطِ بالعراقي ثلاث نقاط قصيرة فقط:
- ألم الجمهور الأساسي
- اعتراض واحد يمنعهم يتفاعلون أو يشترون
- سؤال واحد يفتح فضولهم
لا مقدمات ولا خاتمة."""

DIALECT_SYSTEM = """أنت حارس اللهجة العراقية. راجع النص:
- لازم يكون عراقي (ليس مصري أو خليجي أو شامي)، بدون فصحى ثقيلة.
- الكلمات العراقية من القاموس إذا متوفرة.
إذا كل شي تمام اكتب فقط: OK
إذا فيه مشكلة اكتب كل مشكلة بسطر يبدأ بـ - مع البديل المقترح، بدون شرح آخر."""


@dataclass
class Run:
    checked: Checked
    calls: list[Result] = field(default_factory=list)
    notes: str = ""

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)


async def run_pipeline(fmt: str, system: str, topic: str, angle: str) -> Run:
    calls: list[Result] = []

    analyst = await generate(ANALYST_SYSTEM, f"الموضوع: {topic}\nالزاوية: {angle}",
                             model=FAST_MODEL, max_tokens=400)
    calls.append(analyst)
    notes = "" if analyst.refused else analyst.text

    checked = await generate_checked(fmt, system, topic, angle, notes)
    calls += checked.calls

    if not checked.failures and checked.text:
        dialect = await generate(DIALECT_SYSTEM, checked.text, model=FAST_MODEL, max_tokens=300)
        calls.append(dialect)
        issues = [l.strip() for l in dialect.text.splitlines() if l.strip().startswith("-")]
        if issues:
            feedback = (
                f"الموضوع: {topic}\nالزاوية: {angle}\n"
                "النسخة السابقة فيها مشاكل لهجة، صححها وأعد الرد كامل بنفس الشكل:\n"
                + "\n".join(issues)
            )
            rewrite = await generate(system, feedback)
            calls.append(rewrite)
            content, note = split_owner_note(rewrite.text)
            remaining = check(fmt, content)
            failures = remaining + (["dialect: " + " ".join(issues)] if remaining else [])
            checked = Checked(content, rewrite.provider, False, failures,
                              checked.attempts + 1, note or checked.owner_note, calls)
            return Run(checked, calls, notes)

    checked.calls = calls
    return Run(checked, calls, notes)
