"""Prevent the universal template from re-entering writer/reviewer prompts."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bot'))
import prompts
from format_contracts import GUIDANCE, NATIVE_OUTPUTS, format_contract
from platform_intelligence import PROFILES, LEGACY_FORMATS
from reviewer import DIMENSIONS, GATES, reviewer_system
from pipeline import run_pipeline
from revision import Settings
from llm import Result
from quality import check


class FormatIdentityTests(unittest.TestCase):
    def test_each_format_has_individual_treatment(self):
        self.assertEqual(set(GUIDANCE), set(PROFILES))
        self.assertEqual(len(set(GUIDANCE.values())), 12)
        for fmt in PROFILES:
            with self.subTest(fmt=fmt):
                choice = next((old for old, new in LEGACY_FORMATS.items() if new == fmt), fmt)
                writer = prompts.build_system_prompt(choice)
                reviewer = reviewer_system(choice)
                self.assertTrue(writer.endswith(format_contract(fmt)))
                self.assertIn(GUIDANCE[fmt], writer)
                self.assertIn(GUIDANCE[fmt], reviewer)
                self.assertIn(NATIVE_OUTPUTS[fmt], writer)
                for other in set(PROFILES) - {fmt}:
                    self.assertNotIn(GUIDANCE[other], writer)

    def test_no_active_shared_formula_or_hook_library(self):
        for fmt in prompts.FORMATS:
            with self.subTest(fmt=fmt):
                text = prompts.build_system_prompt(fmt)
                for phrase in ('# Caption formulas', '**1-2-3 List**', 'exactly three points',
                               'بالنهاية؟', 'اكو Hook واضح بالبداية و CTA واضح بالنهاية؟',
                               'Hook formulas for Baghdadi', 'one per post'):
                    self.assertNotIn(phrase, text)

    def test_examples_are_scoped_to_their_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            for folder, marker in [('posts', 'LINKEDIN_STYLE_SAMPLE'), ('transcripts', 'SPOKEN_VIDEO_SAMPLE')]:
                path = kb / 'examples' / folder
                path.mkdir(parents=True)
                (path / 'sample.md').write_text(marker)
            with patch.object(prompts, 'KB', kb):
                for fmt in prompts.FORMATS:
                    text = prompts.build_system_prompt(fmt)
                    self.assertEqual('LINKEDIN_STYLE_SAMPLE' in text, fmt == 'linkedin')
                    self.assertEqual('SPOKEN_VIDEO_SAMPLE' in text, fmt in ('reel', 'tiktok_video'))

    def test_universal_layout_rejected_across_all_formats(self):
        legacy = ('HOOK: شنو المشكلة؟\nCONTENT: هاي ثلاث نقاط.\n'
                  '1. افهم زبونك.\n2. راجع عرضك.\n3. احسب كلفتك.\nCTA: تابعني.')
        for fmt in PROFILES:
            with self.subTest(fmt=fmt):
                self.assertTrue(check(fmt, legacy))

    def test_short_formats_and_articles_keep_distinct_shapes(self):
        self.assertEqual(set(NATIVE_OUTPUTS['instagram_story'].splitlines()[i].split(':')[0]
                             for i in (0, 1)), {'STORY', 'INTERACTION'})
        self.assertEqual(NATIVE_OUTPUTS['instagram_instants'].count('\n'), 0)
        self.assertNotIn('HOOK:', NATIVE_OUTPUTS['instagram_broadcast_channel'])
        self.assertNotIn('CTA:', NATIVE_OUTPUTS['instagram_live'])
        self.assertIn('## Topic-specific', NATIVE_OUTPUTS['linkedin_article'])
        self.assertIn('SCRIPT:', NATIVE_OUTPUTS['tiktok_video'])


class NativeIdentityGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_correct_labels_cannot_hide_a_wrong_creative_structure(self):
        disguised = ('STORY: هاي ثلاث نقاط عن التسويق: افهم زبونك، راجع عرضك، احسب كلفتك.\n'
                     'INTERACTION: تابعني وشنو رأيك؟')
        self.assertEqual(check('story', disguised), [])
        gates = dict.fromkeys(GATES, 'pass'); gates['format_identity'] = 'fail'
        response = json.dumps({'scores': dict.fromkeys(DIMENSIONS, 10), 'gates': gates,
            'issues': [{'section': 'STORY', 'reason': 'Generic three-tip lesson in a moment format',
                        'instruction': 'Use a single immediate observation'}]})
        model = AsyncMock(side_effect=[Result(disguised, 'mock'), Result(response, 'mock')])
        with patch('revision.generate', model):
            run = await run_pipeline('story', prompts.build_system_prompt('story'),
                                     'التسويق', 'tip', settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'blocked')
        self.assertIn('format_identity: fail', run.checked.failures)
        self.assertEqual(model.await_count, 2)

    async def test_revision_receives_same_native_contract(self):
        story = 'STORY: هسه خل نراجع شغلنا بالتسويق.\nINTERACTION: شنو رأيك؟'
        gates = dict.fromkeys(GATES, 'pass')
        def review(score, issues):
            return Result(json.dumps({'scores': dict.fromkeys(DIMENSIONS, score),
                                      'gates': gates, 'issues': issues}), 'mock')
        issues = [{'section': 'STORY', 'reason': 'too vague', 'instruction': 'specific observation'}]
        model = AsyncMock(side_effect=[Result(story, 'mock'), review(5, issues),
            Result(json.dumps({'replacements': {'STORY': 'هسه باوع لأسئلة زبائنك قبل لا تكتب إعلانك.'}}), 'mock'),
            review(8, [])])
        with patch('revision.generate', model):
            run = await run_pipeline('story', prompts.build_system_prompt('story'), 'التسويق',
                                     'tip', settings=Settings(analyst=False))
        self.assertEqual(run.checked.status, 'accepted')
        for idx in (0, 2):
            self.assertIn(GUIDANCE['instagram_story'], model.call_args_list[idx].args[0])
