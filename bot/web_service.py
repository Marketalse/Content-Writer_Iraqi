"""Owner-preview application boundary around the existing writing engine.

No Telegram calls, second editorial loop, or public account support.
"""
import json
import math
from dataclasses import replace
from urllib.parse import urlsplit
from briefs import Brief
from content_layers import CATALOG, STRATEGIES
from layer_navigation import selected_brief
from pipeline import run_pipeline
from prompts import build_system_prompt
from quality import check
from delivery_policy import artifact_fingerprint
from output_layout import render_creator_copy
from reviewer import DIMENSIONS, GATES, Review
from diagnostics import failure_summary
from revision import Settings


def make_brief(strategy):
    if strategy not in STRATEGIES['story']:
        raise ValueError('invalid Story strategy')
    return selected_brief({'feature_id':'story','strategy_id':strategy,
                           'structure_id':CATALOG[strategy].flow},Brief(duration_seconds=30))


def request_context(topic, strategy, *, parent=None, instruction='', answer='', suggestion=None):
    """Keep source request immutable; continuations are bounded and explicit."""
    topic=topic.strip()
    if not topic or len(topic)>(8000 if parent else 4000):raise ValueError('invalid topic')
    brief=make_brief(strategy)
    context={'topic':topic,'strategy_id':strategy,'brief':brief.data(),'clarification_allowed':True}
    if parent:
        context=dict(parent['context'])
        brief=Brief(**{**context['brief'],'evidence':tuple(context['brief'].get('evidence',[]))})
        result=parent['result']
        if instruction:
            if result['state']!='accepted':raise ValueError('only approved scripts can be edited')
            brief=replace(brief,source_material=(
                'النص السابق مرجع للتحرير، مو مصدر إثبات لادعاءات جديدة. حافظ على الموضوع والصوت.\n'
                'النص السابق:\n'+result['copy']+'\nتعديل طلبه صاحب النص:\n'+instruction))
        elif answer:
            if result['state']!='clarification':raise ValueError('no pending clarification')
            context['topic']+='\nسؤال التوضيح: '+result['message']+'\nإجابة المستخدم: '+answer
            if len(context['topic'])>8000:raise ValueError('clarification context too long')
            context['clarification_allowed']=False
        elif suggestion is not None:
            choices=result.get('suggestions',[])
            if result['state'] not in ('blocked','needs_review') or not 0<=suggestion<len(choices):
                raise ValueError('invalid suggestion')
            context['topic']=choices[suggestion]['topic']
            # A new angle must not inherit unrelated instructions from a previous edit.
            brief=make_brief(context['strategy_id'])
            context['clarification_allowed']=True
        else:raise ValueError('select an action')
        context['brief']=brief.data()
    return context


def safe_sources(checked):
    sources=[]
    for item in checked.research.get('sources',[])[:12]:
        url=item.get('url','')
        parsed=urlsplit(url)
        if parsed.scheme in ('https','http') and parsed.hostname and not parsed.username and not parsed.password:
            sources.append(url)
    return sources


async def generate_context(context, *, runner=run_pipeline):
    brief=Brief(**{**context['brief'],'evidence':tuple(context['brief'].get('evidence',[]))})
    brief.validate_format('story')
    cfg=Settings.from_env()
    run=await runner('story',build_system_prompt('story',brief=brief),context['topic'],
        CATALOG[context['strategy_id']].instruction,brief=brief,settings=cfg,
        research=True,suggest_topics=True,clarification_allowed=context['clarification_allowed'])
    checked=run.checked
    result={'state':checked.status,'message':'','copy':'','score':None,'sources':[],
            'suggestions':[],'cost_usd':round(run.cost_usd,6),'calls':len(run.calls),
            'failure_code':checked.failure_code,'notices':[]}
    if any(t.get('fallback_reason')=='provider_credit_exhausted' for t in run.timings):
        result['notices'].append('رصيد المزوّد الأساسي غير كافي؛ استخدمنا البديل مع نفس فحوصات الجودة.')
    if checked.clarification:
        return result|{'state':'clarification','message':checked.clarification}
    if checked.status=='accepted':
        # Revalidate the exact artifact at the web delivery boundary, just as Telegram does.
        latest=checked.review_history[-1] if checked.review_history else {}
        scores=latest.get('scores',{})
        gates=latest.get('gates',{})
        valid=(not checked.refused and not checked.failures and not check('story',checked.text,
            story_mode=brief.story_mode,story_intent=brief.story_intent)
            and checked.story_mode==brief.story_mode and checked.story_intent==brief.story_intent
            and set(gates)==set(GATES) and all(v=='pass' for v in gates.values())
            and checked.reviewed_artifact_hash==artifact_fingerprint(checked))
        try:
            valid=(valid and set(scores)==set(DIMENSIONS) and all(type(v) in (int,float)
                and math.isfinite(v) and 0<=v<=10 for v in scores.values()))
            valid=valid and Review(scores,gates,()).acceptable('story',cfg.threshold,cfg.dimension_floor,brief.story_intent)
        except (KeyError,TypeError,ValueError):valid=False
        if not valid:
            return result|{'state':'blocked','failure_code':'invalid_structure',
                           'message':failure_summary({'failure_code':'invalid_structure'})}
        score=Review(scores,gates,()).score('story',brief.story_intent)
        return result|{'copy':render_creator_copy(checked.text,'story',brief.story_mode),
            'score':round(score,2),'sources':safe_sources(checked),'message':'النص اجتاز المراجعة.'}
    result['state']='needs_review' if checked.status=='needs_review' else 'blocked'
    result['message']=failure_summary({'failure_code':checked.failure_code,
        'review_history':checked.review_history,'structure_details':checked.structure_details})
    # Store only validated suggestion titles, never reasons/draft/provider payloads.
    if checked.topic_advice.get('status')=='ready':
        from topic_adviser import parse
        result['suggestions']=[{'topic':item['topic']} for item in parse(
            json.dumps({'suggestions':checked.topic_advice['suggestions']}))]
    return result
