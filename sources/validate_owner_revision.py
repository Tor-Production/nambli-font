# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Read-only independent scope/layout validator for the owner-directed 1.003.

No outline construction, fitting, offsetting, or repair module is imported.
Actual compiled TTF geometry and HarfBuzz output are the evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import unicodedata

from fontTools.ttLib import TTFont
from audit_visual_quality import EdgePen, audit_contours, flatten
from validate_build import make_shaper, point_recording, shape

TARGETS = frozenset({'uni030C.alt', 'uni013D', 'uni013E', 'uni010F', 'uni0165'})
PRECOMPOSED = TARGETS - {'uni030C.alt'}
LANGUAGES = ('en', 'uk', 'cs', 'sk', 'vi', 'tr')
LAYOUT_TABLES = ('GDEF', 'GSUB', 'GPOS', 'kern', 'STAT', 'meta', 'BASE', 'JSTF',
                 'MATH', 'morx', 'mort', 'kerx', 'ankr', 'feat', 'trak', 'opbd',
                 'lcar', 'HVAR', 'VVAR', 'MVAR', 'avar', 'fvar')
TOPOLOGY_FLAGS = {'open_contour', 'non_finite_coordinate', 'zero_area_contour',
                  'zero_length_segment', 'disconnected_segments',
                  'flattened_proper_crossing'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def outline(font, name):
    glyphs = font.getGlyphSet()
    pen = EdgePen(glyphs)
    glyphs[name].draw(pen)
    return pen.contours


def cyclic_equal(a, b):
    return len(a) == len(b) and (not a or any(a == b[i:] + b[:i] for i in range(len(b))))


def translated_contour(contour, offset):
    dx, dy = offset
    return [tuple((x + dx, y + dy) for x, y in segment) for segment in contour]


def polyline(contour):
    pieces = [flatten(s, .1) for s in contour]
    return ([pieces[0][0]] + [p for piece in pieces for p in piece[1:]]) if pieces else []


def area(contour):
    points = polyline(contour)
    return sum(a[0] * b[1] - a[1] * b[0] for a, b in zip(points, points[1:])) / 2


def topology(contours):
    areas = [area(c) for c in contours]
    return {'contours': len(contours), 'positive': sum(a > .01 for a in areas),
            'negative': sum(a < -.01 for a in areas), 'zero': sum(abs(a) <= .01 for a in areas)}


def point_segment_distance_squared(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    denominator = dx * dx + dy * dy
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / denominator)) if denominator else 0
    return (p[0] - a[0] - t * dx) ** 2 + (p[1] - a[1] - t * dy) ** 2


def boundary_clearance(mark, body):
    """Boundary distance from .1-unit flattened curves; crossings checked separately."""
    edges = lambda contours: [(a, b) for c in contours for a, b in zip(polyline(c), polyline(c)[1:])]
    left, right = edges(mark), edges(body)
    if not left or not right:
        return math.inf
    minimum = math.inf
    for a, b in left:
        for c, d in right:
            minimum = min(minimum, point_segment_distance_squared(a, c, d),
                          point_segment_distance_squared(b, c, d),
                          point_segment_distance_squared(c, a, b),
                          point_segment_distance_squared(d, a, b))
    return math.sqrt(minimum)


