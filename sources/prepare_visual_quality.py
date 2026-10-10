# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Prepare the separate 1.002 visual review candidate from approved UFOs.

This command has no release, network, or deployment operation. Source and
destination must differ. Run the independent compiled-font audit afterwards.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import math
from pathlib import Path
import time
import tempfile
from copy import deepcopy

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen, RecordingPointPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from ufoLib2 import Font
STEMS={300:80,400:100,500:114,600:123,700:132,800:146}
from refine_optical_details import round_bowl_overshoot, missing_glyph
from smooth_contours import smooth_glyph, repair_quantized_g1, cache_info
from smooth_contours import ContourPen,draw_contours
from finalize_visual_outlines import finalize_glyph,retry_glyph,remove_zero_length_segments
from diacritic_scope import preserved_contours

class Drawable:
    def __init__(self, recording): self.recording = recording
    def draw(self, pen): self.recording.replay(pen)

class NativeDrawable:
    def __init__(self,glyph):self.glyph=glyph
    def draw(self,pen):self.glyph.draw(pen,None)

def recording(glyph):
    p=RecordingPointPen();glyph.drawPoints(p);return p.value

def set_outline(glyph, draw, retained=(), italic_angle=0.):
    pen=TTGlyphPen(None)
    draw.replay(Cu2QuPen(pen,max_err=.3,all_quadratic=True))
    tt=pen.glyph()
    repairs=repair_quantized_g1(tt,maximum_shift=3.)
    cleanup=remove_zero_length_segments(tt)
    tt,finalization=finalize_glyph(NativeDrawable(tt))
    finalization['constantSegments']=cleanup
    if finalization.get('remainingCrossings') or finalization.get('remainingJoins'):
        tt,retry=retry_glyph(NativeDrawable(tt),italic_angle=italic_angle)
        finalization['retry']=retry
        finalization['remainingCrossings']=retry.get('remainingCrossings',[])
        finalization['remainingJoins']=retry.get('remainingJoins',[])
        finalization['changed']=finalization['changed'] or retry['changed']
    points=RecordingPointPen();tt.drawPoints(points,None)
    glyph.clearContours();points.replay(glyph.getPointPen())
    for contour in retained:glyph.appendContour(deepcopy(contour))
    return repairs,finalization

