import importlib.util
import sys
import types
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]/'nms_text_generator'
pkg=types.ModuleType('svg_test_package');pkg.__path__=[str(ROOT)];sys.modules[pkg.__name__]=pkg
from svg_test_package import svg_geometry as svg,icon_fit,svg_outline

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

    def test_fill_growth_retains_coverage_and_respects_a_hole(self):
        boundary=icon_fit.Boundary(icon_fit.visible_loops(svg.read_svg(RING)[0]))
        panels=[(.35,.15,.07,0),(.65,.85,.07,0)]
        original=[icon_fit.panel_corners(p) for p in panels]
        self.assertGreater(icon_fit.enlarge_fill(boundary,panels,0),0)
        for panel,corners in zip(panels,original):
            self.assertTrue(boundary.inside(panel))
            self.assertTrue(icon_fit.panel_mask(panel,corners[:,0],corners[:,1]).all())
        self.assertFalse(any(icon_fit.panel_mask(p,np.array([.5]),np.array([.5]))[0] for p in panels))

    def test_collective_pruning_keeps_outline_and_rejects_a_gap(self):
        panels=[(-.2,0,.3,0),(.2,0,.3,0),(0,0,.2,0)]
        outline=list(panels[:2])
        self.assertEqual(icon_fit.prune_contained(panels,2),1)
        self.assertEqual(panels,outline)
        gap=[(-.38,0,.3,0),(.38,0,.3,0),(0,0,.2,0)]
        self.assertEqual(icon_fit.prune_contained(gap,2),0)

    def test_polygon_coverage_proof_retains_a_tiny_internal_hole(self):
        def rect(x0,y0,x1,y1):return np.array([[x0,y0],[x1,y0],[x1,y1],[x0,y1]],float)
        fragments=[rect(0,0,1,1)]
        # The uncovered pocket misses all rectangle corner/midpoint probes.
        for cover in (rect(0,0,.61,1),rect(.63,0,1,1),rect(0,0,1,.31),rect(0,.33,1,1)):
            fragments=[p for f in fragments for p in icon_fit.subtract_convex(f,cover)]
        area=sum(abs(icon_fit.cross(p,np.roll(p,-1,axis=0)).sum())/2 for p in fragments)
        self.assertAlmostEqual(area,.02*.02,places=10)

    def test_exposed_native_edges_exclude_covered_parallel_and_rotated_faces(self):
        for angle in (0,.37,np.pi/2):
            panels=[(.5,.5,.2,angle),(.5,.5,.1,angle)]
            points=icon_fit.exposed_face_points(panels)
            self.assertEqual(len(points),4)
            c,s=np.cos(angle),np.sin(angle);delta=points-[.5,.5]
            inside=(abs(delta[:,0]*c+delta[:,1]*s)<.2*icon_fit.RATIO/2)&(abs(-delta[:,0]*s+delta[:,1]*c)<.2*icon_fit.FACE_SHORT/2)
            self.assertFalse(inside.any())

    def test_exposed_native_edges_find_a_crack_smaller_than_a_preview_pixel(self):
        width=.2;gap=2e-6
        panels=[(.5,.4,width,0),(.5,.4+width*icon_fit.FACE_SHORT+gap,width,0)]
        lower=.4+width*icon_fit.FACE_SHORT/2
        points=icon_fit.exposed_face_points(panels)
        self.assertTrue(np.any((points[:,1]>lower)&(points[:,1]<lower+gap)))

    def test_native_rim_has_a_clear_exit_but_an_internal_seam_is_blocked(self):
        panels=[(.5,.5,.2,0)]
        self.assertEqual(icon_fit.face_segments_blocked(panels,[[.5,.399]],[[.5,.398]]).tolist(),[False])
        self.assertEqual(icon_fit.face_segments_blocked(panels,[[.5,.399]],[[.5,.601]]).tolist(),[True])

    def test_face_growth_preserves_the_old_native_face_and_intentional_holes(self):
        boundary=icon_fit.Boundary([np.array([[0,0],[1,0],[1,1],[0,1]],float)])
        old=(.3,.3,.1,0);point=np.array([.5,.3])
        grown=icon_fit.expand_face_to_point(boundary,old,point)
        self.assertIsNotNone(grown);self.assertTrue(boundary.inside(grown))
        corners=icon_fit.panel_corners(old);corners[:,1]=.3+(corners[:,1]-.3)*icon_fit.FACE_SHORT
        probes=np.vstack((corners,point));x,y,w,a=grown
        self.assertTrue((abs(probes[:,0]-x)<=w*icon_fit.RATIO/2+1e-10).all())
        self.assertTrue((abs(probes[:,1]-y)<=w*icon_fit.FACE_SHORT/2+1e-10).all())
        ring=icon_fit.Boundary(icon_fit.visible_loops(svg.read_svg(RING)[0]))
        self.assertIsNone(icon_fit.expand_face_to_point(ring,(.35,.15,.07,0),np.array([.5,.5])))
    def test_bad_path(self):
        for p in ['M0','M0 0X10 10','M0 0C1 1','M0 0L1e999 2Z']:
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

    def test_dense_exporter_rectangle_cleans_before_union_limit(self):
        source=doc('<path d="M0 0'+''.join(f'C{i+.3} 0 {i+.6} 0 {i+1} 0' for i in range(501))+'V100H0Z"/>')
        raw,_=svg.read_svg(source,cleanup=False)
        self.assertGreater(sum(len(c) for cs,_ in raw for c in cs),12000)
        result=icon_fit.fit_svg(source,50,30)
        self.assertFalse(result['outline_recovered'])
        self.assertEqual(result['cleaned_segments'],4)
        self.assertGreater(result['coverage'],.99)

    def test_curve_sampling_limit_attempts_cleanup(self):
        source=doc('<path d="M0 0'+''.join(f'C{i+.3} 0 {i+.6} 0 {i+1} 0' for i in range(1800))+'V100H0Z"/>')
        shapes,_=svg.read_svg(source)
        self.assertEqual(sum(len(c) for cs,_ in shapes for c in cs),4)

    def test_complex_round_stroke_recovers_under_part_cap(self):
        points=' '.join(f'{i},{50+20*np.sin(i/20):.3f}' for i in range(700))
        source=doc(f'<polyline points="{points}" fill="none" stroke="black" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>')
        raw,_=svg.read_svg(source,cleanup=False)
        self.assertLess(sum(len(c) for cs,_ in raw for c in cs),6000)
        result=icon_fit.fit_svg(source,50,100)
        self.assertTrue(result['outline_recovered'])
        self.assertGreater(result['part_count'],0)
        self.assertLessEqual(result['part_count'],100)

    def test_failed_exact_union_recovers_instead_of_rejecting(self):
        shapes,_=svg.read_svg(RING)
        with patch.object(icon_fit,'visible_loops',side_effect=ValueError('numeric seam')):
            loops,info=icon_fit.prepare_outline(shapes)
        self.assertTrue(info['outline_recovered'])
        self.assertEqual(len(loops),2)
        self.assertFalse(icon_fit.contains([(loops,'nonzero')],[[.5,.5]])[0])

    def test_trace_handles_every_cell_case_borders_and_diagonal_contacts(self):
        rng=np.random.default_rng(7)
        for _ in range(8):
            mask=rng.random((16,16))>.45
            loops=svg_outline.trace_mask(mask)
            restored=svg.rasterize([(loops,'nonzero')],16)
            np.testing.assert_array_equal(restored,mask)
        loops=svg_outline.trace_mask(np.eye(2,dtype=bool))
        self.assertEqual(len(loops),2)

    def test_recovery_keeps_hole_island_and_winding(self):
        source=doc('<path fill-rule="evenodd" d="M0 0H100V100H0Z M20 20H80V80H20Z M40 40H60V60H40Z"/>')
        shapes,_=svg.read_svg(source)
        loops,_=svg_outline.recover(shapes,256)
        self.assertEqual(len(loops),3)
        np.testing.assert_array_equal(icon_fit.contains([(loops,'nonzero')],[[.1,.1],[.3,.3],[.5,.5]]),[True,False,True])
        before=svg.rasterize(shapes,256);after=svg.rasterize([(loops,'nonzero')],256)
        self.assertGreater((before&after).sum()/(before|after).sum(),.999)

    def test_batched_strokes_do_not_cancel_overlaps_or_fill_holes(self):
        source=doc('<path fill="none" stroke="white" stroke-width="5" d="M0 0H100V100H0Z M0 0V100H100V0Z"/>')
        shapes,_=svg.read_svg(source)
        mask=svg.rasterize(shapes,128)
        self.assertFalse(mask[64,64]);self.assertTrue(mask[64,2])

    def test_simplifier_handles_long_zigzag_without_recursion(self):
        points=np.column_stack((np.arange(1600),np.arange(1600)%2))
        np.testing.assert_array_equal(svg_outline.simplify_open(points,.01),points)

    def test_recovery_resource_guard_stays_enabled(self):
        yy,xx=np.mgrid[:330,:330]
        with self.assertRaisesRegex(ValueError,'too many tiny details'):
            svg_outline.trace_mask((xx+yy)%2==0)

    def test_preflight_requests_permission_before_tracing(self):
        points=' '.join(f'{i},{50+20*np.sin(i/20):.3f}' for i in range(700))
        source=doc(f'<polyline points="{points}" fill="none" stroke="black" stroke-width="5" stroke-linejoin="round"/>')
        shapes,_=svg.read_svg(source)
        with patch.object(svg_outline,'recover',side_effect=AssertionError('Must not trace before consent')):
            with self.assertRaises(icon_fit.SimplificationRequired):
                icon_fit.prepare_outline(shapes,allow_simplify=False)

    def test_preflight_does_not_prompt_for_simple_art(self):
        _,_,loops,info=icon_fit.read_outline(RECT,allow_simplify=False)
        self.assertFalse(info['outline_recovered']);self.assertEqual(len(loops),1)

    def test_previous_approved_import_does_not_bypass_new_prompt(self):
        source=doc('<path d="M0 0H100V100H0Z"/>')
        with patch.object(icon_fit,'visible_loops',side_effect=ValueError('numeric seam')):
            icon_fit.read_outline(source,allow_simplify=True)
            with self.assertRaises(icon_fit.SimplificationRequired):
                icon_fit.read_outline(source,allow_simplify=False)

    def test_round_sectors_preserve_stroke_silhouette(self):
        # Compare against the previous full-disk construction, including
        # mirrored/anisotropic transforms, both turn directions and reversals.
        for path in ('M0 0H40V40H0Z','M0 0L40 20L0 40','M0 0H40L0 1','M0 0H40H0'):
            for transform in ('','translate(100 0) scale(-2 .7)'):
                source=doc(f'<path d="{path}" transform="{transform}" fill="none" stroke="black" stroke-width="8" stroke-linejoin="round"/>')
                shapes,bounds=svg.read_svg(source)
                with patch.object(svg,'round_join',side_effect=lambda p,u,v,n,h:svg.circle(*p,h,h)):
                    old,old_bounds=svg.read_svg(source)
                np.testing.assert_allclose(bounds,old_bounds,atol=.001)
                actual=svg.rasterize(shapes,512);expected=svg.rasterize(old,512)
                self.assertGreater((actual&expected).sum()/(actual|expected).sum(),.998)

    def test_traced_heart_pirates_files_reach_simplify_and_keep_holes(self):
        for name in ('icon_heart_pirates.svg','icon_heart_pirates_outline.svg'):
            source=(Path(__file__).parent/'fixtures'/name).read_text()
            with patch.object(svg_outline,'recover',side_effect=AssertionError('Unapproved trace')):
                with self.assertRaises(icon_fit.SimplificationRequired):
                    icon_fit.read_outline(source,allow_simplify=False)
            shapes,bounds,loops,info=icon_fit.read_outline(source)
            self.assertTrue(info['outline_recovered'])
            self.assertLess(info['input_segments'],50000)
            self.assertGreater(len(loops),5)
            before=svg.rasterize(shapes,1024)
            after=svg.rasterize([(loops,'nonzero')],1024)
            # Thin outlines have only a few recovery pixels across their width.
            self.assertGreater((before&after).sum()/(before|after).sum(),.95)
            # Eye/nose/teeth cutouts must not become a solid blob on import.
            self.assertLess(after.mean(),.55)

    def test_rebuild_emits_plain_paths_and_preserves_holes_and_colours(self):
        source=doc('<rect width="100" height="100" fill="red"/><rect x="20" y="20" width="60" height="60" fill="blue"/>')
        rebuilt,info=svg_outline.rebuild_svg(source,with_colors=True,size=256)
        shapes,bounds,paints=svg.read_svg(rebuilt,with_colors=True)
        self.assertTrue(info['rebuilt']);self.assertNotIn('stroke=',rebuilt)
        self.assertEqual(set(paints),{(1.,0.,0.),(0.,0.,1.)})
        blue=paints.index((0.,0.,1.));red=paints.index((1.,0.,0.))
        self.assertTrue(icon_fit.contains([shapes[blue]],[[.5,.5]])[0])
        self.assertFalse(icon_fit.contains([shapes[red]],[[.5,.5]])[0])
        rebuilt,_=svg_outline.rebuild_svg(RING,size=256)
        shapes,_=svg.read_svg(rebuilt)
        self.assertFalse(icon_fit.contains(shapes,[[.5,.5]])[0])
        self.assertTrue(icon_fit.contains(shapes,[[.1,.1]])[0])

    def test_rebuild_keeps_external_resources_and_bitmaps_rejected(self):
        for source in (doc('<image href="file:///secret"/>'),doc('<script/>'),doc('<text>Hello</text>')):
            with self.assertRaises(ValueError):svg_outline.rebuild_svg(source)

    def test_thin_trace_fit_does_not_invent_broad_wedges(self):
        source=(Path(__file__).parent/'fixtures/icon_heart_pirates_outline.svg').read_text()
        result=icon_fit.fit_svg(source,50,300)
        self.assertTrue(result.get('feature_fit'))
        self.assertGreater(result['coverage'],.2)
        self.assertLess(result['excess'],.01)
        self.assertLessEqual(result['part_count'],300)

    def test_filled_trace_uses_fewer_faces_without_visible_seam_gaps(self):
        source=(Path(__file__).parent/'fixtures/icon_heart_pirates.svg').read_text()
        result=icon_fit.fit_svg(source,100,300)
        self.assertTrue(result.get('compact_fit'))
        self.assertLessEqual(result['part_count'],230)
        self.assertGreaterEqual(result['face_coverage'],.975)
        self.assertLess(result['excess'],.04)

if __name__=='__main__':unittest.main()