def validate_outline_scope(before, after, body_report, mark_report, preservation_report):
    failures = []
    fail = lambda kind, **details: failures.append({'kind': kind, **details})
    selected = set(body_report.get('selectedGlyphs', []))
    if not isinstance(body_report.get('selectedGlyphs'), list):
        fail('missing_body_selection')
    mark_selected = set(mark_report.get('changedGlyphs', []))
    if mark_selected != TARGETS:
        fail('unexpected_mark_scope', expected=sorted(TARGETS), actual=sorted(mark_selected))
    old_names, new_names = set(before.getGlyphOrder()), set(after.getGlyphOrder())
    if not selected <= old_names:
        fail('unknown_body_selection', glyphs=sorted(selected - old_names))
    preserved = preservation_report.get('diacritics', {}).get('preservedGlyphs', {})
    if not preserved:
        fail('missing_preservation_metadata')
    if '.notdef' in selected:
        fail('notdef_in_body_selection')
    old_set, new_set = before.getGlyphSet(), after.getGlyphSet()
    common = old_names & new_names
    before_contours = {n: outline(before, n) for n in common}
    after_contours = {n: outline(after, n) for n in common}
    changed = [n for n in before.getGlyphOrder() if n in common and point_recording(old_set[n]) != point_recording(new_set[n])]
    outside = sorted(set(changed) - selected - TARGETS)
    if outside:
        fail('outline_outside_authorized_scope', glyphs=outside)
    if '.notdef' not in common or '.notdef' in changed:
        fail('notdef_changed')
    if not TARGETS <= common:
        fail('missing_selective_target', glyphs=sorted(TARGETS - common))
        return {'failures': failures, 'outlineChanges': changed}

    placements = mark_report.get('placements', [])
    placement_names = [p.get('glyph') for p in placements]
    if set(placement_names) != PRECOMPOSED or len(placement_names) != len(PRECOMPOSED):
        fail('invalid_mark_placements', glyphs=placement_names)
    placements = {p['glyph']: p for p in placements if p.get('glyph') in PRECOMPOSED}
    exact_whole = exact_accents = exact_bodies = 0
    for name, disposition in preserved.items():
        if name not in common:
            fail('missing_preserved_glyph', glyph=name)
            continue
        old, new = before_contours[name], after_contours[name]
        if disposition.get('wholeGlyph'):
            if name == 'uni030C.alt':
                continue
            if name in selected:
                fail('body_selection_overlaps_protected_whole_glyph', glyph=name)
            if point_recording(old_set[name]) != point_recording(new_set[name]):
                fail('protected_whole_glyph_changed', glyph=name)
            else:
                exact_whole += 1
            continue
        count = len(disposition.get('preservedContours', []))
        if count <= 0 or count > min(len(old), len(new)):
            fail('invalid_retained_contour_count', glyph=name, count=count)
            continue
        # 1.002 appended retained accents LAST; original 1.001 indices are not
        # valid indices into these reference TTFs.
        if name in PRECOMPOSED:
            if count != 1:
                fail('ambiguous_sidecaron_count', glyph=name, count=count)
            if name not in selected:
                if old[:-count] != new[:-count]:
                    fail('selected_mark_changed_letter_body', glyph=name)
                else:
                    exact_bodies += 1
        elif old[-count:] != new[-count:]:
            fail('unselected_accent_contours_changed', glyph=name)
        else:
            exact_accents += count

    mark_before, mark_after = before_contours['uni030C.alt'], after_contours['uni030C.alt']
    if len(mark_after) != 1 or topology(mark_before) != topology(mark_after):
        fail('shared_mark_topology_changed', before=topology(mark_before), after=topology(mark_after))
    if 'uni030C.alt' not in changed:
        fail('selective_mark_was_not_changed')
    checks = []
    for name in sorted(TARGETS):
        old, new = before_contours[name], after_contours[name]
        if topology(old) != topology(new):
            fail('selective_glyph_topology_changed', glyph=name, before=topology(old), after=topology(new))
        old_report = audit_contours(old, upm=before['head'].unitsPerEm)
        new_report = audit_contours(new, upm=after['head'].unitsPerEm)
        old_flags = Counter(f['kind'] for f in old_report['flags'] if f['kind'] in TOPOLOGY_FLAGS)
        new_flags = Counter(f['kind'] for f in new_report['flags'] if f['kind'] in TOPOLOGY_FLAGS)
        regression = {kind: count for kind, count in new_flags.items() if count > old_flags.get(kind, 0)}
        if regression:
            fail('selective_glyph_topology_regression', glyph=name, flags=regression)
        if name not in PRECOMPOSED:
            continue
        placement = placements.get(name, {})
        index = placement.get('contour')
        if not isinstance(index, int) or index < 0 or index >= len(new):
            fail('invalid_mark_contour', glyph=name, contour=index)
            continue
        if index != len(new) - 1:
            fail('mark_is_not_retained_last_contour', glyph=name, contour=index)
        translation = placement.get('translation', [])
        if len(translation) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in translation):
            fail('invalid_mark_translation', glyph=name)
            continue
        identical = len(mark_after) == 1 and cyclic_equal(translated_contour(mark_after[0], translation), new[index])
        if not identical:
            fail('placed_mark_does_not_match_shared_mark', glyph=name)
        clearance = boundary_clearance([new[index]], [c for i, c in enumerate(new) if i != index])
        # Each flattened boundary is within .1 unit; retain a .2-unit allowance.
        if clearance < 11.8:
            fail('sidecaron_clearance_below_guard', glyph=name, clearance=clearance)
        checks.append({'glyph': name, 'contour': index, 'exactSharedMarkTranslation': identical,
                       'measuredBoundaryClearance': round(clearance, 4), 'flatteningTolerance': .1})
    return {'failures': failures, 'outlineChanges': changed, 'authorizedBodyGlyphs': sorted(selected),
            'authorizedMarkGlyphs': sorted(TARGETS), 'exactProtectedWholeGlyphs': exact_whole,
            'exactUnselectedAccentContours': exact_accents, 'exactSelectedPrecomposedBodies': exact_bodies,
            'markPlacementChecks': checks}


