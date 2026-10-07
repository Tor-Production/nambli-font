# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
"""Export and validate editable UFO3 snapshots of the input static TTFs.

This preserves the input quadratic curves; it is not a replacement for the
original parametric Python design sources. See README.md for the exact scope.
Run with Python and fonttools installed, or pass --deps to a local dependency
directory. No input file is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bits(value, length=32):
    return [i for i in range(length) if value & (1 << i)]


def font_info(font):
    names = font['name']
    name = names.getDebugName
    head, os2, hhea, post = (font[tag] for tag in ('head', 'OS/2', 'hhea', 'post'))
    style = (name(2) or 'Regular').lower()
    info = dict(
        familyName=name(16) or name(1),
        styleName=name(17) or name(2),
        styleMapFamilyName=name(1),
        styleMapStyleName=style,
        unitsPerEm=head.unitsPerEm,
        versionMajor=int(head.fontRevision),
        versionMinor=round((head.fontRevision-int(head.fontRevision))*1000),
        ascender=os2.sTypoAscender,
        descender=os2.sTypoDescender,
        xHeight=os2.sxHeight,
        capHeight=os2.sCapHeight,
        italicAngle=post.italicAngle,
        copyright=name(0) or '',
        postscriptFontName=name(6),
        postscriptFullName=name(4),
        postscriptUnderlinePosition=post.underlinePosition,
        postscriptUnderlineThickness=post.underlineThickness,
        postscriptIsFixedPitch=bool(post.isFixedPitch),
        openTypeHeadCreated=(datetime(1904, 1, 1) + timedelta(seconds=head.created)).strftime('%Y/%m/%d %H:%M:%S'),
        openTypeHeadFlags=bits(head.flags, 16),
        openTypeHeadLowestRecPPEM=head.lowestRecPPEM,
        openTypeHheaAscender=hhea.ascent,
        openTypeHheaDescender=hhea.descent,
        openTypeHheaLineGap=hhea.lineGap,
        openTypeHheaCaretSlopeRise=hhea.caretSlopeRise,
        openTypeHheaCaretSlopeRun=hhea.caretSlopeRun,
        openTypeHheaCaretOffset=hhea.caretOffset,
        openTypeOS2WeightClass=os2.usWeightClass,
        openTypeOS2WidthClass=os2.usWidthClass,
        openTypeOS2VendorID=os2.achVendID,
        openTypeOS2Selection=[i for i in bits(os2.fsSelection, 16) if i not in (0, 5, 6)],
        openTypeOS2Type=bits(os2.fsType, 16),
        openTypeOS2TypoAscender=os2.sTypoAscender,
        openTypeOS2TypoDescender=os2.sTypoDescender,
        openTypeOS2TypoLineGap=os2.sTypoLineGap,
        openTypeOS2WinAscent=os2.usWinAscent,
        openTypeOS2WinDescent=os2.usWinDescent,
        openTypeOS2FamilyClass=[(os2.sFamilyClass >> 8) & 255, os2.sFamilyClass & 255],
        openTypeOS2Panose=[getattr(os2.panose, k) for k in (
            'bFamilyType', 'bSerifStyle', 'bWeight', 'bProportion', 'bContrast',
            'bStrokeVariation', 'bArmStyle', 'bLetterForm', 'bMidline', 'bXHeight')],
        openTypeOS2UnicodeRanges=[32 * block + bit for block in range(4)
            for bit in bits(getattr(os2, 'ulUnicodeRange' + str(block + 1)))],
        openTypeOS2CodePageRanges=[32 * block + bit for block in range(2)
            for bit in bits(getattr(os2, 'ulCodePageRange' + str(block + 1)))],
        openTypeNameRecords=[dict(nameID=r.nameID, platformID=r.platformID,
            encodingID=r.platEncID, languageID=r.langID, string=r.toUnicode())
            for r in names.names],
    )
    for attr, source in (
        ('openTypeOS2SubscriptXSize', 'ySubscriptXSize'),
        ('openTypeOS2SubscriptYSize', 'ySubscriptYSize'),
        ('openTypeOS2SubscriptXOffset', 'ySubscriptXOffset'),
        ('openTypeOS2SubscriptYOffset', 'ySubscriptYOffset'),
        ('openTypeOS2SuperscriptXSize', 'ySuperscriptXSize'),
        ('openTypeOS2SuperscriptYSize', 'ySuperscriptYSize'),
        ('openTypeOS2SuperscriptXOffset', 'ySuperscriptXOffset'),
        ('openTypeOS2SuperscriptYOffset', 'ySuperscriptYOffset'),
        ('openTypeOS2StrikeoutSize', 'yStrikeoutSize'),
        ('openTypeOS2StrikeoutPosition', 'yStrikeoutPosition'),
    ):
        info[attr] = getattr(os2, source)
    for attr, name_id in (
        ('openTypeNameUniqueID', 3), ('openTypeNameVersion', 5),
        ('openTypeNameManufacturer', 8), ('openTypeNameDesigner', 9),
        ('openTypeNameDescription', 10), ('openTypeNameManufacturerURL', 11),
        ('openTypeNameDesignerURL', 12), ('openTypeNameLicense', 13),
        ('openTypeNameLicenseURL', 14), ('openTypeNamePreferredFamilyName', 16),
        ('openTypeNamePreferredSubfamilyName', 17),
    ):
        if name(name_id) is not None:
            info[attr] = name(name_id)
    if 'gasp' in font:
        info['openTypeGaspRangeRecords'] = [dict(rangeMaxPPEM=key,
            rangeGaspBehavior=bits(value, 4)) for key, value in sorted(font['gasp'].gaspRange.items())]
    return SimpleNamespace(**info)


def feature_source(original, italic):
    if not italic:
        return original
    slant = math.tan(math.radians(10))
    def replace(match):
        x, y = map(int, match.groups())
        return f'<anchor {round(x + slant * y - slant * 265)} {y}>'
    return re.sub(r'<anchor (-?\d+) (-?\d+)>', replace, original)


def export_one(ttf, features, output, transform_italic=True):
    from fontTools.ttLib import TTFont
    from fontTools.pens.pointPen import SegmentToPointPen
    from fontTools.pens.recordingPen import RecordingPointPen
    from fontTools.ufoLib import UFOWriter

    font = TTFont(ttf, recalcTimestamp=False)
    order = font.getGlyphOrder()
    cmap = font.getBestCmap()
    reverse = {}
    for cp, glyph in sorted(cmap.items()):
        reverse.setdefault(glyph, []).append(cp)
    assert order and cmap, (ttf.name, 'empty font')
    assert not any(font['glyf'][n].isComposite() for n in order)
    italic = bool(font['OS/2'].fsSelection & 1)
    ufo = output / (ttf.stem + '.ufo')
    if ufo.exists():
        raise FileExistsError(f'Refusing to overwrite {ufo}; select a new output directory.')
    writer = UFOWriter(ufo, formatVersion=3)
    writer.writeInfo(font_info(font))
    writer.writeLib({
        'public.glyphOrder': order,
        'com.nambli.snapshot.sourceTTF': ttf.name,
        'com.nambli.snapshot.sourceSHA256': digest(ttf.read_bytes()),
        'com.nambli.snapshot.sourceVersion': font['name'].getDebugName(5) or str(font['head'].fontRevision),
        'com.nambli.snapshot.scope': 'Exact editable quadratic outlines; retain original Python design sources separately.',
        'com.nambli.snapshot.hmtx': {n: list(font['hmtx'][n]) for n in order},
        'com.nambli.snapshot.legacyKernSubtables': [
            {'version': k.version, 'coverage': k.coverage, 'pairCount': len(k.kernTable)}
            for k in font['kern'].kernTables],
    })
    writer.writeFeatures(feature_source(features, italic) if transform_italic else features)
    kern = {}
    for table in font['kern'].kernTables:
        assert table.version == 0 and table.coverage == 1
        kern.update(table.kernTable)
    writer.writeKerning(kern)
    glyph_set = writer.getGlyphSet()
    original_glyphs = font.getGlyphSet()
    for glyph_name in order:
        rec = RecordingPointPen()
        original_glyphs[glyph_name].draw(SegmentToPointPen(rec, guessSmooth=False))
        width, lsb = font['hmtx'][glyph_name]
        obj = SimpleNamespace(width=width, unicodes=reverse.get(glyph_name, []),
            lib={'com.nambli.snapshot.leftSideBearing': lsb})
        glyph_set.writeGlyph(glyph_name, obj, rec.replay)
    glyph_set.writeContents()
    writer.writeLayerContents()
    writer.close()
    font.close()
    return ufo


def validate_one(ttf, ufo):
    from fontTools.ttLib import TTFont
    from fontTools.pens.pointPen import SegmentToPointPen
    from fontTools.pens.recordingPen import RecordingPointPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ufoLib import UFOReader
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

    font = TTFont(ttf, recalcTimestamp=False)
    rebuilt = TTFont(ttf, recalcTimestamp=False)
    reader = UFOReader(ufo, validate=True)
    glyphs = reader.getGlyphSet()
    original_glyphs = font.getGlyphSet()
    order = font.getGlyphOrder()
    assert set(glyphs.keys()) == set(order)
    assert reader.readLib()['public.glyphOrder'] == order
    info = SimpleNamespace()
    reader.readInfo(info)
    expected_info = vars(font_info(font))
    assert all(getattr(info, key) == val for key, val in expected_info.items())
    exported_cmap = {}
    point_operations = 0
    exact_binary_outlines = 0
    binary_normalizations = []
    contour_total = 0
    for name in order:
        original_rec, ufo_rec = RecordingPointPen(), RecordingPointPen()
        original_glyphs[name].draw(SegmentToPointPen(original_rec, guessSmooth=False))
        obj = SimpleNamespace(width=0, unicodes=[], lib={})
        glyphs.readGlyph(name, obj, ufo_rec)
        assert ufo_rec.value == original_rec.value, (ttf.name, name, 'UFO points changed')
        point_operations += sum(op == 'addPoint' for op, args, kwargs in ufo_rec.value)
        assert obj.width == font['hmtx'][name][0], (name, 'advance changed')
        assert obj.lib['com.nambli.snapshot.leftSideBearing'] == font['hmtx'][name][1]
        for cp in getattr(obj, 'unicodes', []):
            assert cp not in exported_cmap
            exported_cmap[cp] = name
        pen = TTGlyphPen(None)
        glyphs[name].draw(pen)
        new = pen.glyph()
        new.recalcBounds(None)
        old = font['glyf'][name]
        contour_total += old.numberOfContours
        old_coordinates, old_ends, old_flags = old.getCoordinates(font['glyf'])
        new_coordinates, new_ends, new_flags = new.getCoordinates(rebuilt['glyf'])
        if (old.numberOfContours == new.numberOfContours and old_coordinates == new_coordinates
                and old_ends == new_ends and old_flags == new_flags):
            exact_binary_outlines += 1
        else:
            def contours_without_duplicate_close(coords, ends, flags):
                result, start, removed = [], 0, 0
                for end in ends:
                    points = list(zip(coords[start:end + 1], flags[start:end + 1]))
                    if len(points) > 1 and points[0] == points[-1] and points[0][1] & 1:
                        points.pop()
                        removed += 1
                    result.append(points)
                    start = end + 1
                return result, removed
            before, removed_before = contours_without_duplicate_close(old_coordinates, old_ends, old_flags)
            after, removed_after = contours_without_duplicate_close(new_coordinates, new_ends, new_flags)
            # A legal TrueType contour may start on an off-curve point. UFO's
            # segment representation and TTGlyphPen can rotate it to an on-curve
            # start. Prove exact cyclic equality of coordinates AND flags.
            assert len(before) == len(after), (ttf.name, name, 'Contour count changed')
            rotations = []
            for old_contour, new_contour in zip(before, after):
                assert len(old_contour) == len(new_contour), (ttf.name, name, 'Unexpected point count')
                if old_contour == new_contour:
                    rotations.append(0)
                    continue
                matching = [i for i, point in enumerate(new_contour)
                    if point == old_contour[0] and new_contour[i:] + new_contour[:i] == old_contour]
                assert matching, (ttf.name, name, 'Unexpected binary representation difference')
                rotations.append(matching[0])
            kind = 'cyclic contour start rotation' if any(rotations) else 'redundant explicit closing on-curve point'
            binary_normalizations.append({'glyph': name, 'kind': kind,
                'sourcePoints': len(old_coordinates), 'roundTripPoints': len(new_coordinates),
                'duplicateClosingPointsRemoved': removed_before - removed_after,
                'exactContourStartRotations': rotations})
        rebuilt['glyf'][name] = new
        # hmtx uses the TrueType control-point bbox, which can differ from the
        # exact curve-extrema bbox returned by BoundsPen.
        assert getattr(new, 'xMin', 0) == font['hmtx'][name][1], (name, 'LSB changed')
    assert exported_cmap == font.getBestCmap(), 'Unicode mapping changed'
    # Drawing reconstructed TTF glyphs proves the saved UFO can round-trip back
    # to the exact same normalized quadratic paths, including off-curve points.
    new_glyphs = rebuilt.getGlyphSet()
    for name in order:
        expected, actual = RecordingPointPen(), RecordingPointPen()
        original_glyphs[name].draw(SegmentToPointPen(expected, guessSmooth=False))
        new_glyphs[name].draw(SegmentToPointPen(actual, guessSmooth=False))
        assert expected.value == actual.value, (ttf.name, name, 'TTF path round-trip changed')
    for tag in ('GDEF', 'GSUB', 'GPOS'):
        del rebuilt[tag]
    addOpenTypeFeaturesFromString(rebuilt, reader.readFeatures())
    feature_tables = {}
    for tag in ('GDEF', 'GSUB', 'GPOS'):
        before, after = font[tag].compile(font), rebuilt[tag].compile(rebuilt)
        feature_tables[tag] = {'byteIdentical': before == after, 'bytes': len(before), 'sha256': digest(after)}
        assert before == after, (ttf.name, tag, 'feature source differs')
    kern = reader.readKerning()
    expected_kern = {}
    for table in font['kern'].kernTables:
        expected_kern.update(table.kernTable)
    assert kern == expected_kern
    result = dict(face=ttf.stem, inputSHA256=digest(ttf.read_bytes()),
        ufo=ufo.name, ufoFormat=3, glyphs=len(order), encodedCharacters=len(exported_cmap),
        quadraticPointOperations=point_operations, contours=contour_total,
        exactUFOPointRecordings=len(order), exactTTFPathRoundTrips=len(order),
        exactBinaryGlyphCoordinates=exact_binary_outlines,
        binaryRepresentationNormalization=binary_normalizations,
        exactAdvanceAndLeftSideBearings=len(order), exactUnicodeMappings=len(exported_cmap),
        fontInfoAttributesPreserved=len(expected_info), legacyKerningPairsPreserved=len(kern),
        featureTablesRecompiled=feature_tables,
        italicAnchorsTransformed=bool(font['OS/2'].fsSelection & 1),
        sourceHintingInstructions=sum(len(getattr(font['glyf'][name], 'program', SimpleNamespace(bytecode=b'')).bytecode) for name in order),
        status='PASS')
    reader.close()
    font.close()
    rebuilt.close()
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1], help='Repository root')
    parser.add_argument('--fonts', type=Path, help='Input TTF directory; defaults to REPOSITORY/fonts/ttf')
    parser.add_argument('--features', type=Path, help='Feature source; defaults to REPOSITORY/sources/features.fea')
    parser.add_argument('--output', type=Path, help='UFO directory; defaults to REPOSITORY/sources/ufos')
    parser.add_argument('--report', type=Path, help='Validation JSON; defaults to UFO_DIRECTORY/../ufo-validation.json')
    parser.add_argument('--deps', type=Path, help='Optional directory containing fontTools')
    parser.add_argument('--resume-existing', action='store_true', help='Validate existing completed UFOs without overwriting them')
    args = parser.parse_args(argv)
    args.fonts = args.fonts or args.source / 'fonts' / 'ttf'
    args.features = args.features or args.source / 'sources' / 'features.fea'
    args.output = args.output or args.source / 'sources' / 'ufos'
    args.report = args.report or args.output.parent / 'ufo-validation.json'
    return args


def main():
    args = parse_args()
    if args.deps:
        sys.path.insert(0, str(args.deps))
    import fontTools
    fonts = sorted(args.fonts.glob('Nambli-*.ttf'))
    assert len(fonts) == 12, f'Expected 12 static TTFs, found {len(fonts)}'
    original_features = args.features.read_text(encoding='utf-8')
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for ttf in fonts:
        ufo = args.output / (ttf.stem + '.ufo')
        if not (args.resume_existing and ufo.exists()):
            ufo = export_one(ttf, original_features, args.output)
        results.append(validate_one(ttf, ufo))
        print(json.dumps({'face': ttf.stem, 'status': results[-1]['status'],
            'glyphs': results[-1]['glyphs'], 'binaryExact': results[-1]['exactBinaryGlyphCoordinates']}), flush=True)
    report = {
        'status': 'PASS', 'fontToolsVersion': fontTools.__version__,
        'sourceFeaturesSHA256': digest(original_features.encode('utf-8')),
        'faces': len(results), 'glyphChecks': sum(row['glyphs'] for row in results),
        'unicodeChecks': sum(row['encodedCharacters'] for row in results),
        'featureTableChecks': 3 * len(results),
        'scope': 'Editable quadratic source snapshots exported from input TTFs, with original feature source and exact italic anchor transformation.',
        'verified': ['UFO3 read/write validation', 'exact saved UFO point instructions',
            'exact normalized quadratic path round-trip UFO to TTF', 'advances and left sidebearings',
            'Unicode maps', 'glyph order', 'fontinfo fields', 'legacy kern pairs',
            'GDEF/GSUB/GPOS byte equivalence after compiling saved features.fea'],
        'notClaimed': ['Historical design sources replaced', 'Independent fontmake/gftools build',
            'Complete binary font round-trip including metadata, STAT and hinting',
            'Google Fonts acceptance', 'Legal authorship or licensing clearance'],
        'results': results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('status', 'faces', 'glyphChecks', 'unicodeChecks', 'featureTableChecks')}), flush=True)


if __name__ == '__main__':
    main()
