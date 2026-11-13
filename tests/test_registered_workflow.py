"""Drive the production Application through decoded Telegram updates, no live polling.

The request double implements the Bot API boundary; routing, handlers, markup,
chat_data and bot identity are the real python-telegram-bot implementation.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from telegram import Update
from telegram.request import BaseRequest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import bot as app
from content_choices import FAMILIES, WORKFLOW_VERSION


class BotAPIRequest(BaseRequest):
    def __init__(self):
        self.calls = []

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    async def do_request(self, url, method, request_data=None, **kwargs):
        endpoint = url.rsplit('/',1)[-1]
        params = request_data.parameters if request_data else {}
        self.calls.append((endpoint, params))
        if endpoint == 'getMe':
            result = {'id':42,'is_bot':True,'first_name':'Test writer','username':'WorkflowTestBot'}
        elif endpoint in ('sendMessage','editMessageText'):
            result = {'message_id':params.get('message_id',1),'date':1,
                      'chat':{'id':params['chat_id'],'type':'private'},'text':params['text']}
        elif endpoint == 'answerCallbackQuery':
            result = True
        else:
            raise AssertionError('Unexpected API request: '+endpoint)
        return 200, json.dumps({'ok':True,'result':result}).encode()


class RegisteredWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.request = BotAPIRequest()
        self.application = app.create_application('42:fake_test_token', request=self.request)
        self.errors = []
        async def record_error(update, context):
            self.errors.append(context.error)
        self.application.add_error_handler(record_error)
        await self.application.initialize()
        self.auth = patch.object(app,'_allowed_chat',return_value=True)
        self.auth.start()
        self.model = patch.object(app,'run_pipeline',AsyncMock())
        self.pipeline = self.model.start()
        self.sequence = 0

    async def asyncTearDown(self):
        self.model.stop(); self.auth.stop()
        await self.application.shutdown()
        self.assertEqual(self.errors, [])
        self.assertNotIn('getUpdates',[name for name,_ in self.request.calls])

    async def send(self, text=None, callback=None):
        self.sequence += 1
        user={'id':123,'is_bot':False,'first_name':'Tester'}
        message={'message_id':self.sequence,'date':1,'chat':{'id':123,'type':'private'},'from':user}
        data={'update_id':self.sequence}
        if text is not None:
            message['text']=text
            if text.startswith('/'):
                message['entities']=[{'type':'bot_command','offset':0,'length':len(text.split()[0])}]
            data['message']=message
        else:
            message['from']={'id':42,'is_bot':True,'first_name':'Test writer'}
            message['text']='Choose'
            data['callback_query']={'id':str(self.sequence),'from':user,'chat_instance':'1',
                                    'message':message,'data':callback}
        await self.application.process_update(Update.de_json(data,self.application.bot))
        return self.request.calls[-1][1]

    @property
    def state(self):
        return self.application.chat_data[123]

    async def test_recording_start_now_reaches_five_family_menu_and_all_platform_routes(self):
        for family,(_,formats) in FAMILIES.items():
            menu = await self.send(text='/start')
            self.assertIn('1/3',menu['text'])
            self.assertEqual([row[0]['callback_data'] for row in menu['reply_markup']['inline_keyboard']],
                             ['ly:f:'+key for key in ('post','story','reel','live')]+['ly:legacy'])
            await self.send(callback='ly:legacy')
            menu = await self.send(callback='fam:'+family)
            self.assertIn('2/5',menu['text'])
            callbacks=[row[0]['callback_data'] for row in menu['reply_markup']['inline_keyboard']]
            self.assertEqual(set(callbacks), {'fmt:'+key for key in formats}|{'fam:root'})
            for fmt in formats:
                await self.send(callback='fam:'+family)
                menu=await self.send(callback='fmt:'+fmt)
                self.assertIn('3/5',menu['text'])
                angle=menu['reply_markup']['inline_keyboard'][0][0]['callback_data']
                menu=await self.send(callback=angle)
                self.assertIn('4/5',menu['text'])
                choices=[row[0]['callback_data'] for row in menu['reply_markup']['inline_keyboard']
                         if row[0]['callback_data'].startswith('str:')]
                self.assertEqual(len(choices),3)
                menu=await self.send(callback=choices[0])
                self.assertIn('5/5',menu['text'])
                self.assertEqual(self.state['menu_stage'],'topic')
                self.assertEqual(self.state['format'],fmt)
        self.pipeline.assert_not_awaited()

    async def test_registered_three_layer_route_and_back_navigation(self):
        menu=await self.send(text='/start')
        await self.send(callback='ly:f:live')
        menu=await self.send(callback='ly:p:live:instagram_live')
        self.assertIn('2/3',menu['text'])
        for strategy in ('clinic','workshop','guest'):
            await self.send(callback=f'ly:s:instagram_live:{strategy}')
            flow=self.state['content_brief'].strategy_id
            self.assertEqual(flow,strategy)
            menu=await self.send(callback=f'ly:n:instagram_live:{strategy}:{strategy}')
            self.assertEqual(self.state['menu_stage'],'topic')
            self.assertIn('تم الاختيار',menu['text'])
            await self.send(callback='ly:b:structure')
            await self.send(callback='ly:b:strategy')
        self.pipeline.assert_not_awaited()

    async def test_registered_adviser_button_requires_choice_and_dispatches_new_topic(self):
        await self.send(text='/start')
        await self.send(callback='ly:f:story')
        await self.send(callback='ly:p:story:story')
        await self.send(callback='ly:s:story:insight')
        await self.send(callback='ly:n:story:insight:insight')
        self.state['topic_advice']={'token':'1234abcd',
            'suggestions':[{'topic':'شلون نخصص أول رد للزبون؟','reason':'زاوية عملية','needs_research':False}],
            'selection':app._advice_selection(self.state)}
        with patch.object(app,'on_text',AsyncMock()) as writer:
            await self.send(callback='advice:1234abcd:0')
        writer.assert_awaited_once()
        self.assertEqual(writer.call_args.kwargs['topic_override'],'شلون نخصص أول رد للزبون؟')
        self.assertNotIn('topic_advice',self.state)
        self.pipeline.assert_not_awaited()

    async def test_old_inline_buttons_enter_platform_chooser_instead_of_old_angle_flow(self):
        menu=await self.send(callback='fmt:story')
        self.assertEqual(self.state['menu_stage'],'platform')
        self.assertIn('2/5',menu['text'])
        self.assertNotIn('format',self.state)
        await self.send(text='/cancel')
        self.assertFalse(self.state)
        menu=await self.send(callback='ang:tip')
        self.assertIn('1/3',menu['text'])
        self.assertFalse(self.state)
        # A saved angle callback can also be received after losing in-memory state.
        self.application.chat_data[123].update(format='story',angle='tip')
        menu=await self.send(callback='ang:tip')
        self.assertEqual(self.state['menu_stage'],'platform')
        self.assertNotIn('angle',self.state)
        self.assertIn('2/5',menu['text'])
        self.pipeline.assert_not_awaited()

    async def test_back_buttons_preserve_only_upstream_selections(self):
        await self.send(text='/start')
        await self.send(callback='fam:story')
        await self.send(callback='fmt:tiktok_story')
        await self.send(callback='pick:tiktok_story:story_educational')
        await self.send(callback='str:tiktok_story:checkin')
        self.state['pending_clarification']={'question':'old'}
        await self.send(callback='back:topic')
        self.assertEqual(self.state['format'],'tiktok_story')
        self.assertEqual(self.state['content_brief'].story_intent,'educational')
        self.assertNotIn('structure_id',self.state)
        self.assertNotIn('pending_clarification',self.state)
        await self.send(callback='back:structure')
        self.assertEqual(self.state['menu_stage'],'angle')
        self.assertNotIn('angle',self.state)
        self.assertNotIn('content_brief',self.state)
        await self.send(callback='back:angle')
        self.assertEqual(self.state['menu_stage'],'platform')
        self.assertEqual(self.state['family'],'story')
        self.assertNotIn('format',self.state)
        self.pipeline.assert_not_awaited()

    async def test_startup_and_version_identify_workflow_and_bot_without_secret(self):
        with self.assertLogs(app.log,level='INFO') as captured:
            await self.application.post_init(self.application)
        log='\n'.join(captured.output)
        self.assertIn('workflow='+WORKFLOW_VERSION,log)
        self.assertIn('bot=@WorkflowTestBot',log)
        result=await self.send(text='/version')
        self.assertIn('workflow='+WORKFLOW_VERSION,result['text'])
        self.assertIn('bot_username=WorkflowTestBot',result['text'])
        self.assertNotIn('fake_test_token',log+result['text'])

    async def test_diagnosis_command_is_registered_and_does_not_generate(self):
        with patch.object(app,'diagnostic_report',return_value={'failure_code':'invalid_response'}) as report:
            result=await self.send(text='/diagnose saved-review-id')
        report.assert_called_once_with('saved-review-id',123)
        self.assertIn('invalid_response',result['text'])
        self.pipeline.assert_not_awaited()

    async def test_unauthorized_commands_and_buttons_do_not_mutate_or_reply(self):
        self.auth.stop()
        self.auth=patch.object(app,'_allowed_chat',return_value=False)
        self.auth.start()
        start=len(self.request.calls)
        await self.send(text='/start')
        await self.send(callback='fam:story')
        await self.send(callback='back:angle')
        self.assertFalse(self.state)
        self.assertEqual([name for name,_ in self.request.calls[start:]],
                         ['answerCallbackQuery','answerCallbackQuery'])
        self.pipeline.assert_not_awaited()
