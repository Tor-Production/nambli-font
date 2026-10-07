# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Audit a separately versioned outline candidate against the approved release."""
import argparse
import hashlib
import json
from pathlib import Path
from fontTools.ttLib import TTFont
from validate_build import validate_one

EXPECTED = {
    'Nambli-Bold': {'uniA7C8', 'uni02A6'},
    'Nambli-BoldItalic': {'uniA7C8'},
    'Nambli-LightItalic': {'uni00B6'},
    'Nambli-Medium': {'uni1D7D'},
    'Nambli-MediumItalic': {'uni02A3'},
    'Nambli-SemiBold': {'uni02A3'},
    'Nambli-SemiBoldItalic': {'uni02A3'},
}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['baseline', 'candidate', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    results = []
    assert len(list(a.candidate.glob('*.ttf'))) == 12
    for path in sorted(a.candidate.glob('*.ttf')):
        result = validate_one(a.baseline / path.name, path)
        assert set(result['outlineChanges']) == EXPECTED.get(path.stem, set()), result
        assert result['exactGlyphOrder'] and result['exactUnicodeMapping']
        assert not result['metricChanges'] and not result['shapingMismatchExamples']
        assert all(v['byteIdentical'] for v in result['layoutTables'].values())
        with TTFont(a.baseline / path.name) as old, TTFont(path) as new:
            assert round(old['head'].fontRevision, 3) == 1.000
            assert round(new['head'].fontRevision, 3) == 1.001
            # Only version-dependent name strings may differ.
            old_names = [(n.nameID, n.platformID, n.platEncID, n.langID, n.toUnicode()) for n in old['name'].names]
            new_names = [(n.nameID, n.platformID, n.platEncID, n.langID, n.toUnicode()) for n in new['name'].names]
            assert [(i, p, e, l, s.replace('1.000', '1.001')) for i, p, e, l, s in old_names] == new_names
            for tag in ['hhea', 'OS/2', 'post']:
                assert old[tag].compile(old) == new[tag].compile(new), (path.stem, tag)
        woff = path.with_suffix('.woff2')
        with TTFont(woff) as font:
            font.flavor = None
            with TTFont(path) as original:
                assert font.getBestCmap() == original.getBestCmap()
                for tag in ['glyf', 'hmtx', 'GDEF', 'GSUB', 'GPOS', 'kern']:
                    assert font[tag].compile(font) == original[tag].compile(original), (path.stem, 'WOFF2', tag)
        result['status'] = 'PASS_WITH_EXPECTED_OUTLINE_AND_VERSION_CHANGES'
        result['woff2_sha256'] = hashlib.sha256(woff.read_bytes()).hexdigest()
        results.append(result)
    report = {'status': 'PASS', 'candidate_version': '1.001', 'faces': 12,
        'changed_face_glyph_pairs': sum(len(r['outlineChanges']) for r in results),
        'shaping_comparisons': sum(r['shapingComparisons'] for r in results),
        'visual_approval': 'NEEDS_OWNER_INPUT', 'results': results}
    a.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}))

if __name__ == '__main__':
    main()
