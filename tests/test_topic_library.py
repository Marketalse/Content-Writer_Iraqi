"""Editorial bank compatibility, confirmation, and normal-pipeline integration."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bot'))
import bot as app
from briefs import parse_brief
from content_layers import FEATURES, validate_selection
from pipeline import Run
from prompts import build_system_prompt
from quality import Checked
from reviewer import reviewer_system
from topic_library import BANK, load_topics
from topic_navigation import PAGE_SIZE, home, page


def callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def update(data='',text='موضوع جديد'):
    message=NS(text=text,reply_text=AsyncMock(return_value=NS(edit_text=AsyncMock(),delete=AsyncMock())))
    query=NS(data=data,answer=AsyncMock(),edit_message_text=AsyncMock(),message=message)
    return NS(message=message,callback_query=query,effective_chat=NS(id=123))


class LibraryTests(unittest.TestCase):
    def test_all_145_topics_round_trip_through_native_briefs_writer_and_review(self):
        topics=load_topics()
        self.assertEqual(len(topics),145)
        self.assertEqual(sum(t.ready for t in topics.values()),137)
        self.assertEqual(sum(t.hold for t in topics.values()),4)
        self.assertEqual(sum(t.published for t in topics.values()),4)
        self.assertEqual({t.id for t in topics.values() if t.hold},{'CONT-261','CONT-473','CONT-179','CONT-46'})
        for item in topics.values():
            with self.subTest(id=item.id):
                validate_selection(item.format,item.feature_id,item.strategy_id,item.structure_id)
                self.assertIn(item.format,FEATURES[item.feature_id][1])
                brief=item.brief()
                self.assertEqual(parse_brief(json.dumps(brief.data())).data(),brief.data())
                self.assertIn(item.angle,brief.source_material)
                self.assertFalse(brief.evidence)  # Editorial notes are not verified facts.
                self.assertTrue(build_system_prompt(item.format,brief=brief))
                self.assertTrue(reviewer_system(item.format,story_mode=brief.story_mode,
                    story_intent=brief.story_intent,structure_id=brief.structure_id,
                    feature_id=brief.feature_id,strategy_id=brief.strategy_id))

    def test_every_topic_is_reachable_once_and_callback_sizes_fit_telegram(self):
        topics=load_topics();seen=[]
        _,markup=home(topics)
        for value in callbacks(markup):self.assertLessEqual(len(value.encode()),64)
        for pillar in sorted({t.pillar_id for t in topics.values()}):
            count=sum(t.pillar_id==pillar for t in topics.values())
            for number in range((count+PAGE_SIZE-1)//PAGE_SIZE):
                text,markup=page(topics,pillar,number)
                self.assertLess(len(text),4096)
                for value in callbacks(markup):
                    self.assertLessEqual(len(value.encode()),64)
                    if value.startswith('bank:select:'):seen.append(value.split(':')[2])
        self.assertEqual(len(seen),145)
        self.assertEqual(set(seen),set(topics))
        with self.assertRaises(ValueError):page(topics,'P1',999)

    def test_malformed_banks_rejected(self):
        base=json.loads(BANK.read_text())
        samples=[{'version':True,'topics':base['topics']},
                 {'version':1,'topics':[base['topics'][0]]*2},
                 {'version':1,'topics':[{**base['topics'][0],'hold':'false'}]},
                 {'version':1,'topics':[{**base['topics'][0],'format':'linkedin'}]},
                 {'version':1,'topics':[{**base['topics'][0],'extra':'ignored?'}]}]
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'bank.json'
            for sample in samples:
                target.write_text(json.dumps(sample))
                with self.assertRaises(ValueError):load_topics(target)
            target.write_text('{"version":1,"version":1,"topics":[]}')
            with self.assertRaises(ValueError):load_topics(target)


class TopicHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.topics=load_topics()
        self.item=next(t for t in self.topics.values() if t.ready and t.feature_id=='story' and t.strategy_id=='insight')
        self.ctx=NS(chat_data={})
        self.auth=patch.object(app,'_allowed_chat',return_value=True);self.auth.start()

    async def asyncTearDown(self):self.auth.stop()

    async def prepare(self,item=None):
        upd=update(text='/topic '+(item or self.item).id)
        await app.cmd_topic(upd,self.ctx)
        return upd

    def run_callback(self):
        pending=self.ctx.chat_data['bank_pending']
        return 'bank:run:'+pending['id']+':'+pending['token']

    async def test_preview_has_no_paid_work_and_preserves_compatible_destination(self):
        self.ctx.chat_data={'format':'tiktok_story','topic_advice':{},'family':'old'}
        with patch.object(app,'run_pipeline',AsyncMock()) as model,patch.object(app,'pilot_check') as quota:
            upd=await self.prepare()
        model.assert_not_awaited();quota.assert_not_called()
        self.assertEqual(self.ctx.chat_data['format'],'tiktok_story')
        self.assertEqual(self.ctx.chat_data['content_brief'].data(),self.item.brief('tiktok_story').data())
        self.assertNotIn('family',self.ctx.chat_data)
        self.assertIn(self.run_callback(),callbacks(upd.message.reply_text.call_args.kwargs['reply_markup']))
        self.ctx.chat_data['format']='linkedin'
        await self.prepare()
        self.assertEqual(self.ctx.chat_data['format'],self.item.format)

    async def test_hold_and_used_topics_require_different_actions(self):
        with patch.object(app,'run_pipeline',AsyncMock()) as model,patch.object(app,'pilot_check') as quota:
            for item in self.topics.values():
                if item.hold:
                    upd=await self.prepare(item)
                    self.assertIn('يحتاج تفاصيل',upd.message.reply_text.call_args.args[0])
                    self.assertNotIn('bank_pending',self.ctx.chat_data)
            used=next(t for t in self.topics.values() if t.published)
            upd=await self.prepare(used)
            self.assertIn('مستخدم',upd.message.reply_text.call_args.args[0])
            self.assertIn('إعادة صياغته',upd.message.reply_text.call_args.args[0])
        model.assert_not_awaited();quota.assert_not_called()

    async def test_confirmation_runs_ordinary_pipeline_once_with_bank_brief(self):
        await self.prepare();callback=self.run_callback();upd=update(callback)
        checked=Checked('STORY: شنو يحتاج زبونك حتى تكتبله رد واضح؟','mock',status='accepted',story_intent='educational')
        model=AsyncMock(return_value=Run(checked))
        with patch.object(app,'run_pipeline',model),patch.object(app,'pilot_check',return_value=(True,'')),patch.object(app,'log_post',return_value='id') as log:
            await app.on_bank_chosen(upd,self.ctx)
            self.assertEqual(model.await_count,1)
            call=model.call_args
            self.assertEqual(call.args[2],self.item.title)
            self.assertEqual(call.kwargs['brief'].data(),self.item.brief().data())
            self.assertTrue(call.kwargs['research']);self.assertTrue(call.kwargs['suggest_topics'])
            self.assertEqual(log.call_args.args[0]['topic_id'],self.item.id)
            await app.on_bank_chosen(upd,self.ctx)
            self.assertEqual(model.await_count,1)

    async def test_changed_settings_or_old_token_cannot_start_generation(self):
        await self.prepare();old=self.run_callback()
        await self.prepare()
        with patch.object(app,'run_pipeline',AsyncMock()) as model:
            await app.on_bank_chosen(update(old),self.ctx)
            current=self.run_callback();self.ctx.chat_data['format']='tiktok_story'
            await app.on_bank_chosen(update(current),self.ctx)
        model.assert_not_awaited()

    async def test_back_navigation_and_hold_selection_invalidate_old_confirmation(self):
        held=next(t for t in self.topics.values() if t.hold)
        for action in ('bank:home','bank:page:P1:0','hold','reset'):
            await self.prepare();old=self.run_callback()
            if action=='hold':await self.prepare(held)
            elif action=='reset':app._clear_selection(self.ctx.chat_data)
            else:await app.on_bank_chosen(update(action),self.ctx)
            with patch.object(app,'run_pipeline',AsyncMock()) as model:
                await app.on_bank_chosen(update(old),self.ctx)
            model.assert_not_awaited()

    async def test_new_manual_topic_drops_bank_material_and_stale_confirmation(self):
        await self.prepare();old=self.run_callback()
        with patch.object(app,'pilot_check',return_value=(False,'quota')):
            await app.on_text(update(text='موضوع مختلف'),self.ctx)
        self.assertNotIn('content_brief',self.ctx.chat_data)
        self.assertNotIn('bank_topic_id',self.ctx.chat_data)
        with patch.object(app,'run_pipeline',AsyncMock()) as model:
            await app.on_bank_chosen(update(old),self.ctx)
        model.assert_not_awaited()

    async def test_unavailable_bank_and_unauthorized_chat_do_not_spend(self):
        with patch('topic_library.load_topics',side_effect=FileNotFoundError('/private/path')),patch.object(app,'run_pipeline',AsyncMock()) as model:
            upd=await self.prepare()
            self.assertIn('مو متاحة',upd.message.reply_text.call_args.args[0])
            self.assertNotIn('/private',upd.message.reply_text.call_args.args[0])
        model.assert_not_awaited()
        with patch.object(app,'_allowed_chat',return_value=False):
            upd=await self.prepare()
        upd.message.reply_text.assert_not_awaited()
