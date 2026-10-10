# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Conservative side-caron adjustment; all other accent designs are retained.

The rejected experiment normalised every accent towards the letter stroke.
This replacement increases only the existing side-caron stroke by 30%, with
an ordinary outline expansion around its original centreline. It changes the
shared mark and its four precomposed occurrences. No files are written.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
from pathlib import Path
import re
import time
import unicodedata as ud

import pathops
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.perimeterPen import PerimeterPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPointPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from ufoLib2.objects import Glyph

from build_family import CubicPen,offset,topology,area
from smooth_contours import ContourPen,_polyline,smooth_glyph,repair_quantized_g1

STEMS={300:80,400:100,500:114,600:123,700:132,800:146}
SIDECARONS={'L':'uni013D','l':'uni013E','d':'uni010F','t':'uni0165'}
TARGETS=frozenset(SIDECARONS.values())|{'uni030C.alt'}
BASE_RE=re.compile(r'pos base\s+(\S+)\s+<anchor\s+(-?\d+)\s+(-?\d+)>\s+mark\s+@(\w+);')
CLASS_RE=re.compile(r'markClass\s+(\S+)\s+<anchor\s+(-?\d+)\s+(-?\d+)>\s+@(\w+);')


def path_of(drawable):
    p=pathops.Path();drawable.draw(CubicPen(p.getPen()))
    return p


def _record(drawable):
    p=RecordingPointPen();drawable.drawPoints(p);return p.value


def _native(path,italic_angle):
    smoothed,smoothing=smooth_glyph(path,italic_angle=italic_angle)
    pen=TTGlyphPen(None)
    smoothed.replay(Cu2QuPen(pen,max_err=.25,all_quadratic=True))
    native=pen.glyph()
    repair=repair_quantized_g1(native,maximum_shift=2.)
    result=Glyph('temporary')
    native.drawPoints(result.getPointPen(),None)
    return result,{'smoothing':smoothing,'quantizedG1':repair}


def _gap(a,b):
    import numpy as np
    intersect=pathops.op(a,b,pathops.PathOp.INTERSECTION)
    if len(intersect) and area(intersect)>.01:return 0.
    arrays=[]
    for p in (a,b):
        pen=ContourPen();p.draw(pen)
        vertices=[(v.real,v.imag) for c in pen.contours for v in _polyline(c,.05,3)[0]]
        arrays.append(np.asarray(vertices,dtype=float))
    squared=math.inf
    for i in range(0,len(arrays[0]),256):
        delta=arrays[0][i:i+256,None,:]-arrays[1][None,:,:]
        squared=min(squared,float(np.min(np.sum(delta*delta,axis=2))))
    return math.sqrt(squared)


def _bounds_score(a,b):return max(abs(x-y) for x,y in zip(a,b))


def refine_font(font,increase=.30):
    """Modify only five side-caron glyphs in memory and return measurements."""
    if not 0 < increase <= .35:raise ValueError('Only a conservative increase of up to 35% is supported')
    features=font.features.text
    metrics={g.name:(g.width,tuple(g.unicodes)) for g in font}
    stem=STEMS[font.info.openTypeOS2WeightClass]
    italic_angle=float(font.info.italicAngle or 0)
    shear=math.tan(math.radians(-italic_angle))
    nominal=57*.75*stem/132
    distance=nominal*increase/2
    original=path_of(font['uni030C.alt'])
    upright=original.transform(1,0,-shear,1,0,0)
    expanded=offset(upright,-distance)
    # PathOps can leave a sub-unit triangular hole after expanding a rounded
    # integer contour. The original open curl has no counter; discard only
    # this strictly bounded numerical residue, not a substantial enclosure.
    residuals=[c for c in expanded.contours if not c.clockwise and area(c)<.01]
    if residuals:
        cleaned=pathops.Path()
        for c in expanded.contours:
            if not c.clockwise and area(c)<.01:continue
            c.draw(cleaned.getPen())
        expanded=cleaned
    if topology(expanded)!=topology(upright):
        raise ValueError('The conservative side-caron expansion changed topology')
    shared,construction=_native(expanded.transform(1,0,shear,1,0,0),italic_angle)
    if len(shared.contours)!=1:raise ValueError('Side caron must remain a single contour')
    new_path=path_of(shared)
    classes={n:(int(x),int(y),kind) for n,x,y,kind in CLASS_RE.findall(features)}
    anchors={(n,kind):(int(x),int(y)) for n,x,y,kind in BASE_RE.findall(features)}
    mx,my,kind=classes['uni030C.alt']
    replacements=[]
    for base,name in SIDECARONS.items():
        ax,ay=anchors[(base,kind)]
        dx,dy=ax-mx,ay-my
        expected=original.transform(1,0,0,1,dx,dy)
        glyph=font[name]
        scores=[_bounds_score(path_of(c).bounds,expected.bounds) for c in glyph.contours]
        index=min(range(len(scores)),key=scores.__getitem__)
        if scores[index]>2.1:
            raise ValueError(f'Cannot safely identify side-caron contour in {name}: {scores[index]}')
        before_recordings=[_record(c) for c in glyph.contours]
        old_right_sidebearing=glyph.width-glyph.getBounds(font).xMax
        replacement=copy.deepcopy(shared.contours[0])
        replacement.move((dx,dy))
        body=pathops.Path()
        for i,c in enumerate(glyph.contours):
            if i!=index:c.draw(CubicPen(body.getPen()))
        placed=path_of(replacement)
        gap=_gap(body,placed)
        if gap<12:
            raise ValueError(f'Side caron would crowd {name}: {gap:.2f} units')
        old_bounds=tuple(path_of(glyph.contours[index]).bounds)
        glyph.contours[index]=replacement
        assert all(_record(c)==before_recordings[i] for i,c in enumerate(glyph.contours) if i!=index)
        replacements.append({'glyph':name,'contour':index,'translation':[dx,dy],
                             'beforeBounds':old_bounds,'afterBounds':tuple(placed.bounds),
                             'baseClearance':round(gap,3),'advance':glyph.width,
                             'beforeRightSidebearing':round(old_right_sidebearing,3),
                             'rightSidebearing':round(glyph.width-glyph.getBounds(font).xMax,3),
                             'baseContoursUnchanged':True})
    font['uni030C.alt'].contours[:]=copy.deepcopy(shared.contours)
    assert features==font.features.text
    assert metrics=={g.name:(g.width,tuple(g.unicodes)) for g in font}
    return {'style':font.info.styleName,'scope':'side-carons-only','increase':increase,
            'nominalStrokeBefore':nominal,'nominalStrokeTarget':nominal*(1+increase),
            'normalExpansionPerSide':distance,'changedGlyphs':sorted(TARGETS),
            'numericCavitiesDiscarded':len(residuals),
            'placements':replacements,'construction':construction,
            'otherDiacritics':'RETAIN_EXISTING_DESIGN','featuresUnchanged':True,
            'advancesAndUnicodeUnchanged':True,'canonicalMarkBeforeBounds':tuple(original.bounds),
            'canonicalMarkAfterBounds':tuple(new_path.bounds)}


