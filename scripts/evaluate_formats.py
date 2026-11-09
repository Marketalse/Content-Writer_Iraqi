"""Shared-topic evaluation. Offline mode proves orchestration/contracts, NOT creative quality.

python scripts/evaluate_formats.py --mode offline
python scripts/evaluate_formats.py --mode live --limit 12 --max-usd 3
Live mode requires configured credentials and never sends Telegram messages or publishes.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
from briefs import Brief
from llm import Result
from pipeline import run_pipeline
from prompts import build_system_prompt
from quality import check
from reviewer import DIMENSIONS, GATES

FIXTURES = Path(__file__).resolve().parents[1] / 'tests/fixtures/cross_format_drafts.json'


async def evaluate(mode='offline', limit=39, max_usd=3.0):
    if mode not in ('offline', 'live') or not 1 <= limit <= 39 or not 0 < max_usd <= 20:
        raise ValueError('invalid evaluation limits')
    if mode == 'live' and not os.getenv('ANTHROPIC_API_KEY'):
        raise ValueError('Live evaluation unavailable: configure ANTHROPIC_API_KEY in environment settings.')
    cases = json.loads(FIXTURES.read_text(encoding='utf-8'))[:limit]
    results = []; cost = 0.0
    for case in cases:
        if mode == 'live' and cost + .25 > max_usd:
            break
        async def fake(system, user, **kwargs):
            if system.startswith('Analyze the brief'):
                text = json.dumps({'audience_need':'Iraqi business audience','objection':'',
                    'purpose':'education','framework':'none','logic_chain':['explain the idea'],
                    'missing_information':'','clarification_question':''})
            elif system.startswith('You are an independent'):
                text = json.dumps({'scores':dict.fromkeys(DIMENSIONS,8),
                                   'gates':dict.fromkeys(GATES,'pass'),'issues':[]})
            else:
                text = case['text']
            return Result(text,'mock')
        brief = Brief(audience='أصحاب المشاريع والمسوقين بالعراق', purpose='educate',
                      takeaway=case['topic'], source_material='موضوع عام بدون إحصائيات أو نتائج شخصية مقدمة.')
        args = (case['format'], build_system_prompt(case['format'], brief=brief), case['topic'], 'tip')
        if mode == 'offline':
            with patch('revision.generate', fake):
                run = await run_pipeline(*args, brief=brief)
        else:
            run = await run_pipeline(*args, brief=brief)
        cost += run.cost_usd
        usage_known = all(c.usage_known for c in run.calls) and all(t['status'] == 'ok' for t in run.timings)
        results.append({'topic':case['topic'],'format':case['format'], 'status':run.checked.status,
            'structural_issues':check(case['format'],run.checked.text) if run.checked.text else ['no draft'],
            'logical_calls':len(run.calls),'elapsed_ms':run.elapsed_ms,'estimated_cost_usd':run.cost_usd,
            'usage_known':usage_known, 'input_tokens':run.input_tokens,'output_tokens':run.output_tokens,
            'copy':run.checked.text, 'failures':run.checked.failures, 'review_history':run.checked.review_history,
            'human_review':{'native_character':None,'coherence':None,'iraqi_voice':None,
                            'promise_delivery':None,'evidence':None,'appropriate_action':None}})
        if mode == 'live' and not usage_known:
            break
    return {'kind':'mocked_contract_evaluation' if mode=='offline' else 'live_drafts_pending_human_review',
            'semantic_quality_verified':False,'cases_requested':len(cases),'cases_run':len(results),
            'contract_passes':sum(not row['structural_issues'] for row in results),
            'estimated_cost_usd':round(cost,6),'results':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('offline','live'),default='offline')
    parser.add_argument('--limit',type=int,default=39)
    parser.add_argument('--max-usd',type=float,default=3)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        report=asyncio.run(evaluate(args.mode,args.limit,args.max_usd))
    except ValueError as exc:
        parser.exit(2,str(exc)+'\n')
    text=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(text,encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='results'}))
    else:
        print(text)


if __name__=='__main__':
    main()
