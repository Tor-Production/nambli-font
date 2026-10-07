"""Separate 1.001 visual candidate: simplify only confirmed tiny backtracking paths.

Never run on released production sources. Preserve glyph metrics and metadata;
only selected contour payloads and the candidate version are edited.
"""
from pathlib import Path
import argparse,hashlib,json,plistlib,re,sys,xml.etree.ElementTree as ET
import pathops
from fontTools.ttLib import TTFont
from fontTools.pens.pointPen import SegmentToPointPen
from fontTools.pens.recordingPen import RecordingPointPen
from fontTools.pens.roundingPen import RoundingPen
from fontTools.misc.roundTools import otRound
from fontTools.pens.basePen import BasePen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.pointPen import PointToSegmentPen
GUARDS={
 ('Nambli-Bold','uniA7C8'):[((183,300),(183,301),(183,302))],
 ('Nambli-BoldItalic','uniA7C8'):[((208,329),(209,330),(211,331))],
 ('Nambli-Medium','uni1D7D'):[((419,168),(419,166),(418,165))],
}
class GuardedPen(BasePen):
    def __init__(self,gs,target,guards): super().__init__(gs);self.target=target;self.guards=guards;self.removed=[]
    def _moveTo(self,p):self.target.moveTo(p)
    def _lineTo(self,p):self.target.lineTo(p)
    def _qCurveToOne(self,p1,p2):
        triple=(self._getCurrentPoint(),p1,p2)
        if triple in self.guards:self.removed.append(triple)
        else:self.target.qCurveTo(p1,p2)
    def _closePath(self):self.target.closePath()
    def _endPath(self):raise ValueError('Open contour')
