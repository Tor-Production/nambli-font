# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Synthetic outlines exercise the audit's geometric discrimination."""
import unittest

from audit_visual_quality import audit_contours, crossings, flatten


class GeometryAuditTests(unittest.TestCase):
    def test_smooth_circle_has_no_tangent_break(self):
        h = 55.228474983
        circle = [((100, 0), (100, h), (h, 100), (0, 100)),
                  ((0, 100), (-h, 100), (-100, h), (-100, 0)),
                  ((-100, 0), (-100, -h), (-h, -100), (0, -100)),
                  ((0, -100), (h, -100), (100, -h), (100, 0))]
        self.assertEqual(audit_contours([circle])['flags'], [])

    def test_deliberate_rectangle_is_review_not_curve_failure(self):
        rectangle = [((0, 0), (100, 0)), ((100, 0), (100, 100)),
                     ((100, 100), (0, 100)), ((0, 100), (0, 0))]
        flags = audit_contours([rectangle])['flags']
        self.assertEqual(len(flags), 4)
        self.assertEqual({f['kind'] for f in flags}, {'line_corner'})
        self.assertEqual({f['severity'] for f in flags}, {'intentional_corner_review'})

    def test_broken_round_join_is_located(self):
        outline = [((0, 0), (50, 0), (100, 50)),
                   ((100, 50), (100, 0), (100, -50)),
                   ((100, -50), (0, -50)), ((0, -50), (0, 0))]
        failures = [f for f in audit_contours([outline])['flags']
                    if f['kind'] == 'curve_tangent_break' and f['segment'] == 0]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]['point'], [100, 50])
        self.assertGreater(failures[0]['angle_degrees'], 130)
        self.assertEqual(failures[0]['severity'], 'high')

    def test_tangent_continuity_does_not_hide_abrupt_radius_change(self):
        # Two exact tangent quadratics at (100, 0): radius changes 200 -> 2.5.
        outline = [((0, 100), (100, 100), (100, 0)),
                   ((100, 0), (100, -5), (80, -10)),
                   ((80, -10), (0, 100))]
        flags = audit_contours([outline])['flags']
        candidates = [f for f in flags if f['kind'] == 'sudden_curvature_change' and f['segment'] == 0]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['angle_degrees'], 0)
        self.assertLess(candidates[0]['radius_after'], 10)

    def test_short_tangent_s_wave_is_reviewable(self):
        outline = [((0, 0), (10, 10), (20, 10)),
                   ((20, 10), (30, 10), (40, 20)),
                   ((40, 20), (0, 0))]
        flags = audit_contours([outline])['flags']
        self.assertTrue(any(f['kind'] == 'short_curvature_reversal' and f['segment'] == 0 for f in flags))

    def test_self_crossing_bow_tie_is_found_but_shared_corners_are_not(self):
        bow_tie = [[(0, 0), (100, 100), (0, 100), (100, 0), (0, 0)]]
        found = crossings(bow_tie)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['point'], [50, 50])
        self.assertFalse(crossings([[(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]]))

    def test_backtracking_collinear_curve_is_not_flattened_to_one_edge(self):
        flattened = flatten(((0, 0), (100, 0), (-100, 0), (0, 0)))
        self.assertGreater(len(flattened), 2)
        self.assertGreater(max(x for x, _ in flattened), 20)
        self.assertLess(min(x for x, _ in flattened), -20)

    def test_open_contour_and_zero_length_segment_are_reported(self):
        flags = audit_contours([[((0, 0), (0, 0)), ((0, 0), (100, 0))]], [0])['flags']
        self.assertIn('open_contour', {f['kind'] for f in flags})
        self.assertIn('zero_length_segment', {f['kind'] for f in flags})


if __name__ == '__main__':
    unittest.main()