def measure_marks(font):
    """Read-only diagnostics, not targets for normalising the accent design.

    The capsule formula estimates width from area/perimeter for an open round
    stroke. Rings use their inner/outer boundary ratio. Very compact shapes
    and anisotropic strokes make this an estimate, so it is labelled as such.
    """
    shear=math.tan(math.radians(-float(font.info.italicAngle or 0)))
    stem=STEMS[font.info.openTypeOS2WeightClass]
    result=[]
    for glyph in font:
        if glyph.name!='uni030C.alt' and not any(ud.category(chr(cp)).startswith('M') for cp in glyph.unicodes):continue
        p=path_of(glyph).transform(1,0,-shear,1,0,0)
        ap=AreaPen(None);pp=PerimeterPen(None,tolerance=.001)
        p.draw(ap);p.draw(pp);a=abs(ap.value);per=pp.value
        contours=list(p.contours)
        counters=sum(not c.clockwise for c in contours)
        if counters:
            estimate=2*a/per
        else:
            n=max(1,len(contours))
            discriminant=max(0,per*per-4*math.pi*n*a)
            estimate=(per-math.sqrt(discriminant))/(math.pi*n)
        result.append({'glyph':glyph.name,'unicodes':glyph.unicodes,'bounds':tuple(p.bounds),
                       'estimatedStroke':round(estimate,3),'ratioToStem':round(estimate/stem,3),
                       'disposition':'MODERATE_30_PERCENT_INCREASE' if glyph.name=='uni030C.alt' else 'RETAIN_EXISTING_DESIGN'})
    return result


def apply_directory(input_dir,output_dir,report_dir,increase=.30):
    """Save a separate candidate; never modify the supplied UFO directory."""
    from ufoLib2 import Font
    input_dir,output_dir,report_dir=map(Path,(input_dir,output_dir,report_dir))
    if input_dir.resolve()==output_dir.resolve():
        raise ValueError('Source and destination must be different directories')
    sources=sorted(input_dir.glob('Nambli-*.ufo'))
    if not sources:raise ValueError('No Nambli UFO sources found')
    for source in sources:
        if (output_dir/source.name).exists():
            raise FileExistsError(f'Refusing to overwrite candidate: {source.name}')
    output_dir.mkdir(parents=True,exist_ok=True)
    report_dir.mkdir(parents=True,exist_ok=True)
    results=[]
    for source in sources:
        started=time.monotonic()
        font=Font.open(source)
        report=refine_font(font,increase=increase)
        font.save(output_dir/source.name)
        report['font']=source.stem
        report['seconds']=round(time.monotonic()-started,3)
        (report_dir/(source.stem+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        results.append({'font':source.stem,'changedGlyphs':report['changedGlyphs'],
                        'minimumBaseClearance':min(row['baseClearance'] for row in report['placements']),
                        'seconds':report['seconds']})
        print(json.dumps(results[-1]),flush=True)
    summary={'scope':'side-carons-only','increase':increase,'faces':results,
             'otherDiacritics':'RETAIN_EXISTING_DESIGN','featuresAndAdvancesUnchanged':True}
    (report_dir/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-ufos',type=Path,required=True)
    parser.add_argument('--output-ufos',type=Path,required=True)
    parser.add_argument('--reports',type=Path,required=True)
    parser.add_argument('--increase',type=float,default=.30)
    args=parser.parse_args()
    apply_directory(args.input_ufos,args.output_ufos,args.reports,args.increase)


if __name__=='__main__':main()
