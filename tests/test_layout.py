import importlib.util
import json
import math
import string
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('text_layout',ROOT/'nms_text_generator'/'layout.py')
layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)

class LayoutTests(unittest.TestCase):
    def test_names_and_stable_ids(self):
        self.assertEqual([(k,n) for k,n,_ in layout.FONTS],
            [('FUTURE_Z','Boundary'),('INDUSTRIAL','Bulkhead'),('ORBITAL','Orbit'),('FOUNDRY','Forge'),('VECTOR','Vector')])

    def test_all_libraries(self):
        for key,name,_ in layout.FONTS:
            with self.subTest(font=key):
                data=layout.library(key)
                self.assertEqual(data['name'],name)
                self.assertEqual(set(data['glyphs']),set(layout.CHARACTERS))
                for rows in data['glyphs'].values():
                    for r in rows:
                        self.assertEqual(r['ObjectID'],'^BUILDFLATPANEL')
                        a,b=r['Up'],r['At']
                        lengths=[math.sqrt(sum(v*v for v in vec)) for vec in (a,b)]
                        self.assertGreater(min(lengths),0)
                        # NMS serialization stores scale in Up; At is normalized.
                        # The native Blender test validates the reconstructed uniform matrix.
                        self.assertAlmostEqual(lengths[1],1,places=5)
                        self.assertLess(abs(sum(x*y for x,y in zip(a,b)))/(lengths[0]*lengths[1]),1e-5)
                self.assertEqual(layout.plan(layout.CHARACTERS,font=key)['part_count'],sum(map(len,data['glyphs'].values())))

    def test_approved_counts(self):
        self.assertEqual({k:sum(len(layout.library(k)['glyphs'][c]) for c in string.ascii_uppercase+string.digits) for k,n,p in layout.FONTS},
                         {'FUTURE_Z':646,'INDUSTRIAL':384,'ORBITAL':603,'FOUNDRY':646,'VECTOR':626})
        self.assertEqual(len(layout.library('ORBITAL')['glyphs']['N']),13)
        self.assertEqual(len(layout.library('ORBITAL')['glyphs']['Q']),22)

    def test_multiline_and_alignment(self):
        for font,_,_ in layout.FONTS:
            p=layout.plan('ab\n12',font=font,alignment='CENTER')
            self.assertEqual(p['text'],'AB\n12')
            self.assertEqual(p['lines'],2)
            self.assertEqual(p['placements'][0]['x'],-p['line_widths'][0]/2)
            self.assertEqual(p['placements'][2]['y'],-6.5)
            w=layout.library(font)['widths']['A']
            self.assertEqual(layout.plan('A A',font=font)['line_widths'],[w*2+3])
            self.assertEqual(layout.plan('AA',font=font,height=10,letter_gap=2)['line_widths'],[w*4+2])

    def test_invalid_input(self):
        for args in ({'text':'@'}, {'text':' '}, {'text':'A','font':'INVALID'},
                     {'text':'B'*2000}, {'text':'A','height':float('nan')},
                     {'text':'A','alignment':'BAD'}, {'text':'A','height':0}):
            with self.subTest(args=str(args)[:60]),self.assertRaises(ValueError):layout.plan(**args)

    def test_legacy_default(self):
        self.assertEqual(layout.plan('CCB'),layout.plan('CCB',font='FUTURE_Z'))

    def test_vector_width_and_part_budget(self):
        data=layout.library('VECTOR')
        self.assertEqual(data['widths']['I'],.64)
        self.assertEqual({w for c,w in data['widths'].items() if c!='I' and c.isalnum()},{4.9})
        self.assertEqual(data['max_parts_per_character'],32)
        self.assertEqual(len(data['glyphs']['D']),22)
        self.assertEqual(len(data['glyphs']['7']),8)
        self.assertEqual(len(data['glyphs']['C']),23)
        self.assertEqual({c:len(data['glyphs'][c]) for c in 'ARTS'}, {'A':17,'R':25,'T':7,'S':29})
        self.assertEqual(layout.plan('X'*93,font='VECTOR')['part_count'],2976)
        with self.assertRaises(ValueError):layout.plan('X'*94,font='VECTOR')

    def test_vector_i_spacing(self):
        for alignment in ('LEFT','CENTER','RIGHT'):
            for height,gap in ((5,1),(10,.5)):
                p=layout.plan('RIAL',font='VECTOR',height=height,letter_gap=gap,alignment=alignment)
                places=p['placements'];scale=height/5
                self.assertAlmostEqual(places[1]['x']-places[0]['x'],4.9*scale+gap)
                self.assertAlmostEqual(places[2]['x']-places[1]['x'],.64*scale+gap)
        for part in layout.library('VECTOR')['glyphs']['I']:
            self.assertAlmostEqual(part['Position'][0],.32,places=5)
        self.assertEqual(layout.plan('TYNDUSTRIAL ASTRONAUTICS',font='VECTOR')['part_count'],367)

    def test_preview_files(self):
        for name in ('nmscribe.png','nmscribe_credit.png','nmscribe_sidebar.png'):
            self.assertTrue((ROOT/'nms_text_generator'/'previews'/name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
        for key,_,_ in layout.FONTS:
            data=(ROOT/'nms_text_generator'/'previews'/(key.lower()+'.png')).read_bytes()
            self.assertTrue(data.startswith(b'\x89PNG\r\n\x1a\n'))

    def test_symbols_and_backslash_escaping(self):
        self.assertEqual(len(layout.CHARACTERS),49)
        self.assertEqual(layout.normalize(r'A\nB'),r'A\NB')
        self.assertEqual(layout.normalize(r'A\\nB'),r'A\\NB')
        self.assertEqual(layout.decode_legacy(r'A\nB'),'A\nB')
        self.assertEqual(layout.decode_legacy(r'A\\nB'),r'A\nB')
        self.assertEqual(layout.normalize(r'A\B'),r'A\B')
        self.assertEqual(layout.normalize('\\'),'\\')
        for key,_,_ in layout.FONTS:
            p=layout.plan(layout.SYMBOLS,font=key)
            self.assertEqual(p['character_count'],13)
            self.assertEqual(p['text'],layout.SYMBOLS)
            self.assertEqual(layout.plan(r'\\',font=key)['character_count'],2)
            data=layout.library(key)
            self.assertEqual(len(data['glyphs']['.']),3)
            self.assertEqual(layout.plan('3.14',font=key)['text'],'3.14')
            for c in layout.SYMBOLS:
                self.assertLessEqual(len(data['glyphs'][c]),32 if c=='?' else 8)

    def test_vector_y_optical_spacing(self):
        for alignment in ('LEFT', 'CENTER', 'RIGHT'):
            for height, gap in ((5, 1), (10, 1), (5, .1), (5, 0)):
                p=layout.plan('TYNY', font='VECTOR', height=height,
                              letter_gap=gap, alignment=alignment)
                correction=min(gap/2, .3*height/5)
                for a,b in zip(p['placements'],p['placements'][1:]):
                    self.assertAlmostEqual(b['x']-a['x'],4.9*height/5+gap-correction)
                yy=layout.plan('YY', font='VECTOR', height=height, letter_gap=gap)
                self.assertAlmostEqual(yy['placements'][1]['x'],4.9*height/5+gap-2*correction)
        self.assertEqual(layout.plan('Y Y', font='VECTOR')['line_widths'],[12.8])
        self.assertEqual(layout.plan('TY', font='INDUSTRIAL')['line_widths'],
                         [sum(layout.library('INDUSTRIAL')['widths'][c] for c in 'TY')+1])

if __name__=='__main__':unittest.main()
