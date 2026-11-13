"""Spreadsheet taxonomy, stale-click isolation and shared writer/reviewer selections."""
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from test_content_navigation import update, callbacks
from test_revision import draft, result, assessment
import bot as app
from briefs import Brief, parse_brief
from content_layers import FEATURES, STRATEGIES, FLOWS, get_strategy, selection_prompt
from layer_navigation import selected_brief
from prompts import build_system_prompt
from revision import Settings
from pipeline import run_pipeline
from research_fixtures import routed

class RegistryTests(unittest.TestCase):
    def test_exact_strategy_lists_and_live_choices(self):
        self.assertEqual(STRATEGIES['post'],('comedy','guide','howto','problem','engage','experiment'))
        self.assertEqual(STRATEGIES['story'],('comedy','why','hot_take','howto','mistake','problem','insight','experiment'))
        self.assertEqual(STRATEGIES['reel'],('b2b','deepdive','quiz','poll','professional','engage'))
        self.assertEqual(STRATEGIES['live'],('clinic','workshop','guest'))

    def test_invalid_combinations_rejected_before_generation(self):
        for data,fmt in ((dict(feature_id='post',strategy_id='b2b',structure_id='professional'),'instagram_post'),
                         (dict(feature_id='reel',strategy_id='b2b',structure_id='guide'),'reel'),
                         (dict(feature_id='live',strategy_id='guest',structure_id='guest'),'story'),
                         (dict(strategy_id='insight',structure_id='insight'),'story')):
            with self.assertRaises(ValueError):
                Brief(**data).validate_format(fmt)
        with self.assertRaises(ValueError):
            parse_brief('{"feature_id": 42}')

class NavigationTests(unittest.IsolatedAsyncioTestCase):
    async def choose(self,ctx,callback):
        upd=update(callback)
        with patch.object(app,'_allowed_chat',return_value=True):
            await app.on_layer_chosen(upd,ctx)
        return upd

    async def test_every_feature_platform_strategy_route_and_callback_limit(self):
        for feature,(_,formats) in FEATURES.items():
            for fmt in formats:
                for strategy in STRATEGIES[feature]:
                    ctx=NS(chat_data={})
                    for callback in (f'ly:f:{feature}',f'ly:p:{feature}:{fmt}',f'ly:s:{fmt}:{strategy}'):
                        upd=await self.choose(ctx,callback)
                        for value in callbacks(upd.callback_query.edit_message_text.call_args.kwargs['reply_markup']):
                            self.assertLessEqual(len(value.encode('utf-8')),64)
                    self.assertEqual(ctx.chat_data['menu_stage'],'layer_structure')
                    msg=update()
                    with patch.object(app,'_allowed_chat',return_value=True),patch.object(app,'run_pipeline',AsyncMock()) as model,patch.object(app,'pilot_check') as quota:
                        await app.on_text(msg,ctx)
                    model.assert_not_awaited();quota.assert_not_called()
                    flow=get_strategy(feature,strategy).flow
                    await self.choose(ctx,f'ly:n:{fmt}:{strategy}:{flow}')
                    brief=ctx.chat_data['content_brief']
                    brief.validate_format(fmt)
                    self.assertEqual(brief.feature_id,feature)
                    self.assertEqual(brief.strategy_id,strategy)
                    self.assertEqual(brief.structure_id,flow)
                    self.assertEqual(ctx.chat_data['menu_stage'],'topic')

    async def test_stale_cross_feature_callbacks_and_unauthorized_are_ignored(self):
        ctx=NS(chat_data={})
        await self.choose(ctx,'ly:f:story')
        await self.choose(ctx,'ly:p:story:story')
        saved=dict(ctx.chat_data)
        for callback in ('ly:p:reel:reel','ly:s:reel:b2b','ly:s:story:b2b','ly:n:story:insight:insight'):
            upd=await self.choose(ctx,callback)
            self.assertEqual(ctx.chat_data,saved)
            upd.callback_query.edit_message_text.assert_not_awaited()
        upd=update('ly:f:reel')
        with patch.object(app,'_allowed_chat',return_value=False):
            await app.on_layer_chosen(upd,ctx)
        self.assertEqual(ctx.chat_data,saved)

    async def test_brief_reset_preserves_selection_on_actual_delivery(self):
        ctx=NS(chat_data={})
        for callback in ('ly:f:story','ly:p:story:story','ly:s:story:insight','ly:n:story:insight:insight'):
            await self.choose(ctx,callback)
        with patch.object(app,'_allowed_chat',return_value=True):
            await app.cmd_brief(update(text='/brief reset'),ctx)
        self.assertEqual(ctx.chat_data['content_brief'].strategy_id,'insight')
        model=AsyncMock(side_effect=[routed('write'),result('STORY: قبل لا تغير عرضك، اسأل زبونك شنو يحتاج؟'),result(assessment())])
        with patch.object(app,'_allowed_chat',return_value=True),patch.object(app,'pilot_check',return_value=(True,'')),patch.object(app,'log_post',return_value='id') as log,patch('revision.generate',model),patch('revision.Settings.from_env',return_value=Settings(analyst=False)):
            await app.on_text(update(),ctx)
        self.assertEqual(model.await_count,3)
        self.assertEqual(log.call_args.args[0]['feature_id'],'story')
        self.assertEqual(log.call_args.args[0]['strategy_id'],'insight')

class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_23_selections_reach_facilitator_writer_and_independent_review(self):
        for feature,(_,formats) in FEATURES.items():
            fmt=formats[0]
            for strategy in STRATEGIES[feature]:
                flow=get_strategy(feature,strategy).flow
                brief=selected_brief(dict(feature_id=feature,strategy_id=strategy,structure_id=flow))
                text='STORY: قبل لا تغير عرضك، اسأل زبونك شنو يحتاج؟' if feature=='story' else draft('instagram_reel' if feature=='reel' else fmt)
                model=AsyncMock(side_effect=[routed('write'),result(text),result(assessment())])
                with patch('revision.generate',model):
                    run=await run_pipeline(fmt,build_system_prompt(fmt,brief=brief),'التسويق','',brief=brief,research=True,settings=Settings(analyst=False))
                self.assertEqual(run.checked.status,'accepted',(feature,strategy,run.checked.failures))
                for call in model.call_args_list:
                    data=json.loads(call.args[1])['brief']
                    self.assertEqual((data['feature_id'],data['strategy_id'],data['structure_id']),(feature,strategy,flow))
                prompt=selection_prompt(fmt,feature,strategy,flow)
                self.assertIn(prompt,model.call_args_list[1].args[0])
                self.assertIn(prompt,model.call_args_list[2].args[0])
