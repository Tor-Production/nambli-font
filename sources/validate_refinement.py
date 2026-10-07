# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
"""Real HarfBuzz substitutions and mark stacking on final refined fonts."""
import argparse,json,sys
from pathlib import Path
import runtime
from fontTools.ttLib import TTFont
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
import uharfbuzz as hb
ap=argparse.ArgumentParser()
for key in ('fonts','otfs','ufos','report'):ap.add_argument('--'+key,type=Path,required=True)
a=ap.parse_args()
EXPECTED={'Nambli-'+style+'.ttf' for style in ('Light','LightItalic','Regular','Italic','Medium','MediumItalic','SemiBold','SemiBoldItalic','Bold','BoldItalic','ExtraBold','ExtraBoldItalic')}
font_paths=sorted(a.fonts.glob('*.ttf'))
assert {p.name for p in font_paths}==EXPECTED, 'Expected exactly the twelve Nambli styles'
CASES=[('i\u030d','en','idotless.alt'),('j\u030d','en','uni0237'),('i\u0329\u030d','en','idotless.alt'),
('i\u0328\u030d','en','uni012F.dotless'),('\u012f\u0301','lt','uni012F.dotless'),('\u029d\u030d','en','uni029D.dotless'),
('\u1e2d\u030d','en','uni1E2D.dotless'),('\u1ecb\u030d','en','uni1ECB.dotless'),('\u0268\u030d','en','uni0268.dotless'),
('\u0458\u030d','sr','uni0458.dotless'),('l·l','ca','periodcentered.loclCAT'),('L·L','ca','periodcentered.loclCAT.case'),('i','tr','i.loclTRK'),('i','az','i.loclTRK')]
rows=[]
for src in font_paths:
    f=TTFont(src,recalcTimestamp=False);data=src.read_bytes();hbf=hb.Font(hb.Face(data));hb.ot_font_set_funcs(hbf);order=f.getGlyphOrder()
    before={t:f[t].compile(f) for t in ('GPOS','GSUB','GDEF')}
    fea=(a.ufos/(src.stem+'.ufo')/'features.fea').read_text(encoding='utf-8');addOpenTypeFeaturesFromString(f,fea)
    assert all(f[t].compile(f)==v for t,v in before.items())
    with TTFont(a.otfs/(src.stem+'.otf')) as otf:assert all(otf[t].compile(otf)==v for t,v in before.items())
    tests=[]
    for text,lang,expected in CASES:
        b=hb.Buffer();b.add_str(text);b.guess_segment_properties();b.language=lang;hb.shape(hbf,b)
        names=[order[i.codepoint] for i in b.glyph_infos]
        assert expected in names and '.notdef' not in names,(src.name,text,names)
        tests.append({'text':text,'language':lang,'glyphs':names})
    for text in ('a\u030d\u030d','a\u0329\u0329','\u25cc\u030d','\u0264\u0329\u030d'):
        b=hb.Buffer();b.add_str(text);b.guess_segment_properties();hb.shape(hbf,b)
        positions=[(p.x_advance,p.x_offset,p.y_offset) for p in b.glyph_positions]
        assert all(order[i.codepoint]!='.notdef' for i in b.glyph_infos)
        assert all(p.x_advance==0 and p.y_offset!=0 for p in b.glyph_positions[1:])
        if len(positions)==3 and text[1]==text[2]:assert positions[1]!=positions[2]
        tests.append({'text':text,'positions':positions})
    for n,c in [('uni029D',3),('uni029D.dotless',2),('uniA7B2',2),('uniA7B4',3),('uniA7B5',3)]:assert f['glyf'][n].numberOfContours==c
    rows.append({'font':src.name,'editable_features_compile_exactly':True,'OTF_layout_identical':True,'tests':tests,'open_counter_contours_verified':5})
    print(src.stem+': language/mark/contour checks PASS',flush=True)
assert len(rows)==12 and sum(len(r['tests']) for r in rows)==216 and 5*len(rows)==60
a.report.write_text(json.dumps({'status':'PASS','faces':len(rows),'shaping_probes':sum(len(r['tests']) for r in rows),'counter_topology_checks':5*len(rows),'results':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
