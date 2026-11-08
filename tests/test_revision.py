"""Offline contract, orchestration, budget and cross-format regression tests."""
import asyncio
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
from llm import Result, LLMError
from pipeline import run_pipeline
from platform_intelligence import PROFILES, LEGACY_FORMATS
from prompts import FORMATS, build_system_prompt
from quality import check, generate_checked
from reviewer import DIMENSIONS, GATES, FOCUS, WEIGHTS, parse_review, reviewer_system
from revision import Settings, apply_patch, render, sections

STORY = 'STORY: هسه خل نحچي عن التسويق وشلون تقيس شغلك.\nINTERACTION: شنو رأيك بالتسويق؟'
NEW_STORY = 'هسه شوف شنو يحتاج زبونك قبل لا تختار عرضك.'


def assessment(score=8, gates=None, issues=None):
    return json.dumps({'scores': dict.fromkeys(DIMENSIONS, score),
                       'gates': gates or dict.fromkeys(GATES, 'pass'),
                       'issues': issues or []}, ensure_ascii=False)


def result(text, **kwargs):
    return Result(text, 'anthropic', input_tokens=100, output_tokens=50, cost_usd=0.001, **kwargs)


def draft(fmt):
    from quality import FIELDS
    if fmt in ('instagram_carousel', 'tiktok_photo_carousel'):
        return '\n'.join([f'SLIDE {i}: هسه خل نفهم التسويق ونراجع شغلنا حتى نختار عرض مناسب.'
                          for i in range(1, 5)] + ['CAPTION: خل نبدي بخطوة بسيطة ومفيدة.', 'CTA: شنو رأيك؟'])
    if fmt == 'linkedin_article':
        return ('TITLE: شلون تراجع تسويقك\nSUMMARY: خل نفهم المشكلة.'
                '\n## المشكلة\n' + 'هسه خل نشوف شنو يحتاج زبونك وشنو تگدر تسوي حتى تحسن شغلك. ' * 9
                + '\n## الحل\n' + 'قارن شغلك وافهم زبونك قبل لا تصرف فلوسك على عرض جديد. ' * 9
                + '\nCONCLUSION: شنو أول خطوة راح تجربها؟')
    text = 'هسه خل نشوف شنو يحتاج زبونك حتى نختار عرض مناسب ونتعلم من شغلنا.'
    if fmt == 'instagram_instants':
        text = 'هسه بالشغل ويا الفريق.'
    return '\n'.join(f'{name}: {text}' + (' شنو رأيك؟' if name == 'INTERACTION' else '')
                     for name in FIELDS[fmt])