TARGETS={
 'Nambli-Bold':['uniA7C8','uni02A6'],
 'Nambli-BoldItalic':['uniA7C8'],
 'Nambli-LightItalic':['uni00B6'],
 'Nambli-Medium':['uni1D7D'],
 'Nambli-MediumItalic':['uni02A3'],
 'Nambli-SemiBold':['uni02A3'],
 'Nambli-SemiBoldItalic':['uni02A3'],
}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['worktree','baseline-ufos','reference-fonts','report']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    import subprocess
    branch=subprocess.check_output(['git','-C',str(a.worktree),'branch','--show-current'],text=True).strip()
    assert branch=='codex/fix/google-fonts-outline-candidate','Use the isolated candidate branch'
    assert a.baseline_ufos.resolve()!=(a.worktree/'sources/ufos').resolve()
    changes=[]
    for face,names in TARGETS.items():
        ufo=a.worktree/'sources/ufos'/f'{face}.ufo'
        contents=plistlib.loads((ufo/'glyphs/contents.plist').read_bytes())
        f=TTFont(a.reference_fonts/f'{face}.ttf');assert round(f['head'].fontRevision,3)==1.000;gs=f.getGlyphSet()
        for name in names:
            glif=ufo/'glyphs'/contents[name]
            baseline=a.baseline_ufos/f'{face}.ufo/glyphs'/contents[name]
            before=baseline.read_bytes();tree=ET.fromstring(before)
            assert not tree.findall('outline/component'),(face,name,'components')
            original=pathops.Path();guarded=GuardedPen(gs,original.getPen(),GUARDS.get((face,name),[]));gs[name].draw(guarded)
            assert len(guarded.removed)==len(guarded.guards),(face,name,'guard mismatch')
            cleaned=pathops.simplify(original,fix_winding=True,keep_starting_points=True)
            # Skia normalizes to the opposite winding convention from TrueType.
            cleaned.reverse()
            # Quantization can recreate a sub-unit retraced edge at an old
            # intersection. Re-union only the four reported ligature paths
            # after integer rounding; do not globally normalize the family.
            if name in ['uni02A3','uni02A6']:
                for _ in range(2):
                    integer=pathops.Path()
                    cleaned.draw(RoundingPen(integer.getPen(),roundFunc=otRound))
                    cleaned=pathops.simplify(integer,fix_winding=True,keep_starting_points=True)
                    cleaned.reverse()
            rec=RecordingPointPen();cleaned.draw(RoundingPen(SegmentToPointPen(rec),roundFunc=otRound))
            old=tree.find('outline');tree.remove(old);outline=ET.Element('outline')
            for op,args,kw in rec.value:
                if op=='beginPath': contour=ET.SubElement(outline,'contour')
                elif op=='addPoint':
                    xy,typ=args[:2];attrs={'x':str(xy[0]),'y':str(xy[1])}
                    if typ: attrs['type']=typ
                    ET.SubElement(contour,'point',attrs)
                elif op!='endPath': raise ValueError(op)
            # Remove two precisely identified integer-quantization excursions.
            # Their boxes are only one unit square; unrelated joins are kept.
            if (face,name)==('Nambli-MediumItalic','uni02A3'):
                contour=outline.find('contour');points=list(contour)
                coords=[(float(p.get('x')),float(p.get('y'))) for p in points]
                assert coords[0]==(466,79) and coords[-3:]==[(466,79),(467,79),(467,80)]
                contour.remove(points[-2]);contour.remove(points[-1])
            if (face,name)==('Nambli-SemiBold','uni02A3'):
                pattern=[(543,139),(542,138),(543,138),(543,138),(543,138),(543,139)]
                matches=[]
                for contour in outline.findall('contour'):
                    points=list(contour);coords=[(float(p.get('x')),float(p.get('y'))) for p in points]
                    for i in range(len(points)-len(pattern)+1):
                        if coords[i:i+len(pattern)]==pattern:matches.append((contour,points[i+1:i+len(pattern)]))
                assert len(matches)==1
                contour,points=matches[0]
                for point in points:contour.remove(point)
            # Canonicalize the point sequence through the same quadratic pen
            # used by compilation, especially a duplicate closing endpoint.
            pen=TTGlyphPen(None);pp=PointToSegmentPen(pen)
            for contour in outline.findall('contour'):
                pp.beginPath()
                for point in contour:
                    pp.addPoint((float(point.get('x')),float(point.get('y'))),segmentType=point.get('type'))
                pp.endPath()
            normalized=RecordingPointPen()
            pen.glyph().draw(SegmentToPointPen(normalized),None)
            outline=ET.Element('outline')
            for op,args,kw in normalized.value:
                if op=='beginPath':contour=ET.SubElement(outline,'contour')
                elif op=='addPoint':
                    xy,typ=args[:2];attrs={'x':str(xy[0]),'y':str(xy[1])}
                    if typ:attrs['type']=typ
                    ET.SubElement(contour,'point',attrs)
                elif op!='endPath':raise ValueError(op)
            # Preserve the original outline position among other glyph metadata.
            insert_at=next((i for i,node in enumerate(tree) if node.tag in ['lib','anchor','guideline']),len(tree))
            tree.insert(insert_at,outline);ET.indent(tree,space='  ')
            glif.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(tree,encoding='utf-8')+b'\n')
            changes.append({'face':face,'glyph':name,'before_sha256':hashlib.sha256(before).hexdigest(),
                'after_sha256':hashlib.sha256(glif.read_bytes()).hexdigest(),
                'guarded_short_segments_removed':guarded.removed,
                'original_contours':len(original),'simplified_contours':len(cleaned)})
    for ufo in sorted((a.worktree/'sources/ufos').glob('*.ufo')):
        p=ufo/'fontinfo.plist';info=plistlib.loads(p.read_bytes())
        assert info['versionMajor']==1 and info['versionMinor'] in (0,1)
        info['versionMinor']=1
        for k,v in list(info.items()):
            if isinstance(v,str) and '1.000' in v:info[k]=v.replace('1.000','1.001')
        for r in info.get('openTypeNameRecords',[]):
            if '1.000' in r.get('string',''):r['string']=r['string'].replace('1.000','1.001')
        baseline_info=a.baseline_ufos/ufo.name/'fontinfo.plist'
        original_text=baseline_info.read_text(encoding='utf-8')
        assert plistlib.loads(original_text.encode('utf-8'))['versionMinor']==0
        updated,count=re.subn(r'(<key>versionMinor</key>\s*<integer>)0(</integer>)',r'\g<1>1\2',original_text)
        assert count==1
        updated=updated.replace('1.000','1.001')
        assert plistlib.loads(updated.encode('utf-8'))==info,'Unrelated fontinfo change'
        p.write_text(updated,encoding='utf-8',newline='')
    a.report.write_text(json.dumps({'candidate_version':'1.001','changes':changes},indent=2),encoding='utf-8')
    print(json.dumps(changes,indent=2))
if __name__=='__main__':main()
