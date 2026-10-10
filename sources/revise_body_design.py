# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Rebuild only reported overshoot bodies from 1.001, retaining 1.002 smoothing.

Writes a separate 1.003 candidate UFO family. It does not modify the input,
approved baseline, releases, website, or Google Fonts submission. A fresh
compiled-family audit and visual review are required after this source pass.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import html
import json
from pathlib import Path
import tempfile
import time

from fontTools.pens.recordingPen import RecordingPen, RecordingPointPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from ufoLib2 import Font

from audit_visual_quality import EdgePen, audit_contours
from diacritic_scope import preserved_contours
from finalize_visual_outlines import (_crossings, _join_flags,
    merge_short_curve_facets, remove_zero_length_segments)
from prepare_visual_quality import Drawable, NativeDrawable, recording, set_outline
from smooth_contours import ContourPen, draw_contours, smooth_glyph


CORE_FLAGS={'open_contour','non_finite_coordinate','zero_area_contour',
    'zero_length_segment','disconnected_segments','curve_tangent_break',
    'short_handle_corner','short_line_facet_between_curves','flattened_proper_crossing'}


def selected_glyphs(report):
    """Never infer scope from Unicode, glyph bounds, or font version."""
    return sorted(name for name, detail in report.get('details',{}).items()
                  if detail.get('optical',{}).get('overshoot'))


def _native(drawable):
    pen=TTGlyphPen(None);drawable.draw(pen);return pen.glyph()


def _write_native(glyph,native,retained):
    points=RecordingPointPen();native.drawPoints(points,None)
    glyph.clearContours();points.replay(glyph.getPointPen())
    for contour in retained:glyph.appendContour(deepcopy(contour))


def _body(glyph,retained_count):
    result=deepcopy(glyph)
    if retained_count:
        result.clearContours()
        for contour in glyph.contours[:-retained_count]:result.appendContour(deepcopy(contour))
    return result


def _core_audit(glyph,font,retained_count=0):
    pen=EdgePen(font);glyph.draw(pen)
    report=audit_contours(pen.contours,pen.open_contours,font.info.unitsPerEm or 1000)
    body_count=len(pen.contours)-retained_count
    flags=[flag for flag in report['flags'] if flag['kind'] in CORE_FLAGS and
           (flag.get('contour',0)<body_count or flag.get('other_contour',body_count)<body_count)]
    # Use a finer independent intersection check via the generic contour
    # geometry, retaining only interactions involving the repaired body.
    p=ContourPen();glyph.draw(p)
    fine_crossings=[x for x in _crossings(p.contours,.01)
                    if x['contour']<body_count or x['other_contour']<body_count]
    return {'bodyContours':body_count,'coreFlags':flags,'fineCrossings':fine_crossings,
            'remainingRawJoins15':_join_flags(p.contours[:body_count],15.)}


