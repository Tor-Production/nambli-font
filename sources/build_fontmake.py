# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
"""Build static TTFs from editable quadratic UFO3s with explicit feature source.

An optional import stage snapshots reference TTFs; the actual Fontmake build
and source-driven metadata completion read only the UFOs, never reference TTFs.
"""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def prepare_sources(fonts, ufo_dir, features, features_dir, resume=False):
    import export_ufo
    from fontTools.ttLib import TTFont
    from fontTools.ufoLib import UFOReader, UFOWriter
    ufo_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for path in fonts:
        if features_dir:
            fea = (features_dir / (path.stem + '.fea')).read_text(encoding='utf-8')
        else:
            fea = features.read_text(encoding='utf-8')
        ufo = ufo_dir / (path.stem + '.ufo')
        if not (resume and ufo.exists()):
            ufo = export_ufo.export_one(path, fea, ufo_dir, transform_italic=not bool(features_dir))
        else:
            with UFOReader(ufo) as reader:
                assert reader.readLib()['com.nambli.snapshot.sourceSHA256'] == export_ufo.digest(path.read_bytes()), 'Resumed UFO input hash differs'
        results.append(export_ufo.validate_one(path, ufo))
        print(f'{path.stem}: exact UFO import validated', flush=True)
        # STAT is editable metadata in the UFO lib, not a hidden reference table.
        with TTFont(path, recalcTimestamp=False) as font, UFOReader(ufo) as reader:
            lib = reader.readLib()
            if 'meta' in font:
                lib['public.openTypeMeta'] = {
                    tag: value.split(',') if tag in ('dlng', 'slng') else value
                    for tag, value in font['meta'].data.items()
                }
            if 'STAT' in font:
                table = font['STAT'].table
                axes = []
                for index, record in enumerate(table.DesignAxisRecord.Axis):
                    axis = dict(tag=record.AxisTag, name=record.AxisNameID, ordering=record.AxisOrdering, values=[])
                    for value in table.AxisValueArray.AxisValue:
                        if value.Format != 1:
                            raise ValueError('Import supports existing Nambli static STAT format 1 only')
                        if value.AxisIndex == index:
                            axis['values'].append(dict(value=value.Value, name=value.ValueNameID, flags=value.Flags))
                    axes.append(axis)
                lib['com.nambli.production.STAT'] = dict(axes=axes, elidedFallbackName=table.ElidedFallbackNameID)
        with UFOWriter(ufo, formatVersion=3) as writer:
            writer.writeLib(lib)
    return results


def build(ufos, output, epoch):
    from fontTools.ttLib import TTFont, newTable
    from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0
    from fontTools.ufoLib import UFOReader
    from fontTools.otlLib.builder import buildStatTable
    output.mkdir(parents=True, exist_ok=True)
    for ufo in ufos:
        if (output / (ufo.stem + '.ttf')).exists():
            raise FileExistsError(f'Refusing to overwrite output font: {ufo.stem}')
    command = [sys.executable, '-B', '-m', 'fontmake', '-u', *map(str, ufos), '-o', 'ttf',
        '--output-dir', str(output), '--keep-overlaps', '--keep-direction', '--ttf-curves', 'keep-quad',
        '--no-production-names', '--no-autohint', '--no-generate-GDEF', '--feature-writer', 'None', '--validate-ufo']
    env = os.environ.copy()
    env['SOURCE_DATE_EPOCH'] = str(epoch)
    env['PYTHONHASHSEED'] = '0'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    subprocess.run(command, env=env, check=True)
    for ufo in ufos:
        target = output / (ufo.stem + '.ttf')
        with UFOReader(ufo) as reader:
            lib, kerning = reader.readLib(), reader.readKerning()
        with TTFont(target, recalcTimestamp=False) as font:
            if kerning:
                if any(a not in font.getGlyphOrder() or b not in font.getGlyphOrder() for a, b in kerning):
                    raise ValueError('Group kerning is unsupported in this exact legacy-kern path')
                kern = newTable('kern')
                kern.version = 0
                subtable = KernTable_format_0()
                subtable.version, subtable.coverage = 0, 1
                subtable.kernTable = dict(kerning)
                kern.kernTables = [subtable]
                font['kern'] = kern
            if 'com.nambli.production.STAT' in lib:
                buildStatTable(font, **lib['com.nambli.production.STAT'])
            font.save(target, reorderTables=True)
    return command[3:]


