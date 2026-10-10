# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Independent, read-only edge audit of every compiled glyph in a TTF family.

The audit imports no Nambli drawing or smoothing code. It measures quadratic
Bezier geometry as delivered to users, including implied on-curve points.
Flags are review candidates, not proof that an intentional letter join is bad.
Integer-coordinate rounding is explicitly allowed for endpoint tangents.
No outline is modified and no subjective visual-approval claim is made.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import platform

import fontTools
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont


def vector(a, b):
    return b[0] - a[0], b[1] - a[1]


def length(v):
    return math.hypot(*v)


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def angle(a, b):
    denominator = length(a) * length(b)
    if not denominator:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0,
        (a[0] * b[0] + a[1] * b[1]) / denominator))))


def tangent(segment, end=False):
    origin = segment[-1] if end else segment[0]
    controls = reversed(segment[:-1]) if end else segment[1:]
    for control in controls:
        direction = vector(control, origin) if end else vector(origin, control)
        if length(direction) > 1e-9:
            return direction
    return (0.0, 0.0)


def split(segment):
    rows = [segment]
    while len(rows[-1]) > 1:
        rows.append(tuple(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                          for a, b in zip(rows[-1], rows[-1][1:])))
    return tuple(row[0] for row in rows), tuple(row[-1] for row in reversed(rows))


def evaluate(points, t):
    points = list(points)
    while len(points) > 1:
        points = [((1 - t) * a[0] + t * b[0], (1 - t) * a[1] + t * b[1])
                  for a, b in zip(points, points[1:])]
    return points[0]


def curvature(segment, t):
    """Signed analytical curvature, in inverse font units (not angle/length)."""
    degree = len(segment) - 1
    if degree < 2:
        return 0.0
    first = [tuple(degree * v for v in vector(a, b)) for a, b in zip(segment, segment[1:])]
    second = [tuple((degree - 1) * v for v in vector(a, b)) for a, b in zip(first, first[1:])]
    velocity, acceleration = evaluate(first, t), evaluate(second, t)
    speed = length(velocity)
    if speed < 1e-9:
        return None
    return cross(velocity, acceleration) / speed ** 3


def flatten(segment, tolerance=0.25, depth=0):
    """Adaptive subdivision; tolerance is font units, not display pixels."""
    chord = vector(segment[0], segment[-1])
    denominator = length(chord)
    flatness = max((abs(cross(chord, vector(segment[0], p))) / denominator
                   if denominator else length(vector(segment[0], p))
                   for p in segment[1:-1]), default=0.0)
    # A collinear backtracking curve is not a straight segment.
    polygon_length = sum(length(vector(a, b)) for a, b in zip(segment, segment[1:]))
    if len(segment) == 2 or (flatness <= tolerance and
                            polygon_length <= denominator + tolerance) or depth >= 16:
        return [segment[0], segment[-1]]
    left, right = split(segment)
    return flatten(left, tolerance, depth + 1)[:-1] + flatten(right, tolerance, depth + 1)


class EdgePen(BasePen):
    def __init__(self, glyph_set=None):
        super().__init__(glyph_set)
        self.contours = []
        self.open_contours = []
        self.current = []
        self.start = None

    def _moveTo(self, point):
        self.start = point
        self.current = []

    def _lineTo(self, point):
        self.current.append((self._getCurrentPoint(), point))

    def _qCurveToOne(self, p1, p2):
        self.current.append((self._getCurrentPoint(), p1, p2))

    def _curveToOne(self, p1, p2, p3):
        self.current.append((self._getCurrentPoint(), p1, p2, p3))

    def _closePath(self):
        if self._getCurrentPoint() != self.start:
            self.current.append((self._getCurrentPoint(), self.start))
        self.contours.append(self.current)

    def _endPath(self):
        self.open_contours.append(len(self.contours))
        self.contours.append(self.current)


def proper_crossing(a, b, c, d):
    """Interior crossings only; tangencies/end-point contacts are not failures."""
    u, v = vector(a, b), vector(c, d)
    determinant = cross(u, v)
    if abs(determinant) < 1e-9:
        return None
    delta = vector(a, c)
    t, s = cross(delta, v) / determinant, cross(delta, u) / determinant
    if 1e-6 < t < 1 - 1e-6 and 1e-6 < s < 1 - 1e-6:
        return (a[0] + t * u[0], a[1] + t * u[1])
    return None