def shape_signature(rows):
    return [(gid, xa, ya, xo, yo) for gid, cluster, xa, ya, xo, yo in rows]


def validate_face(before_path, after_path, body_report, mark_report, preservation_report):
    before_data, after_data = before_path.read_bytes(), after_path.read_bytes()
    with TTFont(before_path) as before, TTFont(after_path) as after:
        result = validate_outline_scope(before, after, body_report, mark_report, preservation_report)
        failures = result['failures']
        def check(condition, kind, **detail):
            if not condition:
                failures.append({'kind': kind, **detail})
        check(len(before.getGlyphOrder()) == len(after.getGlyphOrder()) == 998, 'glyph_count')
        check(len(before.getBestCmap()) == len(after.getBestCmap()) == 970, 'unicode_count')
        check(before.getGlyphOrder() == after.getGlyphOrder(), 'glyph_order_changed')
        check(before.getBestCmap() == after.getBestCmap(), 'unicode_mapping_changed')
        check(after['name'].getDebugName(5) == 'Version 1.003', 'wrong_name_version')
        check(abs(after['head'].fontRevision - 1.003) < .00002, 'wrong_head_version')
        check(before['head'].unitsPerEm == after['head'].unitsPerEm, 'units_per_em_changed')
        advances = {n: [before['hmtx'][n][0], after['hmtx'][n][0]] for n in set(before.getGlyphOrder()) & set(after.getGlyphOrder())
                    if before['hmtx'][n][0] != after['hmtx'][n][0]}
        check(not advances, 'advances_changed', glyphs=advances)
        tables = {}
        for tag in LAYOUT_TABLES:
            a = before[tag].compile(before) if tag in before else None
            b = after[tag].compile(after) if tag in after else None
            tables[tag] = {'identical': a == b, 'present': b is not None,
                           'beforeSHA256': digest(a) if a is not None else None,
                           'afterSHA256': digest(b) if b is not None else None}
            check(a == b, 'layout_table_changed', table=tag)
        for tag in ('vmtx',):
            check((tag in before) == (tag in after), 'vertical_metrics_presence_changed', table=tag)
            if tag in before and tag in after:
                check(before[tag].metrics == after[tag].metrics, 'vertical_metrics_changed')
        for table, attrs in [('hhea', ('ascent', 'descent', 'lineGap', 'caretSlopeRise', 'caretSlopeRun', 'caretOffset')),
                             ('OS/2', ('sTypoAscender', 'sTypoDescender', 'sTypoLineGap', 'usWinAscent', 'usWinDescent', 'sxHeight', 'sCapHeight'))]:
            for attr in attrs:
                a, b = getattr(before[table], attr, None), getattr(after[table], attr, None)
                check(a == b, 'line_metric_changed', table=table, field=attr, before=a, after=b)
        check(after['OS/2'].usWinAscent >= after['head'].yMax and after['OS/2'].usWinDescent >= -after['head'].yMin, 'clipped_font_bounds')
        old_shaper, new_shaper = make_shaper(before_data), make_shaper(after_data)
        normalization_count = stable_count = known_count = 0
        known_examples = []
        for cp in before.getBestCmap():
            char = chr(cp); nfd = unicodedata.normalize('NFD', char)
            if char == nfd:
                continue
            for language in LANGUAGES:
                old_nfc, old_nfd = shape_signature(shape(old_shaper, char, language)), shape_signature(shape(old_shaper, nfd, language))
                new_nfc, new_nfd = shape_signature(shape(new_shaper, char, language)), shape_signature(shape(new_shaper, nfd, language))
                normalization_count += 1; stable_count += 2
                check((old_nfc, old_nfd) == (new_nfc, new_nfd), 'shaping_changed', unicode=f'U+{cp:04X}', language=language)
                if new_nfc != new_nfd:
                    if old_nfc == old_nfd:
                        check(False, 'new_normalization_mismatch', unicode=f'U+{cp:04X}', language=language)
                    else:
                        known_count += 1
                        if len(known_examples) < 20:
                            known_examples.append({'unicode': f'U+{cp:04X}', 'language': language})
        for text in ['Ľavý ľad ďalej ťava Ľľďť', 'Ç Ğ İ Ö Ş Ü ç ğ ı ö ş ü',
                     'Iİıi I\u0307 i\u0307', 'ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ',
                     'abcçdefgğhıijklmnoöprsştuüvyz']:
            for language in LANGUAGES:
                for value in (text, unicodedata.normalize('NFD', text)):
                    stable_count += 1
                    check(shape(old_shaper, value, language) == shape(new_shaper, value, language), 'control_text_shaping_changed', text=value, language=language)
        result.update(font=after_path.stem, status='FAIL' if failures else 'PASS', beforeSHA256=digest(before_data), afterSHA256=digest(after_data),
                      glyphs=len(after.getGlyphOrder()), encodedCharacters=len(after.getBestCmap()), identicalLayoutTables=tables,
                      advancesChanged=advances, normalizationComparisons=normalization_count, shapingStabilityComparisons=stable_count,
                      knownNormalizationMismatchCount=known_count, knownNormalizationMismatchExamples=known_examples)
        return result


