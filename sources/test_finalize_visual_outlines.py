# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Final integer geometry safeguards; no font-file fixtures are required."""
import unittest

from fontTools.pens.ttGlyphPen import TTGlyphPen
from smooth_contours import ContourPen
from finalize_visual_outlines import (finalize_glyph,retry_glyph,remove_zero_length_segments,merge_short_curve_facets,_compile,_join_flags,_crossings,
    _boundary_distance,_topology)


class Drawable:
    def __init__(self,glyph):self.glyph=glyph
    def draw(self,pen):self.glyph.draw(pen,None)


def contours(glyph):
    pen=ContourPen();glyph.draw(pen,None);return pen.contours


class FinalizeVisualOutlinesTests(unittest.TestCase):
    def test_implied_half_coordinates_survive_exactly(self):
        pen=TTGlyphPen(None)
        pen.moveTo((0,0));pen.qCurveTo((0,11),(11,20),(20,11),(20,0))
        pen.lineTo((0,0));pen.closePath();original=pen.glyph()
        after,_,_=_compile(contours(original),False)
        self.assertEqual(contours(original),contours(after))

    def test_all_offcurve_contour_survives_exactly(self):
        pen=TTGlyphPen(None)
        pen.qCurveTo((0,11),(11,20),(20,11),(11,0),None);pen.closePath()
        original=pen.glyph();after,_,_=_compile(contours(original),False)
        self.assertEqual(contours(original),contours(after))

    def test_straight_design_corners_are_untouched(self):
        pen=TTGlyphPen(None)
        pen.moveTo((0,0));pen.lineTo((100,0));pen.lineTo((100,100));pen.lineTo((0,100));pen.closePath()
        original=pen.glyph();after,report=finalize_glyph(Drawable(original))
        self.assertFalse(report['changed'])
        self.assertEqual(contours(original),contours(after))

    def test_curve_line_corner_is_rounded_within_bound(self):
        pen=TTGlyphPen(None)
        pen.moveTo((0,0));pen.qCurveTo((0,20),(20,20));pen.lineTo((20,-20));pen.lineTo((0,-20));pen.closePath()
        original=pen.glyph();before=contours(original)
        self.assertTrue(_join_flags(before))
        after,report=finalize_glyph(Drawable(original));end=contours(after)
        self.assertTrue(report['changed'])
        self.assertFalse(_join_flags(end))
        self.assertFalse(_crossings(end))
        self.assertLessEqual(_boundary_distance(before,end)['maximum'],4)
        self.assertEqual(_topology(before),_topology(end))

    def test_empty_glyph_remains_empty(self):
        pen=TTGlyphPen(None);original=pen.glyph()
        after,report=finalize_glyph(Drawable(original))
        self.assertFalse(report['changed']);self.assertEqual(after.numberOfContours,0)

    def test_retry_preserves_already_clean_native_points(self):
        pen=TTGlyphPen(None)
        pen.moveTo((0,0));pen.lineTo((100,0));pen.lineTo((100,100));pen.closePath()
        original=pen.glyph();after,report=retry_glyph(Drawable(original))
        self.assertFalse(report['changed'])
        self.assertEqual(list(original.coordinates),list(after.coordinates))
        self.assertEqual(list(original.flags),list(after.flags))

    def test_retry_rounding_variant_is_bounded_and_crossing_free(self):
        pen=TTGlyphPen(None)
        pen.moveTo((0,0));pen.qCurveTo((0,20),(20,20));pen.lineTo((20,-20));pen.lineTo((0,-20));pen.closePath()
        original=pen.glyph();after,report=retry_glyph(Drawable(original))
        self.assertTrue(report['changed'])
        self.assertFalse(_join_flags(contours(after)))
        self.assertEqual(report['crossingVerification'],{'0.25':0,'0.1':0,'0.05':0,'0.01':0})
        self.assertLessEqual(report['boundaryDistances']['outsideCrossingRegions'],4.)

    def test_constant_quadratic_removed_with_exact_remaining_geometry(self):
        pen=TTGlyphPen(None)
        pen.moveTo((0,0));pen.qCurveTo((0,0),(0,0))
        pen.qCurveTo((0,11),(11,20),(20,11),(20,0));pen.closePath()
        glyph=pen.glyph();before=contours(glyph)
        expected=[[s for s in c if any(p!=s[0] for p in s[1:])] for c in before]
        report=remove_zero_length_segments(glyph)
        self.assertTrue(report['changed']);self.assertTrue(report['geometryExact'])
        self.assertEqual(contours(glyph),expected)
        self.assertFalse(remove_zero_length_segments(glyph)['changed'])

    def test_nonconstant_retracing_curve_not_removed(self):
        pen=TTGlyphPen(None)
        pen.moveTo((0,0));pen.qCurveTo((10,0),(0,0))
        pen.lineTo((0,20));pen.lineTo((20,20));pen.closePath()
        glyph=pen.glyph();coords=list(glyph.coordinates);flags=list(glyph.flags)
        report=remove_zero_length_segments(glyph)
        self.assertFalse(report['changed'])
        self.assertEqual(coords,list(glyph.coordinates));self.assertEqual(flags,list(glyph.flags))

    def test_clean_contour_native_points_unchanged_when_other_contour_cleaned(self):
        pen=TTGlyphPen(None)
        pen.moveTo((0,0));pen.qCurveTo((0,0),(0,0));pen.lineTo((0,20));pen.lineTo((20,20));pen.closePath()
        pen.qCurveTo((40,11),(51,20),(60,11),(51,0),None);pen.closePath()
        glyph=pen.glyph();start=glyph.endPtsOfContours[0]+1
        clean_coords=list(glyph.coordinates[start:]);clean_flags=list(glyph.flags[start:])
        self.assertTrue(remove_zero_length_segments(glyph)['changed'])
        start=glyph.endPtsOfContours[0]+1
        self.assertEqual(clean_coords,list(glyph.coordinates[start:]));self.assertEqual(clean_flags,list(glyph.flags[start:]))

    def test_compile_removes_zero_tangent_masks_before_join_checks(self):
        pen=TTGlyphPen(None)
        pen.moveTo((0,0));pen.qCurveTo((0,20),(20,20))
        pen.qCurveTo((20,20),(20,20));pen.lineTo((20,-20));pen.lineTo((0,-20));pen.closePath()
        glyph=pen.glyph();compiled,actual,_=_compile(contours(glyph),False)
        self.assertTrue(_join_flags(actual))
        self.assertFalse(remove_zero_length_segments(compiled)['changed'])

    def test_short_tangent_facet_merges_with_subunit_movement(self):
        pen=TTGlyphPen(None)
        pen.moveTo((531,33));pen.qCurveTo((524,51),(531,79));pen.lineTo((532,83))
        pen.qCurveTo((533,85),(533,87));pen.lineTo((560,87));pen.lineTo((560,33));pen.closePath()
        glyph=pen.glyph();after,report=merge_short_curve_facets(Drawable(glyph))
        self.assertTrue(report['changed']);self.assertEqual(len(report['merges']),1)
        event=report['merges'][0]
        self.assertLess(event['afterAngle'],5.)
        self.assertLess(event['boundaryMovement'],.3)
        self.assertEqual(event['crossingVerification'],{'0.25':0,'0.1':0,'0.05':0,'0.01':0})
        self.assertEqual(_topology(contours(glyph)),_topology(contours(after)))


if __name__=='__main__':unittest.main()
