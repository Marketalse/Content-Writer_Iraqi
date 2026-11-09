"""Reproduce the installment Reel demo path; offline reviews are synthetic.

python scripts/test_topic.py --mode offline --no-format-repair
python scripts/test_topic.py --mode offline
python scripts/test_topic.py --mode live --output /tmp/installment-live.json
Live mode uses configured environment credentials, max five logical calls and the
normal per-run budgets. It never contacts Telegram or publishes content.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bot'))
from briefs import Brief
from llm import Result
from pipeline import run_pipeline
from prompts import build_system_prompt
from quality import check
from reviewer import DIMENSIONS, GATES
from revision import Settings

FIXTURE=Path(__file__).resolve().parents[1]/'tests/fixtures/installment_reel_demo.json'


async def evaluate(mode='offline',repair_format=True,max_usd=.25):
    if mode not in ('offline','live'):
        raise ValueError('invalid topic test mode')
    if mode=='live' and not os.getenv('ANTHROPIC_API_KEY'):
        raise ValueError('Live test needs ANTHROPIC_API_KEY in workspace secrets; never paste it in chat.')
    cfg=Settings(repair_format=repair_format,max_cost_usd=max_usd)
    case=json.loads(FIXTURE.read_text())
    brief=Brief(audience='أصحاب المحلات والمشاريع بالعراق',purpose='educate',
                structure_id=case['structure_id'],source_material=case['source_material'])
    review_count=0
    async def fake(system,user,**kwargs):
        nonlocal review_count
        data=json.loads(user)
        if system.startswith('Analyze the brief'):
            text=json.dumps({'audience_need':'reduce installment tracking mistakes','objection':'tracking is not guaranteed collection',
                'purpose':'education','framework':'none','logic_chain':['illustrative tracker','visible update','risk limitation'],
                'missing_information':'','clarification_question':''})
        elif system.startswith('You are an independent'):
            review_count+=1
            gates=dict.fromkeys(GATES,'pass')
            if review_count==1:gates['format_identity']='fail'
            text=json.dumps({'scores':dict.fromkeys(DIMENSIONS,6 if review_count==1 else 8),
                'gates':gates,'issues':case['issues'] if review_count==1 else []})
        elif 'current_sections' in data:
            text=json.dumps(case['patch'])
        else:text=case['initial_draft']
        return Result(text,'mock',stop_reason='end_turn',structured_output='output_schema' in kwargs)
    args=(case['format'],build_system_prompt(case['format'],brief=brief),case['topic'],'practical educational illustration')
    if mode=='offline':
        with patch('revision.generate',fake):run=await run_pipeline(*args,brief=brief,settings=cfg)
    else:run=await run_pipeline(*args,brief=brief,settings=cfg)
    return {'kind':'synthetic_protocol_replay' if mode=='offline' else 'live_model_test_pending_human_review',
        'semantic_quality_verified':False,'topic':case['topic'],'format':case['format'],'structure_id':case['structure_id'],
        'repair_format':repair_format,'status':run.checked.status,'failure_code':run.checked.failure_code,
        'failures':run.checked.failures,'manual_review_ready':run.checked.manual_review_ready,
        'calls':len(run.calls),'elapsed_ms':run.elapsed_ms,'estimated_cost_usd':run.cost_usd,
        'input_tokens':run.input_tokens,'output_tokens':run.output_tokens,'stage_timings':run.timings,
        'structural_issues':check(case['format'],run.checked.text) if run.checked.text else ['no draft'],
        'review_history':run.checked.review_history,'copy':run.checked.text}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('offline','live'),default='offline')
    parser.add_argument('--no-format-repair',action='store_true')
    parser.add_argument('--max-usd',type=float,default=.25)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:report=asyncio.run(evaluate(args.mode,not args.no_format_repair,args.max_usd))
    except ValueError as exc:parser.exit(2,str(exc)+'\n')
    rendered=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(rendered+'\n')
        print(json.dumps({key:report[key] for key in ('kind','status','failure_code','calls','estimated_cost_usd','semantic_quality_verified')}))
    else:print(rendered)


if __name__=='__main__':main()
