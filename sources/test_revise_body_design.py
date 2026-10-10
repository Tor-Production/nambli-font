# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
import unittest
from copy import deepcopy
from ufoLib2 import Font
from prepare_visual_quality import recording
from revise_body_design import selected_glyphs,rebuild_glyph


def fixture():
    baseline=Font();baseline.info.unitsPerEm=1000;baseline.info.italicAngle=0
    g=baseline.newGlyph('a');g.width=600;g.unicodes=[0x61]
    p=g.getPen();p.moveTo((265,0));p.qCurveTo((0,0),(0,265));p.qCurveTo((0,530),(265,530))
    p.qCurveTo((530,530),(530,265));p.qCurveTo((530,0),(265,0));p.closePath()
    accent=baseline.newGlyph('aacute');accent.width=g.width;accent.unicodes=[0xE1]
    for contour in g.contours:accent.appendContour(deepcopy(contour))
    p=accent.getPen();p.moveTo((230,700));p.lineTo((300,780));p.lineTo((330,765));p.closePath()
    current=deepcopy(baseline)
    for name in ('a','aacute'):
        for point in current[name].contours[0].points:point.y=point.y*1.04-10
    report={'details':{name:{'optical':{'overshoot':[{'line':0,'delta':-10}]}} for name in ('a','aacute')},
            'diacritics':{'preservedGlyphs':{'aacute':{'preservedContours':[1],'wholeGlyph':False}}}}
    return baseline,current,report


class ReviseBodyDesignTests(unittest.TestCase):
    def test_scope_uses_recorded_overshoot_only(self):
        report={'details':{'a':{'optical':{'overshoot':[{'line':0}]}},
            'b':{'optical':{'overshoot':[]}},'.notdef':{'optical':{'missingGlyph':True}},
            'r':{'smoothing':{'changed':True}}}}
        self.assertEqual(selected_glyphs(report),['a'])

    def test_rebuild_uses_original_design_and_preserves_accents(self):
        baseline,current,report=fixture()
        current_before={g.name:recording(g) for g in current}
        baseline_before={g.name:recording(g) for g in baseline}
        candidate,evidence=rebuild_glyph(current,baseline,'aacute',report)
        self.assertEqual(candidate.contours[-1],baseline['aacute'].contours[-1])
        self.assertEqual(candidate.width,current['aacute'].width)
        self.assertFalse(evidence['audit']['coreFlags'])
        self.assertFalse(evidence['audit']['fineCrossings'])
        self.assertFalse(evidence['audit']['remainingRawJoins15'])
        self.assertEqual(current_before,{g.name:recording(g) for g in current})
        self.assertEqual(baseline_before,{g.name:recording(g) for g in baseline})
        body_y=[p.y for p in candidate.contours[0].points]
        self.assertLessEqual(abs(min(body_y)),2)
        self.assertLessEqual(abs(max(body_y)-530),2)

    def test_scope_conflict_fails_without_mutating_sources(self):
        baseline,current,report=fixture()
        report['diacritics']['preservedGlyphs']['aacute']['wholeGlyph']=True
        before=recording(current['aacute'])
        with self.assertRaisesRegex(ValueError,'deferred whole glyph'):
            rebuild_glyph(current,baseline,'aacute',report)
        self.assertEqual(recording(current['aacute']),before)


if __name__=='__main__':unittest.main()