def rebuild_glyph(current_font,baseline_font,name,preparation_report):
    """Return a new glyph and evidence; neither source font is mutated."""
    old=baseline_font[name];current=current_font[name];candidate=deepcopy(current)
    if old.components or current.components:
        raise ValueError(f'{name}: component outlines require explicit decomposition')
    cmap={cp:g.name for g in baseline_font for cp in g.unicodes}
    indices,disposition=preserved_contours(baseline_font,old,cmap)
    recorded=preparation_report.get('diacritics',{}).get('preservedGlyphs',{}).get(name,{})
    if disposition.get('wholeGlyph') or recorded.get('wholeGlyph'):
        raise ValueError(f'{name}: reported overshoot conflicts with deferred whole glyph')
    if indices!=recorded.get('preservedContours',[]):
        raise ValueError(f'{name}: accent scope differs from preparation evidence')
    retained=[deepcopy(old.contours[i]) for i in indices]
    if retained and current.contours[-len(retained):]!=retained:
        raise ValueError(f'{name}: current accent contours differ from approved originals')
    pen=ContourPen();old.draw(pen)
    body=RecordingPen();draw_contours([c for i,c in enumerate(pen.contours) if i not in indices],body)
    angle=float(current_font.info.italicAngle or 0)
    smoothed,smoothing=smooth_glyph(Drawable(body),italic_angle=angle)
    g1,finalization=set_outline(candidate,smoothed,retained,angle)
    native=_native(_body(candidate,len(retained)))
    cleanup=remove_zero_length_segments(native)
    _write_native(candidate,native,retained)
    audit=_core_audit(candidate,current_font,len(retained))
    facet_report={}
    if any(flag['kind']=='short_line_facet_between_curves' for flag in audit['coreFlags']):
        native,facet_report=merge_short_curve_facets(NativeDrawable(native))
        _write_native(candidate,native,retained)
        audit=_core_audit(candidate,current_font,len(retained))
    if candidate.width!=current.width or candidate.anchors!=current.anchors:
        raise AssertionError(f'{name}: metrics or anchors changed')
    if retained and candidate.contours[-len(retained):]!=retained:
        raise AssertionError(f'{name}: retained accents changed')
    evidence={'removedOvershootFields':preparation_report['details'][name]['optical']['overshoot'],
        'baselineBounds':list(old.getBounds(baseline_font) or ()),
        'previousBounds':list(current.getBounds(current_font) or ()),
        'candidateBounds':list(candidate.getBounds(current_font) or ()),
        'retainedAccentContours':indices,'exactRetainedAccents':True,
        'smoothing':smoothing,'quantizedG1':g1,'finalization':finalization,
        'finalCleanup':cleanup,'facetMerge':facet_report,'audit':audit,
        'changedFromPrevious':recording(candidate)!=recording(current)}
    return candidate,evidence


def _version(font):
    font.info.versionMajor=1;font.info.versionMinor=3
    for key in ('openTypeNameVersion','openTypeNameUniqueID'):
        value=getattr(font.info,key,None)
        if value:setattr(font.info,key,value.replace('1.002','1.003'))
    for row in font.info.openTypeNameRecords or []:
        if row.nameID in (3,5):row.string=row.string.replace('1.002','1.003')


def _preview(path,baseline,current,candidate,selected):
    names=[n for n in ('a','b','e','o','p','q','uni0430','uni044F','uni1E01') if n in selected]
    cards=[]
    for name in names:
        cells=[]
        for label,font in (('1.001: початкова форма',baseline),('1.002: з виносами',current),('1.003: без виносів',candidate)):
            glyph=font[name];pen=SVGPathPen(font);glyph.draw(pen)
            width=max(650,glyph.width+80)
            cells.append(f'<div><p>{label}</p><svg viewBox="-40 -800 {width} 1040"><g fill="#7054e8" transform="scale(1,-1)"><path d="{pen.getCommands()}"/></g><g stroke="#ababbf" stroke-width="1" stroke-dasharray="5 5"><path d="M-40 0H{width}M-40 -530H{width}"/></g></svg></div>')
        cards.append(f'<section><h2>{html.escape(name)}</h2><div class="row">'+''.join(cells)+'</div></section>')
    path.write_text('<!doctype html><html lang="uk"><meta charset="utf-8"><title>Nambli: без доданих виносів</title><style>body{font:16px system-ui;margin:30px;background:#f7f5ff;color:#252435}section{background:white;border:1px solid #ddd5fc;border-radius:16px;padding:18px;margin:18px 0}.row{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}svg{width:100%;max-height:360px}p{font-size:13px;color:#696679}</style><h1>'+html.escape(path.stem)+'</h1><p>Згладжування збережено. Додані оптичні виноси прибрано. Сірі лінії — базова лінія та висота малих літер.</p>'+''.join(cards)+'</html>',encoding='utf-8')