def crossings(flat_contours, cell_size=64):
    """Spatial broad phase avoids a quadratic scan of the whole glyph."""
    cells = defaultdict(list)
    edges = []
    found = []
    for contour_index, contour in enumerate(flat_contours):
        count = len(contour) - 1
        for edge_index, (a, b) in enumerate(zip(contour, contour[1:])):
            if length(vector(a, b)) < 1e-9:
                continue
            occupied = [(x, y)
                for x in range(math.floor(min(a[0], b[0]) / cell_size),
                               math.floor(max(a[0], b[0]) / cell_size) + 1)
                for y in range(math.floor(min(a[1], b[1]) / cell_size),
                               math.floor(max(a[1], b[1]) / cell_size) + 1)]
            prior = set(i for cell in occupied for i in cells[cell])
            for other_index in sorted(prior):
                other_contour, other_edge, c, d = edges[other_index]
                if other_contour == contour_index and (
                        abs(edge_index - other_edge) <= 1 or
                        {edge_index, other_edge} == {0, count - 1}):
                    continue
                crossing = proper_crossing(a, b, c, d)
                if crossing:
                    found.append({'contour': contour_index, 'flattened_edge': edge_index,
                                  'other_contour': other_contour, 'other_flattened_edge': other_edge,
                                  'point': [round(v, 4) for v in crossing]})
            new_index = len(edges)
            edges.append((contour_index, edge_index, a, b))
            for cell in occupied:
                cells[cell].append(new_index)
    return found


