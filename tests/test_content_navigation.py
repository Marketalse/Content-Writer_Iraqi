"""Family/platform routing, selected narratives and LinkedIn document regressions."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import bot as app
from briefs import Brief, parse_brief
from content_choices import FAMILIES, STRUCTURES, get_structure, structure_prompt
from platform_intelligence import LEGACY_FORMATS, PROFILES
from prompts import FORMATS, build_system_prompt
from quality import check
from revision import Settings
from pipeline import run_pipeline
from reviewer import DIMENSIONS, GATES
from llm import Result
from research_fixtures import researched, routed


def update(data='', text='الفرق بين التسويق والمبيعات'):
    status = SimpleNamespace(delete=AsyncMock(), edit_text=AsyncMock())
    return SimpleNamespace(effective_chat=SimpleNamespace(id=123),
        callback_query=SimpleNamespace(data=data, answer=AsyncMock(), edit_message_text=AsyncMock()),
        message=SimpleNamespace(text=text, reply_text=AsyncMock(return_value=status)))


def callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


class RegistryTests(unittest.TestCase):
    def test_all_profiles_have_three_choices_and_all_menu_formats_are_reachable(self):
        self.assertEqual(set(STRUCTURES), set(PROFILES))
        self.assertEqual({k for _, keys in FAMILIES.values() for k in keys}, set(FORMATS))
        for fmt, rows in STRUCTURES.items():
            self.assertEqual(len(rows), 3)
            for item in rows:
                brief = Brief(structure_id=item.id)
                brief.validate_format(fmt)
                self.assertIn(item.instruction, build_system_prompt(fmt, brief=brief))
                self.assertLessEqual(len(f'str:{fmt}:{item.id}'.encode()), 64)
        self.assertEqual(get_structure('carousel','guide'), get_structure('instagram_carousel','guide'))

    def test_invalid_or_cross_format_choice_rejected(self):
        for fmt, choice in [('story','playbook'),('linkedin_carousel','pov'),('reel','unknown')]:
            with self.assertRaises(ValueError):
                Brief(structure_id=choice).validate_format(fmt)
        with self.assertRaises(ValueError):
            parse_brief('{"structure_id":42}')

    def test_linkedin_document_has_native_contract_and_rejects_other_layouts(self):
        text = '\n'.join([f'SLIDE {i}: هاي فكرة مهنية تساعدنا نرتب القرار ونناقش الخيارات ويا الفريق.' for i in range(1,5)]
                         + ['CAPTION: سياق مهني للنقاش.', 'CTA: شنو المعيار الأهم إلك؟'])
        self.assertEqual(check('linkedin_carousel',text), [])
        self.assertTrue(check('linkedin_carousel',text.replace('SLIDE 2:','SLIDE 3:')))
        self.assertTrue(check('linkedin_carousel',text.replace(text.splitlines()[3],'SLIDE 4:')))
        self.assertTrue(check('linkedin_carousel',text.replace('CAPTION: سياق مهني للنقاش.', 'CAPTION:')))
        self.assertTrue(check('linkedin_carousel','INSIGHT: فكرة\nBODY: شرح\nDISCUSSION: سؤال؟'))
        self.assertIn('not a carousel ad',build_system_prompt('linkedin_carousel'))


class NavigationTests(unittest.IsolatedAsyncioTestCase):
    async def choose(self, ctx, handler, data):
        upd = update(data)
        with patch.object(app, '_allowed_chat', return_value=True):
            await handler(upd, ctx)
        return upd

    async def test_start_resets_selection_and_shows_families(self):
        upd=update(); ctx=SimpleNamespace(chat_data={'format':'story','structure_id':'moment','pending_clarification':{}})
        with patch.object(app,'_allowed_chat',return_value=True):
            await app.cmd_start(upd,ctx)
        self.assertFalse(ctx.chat_data)
        self.assertEqual(callbacks(upd.message.reply_text.call_args.kwargs['reply_markup']), ['ly:f:'+key for key in ('post','story','reel','live')]+['bank:home','ly:legacy'])

    async def test_every_family_platform_route_requires_structure_before_topic(self):
        for family, (_, formats) in FAMILIES.items():
            for fmt in formats:
                ctx=SimpleNamespace(chat_data={})
                upd=await self.choose(ctx, app.on_family_chosen, 'fam:'+family)
                menu=callbacks(upd.callback_query.edit_message_text.call_args.kwargs['reply_markup'])
                self.assertEqual(set(menu),{'fmt:'+key for key in formats}|{'fam:root'})
                await self.choose(ctx,app.on_format_chosen,'fmt:'+fmt)
                angle='story_educational' if fmt in ('story','tiktok_story') else 'tip'
                upd=await self.choose(ctx,app.on_angle_chosen,f'pick:{fmt}:{angle}')
                self.assertEqual(ctx.chat_data['menu_stage'],'structure')
                menu=callbacks(upd.callback_query.edit_message_text.call_args.kwargs['reply_markup'])
                self.assertEqual(len([key for key in menu if key.startswith('str:')]),3)
                # Text cannot trigger a model or quota charge before structure selection.
                text=update()
                with patch.object(app,'_allowed_chat',return_value=True), patch.object(app,'run_pipeline',AsyncMock()) as model, patch.object(app,'pilot_check') as quota:
                    await app.on_text(text,ctx)
                model.assert_not_awaited(); quota.assert_not_called()
                await self.choose(ctx,app.on_structure_chosen,menu[0])
                self.assertEqual(ctx.chat_data['menu_stage'],'topic')
                self.assertEqual(ctx.chat_data['content_brief'].structure_id,menu[0].split(':')[-1])

    async def test_stale_cross_platform_callbacks_and_unauthorized_chats(self):
        ctx=SimpleNamespace(chat_data={'family':'story','menu_stage':'platform'})
        upd=await self.choose(ctx,app.on_format_chosen,'fmt:linkedin_article')
        upd.callback_query.edit_message_text.assert_not_awaited()
        await self.choose(ctx,app.on_format_chosen,'fmt:story')
        upd=await self.choose(ctx,app.on_angle_chosen,'pick:tiktok_story:story_educational')
        upd.callback_query.edit_message_text.assert_not_awaited()
        upd=await self.choose(ctx,app.on_angle_chosen,'ang:tip')
        upd.callback_query.edit_message_text.assert_not_awaited()
        await self.choose(ctx,app.on_angle_chosen,'pick:story:story_educational')
        upd=await self.choose(ctx,app.on_structure_chosen,'str:tiktok_story:checkin')
        upd.callback_query.edit_message_text.assert_not_awaited()
        upd=update('fam:carousel'); saved=dict(ctx.chat_data)
        with patch.object(app,'_allowed_chat',return_value=False):
            await app.on_family_chosen(upd,ctx)
        self.assertEqual(ctx.chat_data,saved)
        await self.choose(ctx,app.on_family_chosen,'fam:carousel')
        self.assertNotIn('format',ctx.chat_data)
        self.assertNotIn('content_brief',ctx.chat_data)

    async def test_selected_story_pipeline_delivery_and_brief_reset(self):
        ctx=SimpleNamespace(chat_data={})
        for handler, data in [(app.on_family_chosen,'fam:story'), (app.on_format_chosen,'fmt:tiktok_story'),
                (app.on_angle_chosen,'pick:tiktok_story:story_educational'),
                (app.on_structure_chosen,'str:tiktok_story:checkin')]:
            await self.choose(ctx,handler,data)
        upd=update(text='/brief reset')
        with patch.object(app,'_allowed_chat',return_value=True):
            await app.cmd_brief(upd,ctx)
        # Reset advanced brief settings must not silently erase the selected narrative.
        upd=update()
        model=AsyncMock(side_effect=[
            routed(),
            researched(),
            Result(json.dumps({'audience_need':'one insight','objection':'','purpose':'education','framework':'none',
                               'logic_chain':[],'missing_information':'','clarification_question':''}), 'mock'),
            Result('STORY: قبل لا تختار عرضك، شوف شنو يحتاج زبونك فعلاً.', 'mock'),
            Result(json.dumps({'scores':dict.fromkeys(DIMENSIONS,8),'gates':dict.fromkeys(GATES,'pass'),'issues':[]}), 'mock')])
        with patch.object(app,'_allowed_chat',return_value=True), patch.object(app,'pilot_check',return_value=(True,'')), \
             patch.object(app,'log_post',return_value='id') as log, patch('revision.generate',model):
            await app.on_text(upd,ctx)
        self.assertEqual(model.await_count,5)
        for call in model.call_args_list:
            self.assertEqual(json.loads(call.args[1])['brief']['structure_id'],'checkin')
        self.assertIn(structure_prompt('tiktok_story','checkin'),model.call_args_list[3].args[0])
        self.assertIn(structure_prompt('tiktok_story','checkin'),model.call_args_list[4].args[0])
        self.assertEqual(log.call_args.args[0]['structure_id'],'checkin')
        self.assertEqual(log.call_args.args[0]['quality_status'],'accepted')


class SelectedStructureEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_39_selected_narratives_reach_writer_and_reviewer_without_extra_calls(self):
        fixtures=json.loads((Path(__file__).parent / 'fixtures/cross_format_drafts.json').read_text())
        copies={row['format']:row['text'] for row in fixtures}
        for fmt, choices in STRUCTURES.items():
            for choice in choices:
                with self.subTest(format=fmt, structure=choice.id):
                    review=Result(json.dumps({'scores':dict.fromkeys(DIMENSIONS,8),
                        'gates':dict.fromkeys(GATES,'pass'),'issues':[]}), 'mock')
                    model=AsyncMock(side_effect=[Result(copies[fmt],'mock'),review])
                    brief=Brief(structure_id=choice.id)
                    with patch('revision.generate',model):
                        run=await run_pipeline(fmt,build_system_prompt(fmt,brief=brief),'موضوع عام','tip',
                                               brief=brief,settings=Settings(analyst=False))
                    self.assertEqual(run.checked.status,'accepted',run.checked.failures)
                    self.assertEqual(model.await_count,2)
                    for call in model.call_args_list:
                        self.assertIn(choice.instruction,call.args[0])
                        self.assertEqual(json.loads(call.args[1])['brief']['structure_id'],choice.id)

    async def test_invalid_structure_makes_zero_calls(self):
        model=AsyncMock()
        with patch('revision.generate',model), self.assertRaises(ValueError):
            await run_pipeline('reel','voice','موضوع','tip',brief=Brief(structure_id='playbook'))
        model.assert_not_awaited()

    async def test_revision_preserves_narrative_and_native_document_structure(self):
        text='\n'.join([f'SLIDE {i}: خل نراجع الخيارات المهنية ونفهم شنو نحتاج قبل لا ناخذ قرار بشغلنا.' for i in range(1,5)]+['CAPTION: هاي طريقة لترتيب الفكرة ومناقشتها ويا فريقك.','CTA: شنو المعيار الأهم بقرارك؟'])
        def review(score,issues):
            return Result(json.dumps({'scores':dict.fromkeys(DIMENSIONS,score),'gates':dict.fromkeys(GATES,'pass'),'issues':issues}),'mock')
        issue={'section':'SLIDE 2','reason':'weak reasoning','instruction':'Clarify the decision criterion.'}
        # Patch JSON schema is exercised through the real bounded revision engine.
        patch_text=json.dumps({'replacements':{'SLIDE 2':'قارن الخيارات حسب حاجة فريقك والإمكانيات المتوفرة حتى يصير القرار أوضح.'}})
        model=AsyncMock(side_effect=[Result(text,'mock'),review(5,[issue]),Result(patch_text,'mock'),review(8,[])])
        brief=Brief(structure_id='decision')
        with patch('revision.generate',model):
            run=await run_pipeline('linkedin_carousel',build_system_prompt('linkedin_carousel',brief=brief),'اختيار طريقة شغل','tip',brief=brief,settings=Settings(analyst=False))
        self.assertEqual(run.checked.status,'accepted',run.checked.failures)
        self.assertEqual(model.await_count,4)
        for call in model.call_args_list:
            self.assertEqual(json.loads(call.args[1])['brief']['structure_id'],'decision')
            self.assertIn(structure_prompt('linkedin_carousel','decision'),call.args[0])
        self.assertEqual(check('linkedin_carousel',run.checked.text),[])
        self.assertIn(text.splitlines()[0],run.checked.text)
