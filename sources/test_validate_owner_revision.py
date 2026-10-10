# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Adversarial scope checks on actual TrueType contours, not report assertions."""
from copy import deepcopy
import unittest

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from validate_owner_revision import validate_outline_scope, TARGETS


def rectangle(left=0, bottom=0, right=200, top=500):
    return [(left, bottom), (left, top), (right, top), (right, bottom)]


def glyph(contours):
    pen = TTGlyphPen(None)
    for points in contours:
        pen.moveTo(points[0])
        for point in points[1:]:
            pen.lineTo(point)
        pen.closePath()
    return pen.glyph()


def font(contours):
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(list(contours))
    builder.setupCharacterMap({0x61: 'a', 0xE1: 'aacute', 0x301: 'uni0301',
                              0x13D: 'uni013D', 0x13E: 'uni013E', 0x10F: 'uni010F',
                              0x165: 'uni0165', 0x163: 'uni0163'})
    builder.setupGlyf({name: glyph(value) for name, value in contours.items()})
    builder.setupHorizontalMetrics({name: (500, min(x for c in value for x, y in c))
                                    for name, value in contours.items()})
    return builder.font


class OwnerRevisionScopeTests(unittest.TestCase):
    def setUp(self):
        old_mark = rectangle(-50, 600, -30, 665)
        new_mark = rectangle(-55, 600, -25, 665)
        translate = lambda points: [(x + 300, y) for x, y in points]
        self.old_contours = {'.notdef': [rectangle(0, 0, 300, 700)],
                             'a': [rectangle()], 'aacute': [rectangle(), rectangle(75, 600, 90, 665)],
                             'uni0301': [rectangle(75, 600, 90, 665)],
                             'uni030C.alt': [old_mark],
                             'uni0163': [rectangle(), rectangle(75, -80, 90, -30)]}
        for name in TARGETS - {'uni030C.alt'}:
            self.old_contours[name] = [rectangle(), translate(old_mark)]
        self.new_contours = deepcopy(self.old_contours)
        self.new_contours['uni030C.alt'] = [new_mark]
        for name in TARGETS - {'uni030C.alt'}:
            self.new_contours[name][-1] = translate(new_mark)
        self.new_contours['aacute'][0] = rectangle(right=205)
        self.new_contours['uni010F'][0] = rectangle(top=510)
        self.body = {'selectedGlyphs': ['aacute', 'uni010F']}
        self.marks = {'changedGlyphs': sorted(TARGETS),
                      'placements': [{'glyph': name, 'contour': 1, 'translation': [300, 0]}
                                     for name in sorted(TARGETS - {'uni030C.alt'})]}
        # These are OLD 1.001 indices. Current 1.002 retained contours are last,
        # so deliberately use 0 here to catch applying obsolete indices.
        protected = {name: {'wholeGlyph': False, 'preservedContours': [0]}
                     for name in ['aacute', 'uni013D', 'uni013E', 'uni010F', 'uni0165']}
        protected.update({name: {'wholeGlyph': True} for name in ['uni0301', 'uni030C.alt', 'uni0163']})
        self.preservation = {'diacritics': {'preservedGlyphs': protected}}

    def validate(self):
        return validate_outline_scope(font(self.old_contours), font(self.new_contours),
                                      self.body, self.marks, self.preservation)

    def kinds(self):
        return {f['kind'] for f in self.validate()['failures']}

    def test_precise_allowed_changes_and_last_contour_mapping_pass(self):
        result = self.validate()
        self.assertEqual(result['failures'], [])
        self.assertEqual(result['exactUnselectedAccentContours'], 1)
        self.assertEqual(result['exactSelectedPrecomposedBodies'], 3)
        self.assertTrue(all(p['exactSharedMarkTranslation'] for p in result['markPlacementChecks']))

    def test_unauthorized_plain_letter_change_is_rejected(self):
        self.new_contours['a'][0] = rectangle(right=201)
        self.assertIn('outline_outside_authorized_scope', self.kinds())

    def test_selected_letter_does_not_authorize_its_unchosen_accent(self):
        self.new_contours['aacute'][-1] = rectangle(75, 600, 92, 665)
        self.assertIn('unselected_accent_contours_changed', self.kinds())

    def test_sidecaron_selection_does_not_authorize_base_letter_change(self):
        self.new_contours['uni013D'][0] = rectangle(right=201)
        self.assertIn('selected_mark_changed_letter_body', self.kinds())

    def test_precomposed_mark_must_match_actual_shared_mark(self):
        self.new_contours['uni013D'][-1][1] = (246, 665)
        self.assertIn('placed_mark_does_not_match_shared_mark', self.kinds())

    def test_protected_whole_glyph_stays_protected_even_if_manifest_selects_it(self):
        self.body['selectedGlyphs'].append('uni0163')
        self.new_contours['uni0163'][0] = rectangle(right=201)
        self.assertIn('protected_whole_glyph_changed', self.kinds())
        self.assertIn('body_selection_overlaps_protected_whole_glyph', self.kinds())

    def test_notdef_cannot_be_silently_authorized(self):
        self.body['selectedGlyphs'].append('.notdef')
        self.new_contours['.notdef'][0] = rectangle(right=301)
        self.assertIn('notdef_changed', self.kinds())

    def test_reversed_mark_winding_is_a_topology_regression(self):
        self.new_contours['uni030C.alt'][0].reverse()
        for name in TARGETS - {'uni030C.alt'}:
            self.new_contours[name][-1].reverse()
        self.assertIn('shared_mark_topology_changed', self.kinds())

    def test_crossing_with_base_is_detected_even_if_translation_matches(self):
        self.new_contours['uni030C.alt'] = [rectangle(-50, 450, -30, 550)]
        for row in self.marks['placements']:
            row['translation'] = [220, 0]
            self.new_contours[row['glyph']][-1] = rectangle(170, 450, 190, 550)
        self.assertIn('selective_glyph_topology_regression', self.kinds())
        self.assertIn('sidecaron_clearance_below_guard', self.kinds())


if __name__ == '__main__':
    unittest.main()
