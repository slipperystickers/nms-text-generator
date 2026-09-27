import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('nms_layout',Path(__file__).resolve().parents[1]/'nms_text_generator/layout.py')
layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)

class BreakTags(unittest.TestCase):
    def test_forms(self):
        for tag in ('<br>','<br/>','<br />','<BR>'):
            self.assertEqual(layout.normalize('one'+tag+'two'),'ONE\nTWO')
            self.assertEqual(layout.plan('A'+tag+'B')['lines'],2)
    def test_literal_and_legacy(self):
        self.assertEqual(layout.normalize(r'A\nB'),r'A\NB')
        self.assertEqual(layout.field_text('A\r\nB\nC'),'A<br>B<br>C')
        self.assertEqual(layout.normalize('A<br><br>B'),'A\n\nB')
    def test_other_html_rejected(self):
        for value in ('<b>A</b>','A<hr>B','<script>'):
            with self.assertRaises(ValueError):layout.normalize(value)
