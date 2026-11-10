"""Delivery layout must preserve approved wording and separate filming directions."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bot'))
from output_layout import render_creator_copy

VIDEO = ('HOOK: رسائلك هواية؟\nSCRIPT: السعر {{السعر}} واضح.\n\n'
         'شنو الخطوة الجاية؟\nVISUALS: لقطة موبايل.\nقطع على الرد.\nCTA: دزها لصاحبك.')

class LayoutTests(unittest.TestCase):
    def test_video_aliases_have_clear_sections_and_numbered_blocks(self):
        for fmt in ('tiktok_video','instagram_reel','reel'):
            output=render_creator_copy(VIDEO,fmt)
            for label in ('الافتتاحية','النص المنطوق','المشاهد المقترحة','دعوة التفاعل'):
                self.assertIn(label,output)
            self.assertIn('1. السعر {{السعر}} واضح.\n\n2. شنو الخطوة الجاية؟',output)
            self.assertIn('1. لقطة موبايل.\n\n2. قطع على الرد.',output)
            for raw in ('HOOK:', 'SCRIPT:', 'VISUALS:', 'CTA:'):
                self.assertNotIn(raw,output)
            for body in ('رسائلك هواية؟','السعر {{السعر}} واضح.','شنو الخطوة الجاية؟',
                         'لقطة موبايل.','قطع على الرد.','دزها لصاحبك.'):
                self.assertEqual(output.count(body),1)

    def test_other_formats_and_short_story_keep_their_existing_layout(self):
        self.assertEqual(render_creator_copy('CAPTION: هلا','instagram_post'),'CAPTION: هلا')
        self.assertEqual(render_creator_copy('STORY: شنو رأيك؟','story'),'شنو رأيك؟')

    def test_missing_video_fields_cannot_render_as_complete_script(self):
        with self.assertRaises(ValueError):
            render_creator_copy('HOOK: ناقص','tiktok_video')