def validate(before_dir, after_dir, body_reports, mark_reports, preservation_reports):
    results = []; failures = []
    paths = sorted(after_dir.glob('Nambli-*.ttf'))
    if len(paths) != 12:
        failures.append({'kind': 'face_count', 'actual': len(paths), 'expected': 12})
    if {p.name for p in paths} != {p.name for p in before_dir.glob('Nambli-*.ttf')}:
        failures.append({'kind': 'family_face_set_changed'})
    for path in paths:
        try:
            reports = [json.loads((directory / (path.stem + '.json')).read_text(encoding='utf-8'))
                       for directory in (body_reports, mark_reports, preservation_reports)]
            result = validate_face(before_dir / path.name, path, *reports)
            results.append(result)
            failures.extend({'font': path.stem, **f} for f in result['failures'])
            print(json.dumps({'font': path.stem, 'status': result['status'], 'failures': len(result['failures'])}), flush=True)
        except (OSError, KeyError, ValueError, TypeError) as error:
            failures.append({'font': path.stem, 'kind': 'validation_input_error', 'error': str(error)})
    return {'status': 'FAIL' if failures else 'PASS', 'version': '1.003', 'faces': len(results),
            'glyphsCompared': sum(r['glyphs'] for r in results),
            'normalizationComparisons': sum(r['normalizationComparisons'] for r in results),
            'shapingStabilityComparisons': sum(r['shapingStabilityComparisons'] for r in results),
            'failures': failures, 'results': results,
            'validatorSHA256': digest(Path(__file__).read_bytes()),
            'scope': 'Remove only reported added overshoots and adjust five side-caron glyphs; all other accent designs retained.',
            'notClaimed': ['Visual approval', 'Google Fonts acceptance', 'Frozen whole-family geometry audit or Fontspector pass']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'body-reports', 'mark-reports', 'preservation-reports', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.before, args.after, args.body_reports, args.mark_reports, args.preservation_reports)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'results'}))
    if result['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