def prepare_face(task):
    src,dest,reports=map(Path,task);started=time.monotonic()
    temporary=reports/'.tmp';temporary.mkdir(parents=True,exist_ok=True)
    tempfile.tempdir=str(temporary)
    print(f'{src.stem}: preserving original diacritics',flush=True)
    font=Font.open(src)
    baseline_font=Font.open(src)
    before={g.name:recording(g) for g in font}
    original_widths={g.name:g.width for g in font}
    diacritics={'status':'DEFERRED_BY_OWNER','changedGlyphs':{},'preservedGlyphs':{}}
    cmap={cp:g.name for g in baseline_font for cp in g.unicodes}
    angle=float(font.info.italicAngle or 0)
    stem=STEMS[font.info.openTypeOS2WeightClass]
    details={};reason_counts=Counter();changed=[];g1_count=0
    for index,glyph in enumerate(font):
        if index%200==0:print(f'{src.stem}: smoothing {index}/{len(font)}',flush=True)
        retained_indices,disposition=preserved_contours(baseline_font,baseline_font[glyph.name],cmap)
        if disposition:diacritics['preservedGlyphs'][glyph.name]=disposition
        if disposition.get('wholeGlyph'):continue
        retained=[deepcopy(glyph.contours[i]) for i in retained_indices]
        # A deferred below-mark must keep its original gap. Baseline overshoot
        # would consume that gap, even while preserving the accent itself.
        protected_lines=(0,) if any(c.points and max(p.y for p in c.points)<40 and min(p.y for p in c.points)<0 for c in retained) else ()
        old=ContourPen();glyph.draw(old)
        body=RecordingPen();draw_contours([c for i,c in enumerate(old.contours) if i not in retained_indices],body)
        if glyph.name=='.notdef':
            r=missing_glyph(glyph.width,stem,angle);optical={'missingGlyph':True}
        else:
            r,fields=round_bowl_overshoot(Drawable(body),glyph.unicodes,angle,stem,protected_lines)
            optical={'overshoot':fields} if fields else {}
            if protected_lines:optical['baselineOvershootDeferred']='preserve_original_below_mark_gap'
        smoothed,report=smooth_glyph(Drawable(r),italic_angle=angle)
        g1,finalization=set_outline(glyph,smoothed,retained,angle)
        reason_counts.update(report['reasons'])
        if before[glyph.name]!=recording(glyph):changed.append(glyph.name)
        g1_count+=len(g1['joins'])
        if report['changed'] or g1['changed'] or optical or finalization['changed']:
            details[glyph.name]={'optical':optical,'smoothing':report,'quantizedG1':g1,'finalization':finalization}
    # Keep established line layout; enlarge only OS/2 Windows clipping limits
    # if a bounded contour repair extends a pre-existing extremum.
    bounds=[g.getBounds(font) for g in font if len(g)]
    ymin=min(b[1] for b in bounds);ymax=max(b[3] for b in bounds)
    old_clip=[font.info.openTypeOS2WinAscent,font.info.openTypeOS2WinDescent]
    font.info.openTypeOS2WinAscent=max(old_clip[0],math.ceil(ymax)+20)
    font.info.openTypeOS2WinDescent=max(old_clip[1],math.ceil(-ymin)+20)
    font.info.versionMajor=1;font.info.versionMinor=2
    for key in ('openTypeNameVersion','openTypeNameUniqueID'):
        value=getattr(font.info,key,None)
        if value:setattr(font.info,key,value.replace('1.001','1.002'))
    for row in font.info.openTypeNameRecords or []:
        if row.nameID in (3,5):row.string=row.string.replace('1.001','1.002')
    dest.parent.mkdir(parents=True,exist_ok=True)
    font.save(dest,overwrite=True)
    result={'font':src.stem,'version':'1.002','glyphs':len(font),'changedGlyphCount':len(changed),
        'changedGlyphs':changed,'outlineReasons':dict(reason_counts),'quantizedG1Repairs':g1_count,
        'inkYBounds':[ymin,ymax],'windowsClippingBefore':old_clip,
        'windowsClippingAfter':[font.info.openTypeOS2WinAscent,font.info.openTypeOS2WinDescent],
        'advanceChanges':{g.name:[original_widths[g.name],g.width] for g in font if original_widths[g.name]!=g.width},
        'diacritics':diacritics,'details':details,'cache':cache_info(),'seconds':round(time.monotonic()-started,2)}
    reports.mkdir(parents=True,exist_ok=True)
    (reports/(src.stem+'.json')).write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    return {k:v for k,v in result.items() if k not in {'details','diacritics','changedGlyphs'}}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-ufos',type=Path,required=True)
    p.add_argument('--output-ufos',type=Path,required=True)
    p.add_argument('--reports',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--face',action='append')
    a=p.parse_args()
    temporary=a.reports/'.tmp';temporary.mkdir(parents=True,exist_ok=True)
    tempfile.tempdir=str(temporary)
    if a.input_ufos.resolve()==a.output_ufos.resolve():p.error('Input and output must differ')
    sources=sorted(a.input_ufos.glob('Nambli-*.ufo'))
    if a.face:sources=[f for f in sources if f.stem in a.face]
    tasks=[(str(f),str(a.output_ufos/f.name),str(a.reports)) for f in sources]
    results=[]
    with ProcessPoolExecutor(max_workers=a.workers) as executor:
        futures=[executor.submit(prepare_face,t) for t in tasks]
        for future in as_completed(futures):
            try:row=future.result()
            except Exception:
                import traceback
                traceback.print_exc()
                if hasattr(executor,'terminate_workers'):executor.terminate_workers()
                raise
            results.append(row);print(json.dumps(row),flush=True)
    # A family shares clipping metrics so switching weight does not clip marks
    # differently. Typographic ascender/descender and line gap stay unchanged.
    ascent=max(row['windowsClippingAfter'][0] for row in results)
    descent=max(row['windowsClippingAfter'][1] for row in results)
    for source in sources:
        font=Font.open(a.output_ufos/source.name)
        font.info.openTypeOS2WinAscent=ascent
        font.info.openTypeOS2WinDescent=descent
        font.save(a.output_ufos/source.name,overwrite=True)
    a.reports.mkdir(parents=True,exist_ok=True)
    (a.reports/'summary.json').write_text(json.dumps({'version':'1.002','familyWindowsClipping':[ascent,descent],'faces':sorted(results,key=lambda x:x['font'])},indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
