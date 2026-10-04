import sys
import json
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]/'nms_text_generator'
pkg=types.ModuleType('color_test_package');pkg.__path__=[str(ROOT)];sys.modules[pkg.__name__]=pkg
from color_test_package import color_match as color,icon_fit,svg_geometry as svg

def doc(body):return '<svg>'+body+'</svg>'

class ColorTests(unittest.TestCase):
    def tearDown(self):color.read_regions.cache_clear();color.read_paints.cache_clear()

    def test_named_hex_rgb_and_alpha(self):
        for value in ('red','#f00','#ff0000','rgb(255,0,0)','rgb(100% 0% 0%)','rgba(255 0 0 / 100%)'):
            self.assertEqual(color.parse_color(value),((1,0,0),1))
        self.assertEqual(color.parse_color('rebeccapurple')[0],(102/255,51/255,153/255))
        self.assertAlmostEqual(color.parse_color('#f008')[1],136/255)

    def test_roundtrip_color_space_and_known_oklab(self):
        np.testing.assert_allclose(color.srgb(color.linear([.1,.5,.9])),[.1,.5,.9],atol=1e-8)
        np.testing.assert_allclose(color.oklab([1,1,1]),[1,0,0],atol=1e-7)
        np.testing.assert_allclose(color.oklab([0,0,0]),[0,0,0])

    def test_catalog_and_station_codes(self):
        entries=color.catalog()['palettes']
        self.assertEqual(len(entries),151)
        self.assertEqual([p['id'] for p in entries[115:]],[f'STATION{i}' for i in range(36)])
        self.assertEqual(len(color.candidates(False)),115)
        self.assertEqual(len(color.candidates(True)),151)
        self.assertTrue(all(c['user_data']==c['index'] for c in color.candidates(True)))

    def test_exact_available_colour_wins(self):
        for entry in color.candidates(True):
            match=color.nearest(color.srgb(entry['rgb']),True)
            self.assertLess(match['distance'],1e-7)
            np.testing.assert_allclose(match['rgb'],entry['rgb'])

    def test_saturated_blue_keeps_hue_when_blue_palette_is_available(self):
        blue=color.nearest((34/255,78/255,144/255))
        self.assertGreater(blue['rgb'][2],blue['rgb'][0])

    def test_currentcolor_group_use_and_stroke(self):
        source=doc('<defs><rect id="r" width="10" height="10"/></defs><g color="red" fill="currentColor"><use href="#r"/></g><path fill="none" stroke="blue" stroke-width="2" d="M0 20H20"/>')
        shapes,bounds,paints=svg.read_svg(source,with_colors=True)
        self.assertEqual(paints,[(1,0,0),(0,0,1)])
        self.assertEqual(len(shapes),2)

    def test_partial_opacity_and_gradient_rejected_only_in_color_mode(self):
        for attrs in ('fill="url(#g)"','fill="rgba(255,0,0,.5)"','opacity=".5"','fill-opacity=".7"'):
            source=doc(f'<rect width="20" height="10" {attrs}/>')
            svg.read_svg(source)
            with self.assertRaises(ValueError):svg.read_svg(source,with_colors=True)
        with self.assertRaises(ValueError):svg.read_svg(doc('<g opacity=".5"><rect width="10" height="10"/></g>'),with_colors=True)

    def test_hidden_colours_do_not_create_regions(self):
        source=doc('<rect width="20" height="10" fill="red"/><rect width="20" height="10" fill="blue"/>')
        bounds,regions,_=color.preflight(source)
        self.assertEqual(len(regions),1)
        self.assertEqual(regions[0][1]['user_data'],color.nearest((0,0,1))['user_data'])

    def test_overlap_and_hole_obey_painter_order(self):
        source=doc('<rect width="100" height="100" fill="red"/><path fill="blue" fill-rule="evenodd" d="M20 20H80V80H20Z M40 40H60V60H40Z"/>')
        bounds,regions,_=color.preflight(source)
        for loops,match in regions:
            visible=icon_fit.contains([(loops,'nonzero')],[[.1,.1],[.3,.3],[.5,.5]])
            expected=[True,False,True] if match['user_data']==color.nearest((1,0,0))['user_data'] else [False,True,False]
            np.testing.assert_array_equal(visible,expected)

    def test_collinear_adjacent_regions_and_shared_bounds(self):
        source=doc('<rect width="100" height="50" fill="red"/><rect x="100" width="100" height="50" fill="blue"/>')
        bounds,regions,_=color.preflight(source)
        self.assertEqual(bounds,[1,.25]);self.assertEqual(len(regions),2)
        result=color.fit_svg(source,35,40)
        self.assertLessEqual(result['part_count'],40)
        self.assertGreater(result['coverage'],.95)
        for panel,code in zip(result['panels'],result['panel_userdata']):
            if result.get('layered'):
                shapes,_=svg.read_svg(source);loops,_=icon_fit.prepare_outline(shapes)
                self.assertTrue(icon_fit.Boundary(loops).inside(panel))
            else:
                region=next(loops for loops,m in regions if m['user_data']==code)
                self.assertTrue(icon_fit.Boundary(region).inside(panel))

    def test_continuous_backing_saves_parts_and_orders_colour_depths(self):
        source=doc('<rect width="100" height="80" fill="red"/><rect x="8" y="8" width="84" height="64" fill="blue"/>')
        separate=color.fit_regions(source,100,100);result=color.fit_svg(source,100,100)
        self.assertTrue(result['layered'])
        self.assertLess(result['part_count'],separate['part_count'])
        self.assertGreaterEqual(result['coverage'],separate['coverage']-.001)
        red=color.nearest((1,0,0))['user_data'];blue=color.nearest((0,0,1))['user_data']
        red_depths=[d for c,d in zip(result['panel_userdata'],result['panel_depths']) if c==red]
        blue_depths=[d for c,d in zip(result['panel_userdata'],result['panel_depths']) if c==blue]
        self.assertLess(max(red_depths),min(blue_depths))
        self.assertTrue(all(0<=d<=1 for d in result['panel_depths']))
        self.assertEqual(sum(r['parts'] for r in result['layer_stats']),result['part_count'])
        self.assertLessEqual(result['outline_parts'],result['part_count'])

    def test_occlusion_pruning_never_erases_foreground_with_background(self):
        # The small foreground is covered geometrically by an earlier backing,
        # but deleting it would erase its colour. Only later paint can hide it.
        panels=[(.5,.5,.3,0),(.5,.5,.1,0),(.85,.9,.05,0)]
        retained=[]
        self.assertEqual(icon_fit.prune_contained(panels,0,later_only=True,kept_indices=retained),0)
        self.assertEqual(retained,[0,1,2])
        reverse=[panels[1],panels[0],panels[2]];retained=[]
        self.assertEqual(icon_fit.prune_contained(reverse,0,later_only=True,kept_indices=retained),1)
        self.assertEqual(retained,[1,2])

    def test_flattened_frame_can_become_backing_with_an_inlay(self):
        source=doc('<path fill="red" fill-rule="evenodd" d="M0 0H100V80H0Z M8 8H92V72H8Z"/><rect x="8" y="8" width="84" height="64" fill="blue"/>')
        separate=color.fit_regions(source,100,100);result=color.fit_svg(source,100,100)
        self.assertEqual(result['fit_strategy'],'backing_inlays')
        self.assertLess(result['part_count'],separate['part_count'])
        self.assertGreater(result['coverage'],.98)

    def test_backing_does_not_fill_transparent_holes(self):
        source=doc('<path fill="red" fill-rule="evenodd" d="M0 0H100V100H0Z M35 35H65V65H35Z"/><rect x="8" y="8" width="18" height="18" fill="blue"/>')
        result=color.fit_svg(source,70,100)
        self.assertFalse(any(icon_fit.panel_mask(p,np.array([.5]),np.array([.5]))[0] for p in result['panels']))
        self.assertLess(result['excess'],.001)

    def test_small_component_is_fitted_locally_without_changing_footprint(self):
        loop=np.array([[0,0],[10,0],[10,40],[50,40],[50,0],[60,0],[60,50],[0,50]],float)/1000+(.6,.4)
        result=color.fit_components([loop],[1,1],{},100,60)
        self.assertGreater(result['coverage'],.98)
        self.assertLessEqual(result['part_count'],60)
        boundary=icon_fit.Boundary([loop])
        self.assertTrue(all(boundary.inside(p) for p in result['panels']))

    def test_one_global_budget_and_determinism(self):
        source=(Path(__file__).parent/'fixtures/icon_colors.svg').read_text()
        for cap in (1,3,30):
            a=color.fit_svg(source,30,cap);b=color.fit_svg(source,30,cap)
            self.assertLessEqual(a['part_count'],cap)
            self.assertEqual(a['panels'],b['panels']);self.assertEqual(len(a['panel_userdata']),a['part_count'])
            if cap<4:self.assertTrue(a['budget_hit'])

    def test_coloured_t_preserves_a_continuous_straight_top(self):
        # Area coverage concealed visible steps in this simple horizontal beam.
        source=doc('<path fill="#BBC3BD" d="M0 0H100V20H60V75Q60 80 65 80V85H35V80Q40 80 40 75V20H0Z"/>')
        result=color.fit_svg(source,100,80)
        x=np.linspace(.005,.995,501);y=np.full_like(x,1e-6)
        covered=np.zeros(len(x),bool)
        for panel in result['panels']:covered|=icon_fit.panel_mask(panel,x,y)
        self.assertTrue(covered.all(),'The straight top must be continuous, not inset by random amounts')
        self.assertGreater(result['outline_parts'],0)
        self.assertGreater(result['coverage'],.99)

    def test_coloured_ring_has_a_bounded_faceted_edge(self):
        source=doc('<path fill="orange" fill-rule="evenodd" d="M0 50A50 50 0 1 1 100 50A50 50 0 1 1 0 50Z M8 50A42 42 0 1 1 92 50A42 42 0 1 1 8 50Z"/>')
        result=color.fit_svg(source,100,180)
        angle=np.linspace(0,2*np.pi,1440,endpoint=False)
        # Every radial direction reaches within 0.3% of the logo width of the
        # original circle. Fill-first used conspicuous, irregular deeper steps.
        x=.5+.497*np.cos(angle);y=.5+.497*np.sin(angle)
        covered=np.zeros(len(x),bool)
        for panel in result['panels']:covered|=icon_fit.panel_mask(panel,x,y)
        self.assertTrue(covered.all())
        self.assertGreater(result['outline_parts'],0)
        self.assertLessEqual(result['part_count'],180)

    def test_recovery_needs_new_approval(self):
        source=doc('<rect width="20" height="10" fill="red"/>')
        with patch.object(icon_fit,'visible_loops',side_effect=ValueError('numeric seam')):
            with patch.object(color.svg_outline,'trace_mask',side_effect=AssertionError('Unapproved trace')):
                with self.assertRaises(icon_fit.SimplificationRequired):color.preflight(source)
            bounds,regions,info=color.preflight(source,allow_simplify=True)
            self.assertTrue(info['outline_recovered'])
            with self.assertRaises(icon_fit.SimplificationRequired):color.preflight(source)

    def test_reserved_payload_bits_preserved(self):
        base=(1<<40)|(1<<17)|(1<<16)|(1<<8)|(3<<24)|8
        result=color.apply_userdata(base,150)
        self.assertEqual(result,(1<<40)|(1<<17)|(1<<16)|(1<<8)|150)

    def test_manual_choices_merge_regions_and_retain_source(self):
        source=doc('<rect width="100" height="50" fill="red"/><rect x="100" width="100" height="50" fill="blue"/>')
        automatic=color.fit_svg(source,30,40)
        choices=color.overrides_json({'#ff0000':150,'#0000ff':150})
        manual=color.fit_svg(source,30,40,False,choices)
        self.assertEqual(manual['color_count'],1)
        self.assertEqual(set(manual['panel_userdata']),{150})
        self.assertGreater(manual['coverage'],.95)
        self.assertEqual(set(map(tuple,manual['color_matches'][0]['source_rgbs'])),{(1,0,0),(0,0,1)})
        self.assertEqual(automatic['color_count'],2)
        self.assertEqual(color.fit_svg(source,30,40)['panel_userdata'],automatic['panel_userdata'])

    def test_choices_validated_and_canonical(self):
        self.assertEqual(color.overrides_json({'#ff0000':5,'#0000ff':0}),' {"#0000FF":0,"#FF0000":5}'.strip())
        for value in ('[]','{"red":1}','{"#FF0000":151}','{"#FF0000":true}'):
            with self.assertRaises(ValueError):color.overrides_json(value)

    def test_complex_layered_emblem_fills_shapes_under_global_cap(self):
        # This artwork previously spent all 519 parts on edges and covered
        # just 16% of its area. The control and the source are left unchanged.
        source=(Path(__file__).parent/'fixtures/icon_layered_emblem.svg').read_text()
        result=color.fit_svg(source,100,519)
        self.assertTrue(result['layered'])
        self.assertLessEqual(result['part_count'],519)
        self.assertGreater(result['coverage'],.6)
        self.assertGreater(result['silhouette_coverage'],.9)
        self.assertGreater(result['silhouette_edge_coverage'],.65)
        self.assertLess(result['excess'],.001)
        self.assertTrue(result['unfilled'])
        self.assertEqual(len(result['panel_userdata']),result['part_count'])

    def test_layered_coverage_detects_missing_foreground_colour(self):
        # A complete background alone is not a complete coloured icon.
        source=doc('<rect width="100" height="100" fill="red"/>'+
                   ''.join(f'<rect x="{i*4}" width="3" height="100" fill="blue"/>' for i in range(25)))
        result=color.fit_svg(source,30,5)
        self.assertTrue(result['layered'])
        self.assertLessEqual(result['part_count'],5)
        # A continuous blue backing can legitimately cover more than half
        # these stripes. Verify final paint coverage independently instead.
        n=result['resolution'];yy,xx=np.mgrid[:n,:n];xx=(xx+.5)/n;yy=(yy+.5)/n
        target=np.full((n,n),-1);painted=np.full((n,n),-1)
        for shape,match in zip(*[color.read_paints(source)[j] for j in (0,2)]):
            target[svg.rasterize([shape],n)]=match['user_data']
        for panel,code in zip(result['panels'],result['panel_userdata']):
            painted[icon_fit.panel_mask(panel,xx,yy)]=code
        self.assertAlmostEqual(result['coverage'],((painted==target)&(target>=0)).sum()/(target>=0).sum())
        self.assertLess(result['coverage'],.95)
        self.assertTrue(result['budget_hit'])

    def test_girder_native_faces_cover_previous_subpixel_and_visible_holes(self):
        fixtures=Path(__file__).parent/'fixtures'
        source=(fixtures/'icon_girder.svg').read_text()
        points=np.asarray(json.loads((fixtures/'icon_girder_gap_samples.json').read_text()))
        result=color.fit_svg(source,100,300)
        covered=np.zeros(len(points),bool)
        # Independent measured native back-face projection: no preview mask.
        calibration=3.0078125/2.9921875
        for x,y,w,a in result['panels']:
            scale=w/1.260742425918579*calibration
            delta=points-[x,y];c,s=np.cos(a),np.sin(a)
            covered|=(abs(delta[:,0]*c+delta[:,1]*s)<=2.9921875*scale/2)&(abs(-delta[:,0]*s+delta[:,1]*c)<=1.250976800918579*scale/2)
        self.assertTrue(covered.all(),f'{int((~covered).sum())} known hole samples remain uncovered')
        self.assertLessEqual(result['part_count'],300)
        self.assertEqual(result['remaining_seams'],0)
        self.assertEqual(sum(r['parts'] for r in result['layer_stats']),result['part_count'])
        self.assertGreater(result['coverage'],.98)

if __name__=='__main__':unittest.main()
