"""Topology and shape guards for moving coherent polygon contours."""
import math
from pathlib import Path
import sys
import types
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1] / 'nms_text_generator'
pkg = types.ModuleType('contour_regularization_test_package')
pkg.__path__ = [str(ROOT)]
sys.modules[pkg.__name__] = pkg
from contour_regularization_test_package import icon_fit


def rectangle(x0, y0, x1, y1):
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)


def rotate(points, angle):
    c, s = math.cos(angle), math.sin(angle)
    return (np.asarray(points) - .5) @ np.array([[c, s], [-s, c]]) + .5


def edge_directions(loop):
    edges = np.roll(loop, -1, axis=0) - loop
    return edges / np.linalg.norm(edges, axis=1)[:, None]


class ContourRegularizationTests(unittest.TestCase):
    def nested_loops(self):
        return [rectangle(0, 0, 1, 1),
                rectangle(.4, .4, .6, .6)[::-1],
                rectangle(.401, .45, .402, .451)]

    def test_moved_island_cannot_jump_from_a_hole_into_surrounding_material(self):
        original = self.nested_loops()
        proposed = [loop.copy() for loop in original]
        proposed[2] += [-.003, 0]
        # The final edges do not intersect. Looking only at the OLD island
        # anchor would miss that this material component has been swallowed.
        self.assertFalse(icon_fit.valid_facets(original, proposed))

    def test_nesting_is_preserved_when_all_contours_move_together(self):
        original = self.nested_loops()
        proposed = [loop + [.01, 0] for loop in original]
        # The old island anchor is outside the translated hole; its new
        # anchor remains nested, so unchanged topology must still be accepted.
        self.assertTrue(icon_fit.valid_facets(original, proposed))

    def test_nested_island_can_move_without_changing_its_parent(self):
        original = self.nested_loops()
        proposed = [loop.copy() for loop in original]
        proposed[2] += [.02, .01]
        self.assertTrue(icon_fit.valid_facets(original, proposed))

    def test_a_whole_hole_cannot_move_outside_its_parent(self):
        original = [rectangle(0, 0, 1, 1), rectangle(.001, .45, .002, .451)[::-1]]
        proposed = [loop.copy() for loop in original]
        proposed[1] += [-.003, 0]
        self.assertFalse(icon_fit.valid_facets(original, proposed))

    def test_near_square_corners_regularize_within_the_movement_bound(self):
        loop = np.array([[.2, .2], [.8, .24], [.74, .7], [.2, .7]])
        result = icon_fit.regularize_contours([loop], .04, math.radians(20))[0]
        before, after = edge_directions(loop), edge_directions(result)
        old_square = np.abs(np.sum(before * np.roll(before, 1, axis=0), axis=1)) < 1e-8
        new_square = np.abs(np.sum(after * np.roll(after, 1, axis=0), axis=1)) < 1e-8
        self.assertGreater(int(new_square.sum()), int(old_square.sum()))
        self.assertLessEqual(float(np.linalg.norm(result - loop, axis=1).max()), .04 + 1e-10)
        self.assertTrue(icon_fit.valid_facets([loop], [result]))

    def test_regularization_follows_the_artwork_orientation(self):
        loop = np.array([[.2, .2], [.8, .24], [.74, .7], [.2, .7]])
        angle = math.radians(31)
        result = icon_fit.regularize_contours([loop], .04, math.radians(20))[0]
        rotated = icon_fit.regularize_contours([rotate(loop, angle)], .04, math.radians(20))[0]
        np.testing.assert_allclose(rotated, rotate(result, angle), atol=1e-9)

    def test_concave_cap_junction_does_not_tilt_a_vertical_stem(self):
        loop = np.array([[.2, .1], [.8, .22], [.8, .4], [.55, .35],
                         [.55, .85], [.45, .85], [.45, .33], [.2, .28]])
        result = icon_fit.regularize_contours([loop], .04, math.radians(28))[0]
        original_direction = edge_directions(loop)[[3, 5]]
        final_direction = edge_directions(result)[[3, 5]]
        change = np.arccos(np.clip(np.sum(original_direction * final_direction, axis=1), -1, 1))
        self.assertTrue(np.all(change <= math.radians(.25) + 1e-10))
        self.assertTrue(icon_fit.valid_facets([loop], [result]))

    def test_narrow_separation_caps_both_endpoints_of_both_edges(self):
        left = np.array([[.1, .1], [.5, .13], [.5, .3], [.12, .28]])
        right = np.array([[.501, .13], [.9, .1], [.88, .28], [.501, .3]])
        result = icon_fit.regularize_contours([left, right], .04, math.radians(28))
        # The shared .001 gap is much smaller than the global .04 allowance.
        # Both ends of the long opposed edges must receive the local bound.
        for before, after, ids in ((left, result[0], [1, 2]), (right, result[1], [0, 3])):
            self.assertTrue(np.all(np.linalg.norm(after[ids] - before[ids], axis=1) <= .00025 + 1e-10))
        self.assertTrue(icon_fit.valid_facets([left, right], result))
        ys = np.linspace(.14, .29, 51)
        gap_points = np.column_stack((np.full(len(ys), .5005), ys))
        self.assertFalse(icon_fit.contains([(result, 'nonzero')], gap_points).any())

    def test_small_hole_and_island_survive_regularization(self):
        loops = self.nested_loops()
        result = icon_fit.regularize_contours(loops, .04, math.radians(28))
        self.assertEqual(len(result), 3)
        self.assertTrue(icon_fit.valid_facets(loops, result))
        probes = [[.4015, .4505], [.5, .5], [.2, .2]]
        self.assertEqual(icon_fit.contains([(result, 'nonzero')], probes).tolist(), [True, False, True])

    def test_narrow_taper_limits_the_whole_long_edge_by_its_smallest_width(self):
        loop = np.array([[.4, .2], [.404, .2], [.401, .8], [.4, .8]])
        result = icon_fit.regularize_contours([loop], .04, math.radians(28))[0]
        # Aligning these nearly parallel long sides without the clearance
        # guard moves their ends by about .00075. The .001 minimum width
        # requires the tighter .00025 bound at BOTH ends of each side.
        self.assertTrue(np.all(np.linalg.norm(result - loop, axis=1) <= .00025 + 1e-10))
        self.assertTrue(icon_fit.valid_facets([loop], [result]))

    def test_zero_strength_preserves_all_vertices(self):
        loop = np.array([[.2, .2], [.8, .24], [.74, .7], [.2, .7]])
        for movement, angle in ((0, math.radians(28)), (.04, 0)):
            result = icon_fit.regularize_contours([loop], movement, angle)
            np.testing.assert_array_equal(result[0], loop)

    def test_regularization_does_not_modify_the_source_arrays(self):
        loop = np.array([[.2, .2], [.8, .24], [.74, .7], [.2, .7]])
        original = loop.copy()
        icon_fit.regularize_contours([loop], .04, math.radians(20))
        np.testing.assert_array_equal(loop, original)

    def test_corners_outside_the_angle_window_are_unchanged(self):
        loop = np.array([[.2, .7], [.5, .7 - .3 * math.sqrt(3)], [.8, .7]])
        result = icon_fit.regularize_contours([loop], .04, math.radians(5))
        np.testing.assert_allclose(result[0], loop, atol=1e-12)

    def test_band_connection_accepts_uninterrupted_rectangle_material(self):
        boundary = icon_fit.Boundary([rectangle(.2, .4, .8, .6)])
        self.assertTrue(icon_fit.band_connection_clear(boundary, 0, 2))
        self.assertTrue(icon_fit.band_connection_clear(boundary, 2, 0))

    def test_band_connection_rejects_a_hole_between_the_old_three_probes(self):
        outer = rectangle(.2, .4, .8, .6)
        hole = rectangle(.49, .465, .51, .467)[::-1]
        boundary = icon_fit.Boundary([outer, hole])
        old_probes = [[.5, .44], [.5, .5], [.5, .56]]
        self.assertTrue(icon_fit.contains(boundary.shapes, old_probes).all())
        self.assertFalse(icon_fit.band_connection_clear(boundary, 0, 2))

    def test_band_connection_rejects_boundary_touch_and_collinear_overlap(self):
        outer = rectangle(.2, .4, .8, .6)
        # One triangular hole only touches the connector at its tip. The
        # second hole shares a short vertical edge with the connector.
        obstacles = {
            'touch': np.array([[.5, .465], [.52, .455], [.52, .475]])[::-1],
            'collinear': rectangle(.5, .46, .52, .48)[::-1],
        }
        for name, hole in obstacles.items():
            with self.subTest(kind=name):
                boundary = icon_fit.Boundary([outer, hole])
                self.assertTrue(icon_fit.contains(boundary.shapes, [[.5, .5]])[0])
                self.assertFalse(icon_fit.band_connection_clear(boundary, 0, 2))


if __name__ == '__main__':
    unittest.main()
