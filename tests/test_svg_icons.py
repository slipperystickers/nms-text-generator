import importlib.util
import sys
import types
import unittest
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]/'nms_text_generator'
pkg=types.ModuleType('svg_test_package');pkg.__path__=[str(ROOT)];sys.modules[pkg.__name__]=pkg
from svg_test_package import svg_geometry as svg,icon_fit

def doc(body):return '<svg xmlns="http://www.w3.org/2000/svg">'+body+'</svg>'
RECT=doc('<rect width="100" height="50"/>')
RING=doc('<path fill-rule="evenodd" d="M0 0H100V100H0Z M30 30H70V70H30Z"/>')

class SvgTests(unittest.TestCase):
    def mask(self,body):return svg.rasterize(svg.read_svg(doc(body))[0],100)
    def test_evenodd_hole(self):
        mask=svg.rasterize(svg.read_svg(RING)[0],100)
        self.assertFalse(mask[50,50]);self.assertTrue(mask[5,5])
    def test_nonzero_hole(self):
        mask=self.mask('<path d="M0 0H100V100H0Z M30 30V70H70V30Z"/>')
        self.assertFalse(mask[50,50])
    def test_nonzero_same_direction_fills(self):
        self.assertTrue(self.mask('<path d="M0 0H100V100H0Z M30 30H70V70H30Z"/>')[50,50])
    def test_transforms_use_and_hidden(self):
        body='<defs><rect id="r" width="20" height="10"/></defs><g transform="translate(10,30) scale(2)"><use href="#r"/></g><circle display="none" r="1000"/>'
        _,bounds=svg.read_svg(doc(body));self.assertEqual(bounds,[1,.5])
    def test_curves_and_arcs(self):
        for path in ['M0 0 C20 0 30 20 40 40 S60 60 80 40L0 40Z','M0 0Q20 40 40 0T80 0V60H0Z','M0 50A50 50 0 1 1 100 50A50 50 0 1 1 0 50Z']:
            self.assertGreater(self.mask('<path d="'+path+'"/>').sum(),100)
    def test_stroke(self):
        self.assertGreater(self.mask('<polyline points="0,0 50,50 100,0" fill="none" stroke="red" stroke-width="10" stroke-linejoin="round"/>').sum(),500)
    def test_hidden_parent(self):
        with self.assertRaises(ValueError):svg.read_svg(doc('<g opacity="0"><rect width="10" height="10"/></g>'))
    def test_transparent_paint(self):
        for color in ('transparent','rgba(0,0,0,0)','#FFFFFF00','#fff0'):
            with self.assertRaises(ValueError):svg.read_svg(doc(f'<rect width="10" height="10" fill="{color}"/>'))
    def test_more_accuracy_retains_curved_detail(self):
        source=doc('<circle cx="50" cy="50" r="50"/>')
        low=icon_fit.fit_svg(source,10,300);high=icon_fit.fit_svg(source,90,300)
        self.assertGreater(high['resolution'],low['resolution'])
        self.assertGreater(high['part_count'],low['part_count'])
    def test_unsafe_or_unsupported(self):
        for body in ['<script/>','<image href="file:///secret"/>','<text>Hi</text>','<path d="M0 0L10 0L10 10Z" clip-path="url(#a)"/>','<style>path {fill:red;}</style><path d="M0 0L10 10Z"/>','<use href="https://example.com/a.svg"/>']:
            with self.assertRaises(ValueError):svg.read_svg(doc(body))
        with self.assertRaises(ValueError):svg.read_svg('<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///secret">]><svg/>')
    def test_recursive_use(self):
        with self.assertRaises(ValueError):svg.read_svg(doc('<defs><g id="a"><use href="#a"/></g></defs><use href="#a"/>'))
    def test_external_doctype_is_ignored_without_entities(self):
        for declaration in [
            '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">',
            '<!DOCTYPE svg SYSTEM "file:///this-file-must-not-be-opened.dtd">',
            '<!DOCTYPE svg>',
        ]:
            shapes,bounds=svg.read_svg(declaration+RECT)
            self.assertEqual(bounds,[1,.5]);self.assertTrue(svg.rasterize(shapes,64).any())
        for declaration in ('<!DOCTYPE svg [<!ELEMENT svg ANY>]>','<!DOCTYPE svg [<!ENTITY % x SYSTEM "https://example.com"> %x;]>'):
            with self.assertRaises(ValueError):svg.read_svg(declaration+RECT)
    def test_union_removes_hidden_and_collinear_edges(self):
        source=doc('<rect width="100" height="50"/><rect x="50" width="100" height="50"/>')
        loops=icon_fit.visible_loops(svg.read_svg(source)[0])
        self.assertEqual(len(loops),1)
        simplified=icon_fit.simplify_loop(loops[0],.001)
        self.assertEqual(len(simplified),4)
    def test_arbitrary_outline_angle_and_vector_containment(self):
        source=doc('<g transform="rotate(17)"><rect width="100" height="50"/></g>')
        result=icon_fit.fit_svg(source,85,80)
        self.assertTrue(any(abs(np.sin(a*4))>.1 for x,y,w,a in result['panels'][:result['outline_parts']]))
        loops=icon_fit.visible_loops(svg.read_svg(source)[0])
        boundary=icon_fit.Boundary([icon_fit.simplify_loop(c,result['outline_tolerance']) for c in loops])
        self.assertTrue(all(boundary.inside(p) for p in result['panels']))
        self.assertGreater(result['coverage'],.99)
    def test_vector_check_rejects_small_hole_inside_rectangle(self):
        source=doc('<path fill-rule="evenodd" d="M0 0H100V100H0Z M48 48H52V52H48Z"/>')
        boundary=icon_fit.Boundary(icon_fit.visible_loops(svg.read_svg(source)[0]))
        self.assertFalse(boundary.inside((.5,.5,.2,0)))
        self.assertTrue(boundary.inside((.5,.15,.1,0)))
    def test_bad_path(self):
        for p in ['M0','M0 0X10 10','M0 0C1 1']:
            with self.assertRaises(ValueError):svg.paths(p)
    def test_fit_budget_aspect_hole(self):
        result=icon_fit.fit_svg(RING,30,25)
        self.assertLessEqual(result['part_count'],25)
        self.assertGreater(result['coverage'],.5)
        for x,y,w,a in result['panels']:
            dx=.5-x;dy=.5-y;c=np.cos(a);s=np.sin(a)
            self.assertFalse(abs(c*dx+s*dy)<w*icon_fit.RATIO/2 and abs(-s*dx+c*dy)<w/2)
    def test_simple_rect_efficient_and_deterministic(self):
        a=icon_fit.fit_svg(RECT,30,30);b=icon_fit.fit_svg(RECT,30,30)
        self.assertEqual(a['panels'],b['panels']);self.assertLess(a['part_count'],15)
        self.assertGreater(a['coverage'],.95)
    def test_tight_budget_and_disconnected(self):
        source=doc('<circle cx="15" cy="15" r="15"/><circle cx="85" cy="85" r="15"/>')
        result=icon_fit.fit_svg(source,20,5);self.assertLessEqual(result['part_count'],5)
        self.assertTrue(result['budget_hit'])

if __name__=='__main__':unittest.main()
