"""Reproduce the reported legacy Story output and verify runtime identification."""
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import bot as telegram_bot
from build_info import build_info
from llm import Result
from pipeline import Run, run_pipeline
from prompts import build_system_prompt
from quality import Checked, check
from revision import Settings

LEGACY = (Path(__file__).parent / 'fixtures/retired_story_caption.txt').read_text()


def update():
    status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    upd = SimpleNamespace(effective_chat=SimpleNamespace(id=123),
                          message=SimpleNamespace(text='ميزانية التسويق', reply_text=AsyncMock(return_value=status)))
    return upd, status


class DiagnosticTests(unittest.TestCase):
    def test_screenshot_layout_rejected_by_current_story_validator(self):
        failures = check('story', LEGACY)
        self.assertIn('native sections must appear once in the required order', failures)
        self.assertIn('retired universal caption template is not a native format', failures)

    def test_native_headers_cannot_hide_the_retired_emoji_template(self):
        text = 'STORY: ' + LEGACY + '\nINTERACTION: شنو رأيك؟'
        self.assertIn('retired universal caption template is not a native format', check('story', text))

    def test_blueprint_uses_main_and_expected_start_command(self):
        blueprint = (Path(__file__).resolve().parents[1] / 'render.yaml').read_text()
        self.assertIn('    branch: main\n', blueprint)
        self.assertIn('    startCommand: python bot/bot.py\n', blueprint)
        self.assertNotIn('branch: claude/', blueprint)

    def test_build_identity_does_not_expose_secrets(self):
        with patch.dict(os.environ, {'RENDER_GIT_COMMIT': 'a' * 40, 'RENDER_GIT_BRANCH': 'main',
                                    'ANTHROPIC_API_KEY': 'DO_NOT_PRINT', 'TELEGRAM_BOT_TOKEN': 'NEVER_PRINT'}):
            info = build_info('example prompt')
        self.assertEqual(info['commit'], 'a' * 40)
        self.assertEqual(info['branch'], 'main')
        self.assertEqual(info['format_contract'], 'native-v2')
        self.assertNotIn('PRINT', json.dumps(info))
        self.assertNotIn('example prompt', json.dumps(info))
        self.assertNotEqual(build_info('one')['prompt'], build_info('two')['prompt'])

    def test_absent_or_malformed_commit_is_explicitly_unknown(self):
        with patch.dict(os.environ, {'RENDER_GIT_COMMIT': 'token=private', 'APP_GIT_COMMIT': ''}):
            self.assertEqual(build_info()['commit'], 'unknown')


class RuntimeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_pipeline_blocks_reported_layout_without_reviewer_call(self):
        model = AsyncMock(return_value=Result(LEGACY, 'mock'))
        with patch('revision.generate', model):
            run = await run_pipeline('story', build_system_prompt('story'), 'ميزانية التسويق',
                                     'tip', settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'blocked')
        self.assertEqual(model.await_count, 1)

    async def test_telegram_rechecks_wrongly_accepted_content(self):
        upd, status = update()
        run = Run(Checked(LEGACY, 'mock', status='accepted'), [Result(LEGACY, 'mock')])
        ctx = SimpleNamespace(chat_data={'format': 'story', 'angle': 'tip'})
        with patch.object(telegram_bot, '_allowed_chat', return_value=True), \
             patch.object(telegram_bot, 'pilot_check', return_value=(True, '')), \
             patch.object(telegram_bot, 'run_pipeline', AsyncMock(return_value=run)), \
             patch.object(telegram_bot, 'log_post', return_value='id') as record:
            await telegram_bot.on_text(upd, ctx)
        self.assertEqual(record.call_args.args[0]['quality_status'], 'blocked')
        self.assertIn('source', record.call_args.args[0]['build'])
        sent = '\n'.join(c.args[0] for c in upd.message.reply_text.call_args_list)
        self.assertNotIn('بداية الفيديو', sent)
        status.edit_text.assert_awaited_once()
        status.delete.assert_not_awaited()

    async def test_version_command_reports_the_responding_worker(self):
        upd, _ = update()
        ctx = SimpleNamespace(chat_data={'format': 'story'})
        with patch.object(telegram_bot, '_allowed_chat', return_value=True), \
             patch.dict(os.environ, {'RENDER_GIT_COMMIT': 'b' * 40, 'RENDER_GIT_BRANCH': 'main'}):
            await telegram_bot.cmd_version(upd, ctx)
        text = upd.message.reply_text.call_args.args[0]
        self.assertIn('commit=' + 'b' * 40, text)
        self.assertIn('selected_format=story', text)
        self.assertIn('format_contract=native-v2', text)

    async def test_version_command_preserves_access_control(self):
        upd, _ = update()
        with patch.object(telegram_bot, '_allowed_chat', return_value=False):
            await telegram_bot.cmd_version(upd, SimpleNamespace(chat_data={}))
        upd.message.reply_text.assert_not_awaited()
