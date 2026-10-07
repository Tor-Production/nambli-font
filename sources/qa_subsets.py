# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Generate real WOFF2 NAM subsets and compare all-face cluster shaping.

This models local NAM sets + fontTools layout closure, not Google's private
serving implementation. Whole multi-subfont text is checked by browser QA.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import io
import json
from pathlib import Path
import re
import unicodedata as ud

SUBSETS=['cyrillic','latin-ext','vietnamese','latin']  # same CSS order as the API
MARKS=[0x0302,0x0306,0x030c,0x0330,0x0331,0x1dc7]
def nam(path):
    return {int(m,16) for m in re.findall(r'^0x([0-9A-F]+)',path.read_text(encoding='utf-8'),re.M)}
def clusters(text):
    result=[]
    for c in text:
        if ud.category(c).startswith('M') and result: result[-1]+=c
        else: result.append(c)
    return result
def ranges(cps):
    runs=[]
    for cp in sorted(cps):
        if runs and runs[-1][1]+1==cp: runs[-1][1]=cp
        else: runs.append([cp,cp])
    return ','.join(f'U+{a:X}'+(f'-{b:X}' if b!=a else '') for a,b in runs)
def canonical_closure(cps, available):
    """Keep cmap compositions whose complete NFD is reachable in this subfont."""
    result=set(cps)
    while True:
        extra={cp for cp in available if len(ud.normalize('NFD',chr(cp)))>1
            and set(map(ord,ud.normalize('NFD',chr(cp))))<=result}
        if extra<=result: return result
        result.update(extra)
def shaper(path):
    import uharfbuzz as hb
    from fontTools.ttLib import TTFont
    f=TTFont(path,recalcTimestamp=False);names=f.getGlyphOrder();cmap=f.getBestCmap()
    f.flavor=None;data=io.BytesIO();f.save(data)
    font=hb.Font(hb.Face(data.getvalue()));font.scale=(font.face.upem,font.face.upem)
    return font,names,cmap
def shape(shaper,text,language='en'):
    import uharfbuzz as hb
    font,names,cmap=shaper
    b=hb.Buffer();b.add_str(text);b.guess_segment_properties();b.language=language
    hb.shape(font,b)
    return [(names[g.codepoint],g.cluster,p.x_advance,p.y_advance,p.x_offset,p.y_offset)
        for g,p in zip(b.glyph_infos,b.glyph_positions)]
