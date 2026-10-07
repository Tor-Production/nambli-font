"""Compare the public 0.7.4 outlines and metrics with the technical candidate."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean_outlines import geometry
from fontTools.ttLib import TTFont

ap = argparse.ArgumentParser()
ap.add_argument('--baseline', type=Path, required=True)
ap.add_argument('--candidate', type=Path, required=True)
ap.add_argument('--report', type=Path, required=True)
args = ap.parse_args()
report = {'baseline': 'v0.7.4', 'faces': {}, 'allowed_design_review_glyphs': ['at', 'uni0040', 'uni026C', 'uniA7AD']}
for oldpath in sorted(args.baseline.glob('*.ttf')):
    with TTFont(oldpath) as old, TTFont(args.candidate / oldpath.name) as new:
        unchanged, changed = [], []
        for cp, name in old.getBestCmap().items():
            assert new.getBestCmap().get(cp) == name, (oldpath.name, cp, 'cmap')
        for name in old.getGlyphOrder():
            assert old['hmtx'][name] == new['hmtx'][name], (oldpath.name, name, 'metrics')
            if geometry(old, name) == geometry(new, name):
                unchanged.append(name)
            else:
                assert name in report['allowed_design_review_glyphs'], (oldpath.name, name, 'unexpected geometry change')
                changed.append(name)
        report['faces'][oldpath.stem] = {
            'old_codepoints_preserved': len(old.getBestCmap()),
            'old_metrics_preserved': len(old.getGlyphOrder()),
            'old_normalized_outlines_identical': len(unchanged),
            'changed_outlines_requiring_design_review': changed,
            'candidate_codepoints': len(new.getBestCmap()),
            'candidate_glyphs': len(new.getGlyphOrder()),
        }
        print(oldpath.stem, len(unchanged), 'unchanged;', changed, 'review', flush=True)
report['status'] = 'PASS: only explicitly listed review candidates may differ'
args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
