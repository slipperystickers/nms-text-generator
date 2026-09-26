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
            [('FUTURE_Z','Boundary'),('INDUSTRIAL','Bulkhead'),('ORBITAL','Orbit'),('FOUNDRY','Forge')])

    def test_all_libraries(self):
        for key,name,_ in layout.FONTS:
            with self.subTest(font=key):
                data=layout.library(key)
                self.assertEqual(data['name'],name)
                self.assertEqual(set(data['glyphs']),set(string.ascii_uppercase+string.digits))
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
                self.assertEqual(layout.plan(string.ascii_uppercase+string.digits,font=key)['part_count'],sum(map(len,data['glyphs'].values())))

    def test_approved_counts(self):
        self.assertEqual({k:sum(map(len,layout.library(k)['glyphs'].values())) for k,n,p in layout.FONTS},
                         {'FUTURE_Z':646,'INDUSTRIAL':384,'ORBITAL':603,'FOUNDRY':646})
        self.assertEqual(len(layout.library('ORBITAL')['glyphs']['N']),13)
        self.assertEqual(len(layout.library('ORBITAL')['glyphs']['Q']),22)

    def test_multiline_and_alignment(self):
        for font,_,_ in layout.FONTS:
            p=layout.plan('ab\\n12',font=font,alignment='CENTER')
            self.assertEqual(p['text'],'AB\n12')
            self.assertEqual(p['lines'],2)
            self.assertEqual(p['placements'][0]['x'],-p['line_widths'][0]/2)
            self.assertEqual(p['placements'][2]['y'],-6.5)
            w=layout.library(font)['widths']['A']
            self.assertEqual(layout.plan('A A',font=font)['line_widths'],[w*2+3])
            self.assertEqual(layout.plan('AA',font=font,height=10,letter_gap=2)['line_widths'],[w*4+2])

    def test_invalid_input(self):
        for args in ({'text':'!'}, {'text':' '}, {'text':'A','font':'INVALID'},
                     {'text':'B'*2000}, {'text':'A','height':float('nan')},
                     {'text':'A','alignment':'BAD'}, {'text':'A','height':0}):
            with self.subTest(args=str(args)[:60]),self.assertRaises(ValueError):layout.plan(**args)

    def test_legacy_default(self):
        self.assertEqual(layout.plan('CCB'),layout.plan('CCB',font='FUTURE_Z'))

    def test_preview_files(self):
        for key,_,_ in layout.FONTS:
            data=(ROOT/'nms_text_generator'/'previews'/(key.lower()+'.png')).read_bytes()
            self.assertTrue(data.startswith(b'\x89PNG\r\n\x1a\n'))

if __name__=='__main__':unittest.main()
