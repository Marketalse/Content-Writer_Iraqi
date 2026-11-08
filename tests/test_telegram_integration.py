"""Mocked Telegram delivery and real temporary-file quota regression tests."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import bot as telegram_bot
import pilot
import postlog
from llm import Result
from pipeline import Run
from quality import Checked


def update(cid=123, text='التسويق'):
    status = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    message = SimpleNamespace(text=text, reply_text=AsyncMock(return_value=status))
    return SimpleNamespace(effective_chat=SimpleNamespace(id=cid), message=message), status


def run_with(status='accepted', text='STORY: محتوى\nINTERACTION: شنو رأيك؟'):
    checked = Checked(text, 'anthropic', status=status,
                      failures=[] if status == 'accepted' else ['safety: uncertain'])
    return Run(checked, [Result('response', 'anthropic', cost_usd=.01)],
               timings=[{'status': 'ok', 'stage': 'writer', 'elapsed_ms': 1}])


class TelegramTests(unittest.IsolatedAsyncioTestCase):
    def context(self, **data):
        return SimpleNamespace(chat_data={'format': 'story', 'angle': 'tip', **data})

    async def test_denied_chat_and_quota_do_not_call_pipeline(self):
        for allowed, quota in ((False, True), (True, False)):
            upd, status = update()
            with patch.object(telegram_bot, '_allowed_chat', return_value=allowed), \
                 patch.object(telegram_bot, 'pilot_check', return_value=(quota, 'quota exhausted')), \
                 patch.object(telegram_bot, 'run_pipeline', AsyncMock()) as model:
                await telegram_bot.on_text(upd, self.context())
                model.assert_not_awaited()

    async def test_each_quality_status_accounted_before_delivery(self):
        for state in ('accepted', 'blocked', 'needs_review'):
            upd, status = update()
            with patch.object(telegram_bot, '_allowed_chat', return_value=True), \
                 patch.object(telegram_bot, 'pilot_check', return_value=(True, '')), \
                 patch.object(telegram_bot, 'run_pipeline', AsyncMock(return_value=run_with(state))), \
                 patch.object(telegram_bot, 'log_post', return_value='id') as log:
                await telegram_bot.on_text(upd, self.context())
            self.assertEqual(log.call_args.args[0]['quality_status'], state)
            self.assertEqual(log.call_args.args[0]['cost_usd'], .01)
            sent = '\n'.join(c.args[0] for c in upd.message.reply_text.call_args_list)
            if state == 'accepted':
                self.assertIn('STORY:', sent)
                status.delete.assert_awaited_once()
            else:
                self.assertNotIn('STORY:', sent)
                status.edit_text.assert_awaited_once()

    async def test_refusal_charges_spent_calls(self):
        run = run_with('blocked', '')
        run.checked.refused = True
        upd, _ = update()
        with patch.object(telegram_bot, '_allowed_chat', return_value=True), \
             patch.object(telegram_bot, 'pilot_check', return_value=(True, '')), \
             patch.object(telegram_bot, 'run_pipeline', AsyncMock(return_value=run)), \
             patch.object(telegram_bot, 'log_post', return_value='id') as log:
            await telegram_bot.on_text(upd, self.context())
        self.assertEqual(log.call_args.args[0]['cost_usd'], .01)

    async def test_unknown_usage_reserves_quota(self):
        run = run_with('needs_review')
        run.timings.append({'status': 'error', 'stage': 'review', 'elapsed_ms': 1})
        upd, _ = update()
        with patch.object(telegram_bot, '_allowed_chat', return_value=True), \
             patch.object(telegram_bot, 'pilot_check', return_value=(True, '')), \
             patch.object(telegram_bot, 'run_pipeline', AsyncMock(return_value=run)), \
             patch.object(telegram_bot, 'log_post', return_value='id') as log:
            await telegram_bot.on_text(upd, self.context())
        self.assertFalse(log.call_args.args[0]['usage_known'])
        self.assertEqual(log.call_args.args[0]['quota_cost_usd'], .25)

    async def test_pilot_admin_owner_only(self):
        upd, _ = update()
        with patch.object(telegram_bot, 'is_owner', return_value=False), \
             patch.object(telegram_bot, 'pilot_add') as add:
            await telegram_bot.cmd_pilot(upd, SimpleNamespace(args=['add', '123', 'name']))
            add.assert_not_called()

    async def test_legacy_callback_and_reset(self):
        upd, _ = update()
        upd.callback_query = SimpleNamespace(answer=AsyncMock(), data='fmt:reel', edit_message_text=AsyncMock())
        ctx = self.context()
        with patch.object(telegram_bot, '_allowed_chat', return_value=True):
            await telegram_bot.on_format_chosen(upd, ctx)
            self.assertEqual(ctx.chat_data['format'], 'reel')
            self.assertNotIn('angle', ctx.chat_data)
            await telegram_bot.cmd_cancel(upd, ctx)
            self.assertEqual(ctx.chat_data, {})

    async def test_long_content_delivered_in_safe_plain_chunks(self):
        text = 'STORY: ' + '<&>😀' * 2300 + '\nINTERACTION: شنو رأيك؟'
        upd, _ = update()
        with patch.object(telegram_bot, '_allowed_chat', return_value=True), \
             patch.object(telegram_bot, 'pilot_check', return_value=(True, '')), \
             patch.object(telegram_bot, 'run_pipeline', AsyncMock(return_value=run_with(text=text))), \
             patch.object(telegram_bot, 'log_post', return_value='id'):
            await telegram_bot.on_text(upd, self.context())
        chunks = [c.args[0] for c in upd.message.reply_text.call_args_list][1:-1]
        self.assertEqual(''.join(chunks), text)
        self.assertTrue(all(len(c.encode('utf-16-le')) // 2 <= 4000 for c in chunks))


class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(pilot, 'CONFIG', root / 'pilots.json'),
                        patch.object(postlog, 'LOG', root / 'posts.jsonl'),
                        patch.dict(os.environ, {'OWNER_CHAT_ID': '1', 'ALLOWED_CHAT_IDS': '2'})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_owner_allowlist_and_pilot_quotas(self):
        self.assertTrue(pilot.check(1)[0])
        self.assertTrue(pilot.check(2)[0])
        self.assertFalse(pilot.check(3)[0])
        pilot.add(3, 'pilot', max_posts=2, max_usd=1)
        self.assertTrue(pilot.check(3)[0])
        for status in ('blocked', 'accepted'):
            postlog.log_post({'chat_id': 3, 'quality_status': status, 'cost_usd': .01})
        self.assertFalse(pilot.check(3)[0])
        self.assertEqual(pilot.usage(3), (2, .02))

    def test_dollar_cap_unknown_usage_and_disabled_pilot(self):
        pilot.add(3, 'pilot', max_posts=10, max_usd=.49)
        postlog.log_post({'chat_id': 3, 'cost_usd': .01, 'quota_cost_usd': .25})
        self.assertEqual(pilot.usage(3), (1, .25))
        self.assertFalse(pilot.check(3)[0])
        pilot.set_active(3, False)
        self.assertFalse(pilot.check(3)[0])

    def test_published_accepted_and_legacy_only(self):
        ids = [postlog.log_post({'quality_status': s}) for s in ('blocked', 'needs_review', 'accepted')]
        legacy = postlog.log_post({})
        self.assertEqual(len(set(ids)), 3)
        self.assertFalse(postlog.mark_published(ids[0]))
        self.assertFalse(postlog.mark_published(ids[1]))
        self.assertTrue(postlog.mark_published(ids[2]))
        self.assertTrue(postlog.mark_published(legacy))
