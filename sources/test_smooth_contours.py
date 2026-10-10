# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
"""Meaningful geometry safeguards for the global outline-refitting pass."""
import math
import unittest

from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen

from smooth_contours import (ContourPen, smooth_glyph, smooth_contour,
    audit_contours, boundary_error, draw_contours, _area, _polyline,
    repair_quantized_g1)


class Drawable:
    def __init__(self, contours):
        self.contours=contours
    def draw(self,pen):
        draw_contours(self.contours,pen)


def quantized_circle(radius=48,n=48):
    """Independent rounding of very short quadratics reproduces cap facets."""
    result=[]
    def rounded(z):return complex(round(z.real),round(z.imag))
    for i in range(n):
        a,b=2*math.pi*i/n,2*math.pi*(i+1)/n
        mid=(a+b)/2
        p0=rounded(radius*complex(math.cos(a),math.sin(a)))
        p2=rounded(radius*complex(math.cos(b),math.sin(b)))
        p1=rounded(radius/math.cos((b-a)/2)*complex(math.cos(mid),math.sin(mid)))
        result.append((p0,p1,p2))
    return result


class SmoothContoursTests(unittest.TestCase):
    def test_round_terminal_improves_after_integer_ttf_conversion(self):
        original=quantized_circle()
        rec,report=smooth_glyph(Drawable([original]))
        self.assertTrue(report['changed'])
        pen=TTGlyphPen(None)
        rec.replay(Cu2QuPen(pen,max_err=.3,reverse_direction=False))
        glyph=pen.glyph()
        compiled=ContourPen();glyph.draw(compiled,None)
        before=[f for f in audit_contours([original]) if f['kind']=='tangent_break']
        after=[f for f in audit_contours(compiled.contours) if f['kind']=='tangent_break']
        self.assertLess(len(after),len(before)//3)
        self.assertEqual(len(compiled.contours),1)
        # The design limit applies before the separate final integer rounding.
        source=ContourPen();rec.replay(source)
        self.assertLessEqual(boundary_error(original,source.contours[0]),1.5)

    def test_true_polygon_corners_are_preserved_exactly(self):
        original=[(0j,100+0j),(100+0j,100+200j),(100+200j,200j),(200j,0j)]
        candidate,report=smooth_contour(original)
        self.assertEqual(candidate,original)
        self.assertFalse(report['changed'])

    def test_translations_reuse_same_shape_without_shifting_design(self):
        original=quantized_circle()
        shift=237+715j
        a,_=smooth_contour(original)
        b,_=smooth_contour([tuple(p+shift for p in s) for s in original])
        for sa,sb in zip(a,b):
            for pa,pb in zip(sa,sb):self.assertAlmostEqual(abs((pb-pa)-shift),0,places=8)

    def test_winding_hole_count_and_italic_frame_are_preserved(self):
        contours=[quantized_circle(90),[tuple(reversed(s)) for s in reversed(quantized_circle(42))]]
        shear=math.tan(math.radians(10))
        sheared=[[tuple(complex(p.real+shear*p.imag,p.imag) for p in s) for s in c] for c in contours]
        rec,report=smooth_glyph(Drawable(sheared),italic_angle=-10)
        after=ContourPen();rec.replay(after)
        self.assertEqual(len(after.contours),2)
        for a,b in zip(sheared,after.contours):
            self.assertGreater(_area(_polyline(a)[0])*_area(_polyline(b)[0]),0)
            self.assertLessEqual(boundary_error(a,b),1.5)

    def test_open_contour_fails_explicitly(self):
        class Open:
            def draw(self,pen):
                pen.moveTo((0,0));pen.lineTo((100,100));pen.endPath()
        with self.assertRaisesRegex(ValueError,'Open contour'):
            smooth_glyph(Open())

    def test_integer_g1_repair_respects_local_boundary_bound(self):
        pen=TTGlyphPen(None);draw_contours([quantized_circle()],pen)
        glyph=pen.glyph()
        before=ContourPen();glyph.draw(before,None)
        report=repair_quantized_g1(glyph,maximum_shift=3,maximum_control_shift=3)
        after=ContourPen();glyph.draw(after,None)
        self.assertTrue(report['changed'])
        self.assertLessEqual(report['maximum_endpoint_shift'],3)
        self.assertLessEqual(report['maximum_control_shift'],3)
        self.assertLessEqual(boundary_error(before.contours[0],after.contours[0]),3)
        self.assertFalse([f for f in audit_contours(after.contours) if f['kind']=='tangent_break'])

    def test_collapsed_quantized_handle_is_repaired(self):
        pen=TTGlyphPen(None)
        pen.moveTo((-20,-20))
        pen.qCurveTo((-5,-10),(0,-8),(0,0),(0,0))
        pen.qCurveTo((-1,1),(-5,-3),(-12,-12),(-12,-13))
        pen.lineTo((-20,-20));pen.closePath()
        glyph=pen.glyph()
        report=repair_quantized_g1(glyph)
        events=[e for e in report['joins'] if e['before']==(0.,0.)]
        self.assertTrue(events)
        self.assertEqual(events[0]['kind'],'implicit_midpoint')
        self.assertEqual(events[0]['angle_after'],0.)

    def test_shared_integer_controls_remove_unequal_handle_corner(self):
        # This is the exact 1.001-style unequal-handle degeneracy from the
        # Bold dz construction, translated to the origin for this fixture.
        pen=TTGlyphPen(None)
        pen.moveTo((0,40));pen.qCurveTo((0,1),(0,0))
        pen.qCurveTo((-17,-15),(-35,-20));pen.lineTo((0,40));pen.closePath()
        glyph=pen.glyph();report=repair_quantized_g1(glyph)
        events=[e for e in report['joins'] if e['before']==(0.,0.)]
        self.assertTrue(events)
        self.assertEqual(events[0]['kind'],'integer_control_snap')
        self.assertEqual(events[0]['angle_after'],0.)
        self.assertLessEqual(max(events[0]['control_shifts']),3.)

    def test_drawer_preserves_implied_half_unit_points_before_rounding(self):
        original_pen=TTGlyphPen(None)
        original_pen.moveTo((0,0))
        original_pen.qCurveTo((0,11),(11,20),(20,11),(20,0))
        original_pen.lineTo((0,0));original_pen.closePath()
        original=original_pen.glyph();segments=ContourPen();original.draw(segments,None)
        self.assertTrue(any(p.real%1 or p.imag%1 for c in segments.contours for s in c for p in s))
        output_pen=TTGlyphPen(None);draw_contours(segments.contours,output_pen)
        output=output_pen.glyph();actual=ContourPen();output.draw(actual,None)
        self.assertEqual(segments.contours,actual.contours)
        self.assertEqual(list(original.coordinates),list(output.coordinates))
        self.assertEqual(list(original.flags),list(output.flags))


if __name__=='__main__':
    unittest.main()