def build_woff2(output):
    from fontTools.ttLib import TTFont
    from validate_build import point_recording, sha256
    results = []
    for path in sorted(output.glob('Nambli-*.ttf')):
        target = path.with_suffix('.woff2')
        if target.exists():
            raise FileExistsError(f'Refusing to overwrite {target}')
        with TTFont(path, recalcTimestamp=False) as font:
            font.flavor = 'woff2'
            font.save(target)
        with TTFont(path, recalcTimestamp=False) as a, TTFont(target, recalcTimestamp=False) as b:
            assert a.getGlyphOrder() == b.getGlyphOrder()
            assert a.getBestCmap() == b.getBestCmap()
            assert a['hmtx'].metrics == b['hmtx'].metrics
            ga, gb = a.getGlyphSet(), b.getGlyphSet()
            assert all(point_recording(ga[n]) == point_recording(gb[n]) for n in a.getGlyphOrder())
            for tag in set(a.keys()) - {'GlyphOrder', 'head', 'glyf', 'loca'}:
                assert a[tag].compile(a) == b[tag].compile(b), (path.name, tag, 'WOFF2 changed a table')
        results.append(dict(font=target.name, sha256=sha256(target.read_bytes()), status='PASS'))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source_root = Path(__file__).resolve().parent
    parser.add_argument('--input-fonts', type=Path, help='Optional TTF import directory; UFO output must be new')
    parser.add_argument('--reference-fonts', type=Path, help='Validation reference directory; defaults to --input-fonts')
    parser.add_argument('--features', type=Path, help='Upright feature source; original italic anchors are transformed by exporter')
    parser.add_argument('--features-dir', type=Path, help='Alternative: per-face STEM.fea files, already transformed')
    parser.add_argument('--ufo-dir', type=Path, default=source_root / 'ufos', help='Editable UFO source directory, generated only with --input-fonts')
    parser.add_argument('--output', type=Path, default=source_root.parent / 'build-fonts', help='New TTF/WOFF2 destination')
    parser.add_argument('--report', type=Path, help='Defaults to OUTPUT/build-validation.json')
    parser.add_argument('--license', type=Path, default=source_root.parent / 'OFL.txt', help='OFL file to copy beside outputs when present')
    parser.add_argument('--deps', type=Path, help='Optional isolated pip --target dependency directory')
    parser.add_argument('--expected-faces', type=int, default=12)
    parser.add_argument('--face', action='append', help='Select a specific font stem; repeat to choose multiple faces')
    parser.add_argument('--source-date-epoch', type=int, default=1791331200, help='Deterministic build timestamp: 2026-10-07 UTC')
    parser.add_argument('--verify-reproducible', action='store_true', help='Build a second time and require equal SHA-256')
    parser.add_argument('--no-woff2', action='store_true', help='Build TTF only (otherwise also generate and verify WOFF2)')
    parser.add_argument('--resume-import', action='store_true', help='Revalidate existing UFO imports against identical input hashes; never overwrite outlines')
    args = parser.parse_args()
    args.report = args.report or args.output / 'build-validation.json'
    if args.deps:
        sys.path.insert(0, str(args.deps.resolve()))
        os.environ['PYTHONPATH'] = str(args.deps.resolve()) + os.pathsep + os.environ.get('PYTHONPATH', '')
    if args.input_fonts and bool(args.features) == bool(args.features_dir):
        parser.error('Import requires exactly one of --features or --features-dir')
    if args.reference_fonts is None:
        args.reference_fonts = args.input_fonts
    protected = [args.reference_fonts.resolve()] if args.reference_fonts else []
    if args.input_fonts:
        protected.append(args.input_fonts.resolve())
    if args.output.resolve() in protected or args.output.resolve() == args.ufo_dir.resolve():
        parser.error('Output must differ from source/reference paths')
    import_results = []
    if args.input_fonts:
        fonts = sorted(args.input_fonts.glob('Nambli-*.ttf'))
        if args.face:
            fonts = [font for font in fonts if font.stem in args.face]
        if len(fonts) != args.expected_faces:
            parser.error(f'Expected {args.expected_faces} input fonts, found {len(fonts)}')
        import_results = prepare_sources(fonts, args.ufo_dir, args.features, args.features_dir, args.resume_import)
    ufos = sorted(args.ufo_dir.glob('Nambli-*.ufo'))
    if args.face:
        ufos = [ufo for ufo in ufos if ufo.stem in args.face]
    if len(ufos) != args.expected_faces:
        parser.error(f'Expected {args.expected_faces} UFOs, found {len(ufos)}')
    command = build(ufos, args.output, args.source_date_epoch)
    from validate_build import validate_all, validate_ufo_sources, sha256
    report = validate_ufo_sources(args.output, ufos)
    if args.license.is_file():
        license_text = args.license.read_text(encoding='utf-8')
        if 'SIL OPEN FONT LICENSE Version 1.1' not in license_text:
            raise ValueError('Supplied license does not identify SIL OFL 1.1')
        shutil.copyfile(args.license, args.output / 'OFL.txt')
        report['licenseFile'] = dict(name='OFL.txt', sha256=sha256(args.license.read_bytes()))
    if args.reference_fonts:
        reference = validate_all(args.reference_fonts, args.output, ufos)
        report['referenceComparison'] = reference
        report['shapingComparisons'] = reference['shapingComparisons']
        if reference['status'] != 'PASS':
            report['status'] = 'FAIL'
    if not args.no_woff2:
        report['woff2'] = build_woff2(args.output)
    report['toolVersions'] = {name: importlib.metadata.version(name) for name in ['fontmake', 'ufo2ft', 'fonttools', 'uharfbuzz', 'brotli']}
    report['sourceDateEpoch'] = args.source_date_epoch
    report['sourceImportValidation'] = import_results
    report['buildFlags'] = command[command.index('-o'):]
    report['buildFlags'][report['buildFlags'].index('--output-dir') + 1] = '[output-directory]'
    args.report.parent.mkdir(parents=True, exist_ok=True)
    if args.verify_reproducible:
        checkpoint = args.report.with_name(args.report.stem + '-first-build.json')
        checkpoint_report = dict(report, reproducibility=dict(status='PENDING'))
        checkpoint.write_text(json.dumps(checkpoint_report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'First build validation {report["status"]}; reproducibility pending; report {checkpoint.name}', flush=True)
        repeat = args.output.with_name(args.output.name + '-repeat')
        build(ufos, repeat, args.source_date_epoch)
        if not args.no_woff2:
            build_woff2(repeat)
        hashes = [{ 'font': f.name, 'sha256': sha256(f.read_bytes()),
            'repeatSHA256': sha256((repeat / f.name).read_bytes())} for f in sorted(args.output.iterdir()) if f.suffix in ('.ttf', '.woff2')]
        assert all(row['sha256'] == row['repeatSHA256'] for row in hashes), 'Non-reproducible output'
        report['reproducibility'] = dict(status='PASS', fonts=hashes)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['status', 'faces', 'glyphsCompared', 'shapingComparisons', 'toolVersions']}), flush=True)
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