class ContractTests(unittest.TestCase):
    def test_all_formats_have_distinct_focus_and_weights(self):
        self.assertEqual(set(FOCUS), set(PROFILES))
        self.assertEqual(len(set(FOCUS.values())), 12)
        self.assertEqual(set(WEIGHTS), set(PROFILES))

    def test_strict_reviews_reject_malformed(self):
        base = json.loads(assessment())
        bad = ['not json', '```json\n' + assessment() + '\n```', '[]', '{}']
        for key in ('scores', 'gates', 'issues'):
            item = dict(base); item.pop(key); bad.append(json.dumps(item))
        for score in (True, -1, 11, '8', float('nan'), float('inf')):
            item = json.loads(assessment()); item['scores']['hook'] = score
            bad.append(json.dumps(item))
        item = json.loads(assessment()); item['gates']['safety'] = True; bad.append(json.dumps(item))
        item = json.loads(assessment()); item['gates'].pop('factual_integrity'); bad.append(json.dumps(item))
        item = json.loads(assessment()); item['issues'] = [{'section': 'UNKNOWN', 'reason': 'x', 'instruction': 'x'}]
        bad.append(json.dumps(item))
        for text in bad:
            with self.subTest(text=text[:50]), self.assertRaises((ValueError, TypeError)):
                parse_review(text, {'STORY', 'INTERACTION'})

    def test_gate_always_overrides_ten(self):
        for name in GATES:
            for state in ('fail', 'uncertain'):
                gates = dict.fromkeys(GATES, 'pass'); gates[name] = state
                self.assertFalse(parse_review(assessment(10, gates), set()).acceptable('story', 7, 6))

    def test_dimension_floor_and_instants_cta(self):
        data = json.loads(assessment(10)); data['scores']['cta'] = 0
        review = parse_review(json.dumps(data), set())
        self.assertTrue(review.acceptable('instagram_instants', 7, 6))
        self.assertFalse(review.acceptable('story', 7, 6))

    def test_targeted_patch_preserves_other_sections(self):
        parts = sections(STORY)
        updated = apply_patch(parts, json.dumps({'replacements': {'STORY': NEW_STORY}}), {'STORY'})
        self.assertEqual(sections(updated)['INTERACTION'], parts['INTERACTION'])
        for changes in ({'INTERACTION': 'x'}, {'STORY': ''}, {'STORY': 'x\nCTA: changed'}, {}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                apply_patch(parts, json.dumps({'replacements': changes}), {'STORY'})

    def test_structure_roundtrip_all_formats(self):
        for fmt in PROFILES:
            with self.subTest(fmt=fmt):
                text = draft(fmt)
                self.assertEqual(check(fmt, text), [])
                self.assertEqual(check(fmt, render(sections(text))), [])

    def test_duplicate_empty_and_reordered_sections(self):
        for text in (STORY + '\nSTORY: extra', 'STORY:\nINTERACTION: شنو؟',
                     'INTERACTION: شنو؟\nSTORY: هسه خل نحچي عن التسويق.'):
            with self.subTest(text=text):
                from revision import sections
                try:
                    issues = check('story', text)
                    sections(text)
                except ValueError:
                    issues = ['invalid']
                self.assertTrue(issues)

    def test_prompt_newlines_and_legacy_routing(self):
        for fmt in FORMATS:
            prompt = build_system_prompt(fmt)
            self.assertNotIn('\\n', prompt[prompt.index('# Required platform-specific'):])
        for old, new in LEGACY_FORMATS.items():
            self.assertEqual(reviewer_system(old), reviewer_system(new))

    def test_settings_validation(self):
        for options in ({'max_revisions': 3}, {'threshold': float('nan')}, {'max_calls': 0},
                        {'timeout_seconds': 0}, {'max_calls': True}, {'max_calls': 2.5}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                Settings(**options)
        with patch.dict(os.environ, {'QUALITY_MAX_REVISIONS': '0', 'QUALITY_ANALYST': 'false'}):
            self.assertEqual(Settings.from_env().max_revisions, 0)
            self.assertFalse(Settings.from_env().analyst)


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def run_mock(self, responses, settings=None, **kwargs):
        mock = AsyncMock(side_effect=responses)
        with patch('revision.generate', mock):
            run = await run_pipeline('story', 'creator voice', 'التسويق', 'tip',
                                     settings=settings or Settings(analyst=False), **kwargs)
        return run, mock

    async def test_happy_path_two_calls(self):
        run, mock = await self.run_mock([result(STORY), result(assessment())])
        self.assertEqual(run.checked.status, 'accepted')
        self.assertEqual(len(run.calls), 2)
        self.assertAlmostEqual(run.cost_usd, 0.002)
        self.assertEqual(run.input_tokens, 200)
        self.assertEqual(run.output_tokens, 100)
        self.assertEqual(len(run.timings), 2)
        self.assertGreater(run.elapsed_ms, 0)

    async def test_default_analyst_three_calls(self):
        run, mock = await self.run_mock([result('audience'), result(STORY), result(assessment())], Settings())
        self.assertEqual(run.checked.status, 'accepted')
        self.assertEqual(len(run.calls), 3)
        self.assertIn('audience', mock.call_args_list[1].args[1])

    async def test_weak_section_revised_and_reassessed(self):
        issues = [{'section': 'STORY', 'reason': 'generic opening', 'instruction': 'make specific'}]
        run, mock = await self.run_mock([
            result(STORY), result(assessment(5, issues=issues)),
            result(json.dumps({'replacements': {'STORY': NEW_STORY}})), result(assessment(8))])
        self.assertEqual(run.checked.status, 'accepted')
        self.assertEqual(run.checked.attempts, 2)
        self.assertEqual(len(run.checked.review_history), 2)
        self.assertIn(STORY, json.loads(mock.call_args_list[3].args[1])['original_draft'])
        self.assertEqual(sections(run.checked.text)['INTERACTION'], sections(STORY)['INTERACTION'])

    async def test_high_score_cannot_bypass_gate_or_trigger_rewrite(self):
        for gate in GATES:
            gates = dict.fromkeys(GATES, 'pass'); gates[gate] = 'fail'
            run, mock = await self.run_mock([result(STORY), result(assessment(10, gates))])
            self.assertEqual(run.checked.status, 'blocked')
            self.assertEqual(mock.await_count, 2)

    async def test_structural_failure_skips_reviewer(self):
        run, mock = await self.run_mock([result('HOOK: wrong native format')])
        self.assertEqual(run.checked.status, 'blocked')
        self.assertEqual(mock.await_count, 1)

    async def test_malformed_review_never_accepts(self):
        for raw in ('{}', 'bad json', assessment().replace('"pass"', '"unknown"', 1)):
            run, _ = await self.run_mock([result(STORY), result(raw)])
            self.assertNotEqual(run.checked.status, 'accepted')
            self.assertTrue(run.checked.failures)

    async def test_no_revisions_configuration(self):
        issues = [{'section': 'STORY', 'reason': 'generic', 'instruction': 'fix'}]
        run, mock = await self.run_mock([result(STORY), result(assessment(4, issues=issues))],
                                        Settings(analyst=False, max_revisions=0))
        self.assertEqual(mock.await_count, 2)
        self.assertEqual(run.checked.status, 'needs_review')

    async def test_non_improvement_stops(self):
        issues = [{'section': 'STORY', 'reason': 'generic', 'instruction': 'fix'}]
        run, mock = await self.run_mock([result(STORY), result(assessment(4, issues=issues)),
            result(json.dumps({'replacements': {'STORY': NEW_STORY}})), result(assessment(4, issues=issues))],
            Settings(analyst=False, max_revisions=2, max_calls=7, max_total_output_tokens=30000))
        self.assertEqual(mock.await_count, 4)
        self.assertIn('revision did not improve score', run.checked.failures)

    async def test_fact_preservation(self):
        run, mock = await self.run_mock([result(STORY)], verified_facts=(('20%', 'owner sales ledger'),))
        self.assertEqual(run.checked.status, 'blocked')
        self.assertEqual(mock.await_count, 1)
        text = STORY.replace('التسويق', 'التسويق 20%', 1)
        run, _ = await self.run_mock([result(text), result(assessment())],
                                    verified_facts=(('20%', 'owner sales ledger'),))
        self.assertEqual(run.checked.status, 'accepted')

    async def test_revision_cannot_remove_fact(self):
        text = STORY.replace('التسويق', 'التسويق 20%', 1)
        issues = [{'section': 'STORY', 'reason': 'generic', 'instruction': 'fix'}]
        run, mock = await self.run_mock([result(text), result(assessment(4, issues=issues)),
            result(json.dumps({'replacements': {'STORY': NEW_STORY}}))],
            verified_facts=(('20%', 'ledger'),))
        self.assertEqual(run.checked.status, 'blocked')
        self.assertEqual(mock.await_count, 3)

    async def test_refusal_empty_truncation_and_error(self):
        for response in (result('', refused=True), result(''), result(STORY, truncated=True),
                         LLMError('sensitive error data')):
            run, mock = await self.run_mock([response])
            self.assertNotEqual(run.checked.status, 'accepted')
            self.assertEqual(mock.await_count, 1)
            self.assertNotIn('sensitive', str(run.checked.failures))

    async def test_unknown_pricing_stops_subsequent_calls(self):
        run, mock = await self.run_mock([result(STORY, usage_known=False)])
        self.assertEqual(mock.await_count, 1)
        self.assertNotEqual(run.checked.status, 'accepted')

    async def test_call_cost_output_and_input_budgets(self):
        for cfg in (Settings(analyst=False, max_calls=1),
                    Settings(analyst=False, max_cost_usd=0.001),
                    Settings(analyst=False, max_total_output_tokens=4000)):
            run, mock = await self.run_mock([result(STORY)], cfg)
            self.assertEqual(mock.await_count, 1)
            self.assertNotEqual(run.checked.status, 'accepted')
        run, mock = await self.run_mock([result(STORY)], Settings(analyst=False, max_input_chars=1000))
        self.assertEqual(mock.await_count, 1)
        self.assertNotEqual(run.checked.status, "accepted")

    async def test_timeout_retains_accounting(self):
        async def slow(*args, **kwargs):
            await asyncio.sleep(2)
        with patch('revision.generate', slow):
            run = await run_pipeline('story', 'voice', 'topic', 'tip',
                                    settings=Settings(analyst=False, call_timeout_seconds=1))
        self.assertEqual(run.checked.status, 'needs_review')
        self.assertEqual(run.timings[0]['status'], 'error')
        self.assertLess(run.elapsed_ms, 1500)

    async def test_all_twelve_and_legacy_pipeline_paths(self):
        for fmt in list(PROFILES) + list(LEGACY_FORMATS):
            native = LEGACY_FORMATS.get(fmt, fmt)
            with self.subTest(fmt=fmt), patch('revision.generate', AsyncMock(
                    side_effect=[result(draft(native)), result(assessment())])):
                run = await run_pipeline(fmt, build_system_prompt(next(
                    (old for old, new in LEGACY_FORMATS.items() if new == native), native)),
                    'التسويق', 'tip', settings=Settings(analyst=False))
                self.assertEqual(run.checked.status, 'accepted')

    async def test_compatibility_generate_checked(self):
        with patch('revision.generate', AsyncMock(side_effect=[result(STORY), result(assessment())])):
            checked = await generate_checked('story', 'voice', 'التسويق')
        self.assertEqual(checked.status, 'accepted')

class AdverseRevisionTests(unittest.IsolatedAsyncioTestCase):
    async def test_revised_draft_must_pass_factual_gate(self):
        issues = [{'section': 'STORY', 'reason': 'weak opening', 'instruction': 'be specific'}]
        gates = dict.fromkeys(GATES, 'pass'); gates['factual_integrity'] = 'uncertain'
        mock = AsyncMock(side_effect=[result(STORY), result(assessment(5, issues=issues)),
            result(json.dumps({'replacements': {'STORY': NEW_STORY}})), result(assessment(10, gates))])
        with patch('revision.generate', mock):
            run = await run_pipeline('story', 'voice', 'التسويق', 'tip', settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'blocked')
        self.assertEqual(mock.await_count, 4)
        self.assertNotIn('creative thresholds not met', run.checked.failures)

    async def test_malicious_patch_and_reviewer_refusal_do_not_accept(self):
        issues = [{'section': 'STORY', 'reason': 'weak opening', 'instruction': 'be specific'}]
        for patch_result in (result('{"replacements":{"INTERACTION":"changed"}}'),
                             result('', refused=True), result('{}', truncated=True)):
            mock = AsyncMock(side_effect=[result(STORY), result(assessment(5, issues=issues)), patch_result])
            with patch('revision.generate', mock):
                run = await run_pipeline('story', 'voice', 'التسويق', 'tip', settings=Settings(analyst=False))
            self.assertNotEqual(run.checked.status, 'accepted')
            self.assertEqual(run.checked.text, STORY)
        for reply in (result('', refused=True), result(assessment(), truncated=True)):
            with patch('revision.generate', AsyncMock(side_effect=[result(STORY), reply])):
                run = await run_pipeline('story', 'voice', 'التسويق', 'tip', settings=Settings(analyst=False))
            self.assertNotEqual(run.checked.status, 'accepted')

    async def test_concurrent_runs_keep_independent_state(self):
        async def model(system, user, **kwargs):
            await asyncio.sleep(0)
            return result(assessment() if system.startswith('You are an independent') else STORY)
        with patch('revision.generate', model):
            runs = await asyncio.gather(*(run_pipeline('story', 'voice', f'topic {i}', 'tip',
                settings=Settings(analyst=False)) for i in range(12)))
        self.assertTrue(all(r.checked.status == 'accepted' and len(r.calls) == 2 for r in runs))
        self.assertEqual(len({id(r.calls) for r in runs}), 12)

    async def test_elapsed_deadline_prevents_new_call(self):
        from revision import Session, LimitReached
        session = Session(Settings(timeout_seconds=1))
        session.started -= 2
        with patch('revision.generate', AsyncMock()) as model:
            with self.assertRaises(LimitReached):
                await session.call('writer', 'voice', 'brief')
            model.assert_not_awaited()


class StructuralEdgeTests(unittest.TestCase):
    def test_empty_slide_and_field_do_not_consume_next_header(self):
        text = draft('instagram_carousel').replace('SLIDE 2: هسه خل نفهم التسويق ونراجع شغلنا حتى نختار عرض مناسب.', 'SLIDE 2:')
        self.assertTrue(any('empty' in issue for issue in check('carousel', text)))
        self.assertTrue(any('empty STORY' in issue for issue in check('story', 'STORY:\nINTERACTION: شنو رأيك؟')))