def audit_contours(contours, open_contours=(), upm=1000, point_indices=None):
    scale = upm / 1000.0
    point_indices = point_indices or {}
    flags, flat_contours, contour_details = [], [], []
    counts = Counter()
    for ci, segments in enumerate(contours):
        counts['contours'] += 1
        if ci in open_contours:
            flags.append({'kind': 'open_contour', 'severity': 'error', 'contour': ci})
        points = [p for segment in segments for p in segment]
        if not all(math.isfinite(v) for p in points for v in p):
            flags.append({'kind': 'non_finite_coordinate', 'severity': 'error', 'contour': ci})
            flat_contours.append([])
            continue
        flattened = [flatten(segment, .25 * scale) for segment in segments]
        flat = ([flattened[0][0]] + [p for line in flattened for p in line[1:]]) if flattened else []
        flat_contours.append(flat)
        area = sum(cross(a, b) for a, b in zip(flat, flat[1:])) / 2
        contour_details.append({'contour': ci, 'segments': len(segments),
                                'signed_area': round(area, 3),
                                'winding': 'counterclockwise' if area > 0 else 'clockwise' if area < 0 else 'zero'})
        if segments and abs(area) < .01 * scale * scale:
            flags.append({'kind': 'zero_area_contour', 'severity': 'error', 'contour': ci})
        arc_lengths = [sum(length(vector(a, b)) for a, b in zip(line, line[1:])) for line in flattened]
        for i, current in enumerate(segments):
            counts['segments'] += 1
            following = segments[(i + 1) % len(segments)]
            at = current[-1]
            location = {'contour': ci, 'segment': i, 'point': [round(v, 4) for v in at],
                        'ttf_point_indices': point_indices.get(at, []),
                        'point_kind': 'explicit' if at in point_indices else 'implied_or_decomposed'}
            if arc_lengths[i] < 1e-7:
                flags.append(dict(location, kind='zero_length_segment', severity='review'))
                continue
            if current[-1] != following[0]:
                flags.append(dict(location, kind='disconnected_segments', severity='error'))
            before, after = tangent(current, True), tangent(following)
            raw_angle = angle(before, after)
            counts['joins'] += 1
            counts['joins_angle_gt_8'] += raw_angle > 8
            counts['joins_angle_gt_30'] += raw_angle > 30
            counts['joins_angle_gt_90'] += raw_angle > 90
            curved_join = len(current) > 2 or len(following) > 2
            counts['curve_joins'] += curved_join
            # Each integer-coordinate control vector may move by sqrt(2) units
            # from rounding its two endpoints. This conservative bound prevents
            # calling small quantization noise a certain design defect.
            allowance = sum(math.degrees(math.asin(min(1, math.sqrt(2) / max(length(v), 1e-9))))
                            for v in (before, after))
            effective = max(0, raw_angle - allowance)
            detail = dict(location, angle_degrees=round(raw_angle, 3),
                          quantization_allowance_degrees=round(allowance, 3),
                          angle_beyond_allowance_degrees=round(effective, 3),
                          adjacent_lengths=[round(arc_lengths[i], 3),
                                            round(arc_lengths[(i + 1) % len(segments)], 3)],
                          adjacent_types=['line' if len(s) == 2 else 'quadratic' if len(s) == 3 else 'cubic'
                                          for s in (current, following)])
            if curved_join and raw_angle > 8 and effective > 4:
                flags.append(dict(detail, kind='curve_tangent_break',
                                  severity='high' if effective >= 25 else 'review'))
            elif not curved_join and raw_angle > 8:
                flags.append(dict(detail, kind='line_corner', severity='intentional_corner_review'))
            elif curved_join and raw_angle > 30 and min(length(before), length(after)) < 4 * scale:
                flags.append(dict(detail, kind='short_handle_corner', severity='review'))
            # G1 (tangent) continuity alone does not imply visually fair curves.
            # A tiny fillet can join a large bowl perfectly tangentially while
            # making a conspicuous bump. Screen G1 joins independently for a
            # sudden radius change and a short, reversing curvature wave.
            curvature_a, curvature_b = curvature(current, 1), curvature(following, 0)
            if curved_join and effective <= 4 and curvature_a is not None and curvature_b is not None:
                ca, cb = curvature_a * scale, curvature_b * scale
                radius_detail = dict(detail,
                    curvature_before=round(curvature_a, 7), curvature_after=round(curvature_b, 7),
                    radius_before=None if abs(curvature_a) < 1e-10 else round(1 / abs(curvature_a), 3),
                    radius_after=None if abs(curvature_b) < 1e-10 else round(1 / abs(curvature_b), 3))
                smaller, larger = sorted([abs(ca), abs(cb)])
                # Very short integer-rounded handles make analytical curvature
                # ill-conditioned. Those are covered by the angle/micro-facet
                # checks above rather than mixed into the broader curve screen.
                if min(arc_lengths[i], arc_lengths[(i + 1) % len(segments)]) >= 8 * scale and min(length(before), length(after)) >= 3 * scale:
                    if abs(ca - cb) > .015 and larger > max(4 * smaller, .02):
                        flags.append(dict(radius_detail, kind='sudden_curvature_change', severity='review'))
                    if ca * cb < 0 and min(abs(ca), abs(cb)) > .004 and (
                            arc_lengths[i] + arc_lengths[(i + 1) % len(segments)] < 80 * scale):
                        flags.append(dict(radius_detail, kind='short_curvature_reversal', severity='review'))
            if len(current) == 2 and 0 < arc_lengths[i] <= 12 * scale and len(segments) > 2:
                preceding = segments[(i - 1) % len(segments)]
                if len(preceding) > 2 and len(following) > 2:
                    entrance = angle(tangent(preceding, True), tangent(current))
                    if max(entrance, raw_angle) > 8:
                        flags.append(dict(detail, kind='short_line_facet_between_curves', severity='review',
                                          facet_length=round(arc_lengths[i], 4),
                                          entrance_angle_degrees=round(entrance, 3)))
    intersections = crossings(flat_contours, 64 * scale)
    counts['proper_crossings'] = len(intersections)
    for found in intersections:
        flags.append(dict(found, kind='flattened_proper_crossing', severity='high',
                          note='Confirm in exact outline; adaptive flattening tolerance is 0.25 units per 1000 UPM.'))
    return {'counts': dict(counts), 'contours': contour_details, 'flags': flags}


def source_point_indices(font, glyph_name):
    glyph = font['glyf'][glyph_name]
    coordinates, _, _ = glyph.getCoordinates(font['glyf'])
    indices = defaultdict(list)
    for index, point in enumerate(coordinates):
        indices[tuple(point)].append(index)
    return dict(indices)