def subset_font(src,dst,cps):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    f=TTFont(src,recalcTimestamp=False)
    options=subset.Options();options.glyph_names=True;options.layout_features=['*'];options.name_IDs=['*']
    options.name_legacy=True;options.name_languages=['*'];options.recalc_timestamp=False
    sub=subset.Subsetter(options);sub.populate(unicodes=cps);sub.subset(f)
    f.flavor='woff2';f.save(dst)
    return {'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'bytes':dst.stat().st_size,
        'cmap':sorted(f.getBestCmap()),'glyphs':len(f.getGlyphOrder())}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ['family','baseline-nam','patched-nam','corpus','output']:
        p.add_argument('--'+arg,type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'fonts').mkdir()
    corpus=json.loads(args.corpus.read_text(encoding='utf-8'))
    sets={v:{s:nam(root/f'{s}_unique-glyphs.nam') for s in SUBSETS} for v,root in [
        ('baseline',args.baseline_nam),('patched',args.patched_nam)]}
    sets['ext-only']={s:set(cps) for s,cps in sets['baseline'].items()}
    sets['ext-only']['latin-ext'].update(MARKS)
    manifest={'model':'NAM union sets, fontTools layout closure, CSS order cyrillic/latin-ext/vietnamese/latin',
        'nam_sha256':{v:{s:hashlib.sha256((root/f'{s}_unique-glyphs.nam').read_bytes()).hexdigest() for s in SUBSETS}
            for v,root in [('baseline',args.baseline_nam),('patched',args.patched_nam)]},
        'python_unicode':ud.unidata_version,'corpus_sha256':hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
        'fonts':{},'shape_results':[],'single_subfont_cluster_tests':[]}
    css=[];faces=[]
    for src in sorted(args.family.glob('*.ttf')):
        face=src.stem;faces.append(face);full=args.output/'fonts'/f'{face}-full.woff2'
        from fontTools.ttLib import TTFont
        full_cps=set(TTFont(src).getBestCmap())
        manifest['fonts'][full.name]=subset_font(src,full,full_cps)
        css.append(f"@font-face{{font-family:'{face}-full';src:url(fonts/{full.name}) format('woff2');font-weight:400;font-style:normal;}}")
        full_shaper=shaper(full);subset_shapers={}
        for variant in ['baseline','ext-only','patched']:
            subset_shapers[variant]={}
            for s in SUBSETS:
                dst=args.output/'fonts'/f'{face}-{variant}-{s}.woff2'
                manifest['fonts'][dst.name]=subset_font(src,dst,full_cps & sets[variant][s])
                subset_shapers[variant][s]=shaper(dst)
                css.append(f"@font-face{{font-family:'{face}-{variant}';src:url(fonts/{dst.name}) format('woff2');font-weight:400;font-style:normal;unicode-range:{ranges(sets[variant][s])};}}")
        # A second serving candidate, rather than claiming NAM union alone is
        # sufficient: coalesce the three declared Latin subsets so mixed Latin
        # words, their marks and kerning pairs stay in one physical font.
        # METADATA subset labels are unchanged. This is an explicit local model
        # requiring a backend/CSS-serving change, not Google's current output.
        coherent_shapers={}
        for group, advertised in [('cyrillic',sets['patched']['cyrillic']),
            ('latin-coherent',set.union(*(sets['patched'][s] for s in ['latin','latin-ext','vietnamese'])))]:
            dst=args.output/'fonts'/f'{face}-coherent-{group}.woff2'
            manifest['fonts'][dst.name]=subset_font(src,dst,canonical_closure(full_cps & advertised,full_cps))
            coherent_shapers[group]=shaper(dst)
            css.append(f"@font-face{{font-family:'{face}-coherent';src:url(fonts/{dst.name}) format('woff2');font-weight:400;font-style:normal;unicode-range:{ranges(advertised)};}}")
        # Exact samples, NFC/NFD equivalence, and control strings in full fonts.
        original=shaper(src)
        for sample in corpus['samples']:
            # The tofu check removes LF; the immutable corpus retains the raw
            # original. HarfBuzz is a line shaper and not a paragraph layout API.
            text=sample['text'].replace('\n','');lang=sample.get('language','en')
            actual=shape(full_shaper,text,lang);reference=shape(original,text,lang)
            assert actual==reference and all(g[0]!='.notdef' for g in actual),(face,sample['id'])
            nfc=shape(full_shaper,ud.normalize('NFC',text),lang)
            nfd=shape(full_shaper,ud.normalize('NFD',text),lang)
            # Cluster indices differ after normalization; compare names and positions.
            strip=lambda seq:[(g[0],*g[2:]) for g in seq]
            assert strip(nfc)==strip(nfd),(face,sample['id'],'NFC/NFD')
            coherent=coherent_shapers['cyrillic' if lang=='uk' else 'latin-coherent']
            assert shape(coherent,text,lang)==reference,(face,sample['id'],'coherent shaping')
            manifest['shape_results'].append({'face':face,'sample':sample['id'],'full_woff2_equals_ttf':True,
                'nfc_nfd_equivalent':True,'coherent_shaping_equals_ttf':True})
        all_clusters=sorted(set(c for sample in corpus['samples'] for norm in ['NFC','NFD']
            for c in clusters(ud.normalize(norm,sample['text'].replace('\n',''))) if any(ud.category(x).startswith('M') for x in c)))
        for text in all_clusters:
            ref=shape(full_shaper,text)
            outcomes={v:[s for s,sh in subset_shapers[v].items() if shape(sh,text)==ref] for v in subset_shapers}
            manifest['single_subfont_cluster_tests'].append({'face':face,'cluster':text,'matching_subfonts':outcomes})
        print(face, 'WOFF2 and cluster shaping checked',flush=True)
    manifest['summary']={'faces':len(faces),'woff2_files':len(manifest['fonts']),
        'full_shape_tests':len(manifest['shape_results']),
        'cluster_tests':len(manifest['single_subfont_cluster_tests']),
        'unmatched_clusters':{v:sum(not r['matching_subfonts'][v] for r in manifest['single_subfont_cluster_tests']) for v in sets}}
    (args.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.output/'corpus.json').write_text(json.dumps(corpus,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.output/'fonts.css').write_text('\n'.join(css),encoding='utf-8')
    # Compact visible controls plus exact samples available from the selector.
    rows=''.join(f'<tr data-sample="{html.escape(s["id"])}"><th>{html.escape(s["id"])}</th>'+''.join(
        f'<td class="sample" data-variant="{v}" lang="{html.escape(s.get("language","en"))}">{html.escape(s["text"])}</td>' for v in ['full','baseline','ext-only','patched','coherent'])+'</tr>' for s in corpus['samples'] if s.get('display'))
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Nambli subset regression review</title>
<link rel="stylesheet" href="fonts.css"><style>body{margin:28px;background:#f7f6ff;color:#242338;font:15px system-ui}h1{font-size:26px}select{padding:10px}table{width:100%;border-collapse:collapse;background:white;margin-top:24px;table-layout:fixed}th,td{border:1px solid #ddd9f4;padding:16px}th{font:12px system-ui;text-align:left}td.sample{font-size:44px;overflow-wrap:anywhere;line-height:1.5}details{margin-top:24px}pre{white-space:pre-wrap}#status{margin-top:12px}</style>
<h1>Nambli — full font and actual WOFF2 subsets</h1><p>Local NAM/fontTools model. The coherent candidate merges the three declared Latin sets into one physical font with canonical cmap closure. This requires a serving change; it does not verify Google's private pipeline or Safari/iOS.</p>
<label>Style <select id="face">'''+''.join(f'<option>{f}</option>' for f in faces)+'''</select></label><div id="status">Loading fonts…</div>
<table><thead><tr><th>Control</th><th>Full font</th><th>Stock NAM</th><th>Six marks in latin-ext only</th><th>Patched NAM, literal splits</th><th>Coherent serving candidate</th></tr></thead><tbody>'''+rows+'''</tbody></table>
<details><summary>Exact failing language samples and regression corpus</summary><pre id="corpus"></pre></details>
<script>window.qaReady=false;const face=document.querySelector('#face');window.setFace=async value=>{face.value=value;for(const el of document.querySelectorAll('.sample'))el.style.fontFamily='"'+value+'-'+el.dataset.variant+'"';await Promise.all([...document.querySelectorAll('.sample')].map(el=>document.fonts.load('44px '+el.style.fontFamily,el.textContent)));await document.fonts.ready;document.querySelector('#status').textContent='Fonts ready · '+value;window.qaReady=true;};face.onchange=()=>setFace(face.value);fetch('corpus.json').then(r=>r.json()).then(c=>{window.corpus=c;document.querySelector('#corpus').textContent=JSON.stringify(c,null,2);return setFace(face.value)});</script></html>'''
    (args.output/'Nambli-Subset-Review.html').write_text(page,encoding='utf-8')
    print(json.dumps(manifest['summary'],indent=2))
if __name__=='__main__': main()
