"""Run: python -m unittest discover -s tests -v
No API keys or network calls required.
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bot"))

from platform_intelligence import PROFILES, LEGACY_FORMATS, get_profile
from quality import check, split_owner_note

class PlatformQualityTest(unittest.TestCase):
    def test_all_twelve_profiles_exist(self):
        self.assertEqual(len(PROFILES), 13)
        for key in PROFILES:
            self.assertTrue(get_profile(key).official_urls)

    def test_legacy_ids_still_route(self):
        for old, new in LEGACY_FORMATS.items():
            self.assertEqual(get_profile(old), get_profile(new))

    def test_story_accepts_interaction_without_three_blocks(self):
        self.assertEqual(check("story", "STORY: اليوم عندنا فكرة جديدة.\nINTERACTION: شنو رأيكم؟"), [])

    def test_reel_accepts_script_not_three_point_caption(self):
        text = ("HOOK: تعرف ليش المبيعات تقل؟\n"
                "SCRIPT: حتى نفهم السبب لازم نقرأ أرقام البيع، نحدد الفترة، ونقارن العروض. "
                "مو كل انخفاض سببه الراتب، يمكن الموسم أو نقص مخزون. "
                "نسوي تجربة صغيرة ونتابع النتائج.\n"
                "VISUALS: عرض مقارنة على الشاشة وأرقام افتراضية بدون ادعاء نتائج.\n"
                "CTA: شنو أول شي راح تراجعه؟")
        self.assertEqual(check("reel", text), [])

    def test_carousel_needs_sequential_slides(self):
        text = ("SLIDE 1: السؤال\nSLIDE 3: الجواب\n"
                "SLIDE 4: مثال\nSLIDE 5: الخلاصة\n"
                "CAPTION: تحليل المبيعات يبدأ من بياناتك الحقيقية، ونحدد المشكلة قبل التخمين.\n"
                "CTA: احفظ الدليل حتى ترجعله.")
        self.assertTrue(any("numbering" in x for x in check("carousel", text)))

    def test_article_requires_headings_not_three_bullets(self):
        body = ("TITLE: كيف تطور المبيعات\nSUMMARY: نراجع أداء التسويق بالأدلة.\n"
                "## المشكلة\n" + ("قياس المبيعات يساعدنا نفهم المشكلة ونتجنب قرارات متسرعة. " * 12) +
                "\n## التجربة\n" + ("نحدد فرضية ونقارن مجموعات وفترات عادلة قبل إصدار الحكم. " * 12) +
                "\nCONCLUSION: نبدأ باختبار صغير ثم نقيس النتائج.")
        self.assertEqual(check("linkedin_article", body), [])

    def test_rejects_missing_native_section(self):
        self.assertTrue(any("VISUALS" in issue for issue in check(
            "tiktok_video", "HOOK: سؤال\nSCRIPT: الفكرة\nCTA: شارك رأيك " * 6)))

    def test_owner_notes_are_not_publishable(self):
        main, note = split_owner_note("CAPTION: هسة نصيحة\nNOTE FOR OWNER: لا تنشر الملاحظة")
        self.assertNotIn("NOTE", main)
        self.assertIn("لا تنشر", note)

if __name__ == "__main__":
    unittest.main()
