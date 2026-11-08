"""Offline orchestration benchmark, NOT a live model latency/cost benchmark.

Run: python scripts/benchmark_quality.py
Uses a deterministic asynchronous fake transport at 0ms and 10ms per logical call.
"""
import asyncio
import json
import statistics
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
from llm import Result
from pipeline import run_pipeline
from reviewer import DIMENSIONS, GATES
from revision import Settings


async def scenario(delay, count=40, analyst=True):
    async def fake(system, user, **kwargs):
        await asyncio.sleep(delay)
        if system.startswith('Analyze the brief'):
            text = json.dumps({'audience_need': 'useful observation', 'objection': '',
                'purpose': 'conversation', 'framework': 'none', 'logic_chain': ['moment', 'reply'],
                'missing_information': '', 'clarification_question': ''})
        elif system.startswith('You are an independent'):
            text = json.dumps({'scores': dict.fromkeys(DIMENSIONS, 8),
                               'gates': dict.fromkeys(GATES, 'pass'), 'issues': []})
        else:
            text = 'STORY: هسه خل نراجع شغل التسويق.\nINTERACTION: شنو رأيك؟'
        return Result(text, 'mock', usage_known=True)
    with patch('revision.generate', fake):
        runs = [await run_pipeline('story', 'voice', 'التسويق', 'tip', settings=Settings(analyst=analyst))
                for _ in range(count)]
    times = sorted(r.elapsed_ms for r in runs)
    assert all(r.checked.status == 'accepted' and len(r.calls) == (3 if analyst else 2) for r in runs)
    return {'samples': count, 'fake_call_delay_ms': delay * 1000,
            'p50_ms': round(statistics.median(times), 3),
            'p95_ms': times[int(count * .95) - 1], 'logical_calls_per_run': 3 if analyst else 2,
            'mean_input_chars_per_run': round(statistics.mean(
                sum(t['input_chars'] for t in r.timings) for r in runs), 1)}


async def main():
    print(json.dumps({'kind': 'offline_mock_orchestration',
                      'scenarios': [await scenario(0), await scenario(.01)]}, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