def audit_font(path):
    with TTFont(path) as font:
        glyph_set = font.getGlyphSet()
        unicode_map = defaultdict(list)
        for codepoint, name in font.getBestCmap().items():
            unicode_map[name].append(f'U+{codepoint:04X}')
        glyph_reports = {}
        totals = Counter()
        kinds = Counter()
        severities = Counter()
        for glyph_name in font.getGlyphOrder():
            pen = EdgePen(glyph_set)
            glyph_set[glyph_name].draw(pen)
            report = audit_contours(pen.contours, pen.open_contours, font['head'].unitsPerEm,
                                    source_point_indices(font, glyph_name))
            report['unicodes'] = unicode_map.get(glyph_name, [])
            glyph_reports[glyph_name] = report
            totals.update(report['counts'])
            kinds.update(f['kind'] for f in report['flags'])
            severities.update(f['severity'] for f in report['flags'])
        probes = {}
        for name in ['.notdef', 'O', 'o', 'a', 'b', 'e', 'r', 'k', 's', 'x', 'n']:
            if name not in glyph_set:
                continue
            glyph = font['glyf'][name]
            glyph.recalcBounds(font['glyf'])
            probes[name] = {'bounds': [getattr(glyph, field, None)
                                       for field in ['xMin', 'yMin', 'xMax', 'yMax']],
                            'advance': font['hmtx'][name][0],
                            'contours': len(glyph_reports[name]['contours'])}
        notdef_equal_o = False
        if '.notdef' in glyph_set and 'O' in glyph_set:
            pen_a, pen_b = EdgePen(glyph_set), EdgePen(glyph_set)
            glyph_set['.notdef'].draw(pen_a)
            glyph_set['O'].draw(pen_b)
            notdef_equal_o = pen_a.contours == pen_b.contours
        return {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'upm': font['head'].unitsPerEm, 'version': round(font['head'].fontRevision, 3),
                'glyphs_scanned': len(glyph_reports), 'encoded_codepoints': len(font.getBestCmap()),
                'counts': dict(totals), 'flag_counts': dict(kinds), 'severity_counts': dict(severities),
                'overshoot_probes': probes, 'notdef_exactly_equals_O': notdef_equal_o,
                'glyphs': glyph_reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fonts', type=Path, required=True, help='Directory containing compiled TTF files')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(args.fonts.glob('*.ttf'))
    if not paths:
        parser.error('No TTF files in --fonts directory')
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for path in paths:
        result = audit_font(path)
        (args.output / (path.stem + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
        summary = {k: v for k, v in result.items() if k != 'glyphs'}
        results.append(summary)
        print(json.dumps({'font': path.stem, 'glyphs': result['glyphs_scanned'],
                          'flags': result['flag_counts']}), flush=True)
    combined = Counter()
    for result in results:
        combined.update(result['flag_counts'])
    report = {'audit_schema': 2, 'status': 'MEASURED_REQUIRES_VISUAL_REVIEW',
              'audit_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'python_version': platform.python_version(), 'fonttools_version': fontTools.__version__,
              'scope': 'Every glyph and every decomposed contour, including unencoded glyphs, in all supplied TTFs',
              'faces': len(results), 'glyph_face_pairs': sum(r['glyphs_scanned'] for r in results),
              'flag_counts': dict(combined), 'criteria': {
                  'curve_tangent_break': 'Raw endpoint tangent angle > 8 degrees and exceeds conservative integer rounding allowance by > 4 degrees; high if excess >= 25 degrees.',
                  'short_handle_corner': 'Angle > 30 degrees at a curve join with a tangent vector shorter than 4/1000 UPM, otherwise masked by integer rounding allowance.',
                  'short_line_facet_between_curves': 'Line <= 12/1000 UPM between curves, with an endpoint angle > 8 degrees.',
                  'line_corner': 'Line/line angle > 8 degrees; preserved as intentional-design review, never blindly rounded or required to reach zero.',
                  'sudden_curvature_change': 'At a join within 4 degrees of tangent continuity after rounding allowance: adjacent lengths >=8 and tangent control vectors >=3/1000 UPM, signed curvature jump > .015 inverse units and >4:1 magnitude ratio with peak > .02 (normalized to 1000 UPM). Includes possibly intentional line-to-fillet transitions; review required.',
                  'short_curvature_reversal': 'At a join within 4 degrees of tangent continuity after rounding allowance: opposite signed endpoint curvatures, both > .004 inverse units, tangent control vectors >=3, adjacent lengths >=8 and total <80 (normalized to 1000 UPM). Natural S-curves remain possible; review required.',
                  'proper_crossings': 'Interior segment crossings after adaptive Bezier subdivision at 0.25/1000 UPM tolerance; exact-outline confirmation required.',
                  'limitations': 'Does not prove perceived smoothness, classify all intentional corners, or measure optical balance. Curvature screens nominate local changes but do not establish visual defects; image review is required.'},
              'results': results}
    (args.output / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ['results', 'criteria']}))


if __name__ == '__main__':
    main()