def revise_face(task):
    current_path,baseline_path,preparation_path,output_path,reports_path=map(Path,task)
    started=time.monotonic();reports_path.mkdir(parents=True,exist_ok=True)
    temporary=reports_path/'.tmp';temporary.mkdir(exist_ok=True);tempfile.tempdir=str(temporary)
    if output_path.exists():raise FileExistsError(f'Refusing to overwrite candidate {output_path}')
    preparation=json.loads(preparation_path.read_text(encoding='utf-8'))
    selected=selected_glyphs(preparation)
    baseline=Font.open(baseline_path);previous=Font.open(current_path);font=Font.open(current_path)
    before={g.name:recording(g) for g in previous}
    widths={g.name:g.width for g in previous};anchors={g.name:deepcopy(g.anchors) for g in previous}
    details={};pending=[]
    print(f'{current_path.stem}: rebuilding {len(selected)} reported overshoot glyphs',flush=True)
    for index,name in enumerate(selected):
        glyph,detail=rebuild_glyph(font,baseline,name,preparation)
        if detail['audit']['coreFlags'] or detail['audit']['fineCrossings'] or detail['audit']['remainingRawJoins15']:
            pending.append(name)
        font[name]=glyph;details[name]=detail
        if index%40==0:print(f'{current_path.stem}: {index+1}/{len(selected)}; pending {len(pending)}',flush=True)
    selected_set=set(selected)
    untouched=[g.name for g in font if g.name not in selected_set]
    for name in untouched:
        if recording(font[name])!=before[name]:raise AssertionError(f'{name}: unselected native outline changed')
    for glyph in font:
        if glyph.width!=widths[glyph.name] or glyph.anchors!=anchors[glyph.name]:
            raise AssertionError(f'{glyph.name}: advance or anchors changed')
    _version(font)
    changed=[name for name in selected if recording(font[name])!=before[name]]
    result={'font':current_path.stem,'version':'1.003','scope':'remove_reported_added_overshoot_only',
        'selectedGlyphs':selected,'selectedGlyphCount':len(selected),'changedGlyphs':changed,
        'changedGlyphCount':len(changed),'unchangedNativeGlyphCount':len(untouched),
        'notdefExactlyPreserved':recording(font['.notdef'])==before['.notdef'],
        'advancesAndAnchorsExactlyPreserved':True,'pendingGlyphs':pending,'details':details,
        'baseline':str(baseline_path),'previousCandidate':str(current_path),
        'sourcePreparationReport':str(preparation_path),'outputUfo':str(output_path),
        'seconds':round(time.monotonic()-started,2)}
    (reports_path/(current_path.stem+'.json')).write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    if pending:
        raise ValueError(f'{current_path.stem}: unsafe body outlines {pending}; report saved, no UFO written')
    output_path.parent.mkdir(parents=True,exist_ok=True);font.save(output_path)
    # A save/reopen comparison tests the actual editable source, not only RAM.
    reopened=Font.open(output_path)
    for glyph in font:
        if recording(reopened[glyph.name])!=recording(glyph):
            raise AssertionError(f'{glyph.name}: native outline changed during UFO save')
    _preview(reports_path/(current_path.stem+'-No-Overshoot.html'),baseline,previous,font,selected)
    return {k:v for k,v in result.items() if k not in {'details','selectedGlyphs','changedGlyphs'}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-ufos',type=Path,required=True)
    p.add_argument('--baseline-ufos',type=Path,required=True)
    p.add_argument('--preparation-reports',type=Path,required=True)
    p.add_argument('--output-ufos',type=Path,required=True)
    p.add_argument('--reports',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--face',action='append')
    a=p.parse_args();out=a.output_ufos.resolve()
    for protected in (a.input_ufos.resolve(),a.baseline_ufos.resolve()):
        if out==protected or out in protected.parents or protected in out.parents:
            p.error('Output must be separate from both protected source trees')
    sources=sorted(a.input_ufos.glob('Nambli-*.ufo'))
    if a.face:sources=[source for source in sources if source.stem in a.face]
    if not sources:p.error('No selected UFOs found')
    tasks=[tuple(map(str,(source,a.baseline_ufos/source.name,
        a.preparation_reports/(source.stem+'.json'),a.output_ufos/source.name,a.reports))) for source in sources]
    if any(Path(task[3]).exists() for task in tasks):p.error('Output UFO already exists; choose a fresh candidate directory')
    rows=[]
    with ProcessPoolExecutor(max_workers=max(1,a.workers)) as pool:
        futures=[pool.submit(revise_face,task) for task in tasks]
        for future in as_completed(futures):
            row=future.result();rows.append(row);print(json.dumps(row),flush=True)
    a.reports.mkdir(parents=True,exist_ok=True)
    (a.reports/'summary.json').write_text(json.dumps({'version':'1.003','faces':sorted(rows,key=lambda r:r['font'])},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
