# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
"""Independent reference-vs-Fontmake geometry, layout and shaping audit."""
from __future__ import annotations
import hashlib
import unicodedata


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def point_recording(glyph):
    from fontTools.pens.pointPen import SegmentToPointPen
    from fontTools.pens.recordingPen import RecordingPointPen
    pen = RecordingPointPen()
    glyph.draw(SegmentToPointPen(pen, guessSmooth=False))
    return pen.value


def make_shaper(data):
    import uharfbuzz as hb
    font = hb.Font(hb.Face(data))
    font.scale = (font.face.upem, font.face.upem)
    return font


def shape(font, text, language, features=None):
    import uharfbuzz as hb
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    buffer.language = language
    hb.shape(font, buffer, features or {})
    return [(g.codepoint, g.cluster, p.x_advance, p.y_advance, p.x_offset, p.y_offset)
        for g, p in zip(buffer.glyph_infos, buffer.glyph_positions)]


def shaping_samples(font):
    cmap = font.getBestCmap()
    chars = ''.join(chr(cp) for cp in sorted(cmap))
    texts = set()
    for char in chars:
        texts.add(char)
        texts.add(unicodedata.normalize('NFD', char))
    # Exercise every encoded kern pair rather than only a headline sample.
    reverse = {name: chr(cp) for cp, name in cmap.items()}
    if 'kern' in font:
        for table in font['kern'].kernTables:
            for left, right in table.kernTable:
                if left in reverse and right in reverse:
                    texts.add(reverse[left] + reverse[right])
    for text in ['Nambli AVATAR To Wa office', 'Українська Ґґ Єє Іі Її Йй Щщ Яя',
            'бгдийптцшщь', 'Љљ Њњ Ћћ Ђђ Џџ Ќќ Ѓѓ', 'i\u0301 i\u0308 j\u0302',
            'A\u0308\u0304 a\u030a\u0301 u\u0308\u030c', '0123456789 @&%§¶']:
        texts.add(text)
        texts.add(unicodedata.normalize('NFD', text))
    return sorted(texts)


def validate_one(reference, target):
    from fontTools.ttLib import TTFont
    before_data, after_data = reference.read_bytes(), target.read_bytes()
    before, after = TTFont(reference, recalcTimestamp=False), TTFont(target, recalcTimestamp=False)
    old_order, new_order = before.getGlyphOrder(), after.getGlyphOrder()
    old_set, new_set = before.getGlyphSet(), after.getGlyphSet()
    common = sorted(set(old_order) & set(new_order))
    outline_changes, metric_changes, normalization = [], [], []
    max_delta = 0
    for name in common:
        old, new = point_recording(old_set[name]), point_recording(new_set[name])
        if old != new:
            outline_changes.append(name)
            p = [args[0] for op, args, kwargs in old if op == 'addPoint']
            q = [args[0] for op, args, kwargs in new if op == 'addPoint']
            if len(p) == len(q):
                if max_delta is not None:
                    max_delta = max(max_delta, *(abs(a - b) for x, y in zip(p, q) for a, b in zip(x, y)))
            else:
                max_delta = None
        elif before['glyf'][name].getCoordinates(before['glyf']) != after['glyf'][name].getCoordinates(after['glyf']):
            normalization.append(name)
        if before['hmtx'][name] != after['hmtx'][name]:
            metric_changes.append(dict(glyph=name, before=before['hmtx'][name], after=after['hmtx'][name]))
    layouts = {}
    for tag in ['GDEF', 'GSUB', 'GPOS', 'kern', 'STAT', 'meta']:
        a = before[tag].compile(before) if tag in before else b''
        b = after[tag].compile(after) if tag in after else b''
        layouts[tag] = dict(byteIdentical=a == b, beforeBytes=len(a), afterBytes=len(b),
            beforeSHA256=sha256(a), afterSHA256=sha256(b))
    mismatches, total = [], 0
    samples = shaping_samples(before)
    before_shaper, after_shaper = make_shaper(before_data), make_shaper(after_data)
    for language in ['en', 'uk', 'bg', 'sr', 'mk']:
        for text in samples:
            a, b = shape(before_shaper, text, language), shape(after_shaper, text, language)
            total += 1
            if a != b and len(mismatches) < 30:
                mismatches.append(dict(text=text, language=language, before=a, after=b))
    # Explicitly check kerning-disabled behavior as well as defaults.
    for text in ['AVATAR To Wa', 'Україна', 'бгдийптцшщь']:
        a, b = shape(before_shaper, text, 'uk', {'kern': False}), shape(after_shaper, text, 'uk', {'kern': False})
        total += 1
        if a != b:
            mismatches.append(dict(text=text, language='uk', feature='kern=0', before=a, after=b))
    meta_changes = {}
    for tag in ['head', 'hhea', 'OS/2', 'post', 'maxp']:
        changed = {}
        for key in sorted(set(vars(before[tag])) | set(vars(after[tag]))):
            a, b = getattr(before[tag], key, None), getattr(after[tag], key, None)
            if isinstance(a, (int, float, str, bool, type(None))) and a != b:
                changed[key] = dict(before=a, after=b)
        if changed:
            meta_changes[tag] = changed
    order_equal = old_order == new_order
    cmap_equal = before.getBestCmap() == after.getBestCmap()
    name_equal = before['name'].compile(before) == after['name'].compile(after)
    result = dict(face=reference.stem, sourceSHA256=sha256(before_data), builtSHA256=sha256(after_data),
        sourceGlyphs=len(old_order), outputGlyphs=len(new_order), encodedCharacters=len(before.getBestCmap()),
        exactGlyphOrder=order_equal, exactUnicodeMapping=cmap_equal, exactNameTable=name_equal,
        missingGlyphs=sorted(set(old_order) - set(new_order)), addedGlyphs=sorted(set(new_order) - set(old_order)),
        outlineChanges=outline_changes, maxCoordinateDifferenceUnits=max_delta, metricChanges=metric_changes,
        exactNormalizedQuadraticOutlines=len(common) - len(outline_changes),
        representationOnlyNormalizedGlyphs=normalization, layoutTables=layouts,
        shapingComparisons=total, shapingMismatchExamples=mismatches,
        metadataChanges=meta_changes, sourceTables=before.keys()[1:], outputTables=after.keys()[1:])
    result['status'] = 'PASS' if (order_equal and cmap_equal and name_equal and not outline_changes
        and not metric_changes and not mismatches and all(v['byteIdentical'] for v in layouts.values())) else 'FAIL'
    before.close()
    after.close()
    return result


