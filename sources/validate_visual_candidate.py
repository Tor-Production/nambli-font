# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Validate intended visual changes without pretending release equivalence."""
import argparse
import hashlib
import json
from pathlib import Path
import unicodedata
from fontTools.ttLib import TTFont
from validate_build import make_shaper,shape,point_recording
from audit_visual_quality import EdgePen

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def signature(rows):return [(gid,xa,ya,xo,yo) for gid,cluster,xa,ya,xo,yo in rows]

def validate(before,after,reports):
    results=[];failures=[]
    for path in sorted(after.glob('Nambli-*.ttf')):
        old_path=before/path.name
        a,b=TTFont(old_path),TTFont(path)
        report=json.loads((reports/(path.stem+'.json')).read_text(encoding='utf-8'))
        expected=report['advanceChanges']
        assert a.getGlyphOrder()==b.getGlyphOrder(),(path.name,'glyph order')
        assert a.getBestCmap()==b.getBestCmap(),(path.name,'Unicode coverage')
        advances={n:[a['hmtx'][n][0],b['hmtx'][n][0]] for n in b.getGlyphOrder() if a['hmtx'][n][0]!=b['hmtx'][n][0]}
        assert advances==expected,(path.name,'unexpected advances',advances,expected)
        tables={}
        for tag in ('GDEF','GSUB','GPOS','kern','STAT','meta'):
            tables[tag]=a[tag].compile(a)==b[tag].compile(b)
            assert tables[tag],(path.name,tag)
        assert b['name'].getDebugName(5)=='Version 1.002',(path.name,'version')
        assert abs(b['head'].fontRevision-1.002)<.00002
        for table,attrs in [('hhea',('ascent','descent','lineGap')),('OS/2',('sTypoAscender','sTypoDescender','sTypoLineGap'))]:
            assert all(getattr(a[table],k)==getattr(b[table],k) for k in attrs),(path.name,'line layout')
        assert b['OS/2'].usWinAscent>=b['head'].yMax
        assert b['OS/2'].usWinDescent>=-b['head'].yMin
        old_s,new_s=make_shaper(old_path.read_bytes()),make_shaper(path.read_bytes())
        normalization=[];known=[];checks=0
        for cp in a.getBestCmap():
            char=chr(cp);nfd=unicodedata.normalize('NFD',char)
            if char==nfd:continue
            for language in ('en','uk','cs','sk','vi'):
                checks+=1
                x,y=signature(shape(new_s,char,language)),signature(shape(new_s,nfd,language))
                if x!=y:
                    row={'unicode':f'U+{cp:04X}','language':language,'nfc':x,'nfd':y}
                    old_ok=signature(shape(old_s,char,language))==signature(shape(old_s,nfd,language))
                    (normalization if old_ok else known).append(row)
        failures.extend({'font':path.stem,**row} for row in normalization)
        ga,gb=a.getGlyphSet(),b.getGlyphSet()
        protected_glyphs=protected_contours=0
        for name,disposition in report['diacritics'].get('preservedGlyphs',{}).items():
            if disposition['wholeGlyph']:
                assert point_recording(ga[name])==point_recording(gb[name]),(path.name,name,'deferred glyph changed')
                protected_glyphs+=1
            else:
                old_pen,new_pen=EdgePen(ga),EdgePen(gb)
                ga[name].draw(old_pen);gb[name].draw(new_pen)
                preserved=disposition['preservedContours']
                expected_contours=[old_pen.contours[i] for i in preserved]
                assert expected_contours==new_pen.contours[-len(preserved):],(path.name,name,'deferred accent contour changed')
                protected_contours+=len(preserved)
        changes=[n for n in b.getGlyphOrder() if point_recording(ga[n])!=point_recording(gb[n])]
        results.append({'font':path.stem,'beforeSHA256':sha(old_path),'candidateSHA256':sha(path),
            'glyphs':len(b.getGlyphOrder()),'unicodeMappings':len(b.getBestCmap()),'outlineChanges':len(changes),
            'advanceChanges':advances,'identicalTables':tables,'normalizationComparisons':checks,
            'exactDeferredGlyphs':protected_glyphs,'exactRetainedAccentContours':protected_contours,
            'newNormalizationMismatches':normalization,'existingNormalizationMismatches':known,
            'fontBounds':[b['head'].xMin,b['head'].yMin,b['head'].xMax,b['head'].yMax],
            'windowsClipping':[b['OS/2'].usWinAscent,b['OS/2'].usWinDescent]})
    assert len(results)==12,'Expected 12 compiled faces'
    assert len({tuple(r['windowsClipping']) for r in results})==1,'Family clipping metrics differ'
    return {'status':'FAIL' if failures else 'PASS','faces':12,'glyphsCompared':sum(r['glyphs'] for r in results),
        'normalizationComparisons':sum(r['normalizationComparisons'] for r in results),
        'failures':failures,'results':results,
        'scope':'Contour-only visual candidate. Layout/kerning tables, advances and deferred diacritic outlines preserved.',
        'notClaimed':['User visual approval','Google Fonts acceptance','Official Fontspector zero FAIL']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True)
    p.add_argument('--reports',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=validate(args.before,args.after,args.reports)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='results'}))
    if result['status']!='PASS':raise SystemExit(1)

if __name__=='__main__':main()
