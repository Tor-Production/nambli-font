# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
"""Build six upright and six italic Nambli faces from the approved CFF master.

The master is immutable. Components are offset in both axes, with optical
compensation of the design frame. Marks and small letters have separate
stroke scales. This is a static display family, not an interpolating font.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import unicodedata as ud

from runtime import ROOT
import pathops
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.perimeterPen import PerimeterPen
from fontTools.pens.basePen import BasePen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.roundingPen import RoundingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.otlLib.builder import buildStatTable

STYLES = [('Light', 300, 80), ('Regular', 400, 100), ('Medium', 500, 114),
          ('SemiBold', 600, 123), ('Bold', 700, 132), ('ExtraBold', 800, 146)]
SLANT=math.tan(math.radians(10))
def face_name(style,italic):
    return ('Italic' if style=='Regular' else style+'Italic') if italic else style
FACES=[(face_name(s,i),w,t,i) for s,w,t in STYLES for i in (False,True)]
def style_label(face):
    return face.replace('Italic',' Italic').strip()
MASTER = ROOT / 'sources' / 'master'
OUT = ROOT / 'build-fonts'
MARK_WIDTH = {0x300:72,0x301:72,0x302:67,0x303:61,0x304:64,0x305:62,
              0x306:68,0x307:92,0x308:90,0x309:59,0x30a:53,0x30b:65,
              0x30c:67,0x30f:65,0x311:63,0x313:57,0x31b:65,0x323:88,
              0x324:84,0x325:49,0x326:56,0x327:54,0x328:58,0x32d:61,
              0x32e:62,0x32f:63,0x330:61,0x331:64,0x1dc6:68,0x1dc7:68}
SMALL = {ord(c):.51 for c in 'ʰʷᵉᵍᵘⁿˀˤ'} | {ord(c):.57 for c in 'ªº'}
BODY_SCALE = {ord(c):.82 for c in 'ьъыљњѣ'} | {ord('в'):.84,ord('я'):.78}


class CubicPen(BasePen):
    """Exact quadratic-to-cubic conversion, including all-offcurve loops."""
    def __init__(self, out):
        super().__init__(None)
        self.out = out
    def _moveTo(self, p): self.out.moveTo(p)
    def _lineTo(self, p): self.out.lineTo(p)
    def _curveToOne(self, p1,p2,p3): self.out.curveTo(p1,p2,p3)
    def _qCurveToOne(self, p1,p2):
        p0 = self._getCurrentPoint()
        self.out.curveTo(tuple(a+(b-a)*2/3 for a,b in zip(p0,p1)),
                         tuple(a+(b-a)*2/3 for a,b in zip(p2,p1)),p2)
    def _closePath(self): self.out.closePath()
    def _endPath(self): self.out.endPath()


def area(p):
    pen = AreaPen(None)
    p.draw(pen)
    return abs(pen.value)


def perimeter(p):
    pen = PerimeterPen(None, tolerance=.001)
    p.draw(pen)
    return pen.value


def clean(p):
    return pathops.simplify(p, clockwise=True)


def combine(paths):
    p = pathops.Path()
    for part in paths:
        if len(part):
            # Each constructed part has its own fill winding. Boolean
            # union prevents opposite windings cancelling at a junction.
            p = pathops.op(p,part,pathops.PathOp.UNION,clockwise=True)
    return p


def components(p):
    """Keep each outer contour and its enclosed counters together."""
    contours = list(p.contours)
    outers = [c for c in contours if c.clockwise]
    groups = [[c] for c in outers]
    for hole in [c for c in contours if not c.clockwise]:
        point = next(hole.segments)[1][0]
        containers = [i for i,c in enumerate(outers) if c.contains(point)]
        if not containers:
            raise ValueError('Counter has no containing outline')
        groups[min(containers,key=lambda i:area(outers[i]))].append(hole)
    result = []
    for group in groups:
        q = pathops.Path()
        pen = q.getPen()
        for contour in group:
            contour.draw(pen)
        result.append(q)
    return result


def topology(p):
    cs = list(p.contours)
    return (sum(c.clockwise for c in cs), sum(not c.clockwise for c in cs))


def offset(p, distance):
    if abs(distance) < .0001:
        return pathops.Path(p)
    border = pathops.Path(p)
    border.stroke(2*abs(distance), pathops.LineCap.ROUND_CAP,
                  pathops.LineJoin.ROUND_JOIN, 4)
    border.convertConicsToQuads(.025)
    operation = pathops.PathOp.DIFFERENCE if distance > 0 else pathops.PathOp.UNION
    return pathops.op(p, border, operation, clockwise=True)


def centered_scale(p, cx, cy, sx, sy):
    return p.transform(sx,0,0,sy,cx*(1-sx),cy*(1-sy))


def is_dot(p):
    x0,y0,x1,y1 = p.bounds
    w,h = x1-x0,y1-y0
    return (topology(p)[1] == 0 and w > 0 and h > 0 and max(w,h) <= 202
            and .77 < w/h < 1.3 and area(p)/(w*h) > .69)


def component_parameters(p, cp, base_cp):
    x0,y0,x1,y1 = p.bounds
    w,h = x1-x0,y1-y0
    # Detached diacritics use their own stroke, not the 132-unit body.
    if cp in MARK_WIDTH:
        return MARK_WIDTH[cp]/132, 200, 200, 'mark'
    small = SMALL.get(base_cp,1)
    if small != 1:
        return small,528*small,530*small,'small-letter'
    accent = h < 285 and (y0 > 520 or y1 < 0)
    if accent:
        estimate = 2*area(p)/max(perimeter(p),1)
        scale = min(.66,max(.35,estimate/110))
        return scale,200,200,'detached-mark'
    nominal = BODY_SCALE.get(base_cp,1)
    # Symbols sometimes contain much smaller strokes than the alphabet.
    if cp is not None and ud.category(chr(cp))[0] in 'PS':
        estimate = 2*area(p)/max(perimeter(p),1)
        nominal = min(1,max(.35,estimate/132))
    return nominal,528*nominal,530*nominal,'body'


def derive(p, cp, distance, target):
    if not len(p):
        return pathops.Path(p), []
    base_cp = ord(ud.normalize('NFD',chr(cp))[0]) if cp is not None else None
    parts, notes = [], []
    for part in components(p):
        x0,y0,x1,y1 = part.bounds
        cx,cy = (x0+x1)/2,(y0+y1)/2
        if is_dot(part) or cp==0x2d0:
            parts.append(centered_scale(part,cx,cy,target/132,target/132))
            continue
        factor, min_w, min_h, kind = component_parameters(part,cp,base_cp)
        actual_distance = distance*factor
        original_topology = topology(part)
        # Protect very small counters / signs from a topology change.
        for attempt in range(13):
            q = offset(part,actual_distance)
            if len(q) and topology(q) == original_topology:
                break
            actual_distance *= .85
        else:
            raise ValueError(('Unstable outline topology', cp, part.bounds))
        if attempt:
            notes.append({'kind':kind,'offsetFactor':round(actual_distance/distance,5),
                          'reason':'preserve component and counter topology'})
        fw,fh = max(x1-x0,min_w), max(y1-y0,min_h)
        sx,sy = fw/(fw-2*actual_distance),fh/(fh-2*actual_distance)
        q = centered_scale(q,cx,cy,sx,sy)
        parts.append(q)
    return combine(parts),notes


def slant_anchors(table):
    seen=set()
    def visit(value):
        if id(value) in seen:return
        seen.add(id(value))
        if isinstance(value,(str,int,float,bytes,type(None))):return
        if value.__class__.__name__=='Anchor' and hasattr(value,'XCoordinate'):
            value.XCoordinate=round(value.XCoordinate+SLANT*value.YCoordinate-SLANT*265)
            return
        if isinstance(value,(list,tuple)):
            for v in value:visit(v)
        elif isinstance(value,dict):
            for v in value.values():visit(v)
        elif hasattr(value,'__dict__'):
            for v in vars(value).values():visit(v)
    visit(table)


def compile_font(paths, master, style, weight, is_ttf, lsbs,italic=False):
    order = master.getGlyphOrder()
    advances = master['hmtx'].metrics
    fb = FontBuilder(1000,isTTF=is_ttf)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(master.getBestCmap())
    outlines = {}
    for name in order:
        if is_ttf:
            pen = TTGlyphPen(None)
            paths[name].draw(Cu2QuPen(pen,max_err=.10,reverse_direction=False))
            outlines[name] = pen.glyph()
            outlines[name].recalcBounds(None)
            lsbs[name] = getattr(outlines[name],'xMin',0)
        else:
            pen = T2CharStringPen(advances[name][0],None,roundTolerance=0)
            paths[name].draw(CubicPen(RoundingPen(pen,roundFunc=lambda v:round(v*16384)/16384)))
            outlines[name] = pen.getCharString(private=None,globalSubrs=None)
    if is_ttf:
        fb.setupGlyf(outlines)
    else:
        fb.setupCFF('Nambli-'+style, {'FullName':'Nambli '+style_label(style),'FamilyName':'Nambli',
                                    'Weight':style_label(style),'version':'0.7.4',
                                    'ItalicAngle':-10 if italic else 0},outlines,{})
    fb.setupHorizontalMetrics({n:(advances[n][0],lsbs[n]) for n in order})
    fb.setupHorizontalHeader(ascent=1200,descent=-400,lineGap=0,
                             caretSlopeRise=1000 if italic else 1,
                             caretSlopeRun=round(1000*SLANT) if italic else 0)
    base_style='Regular' if style=='Italic' else style.removesuffix('Italic')
    legacy_family = 'Nambli' if weight in (400,700) else 'Nambli '+base_style
    legacy_style=('Bold Italic' if italic else 'Bold') if weight==700 else ('Italic' if italic else 'Regular')
    fb.setupNameTable({
        'familyName':legacy_family,'styleName':legacy_style,
        'uniqueFontIdentifier':f'NAMB:Nambli-{style}:0.7.4:20261007',
        'fullName':'Nambli '+style_label(style),'psName':'Nambli-'+style,
        'version':'Version 0.704','typographicFamily':'Nambli',
        'typographicSubfamily':style_label(style),
        'copyright':(master['name'].getDebugName(0) or '').replace('Nembli','Nambli'),
        'description':'Nambli rounded display family. Six weights with native italic forms; optical stroke corrections. Family v0.7.4. Open @ tail, dje and tje crossbar corrections.',
        'designer':'Yurii Tor', 'manufacturer':'Yurii Tor', 'licenseInfoURL':'https://openfontlicense.org',
        'licenseDescription':(master['name'].getDebugName(13) or '').replace('Nembli','Nambli'),
    })
    fb.setupOS2(version=4,sTypoAscender=1200,sTypoDescender=-400,sTypoLineGap=0,
                usWinAscent=1200,usWinDescent=400,sxHeight=530,sCapHeight=740,
                usWeightClass=weight,usWidthClass=5,fsType=0,
                fsSelection=0x80 | (0x20 if weight==700 else 0) | (1 if italic else (0 if weight==700 else 0x40)),
                achVendID='NAMB')
    fb.font['OS/2'].panose = copy.deepcopy(master['OS/2'].panose)
    fb.font['OS/2'].panose.bWeight = {300:3,400:5,500:6,600:7,700:8,800:9}[weight]
    fb.setupPost(keepGlyphNames=True,italicAngle=-10 if italic else 0)
    if is_ttf:
        fb.setupMaxp()
        gasp = newTable('gasp')
        gasp.gaspRange = {65535:15}
        fb.font['gasp'] = gasp
    fb.font['head'].macStyle = (1 if weight==700 else 0) | (2 if italic else 0)
    fb.font['head'].fontRevision = .704
    date = datetime(2026,10,2,tzinfo=timezone.utc)
    epoch = datetime(1904,1,1,tzinfo=timezone.utc)
    fb.font['head'].created = fb.font['head'].modified = int((date-epoch).total_seconds())
    fb.font.recalcTimestamp = False
    for tag in ['GDEF','GSUB','GPOS','kern']:
        if tag in master:
            fb.font[tag] = copy.deepcopy(master[tag])
    if italic:slant_anchors(fb.font['GPOS'].table)
    buildStatTable(fb.font,[{'tag':'wght','name':'Weight','ordering':0,
                            'values':[{'value':weight,'name':base_style,
                                       'flags':2 if weight==400 else 0}]},
                           {'tag':'ital','name':'Italic','ordering':1,
                            'values':[{'value':int(italic),'name':'Italic' if italic else 'Roman',
                                       'flags':0 if italic else 2}]}],
                   elidedFallbackName='Regular')
    ext = 'ttf' if is_ttf else 'otf'
    fb.save(OUT/f'Nambli-{style}.{ext}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--style',choices=[s for s,_,_,_ in FACES])
    parser.add_argument('--italic-only',action='store_true')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    master = TTFont(MASTER/'Nambli-Bold.otf',recalcTimestamp=False)
    cmap = master.getBestCmap()
    codepoints = {name:cp for cp,name in cmap.items()}
    gs = master.getGlyphSet()
    original = {}
    for name in master.getGlyphOrder():
        p = pathops.Path()
        gs[name].draw(p.getPen())
        original[name] = p
    report_file = ROOT/'sources'/'build-report.json'
    reports = json.loads(report_file.read_text(encoding='utf-8')) if report_file.exists() else {}
    for style,weight,target,italic in FACES:
        if args.style and args.style != style:
            continue
        if args.italic_only and not italic:continue
        nominal_target=target
        # The small normal-width compensation offsets shear's reduction of
        # a vertical stroke's perpendicular thickness.
        if italic:target=target/math.cos(math.radians(10))
        # Solve for a 528-unit optical frame with the selected stem width.
        distance = 528*(132-target)/(2*(528-target))
        paths,exceptions = {},{}
        for name,p in original.items():
            paths[name],notes = derive(p,codepoints.get(name),distance,target)
            if notes:
                exceptions[name] = notes
        from optical import refine
        from outline_polish import polish
        paths={n:polish(p,distance=12*target/132)[0] if len(p) else p for n,p in paths.items()}
        optically_built=refine(paths,master,target,combine,italic)
        paths={n:polish(p,distance=12*target/132)[0] if len(p) else p for n,p in paths.items()}
        if italic:
            paths={n:p.transform(1,0,SLANT,1,-SLANT*265,0) for n,p in paths.items()}
            # Shear can turn a previously sub-threshold join into a visible
            # corner. Fair the actual italic geometry after transforming it.
            paths={n:polish(p,distance=12*target/132)[0] if len(p) else p for n,p in paths.items()}
        exceptions={n:v for n,v in exceptions.items() if n not in optically_built}
        lsbs = {}
        compile_font(paths,master,style,weight,True,lsbs,italic)
        compile_font(paths,master,style,weight,False,lsbs,italic)
        web = TTFont(OUT/f'Nambli-{style}.ttf',recalcTimestamp=False)
        web.flavor = 'woff2'
        web.save(OUT/f'Nambli-{style}.woff2')
        reports[style] = {'weight':weight,'referenceStroke':nominal_target,
                         'italic':italic,'slantDegrees':10 if italic else 0,
                         'offset':distance,'adaptiveExceptions':exceptions,
                         'separatelyConstructedGlyphs':sorted(optically_built),
                         'glyphs':len(paths),'characters':len(cmap)}
        print(f'{style}: {len(paths)} glyphs; {len(exceptions)} adaptive exceptions',flush=True)
    report_file.write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