def validate_all(reference_dir, output_dir, ufos):
    results = []
    for ufo in ufos:
        result = validate_one(reference_dir / (ufo.stem + '.ttf'), output_dir / (ufo.stem + '.ttf'))
        results.append(result)
        print(f"{result['face']}: {result['status']}; outlines {result['exactNormalizedQuadraticOutlines']}; shapes {result['shapingComparisons']}", flush=True)
    return dict(status='PASS' if all(r['status'] == 'PASS' for r in results) else 'FAIL', faces=len(results),
        glyphsCompared=sum(r['sourceGlyphs'] for r in results), shapingComparisons=sum(r['shapingComparisons'] for r in results),
        scope='Editable UFO to independent Fontmake/ufo2ft TTF build; no source binary outlines or tables copied during compilation.',
        notClaimed=['Google Fonts acceptance or all Fontspector checks passed', 'New repertoire or visual design approval',
            'A variable font or interpolation-compatible masters', 'Complete parametric Python design pipeline reproduction'], results=results)


def validate_ufo_sources(output_dir, ufos):
    """Verify directly against editable sources; no original binary is needed."""
    from fontTools.ttLib import TTFont
    from fontTools.ufoLib import UFOReader
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from types import SimpleNamespace
    from copy import deepcopy
    results = []
    for ufo in ufos:
        path = output_dir / (ufo.stem + '.ttf')
        with TTFont(path, recalcTimestamp=False) as font, UFOReader(ufo) as source:
            lib, glyphs = source.readLib(), source.getGlyphSet()
            order = lib['public.glyphOrder']
            assert order == font.getGlyphOrder(), (ufo.name, 'glyph order')
            built_glyphs = font.getGlyphSet()
            cmap = {}
            for name in order:
                glyph = SimpleNamespace(width=0, unicodes=[])
                glyphs.readGlyph(name, glyph)
                for cp in glyph.unicodes:
                    assert cp not in cmap
                    cmap[cp] = name
                assert point_recording(glyphs[name]) == point_recording(built_glyphs[name]), (ufo.name, name, 'outline')
                pen = TTGlyphPen(None)
                glyphs[name].draw(pen)
                expected = pen.glyph()
                expected.recalcBounds(None)
                assert (glyph.width, getattr(expected, 'xMin', 0)) == font['hmtx'][name], (ufo.name, name, 'metrics')
            assert cmap == font.getBestCmap(), (ufo.name, 'Unicode')
            reconstructed = deepcopy(font)
            for tag in ('GDEF', 'GSUB', 'GPOS'):
                if tag in reconstructed:
                    del reconstructed[tag]
            addOpenTypeFeaturesFromString(reconstructed, source.readFeatures())
            for tag in ('GDEF', 'GSUB', 'GPOS'):
                a = font[tag].compile(font) if tag in font else b''
                b = reconstructed[tag].compile(reconstructed) if tag in reconstructed else b''
                assert a == b, (ufo.name, tag, 'textual feature compilation')
            actual_kern = {}
            if 'kern' in font:
                for subtable in font['kern'].kernTables:
                    actual_kern.update(subtable.kernTable)
            assert source.readKerning() == actual_kern, (ufo.name, 'kerning')
            for tag, value in lib.get('public.openTypeMeta', {}).items():
                expected = ','.join(value) if tag in ('dlng', 'slng') else value
                assert font['meta'].data[tag] == expected, (ufo.name, 'meta', tag)
            results.append(dict(face=ufo.stem, status='PASS', glyphs=len(order), encodedCharacters=len(cmap),
                exactNormalizedQuadraticOutlines=len(order), exactMetrics=len(order),
                sourceKerningPairs=len(actual_kern), textualFeaturesMatch=True,
                sha256=sha256(path.read_bytes())))
    return dict(status='PASS', faces=len(results), glyphsCompared=sum(r['glyphs'] for r in results),
        shapingComparisons=0, scope='Self-contained editable UFO to Fontmake TTF build, verified directly against the UFO source.',
        referenceComparison=None, results=results,
        notClaimed=['Google Fonts acceptance or all Fontspector checks passed', 'Previous-release binary equivalence unless a reference comparison is included',
            'Visual design approval', 'A variable font or interpolation-compatible masters',
            'Complete parametric Python design pipeline reproduction'])
