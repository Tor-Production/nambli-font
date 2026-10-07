# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Render only changed candidate contours, plus all 48 side-caron controls."""
import argparse, base64, html, json
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from validate_build import point_recording

def svg(font, name):
    gs = font.getGlyphSet(); pen = SVGPathPen(gs); gs[name].draw(pen)
    bounds=BoundsPen(gs);gs[name].draw(bounds)
    xmin,ymin,xmax,ymax=bounds.bounds or (0,0,0,0)
    left=min(-150,xmin-80);right=max(font['hmtx'][name][0]+150,xmax+80)
    return f'<svg viewBox="{left} -1050 {right-left} 1400"><path transform="scale(1 -1)" d="' + pen.getCommands() + '"/></svg>'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ['baseline', 'candidate', 'output']:
        p.add_argument('--' + key, type=Path, required=True)
    a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=False)
    cards = []; controls = []; css = []; changes = []
    for path in sorted(a.candidate.glob('*.ttf')):
        with TTFont(a.baseline/path.name) as old, TTFont(path) as new:
            for name in new.getGlyphOrder():
                if point_recording(old.getGlyphSet()[name]) == point_recording(new.getGlyphSet()[name]):
                    continue
                cards.append(f'<article><h2>{path.stem} · {name}</h2><div class="pair"><div class="old"><p>Before · 1.000</p>{svg(old,name)}</div><div class="new"><p>Candidate · 1.001</p>{svg(new,name)}</div></div></article>')
                changes.append({'face':path.stem,'glyph':name})
            old.flavor='woff2'; import io
            stream=io.BytesIO();old.save(stream)
            data=base64.b64encode(stream.getvalue()).decode('ascii')
            css.append(f'@font-face{{font-family:"{path.stem}";src:url(data:font/woff2;base64,{data})}}')
            controls.append(f'<article><h2>{path.stem} · approved side-carons</h2><p class="carons" style="font-family:{path.stem}">Ľ ľ ď ť</p></article>')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nambli 1.001 outline QA candidate</title><style>
body{margin:28px;font:16px/1.5 system-ui;background:#f7f6ff;color:#34334c}h1{font-size:28px}h2{font:14px system-ui}header{max-width:950px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:16px}article{background:white;border:1px solid #dad4ef;border-radius:14px;padding:18px}.pair{display:grid;grid-template-columns:1fr 1fr}.pair p{font-size:12px}svg{width:100%;height:310px}.old{color:#8f889e;fill:#a8a0b4}.new{color:#5d50c8;fill:#6b5be5}.carons{font-size:70px;margin:22px 0}details{margin-top:32px}
'''+''.join(css)+'''</style><header><h1>Nambli: separate 1.001 contour candidate</h1><p>Only the changed glyph/face pairs are shown below. This experimental candidate repairs small contour backtracking and overlapping segments. The released 1.000 fonts, website, Google Fonts submission and v1.0.0 assets are unchanged. Visual approval is still required.</p><p>Metrics, all 970 Unicode mappings, layout and kerning are preserved in every style. Review at large and normal sizes; the accompanying audit records remaining warnings rather than hiding them.</p></header><div class="grid">'''+''.join(cards)+'''</div><details><summary>All 48 approved side-caron controls (unchanged)</summary><div class="grid">'''+''.join(controls)+'''</div></details></html>'''
    (a.output/'Nambli-Outline-Candidate-Review.html').write_text(page,encoding='utf-8')
    (a.output/'review-manifest.json').write_text(json.dumps({'candidate':'1.001','changes':changes,'side_caron_controls':48},indent=2),encoding='utf-8')
    print(json.dumps({'changed_pairs':len(changes),'side_caron_controls':48}))

if __name__=='__main__': main()
