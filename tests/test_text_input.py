import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('text_input',Path(__file__).resolve().parents[1]/'nms_text_generator/text_input.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class InputTests(unittest.TestCase):
    def test_shift_enter_literal_backslash(self):
        b=m.Buffer('A');b.key('RET',shift=True);b.replace(r'B\nC')
        self.assertEqual(b.text,'A\nB\\nC')
        self.assertFalse(b.key('RET'))
        self.assertEqual(b.text,'A\nB\\nC')
    def test_selection_clipboard_delete_undo(self):
        b=m.Buffer('ABC');b.key('A',ctrl=True)
        self.assertEqual(b.selected(),'ABC')
        b.replace('X\r\nY');self.assertEqual(b.text,'X\nY')
        b.key('Z',ctrl=True);self.assertEqual(b.text,'ABC')
        b.key('Y',ctrl=True);self.assertEqual(b.text,'X\nY')
        b.key('BACK_SPACE');self.assertEqual(b.text,'X\n')
        b.key('HOME',ctrl=True);b.key('DEL');self.assertEqual(b.text,'\n')
    def test_movement_and_limits(self):
        b=m.Buffer('ABC\nD',limit=8);b.key('UP_ARROW');self.assertEqual(b.cursor,1)
        b.key('HOME');b.key('RIGHT_ARROW',shift=True)
        self.assertEqual(b.selected(),'A')
        self.assertFalse(b.replace('TOO MUCH TEXT'));self.assertEqual(b.text,'ABC\nD')
        self.assertEqual(b.rows(2),[(0,'AB'),(2,'C'),(4,'D')])
