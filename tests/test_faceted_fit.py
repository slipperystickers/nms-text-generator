"""Geometry regressions for shared faceted contours and native panel seams."""
import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1] / 'nms_text_generator'
pkg = types.ModuleType('faceted_test_package')
pkg.__path__ = [str(ROOT)]
sys.modules[pkg.__name__] = pkg
from faceted_test_package import icon_fit


def rectangle(x0, y0, x1, y1):
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)


def transform(points, angle):
    c, s = math.cos(angle), math.sin(angle)
    return (np.asarray(points) - .5) @ np.array([[c, s], [-s, c]]) + .5


def covered(panels, points):
    points = np.asarray(points)
    result = np.zeros(len(points), bool)
    for panel in panels:
        result |= icon_fit.native_face_mask(panel, points[:, 0], points[:, 1])
    return result


class FacetedFitTests(unittest.TestCase):
    def test_complete_candidate_can_use_more_parts_than_an_unfilled_fit(self):
        source='<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="50"/></svg>'
        baseline={'part_count':10,'unfilled':True,'budget_hit':True,'excess':0,'coverage':.8}
        candidate={'part_count':12,'face_coverage':.999,'seam_check_complete':True}
        cases=[(True,True,12,True,True),(False,True,12,True,False),
               (False,False,10,True,True),(True,True,21,True,False),
               (True,True,12,False,False)]
        with patch.object(icon_fit,'contour_plan',return_value=[{'limited':False}]*101):
            for unfilled,budget_hit,count,complete,accepted in cases:
                with self.subTest(unfilled=unfilled,budget_hit=budget_hit,count=count,complete=complete):
                    current={**baseline,'unfilled':unfilled,'budget_hit':budget_hit}
                    proposed={**candidate,'part_count':count,'seam_check_complete':complete}
                    with patch.object(icon_fit,'fit_outline',return_value=current), \
                         patch.object(icon_fit,'facet_fit',return_value=proposed):
                        result=icon_fit.fit_svg(source,60,20)
                    self.assertIs(result,proposed if accepted else current)

    def test_accuracy_only_removes_contour_detail_and_preserves_topology(self):
        source=(Path(__file__).parent/'fixtures/icon_heart_pirates.svg').read_text()
        plans=icon_fit.contour_plan(source,300)
        self.assertIsNotNone(plans)
        self.assertIs(plans,icon_fit.contour_plan(source,300))
        original=icon_fit.read_outline(source)[2]
        for accuracy in range(100):
            coarser,finer=plans[accuracy],plans[accuracy+1]
            self.assertGreaterEqual(coarser['tolerance'],finer['tolerance'])
            self.assertTrue(all(len(a)<=len(b) for a,b in zip(coarser['loops'],finer['loops'])))
            self.assertTrue(icon_fit.valid_facets(original,coarser['loops']))
        self.assertLess(sum(map(len,plans[60]['loops'])),sum(map(len,plans[100]['loops'])))

    def test_pruning_keeps_native_crack_bridge_and_small_island(self):
        width=.1;half=width*icon_fit.RATIO/2
        lower,upper=.4,.4+width*icon_fit.FACE_SHORT+2e-6
        tiny=rectangle(.8,.5,.805,.501)
        boundary=icon_fit.Boundary([rectangle(.5-half,lower-width/2,.5+half,upper+width/2),tiny])
        panels=[(.5,lower,width,0),(.5,upper,width,0)]
        check=icon_fit.repair_facet_gaps(boundary,panels,24,size=128)
        self.assertTrue(check['seam_check_complete'])
        panels.append(panels[0])  # A provably redundant copy can be removed.
        self.assertGreater(icon_fit.prune_facet_panels(boundary,panels,size=128),0)
        seam=lower+width*icon_fit.FACE_SHORT/2+1e-6
        points=np.column_stack((np.linspace(.5-half+.002,.5+half-.002,83),np.full(83,seam)))
        self.assertTrue(covered(panels,points).all())
        self.assertTrue(covered(panels,[[.80001,.5005],[.8025,.5005],[.80499,.5005]]).all())
        self.assertFalse(icon_fit.native_seam_probes(boundary,panels))

    def test_rotated_straight_band_uses_large_shared_faces(self):
        angle = math.radians(17)
        loop = transform(rectangle(.15, .45, .85, .55), angle)
        baseline = {'_fill_loops': [loop.tolist()], 'outline_tolerance': .0006,
                    'outline_relaxed': False}
        result = icon_fit.facet_fit([([loop], 'nonzero')], [1, 1], [loop], {}, 100, 40, baseline)
        self.assertIsNotNone(result)
        self.assertLessEqual(result['part_count'], 12)
        boundary = icon_fit.Boundary([loop])
        self.assertTrue(all(boundary.inside(panel) for panel in result['panels']))
        # A deep regular sampling grid tests coverage independently of the
        # fitter's raster resolution and reported percentages.
        x, y = np.meshgrid(np.linspace(.151, .849, 139), np.linspace(.452, .548, 19))
        probes = transform(np.column_stack((x.ravel(), y.ravel())), angle)
        self.assertTrue(covered(result['panels'], probes).all())
        self.assertTrue(result['seam_check_complete'])

    def test_repair_finds_an_entirely_omitted_island(self):
        width = .1
        half = width * icon_fit.RATIO / 2
        loops = [rectangle(x - half, .45, x + half, .55) for x in (.25, .75)]
        boundary = icon_fit.Boundary(loops)
        panels = [(.25, .5, width, 0)]
        # No exposed edge of the first island can locate the second island.
        before = icon_fit.native_seam_probes(boundary, panels)
        self.assertFalse(any(point[0] > .5 for _, _, point, _ in before))
        report = icon_fit.repair_facet_gaps(boundary, panels, 12, size=128)
        self.assertGreater(report['seam_repairs'], 0)
        self.assertTrue(covered(panels, [[.75, .5]])[0])
        self.assertLessEqual(len(panels), 12)
        self.assertTrue(all(boundary.inside(panel) for panel in panels))

    def test_candidates_preserve_a_gap_smaller_than_a_raster_pixel(self):
        angle = math.radians(17)
        gap = .0002
        loops = [transform(rectangle(.2, .35, .8, .40), angle),
                 transform(rectangle(.2, .40 + gap, .8, .45 + gap), angle)]
        boundary = icon_fit.Boundary(loops)
        panels = icon_fit.facet_candidates(boundary)
        self.assertTrue(panels)
        self.assertTrue(all(boundary.inside(panel) for panel in panels))
        gap_probes = transform(np.column_stack((np.linspace(.201, .799, 211), np.full(211, .40 + gap / 2))), angle)
        self.assertFalse(covered(panels, gap_probes).any())

    def test_repair_retains_a_tiny_island_between_global_raster_samples(self):
        width = .1
        half = width * icon_fit.RATIO / 2
        tiny = rectangle(.8, .5, .805, .501)
        boundary = icon_fit.Boundary([rectangle(.25 - half, .45, .25 + half, .55), tiny])
        self.assertFalse(icon_fit.svg_geometry.rasterize([([tiny], 'nonzero')], 128).any())
        panels = [(.25, .5, width, 0)]
        report = icon_fit.repair_facet_gaps(boundary, panels, 20, size=128)
        # Check the full line just inside the feature-scaled outside rim,
        # independently of the local sampling grid used to locate the island.
        line = np.column_stack((np.linspace(.80001, .80499, 101), np.full(101, .5005)))
        self.assertTrue(covered(panels, line).all())
        self.assertEqual(report['remaining_islands'], 0)
        self.assertTrue(report['seam_check_complete'])
        self.assertLessEqual(len(panels), 20)
        self.assertTrue(all(boundary.inside(panel) for panel in panels))

    def test_exhausted_budget_reports_an_island_absent_from_global_pixels(self):
        width = .1
        half = width * icon_fit.RATIO / 2
        tiny = rectangle(.8, .5, .805, .501)
        boundary = icon_fit.Boundary([rectangle(.25 - half, .45, .25 + half, .55), tiny])
        self.assertFalse(icon_fit.svg_geometry.rasterize([([tiny], 'nonzero')], 128).any())
        panels = [(.25, .5, width, 0)]
        report = icon_fit.repair_facet_gaps(boundary, panels, 1, size=128)
        self.assertEqual(len(panels), 1)
        self.assertEqual(report['remaining_islands'], 1)
        self.assertFalse(report['seam_check_complete'])

    def test_candidates_retain_a_narrow_connecting_neck(self):
        loop = np.array([[.1, .3], [.4, .3], [.4, .49], [.6, .49],
                         [.6, .3], [.9, .3], [.9, .7], [.6, .7],
                         [.6, .51], [.4, .51], [.4, .7], [.1, .7]])
        boundary = icon_fit.Boundary([loop])
        panels = icon_fit.facet_candidates(boundary)
        self.assertTrue(all(boundary.inside(panel) for panel in panels))
        neck = np.column_stack((np.linspace(.425, .575, 71), np.full(71, .5)))
        self.assertTrue(covered(panels, neck).all())
        self.assertFalse(covered(panels, [[.5, .48], [.5, .52]]).any())

    def test_native_audit_finds_and_repairs_a_subpixel_internal_crack(self):
        width = .1
        gap = 2e-6
        lower, upper = .4, .4 + width * icon_fit.FACE_SHORT + gap
        half = width * icon_fit.RATIO / 2
        boundary = icon_fit.Boundary([rectangle(.5 - half, lower - width / 2,
                                               .5 + half, upper + width / 2)])
        panels = [(.5, lower, width, 0), (.5, upper, width, 0)]
        crack_y = lower + width * icon_fit.FACE_SHORT / 2 + gap / 2
        crack = np.column_stack((np.linspace(.5 - half + .002, .5 + half - .002, 83), np.full(83, crack_y)))
        self.assertFalse(covered(panels, crack).any())
        self.assertTrue(any(blocked for blocked, _, _, _ in icon_fit.native_seam_probes(boundary, panels)))
        report = icon_fit.repair_facet_gaps(boundary, panels, 16, size=128)
        self.assertTrue(covered(panels, crack).all())
        self.assertEqual(report['remaining_seams'], 0)
        self.assertTrue(all(boundary.inside(panel) for panel in panels))

    def test_repair_reports_unfilled_target_when_the_part_cap_is_exhausted(self):
        boundary = icon_fit.Boundary([rectangle(.1, .1, .9, .9)])
        panels = [(.5, .5, .05, 0)]
        report = icon_fit.repair_facet_gaps(boundary, panels, 1, size=64)
        self.assertEqual(len(panels), 1)
        self.assertFalse(report['seam_check_complete'])
        self.assertGreater(report['remaining_interior_samples'], 0)

    def test_faceting_rejects_crossing_or_swallowing_a_separate_island(self):
        outer = np.array([[0, 0], [1, 0], [1, 1], [.7, 1], [.7, .4],
                          [.3, .4], [.3, 1], [0, 1]], float)
        island = rectangle(.4, .6, .6, .8)
        original = [outer, island]
        self.assertTrue(icon_fit.valid_facets(original, original))
        # Both replacements retain the anchor, winding and original vertices.
        # One chord crosses the island; the other encloses it without touching.
        crossing = outer[[0, 1, 2, 5, 7]]
        swallowing = outer[[0, 1, 2, 7]]
        self.assertFalse(icon_fit.valid_facets(original, [crossing, island]))
        self.assertFalse(icon_fit.valid_facets(original, [swallowing, island]))

    def test_faceting_rejects_self_crossing_even_when_winding_stays_positive(self):
        angles = np.linspace(0, 2 * np.pi, 5, endpoint=False)
        loop = np.column_stack((np.cos(angles), np.sin(angles))) * .4 + .5
        star = loop[[0, 2, 4, 1, 3]]
        self.assertGreater(icon_fit.cross(star, np.roll(star, -1, axis=0)).sum(), 0)
        self.assertFalse(icon_fit.valid_facets([loop], [star]))

    def test_faceting_preserves_hole_winding_and_nesting(self):
        outer = rectangle(.1, .1, .9, .9)
        hole = rectangle(.65, .65, .75, .75)[::-1]
        self.assertTrue(icon_fit.valid_facets([outer, hole], [outer, hole]))
        self.assertFalse(icon_fit.valid_facets([outer, hole], [outer, hole[::-1]]))
        # A hole outside its parent would silently become painted geometry
        # under nonzero filling. No contour intersection is needed for this.
        shortened_outer = outer[[0, 1, 3]]
        self.assertFalse(icon_fit.valid_facets([outer, hole], [shortened_outer, hole]))


if __name__ == '__main__':
    unittest.main()
