# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
import unittest
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from primitives import ring
from refine_optical_details import round_bowl_overshoot, missing_glyph

class Drawable:
    def __init__(self,p):self.p=p
    def draw(self,pen):self.p.draw(pen)

class OpticalDetailsTests(unittest.TestCase):
    def test_round_bowl_extends_beyond_alignment_lines(self):
        before=Drawable(ring(310,265,264,265,100))
        after,fields=round_bowl_overshoot(before,[ord('o')])
        bounds=BoundsPen(None);after.replay(bounds)
        self.assertEqual(len(fields),2)
        self.assertAlmostEqual(bounds.bounds[1],-10)
        self.assertAlmostEqual(bounds.bounds[3],540)
        self.assertAlmostEqual(bounds.bounds[0],46)
        self.assertAlmostEqual(bounds.bounds[2],574)
    def test_unselected_forms_are_unchanged(self):
        before=Drawable(ring(350,370,304,382,100))
        r=RecordingPen();before.draw(r)
        after,fields=round_bowl_overshoot(before,[ord('O')])
        self.assertEqual(fields,[]);self.assertEqual(r.value,after.value)
    def test_preserved_belowmark_gap_blocks_baseline_overshoot(self):
        before=Drawable(ring(310,265,264,265,100))
        after,fields=round_bowl_overshoot(before,[ord('o')],protected_lines=(0,))
        bounds=BoundsPen(None);after.replay(bounds)
        self.assertEqual(len(fields),1)
        self.assertAlmostEqual(bounds.bounds[1],0)
        self.assertAlmostEqual(bounds.bounds[3],540)
    def test_missing_glyph_is_crossed_and_stays_in_advance(self):
        r=missing_glyph();bounds=BoundsPen(None);r.replay(bounds)
        self.assertEqual(bounds.bounds,(55,0,565,740))
        # Frame plus two crossing strokes: its recording cannot be the
        # two nested ellipses that previously resembled a capital O.
        self.assertGreater(sum(op=='moveTo' for op,args in r.value),2)

if __name__=='__main__':unittest.main()
