# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Bounded local rounding and micro-loop cleanup of the compiled candidate.

Run after the global fit and after integer quantization. The independent final
audit is still required. This pass preserves intentional line/line corners,
fillets remaining curved joins, and accepts only candidates with no crossings,
the same substantial contour topology, and <=4-unit sampled boundary movement.
Only a verified crossing region may move farther (<=12 units within a 16-unit
radius), allowing a thin self-intersecting spike to be removed completely.
No advance, anchor, name, feature, or Unicode metadata is handled here.
"""
from __future__ import annotations

import math
from array import array

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates

from smooth_contours import (ContourPen, draw_contours, _xy, _z, _angle,
    _tangent, _unit, _dot, _point, _polyline, _area, _Grid,
    repair_quantized_g1,smooth_glyph,SmoothingOptions)
from audit_visual_quality import crossings


def _cross(a,b):return (a.conjugate()*b).imag


def _split(s,t):
    rows=[list(s)]
    while len(rows[-1])>1:
        rows.append([a+(b-a)*t for a,b in zip(rows[-1],rows[-1][1:])])
    return tuple(r[0] for r in rows),tuple(r[-1] for r in reversed(rows))


def _trim(s,t0,t1):
    left=_split(s,t1)[0] if t1<1 else s
    return _split(left,t0/t1)[1] if t0>0 else left


def _arc(s):
    table=[0.];last=s[0]
    for i in range(1,33):
        p=_point(s,i/32);table.append(table[-1]+abs(p-last));last=p
    return table


def _parameter(table,d):
    d=max(0.,min(table[-1],d))
    for i in range(1,len(table)):
        if table[i]>=d:
            span=table[i]-table[i-1]
            return (i-1+(d-table[i-1])/span)/32 if span else (i-1)/32
    return 1.


def _bridge(a,b,angle):
    p,q=a[-1],b[0];va,vb=_unit(_tangent(a,True)),_unit(_tangent(b))
    determinant=_cross(va,vb);delta=q-p
    if abs(determinant)>1e-8:
        before=_cross(delta,vb)/determinant;after=_cross(va,delta)/determinant
    else:before=after=-1
    alpha=4/3*math.cos(angle/2)/(1+math.cos(angle/2))
    if 0<before<abs(delta)*5 and 0<after<abs(delta)*5:
        h0,h1=alpha*before,alpha*after
    else:h0=h1=abs(delta)/3
    return p,p+h0*va,q-h1*vb,q


def _join_flags(contours,minimum_angle=15.):
    result=[]
    for ci,c in enumerate(contours):
        for i,a in enumerate(c):
            b=c[(i+1)%len(c)]
            if len(a)==len(b)==2:continue
            angle=_angle(_tangent(a,True),_tangent(b))
            if angle>=minimum_angle:
                result.append({'contour':ci,'segment':i,'point':_xy(a[-1]),
                    'angle':round(angle,6)})
    return result


def _flattened(contours,tolerance=.1):
    return [[_xy(p) for p in _polyline(c,tolerance,3)[0]+[c[0][0]]]
            for c in contours if c]


def _crossings(contours,tolerance=.1):
    return crossings(_flattened(contours,tolerance))


def _topology(contours):
    areas=[_area(_polyline(c,.05,3)[0]) for c in contours]
    return {'contourCount':len(contours),'substantialPositive':sum(a>4 for a in areas),
            'substantialNegative':sum(a<-4 for a in areas),
            'tinyContours':sum(abs(a)<=4 for a in areas)}


def _boundary_distance(before,after,crossing_regions=()):
    a=[_polyline(c,.025,2)[0] for c in before if c]
    b=[_polyline(c,.025,2)[0] for c in after if c]
    if not a and not b:return {'maximum':0.,'outsideCrossingRegions':0.}
    if not a or not b:return {'maximum':float('inf'),'outsideCrossingRegions':float('inf')}
    cell=24 if crossing_regions else 5
    ga,gb=[_Grid(c,cell) for c in a],[_Grid(c,cell) for c in b]
    maximum=outside=0.;worst=None
    for contours,grids in ((a,gb),(b,ga)):
        for c in contours:
            for p in c:
                distance=min(g.distance(p) for g in grids)
                if distance>maximum:maximum=distance;worst=_xy(p)
                if not any(abs(p-region)<=16 for region in crossing_regions):outside=max(outside,distance)
    return {'maximum':maximum,'outsideCrossingRegions':outside,'worstPoint':worst}


def _fillet(contours,distance,minimum_angle=15.):
    result=[];events=[]
    for ci,original in enumerate(contours):
        if not original:result.append(original);continue
        tables=[_arc(s) for s in original]
        begins=[0.]*len(original);ends=[1.]*len(original);angles={}
        for i,a in enumerate(original):
            j=(i+1)%len(original);b=original[j]
            if len(a)==len(b)==2:continue
            angle=math.radians(_angle(_tangent(a,True),_tangent(b)))
            if math.degrees(angle)<minimum_angle:continue
            da=min(distance,tables[i][-1]*.34);db=min(distance,tables[j][-1]*.34)
            if min(da,db)<.05:continue
            ends[i]=_parameter(tables[i],tables[i][-1]-da)
            begins[j]=_parameter(tables[j],db)
            angles[i]=angle
            events.append({'contour':ci,'point':_xy(a[-1]),
                'angleBefore':round(math.degrees(angle),6),'trimDistances':[da,db]})
        trimmed=[_trim(s,a,b) for s,a,b in zip(original,begins,ends)]
        new=[]
        for i,s in enumerate(trimmed):
            new.append(s)
            if i in angles:new.append(_bridge(s,trimmed[(i+1)%len(trimmed)],angles[i]))
        result.append(new)
    return result,events


def _simplify(contours):
    import pathops
    from build_family import CubicPen
    p=pathops.Path();draw_contours(contours,CubicPen(p.getPen()))
    p=pathops.simplify(p,clockwise=True)
    pen=ContourPen();p.draw(pen)
    # Tiny loops generated by a crossing are quantization debris, not marks.
    return [c for c in pen.contours if abs(_area(_polyline(c,.025,1)[0]))>4]


def _draw_preserving_implied(contours,pen):
    """Compatibility wrapper around the one shared native-quadratic drawer."""
    draw_contours(contours,pen)


def _compile(contours,g1,quad_error=.3):
    pen=TTGlyphPen(None)
    _draw_preserving_implied(contours,Cu2QuPen(pen,max_err=quad_error,all_quadratic=True))
    glyph=pen.glyph()
    repairs=repair_quantized_g1(glyph) if g1 else {'changed':False,'joins':[]}
    # A constant segment has no tangent and must not hide the actual join
    # between its nonconstant neighbours from the acceptance checks below.
    remove_zero_length_segments(glyph)
    contours_pen=ContourPen();glyph.draw(contours_pen,None)
    return glyph,contours_pen.contours,repairs


def remove_zero_length_segments(glyph,glyf_table=None):
    """Remove constant segments from an unhinted native TTGlyph, in place.

    No fitting, rounding, tangent repair, or coordinate movement occurs. Clean
    contours retain their original native coordinates and flags byte for byte.
    Dirty contours are reconstructed with implied points preserved, and their
    expanded nonconstant segments must match exactly before accepting a change.
    Retracing but nonconstant curves are deliberately not treated as zero.
    """
    report={'changed':False,'removedSegments':[],'geometryExact':True}
    if glyph.numberOfContours<=0:
        report['reason']='empty_or_composite';return report
    if getattr(glyph,'program',None) and glyph.program.getBytecode():
        raise ValueError('Removing native points from a hinted glyph is unsafe')
    pen=ContourPen();glyph.draw(pen,glyf_table);contours=pen.contours
    coordinates=GlyphCoordinates();flags=array('B');ends=[];start=0
    for ci,(contour,end) in enumerate(zip(contours,glyph.endPtsOfContours)):
        cleaned=[s for s in contour if any(p!=s[0] for p in s[1:])]
        removed=[{'contour':ci,'segment':i,'point':_xy(s[0])}
                 for i,s in enumerate(contour) if all(p==s[0] for p in s[1:])]
        if not removed or not cleaned:
            coordinates.extend(glyph.coordinates[start:end+1]);flags.extend(glyph.flags[start:end+1])
        else:
            native_pen=TTGlyphPen(None);draw_contours([cleaned],native_pen)
            native=native_pen.glyph();check=ContourPen();native.draw(check,None)
            observed=check.contours[0] if len(check.contours)==1 else []
            exact=(len(observed)==len(cleaned) and any(
                observed==cleaned[offset:]+cleaned[:offset] for offset in range(len(cleaned))))
            if not exact or any(x!=int(x) or y!=int(y) for x,y in native.coordinates):
                raise ValueError('Zero-segment cleanup did not preserve exact native geometry')
            # The overlap flag is metadata, independent of the on-curve bit.
            if any(f&0x40 for f in glyph.flags[start:end+1]):native.flags[0]|=0x40
            coordinates.extend(native.coordinates);flags.extend(native.flags)
            report['removedSegments'].extend(removed)
        ends.append(len(coordinates)-1);start=end+1
    if report['removedSegments']:
        before=len(glyph.coordinates)
        glyph.coordinates=coordinates;glyph.flags=flags;glyph.endPtsOfContours=ends
        report.update(changed=True,removedPoints=before-len(coordinates),
                      reason='exact_constant_segment_removal')
    else:report['reason']='no_constant_segments'
    return report


def merge_short_curve_facets(drawable,maximum_length=6.,maximum_deviation=1.5):
    """Absorb an almost-tangent short line into one neighbouring quadratic.

    This does not refit a contour. Exactly one existing quadratic start or end
    changes per accepted facet. Its neighbouring controls remain untouched.
    The local tangent mismatch must shrink by at least half, the whole sampled
    boundary stays within the stated bound, and topology/crossing checks apply.
    Existing genuine corners or non-tangent short lines are not candidates.
    """
    native_pen=TTGlyphPen(None);drawable.draw(native_pen);native=native_pen.glyph()
    cleanup=remove_zero_length_segments(native)
    pen=ContourPen();native.draw(pen,None);original=pen.contours;current=original
    report={'changed':cleanup['changed'],'nativeCleanup':cleanup,'merges':[]}
    topology=_topology(original)
    for iteration in range(32):
        accepted=None
        for ci,c in enumerate(current):
            for i,s in enumerate(c):
                if len(s)!=2 or not 0<abs(s[-1]-s[0])<=maximum_length:continue
                a,b=c[i-1],c[(i+1)%len(c)]
                if len(a)!=3 or len(b)!=3:continue
                angles=(_angle(_tangent(a,True),_tangent(s)),
                        _angle(_tangent(s,True),_tangent(b)))
                if min(angles)>3 or not 3<max(angles)<=25:continue
                for side in ('next','previous'):
                    new=c[:i]+c[i+1:]
                    if side=='next':new[i%len(new)]=(s[0],*b[1:])
                    else:new[(i-1)%len(new)]=(*a[:-1],s[-1])
                    na,nb=new[(i-1)%len(new)],new[i%len(new)]
                    new_angle=_angle(_tangent(na,True),_tangent(nb))
                    if new_angle>max(angles)/2:continue
                    work=current[:ci]+[new]+current[ci+1:]
                    candidate,actual,_=_compile(work,False)
                    if _topology(actual)!=topology:continue
                    if len(_join_flags(actual,10))>len(_join_flags(current,10)):continue
                    crossing_check={str(t):len(_crossings(actual,t)) for t in (.25,.1,.05,.01)}
                    if any(crossing_check.values()):continue
                    bound=_boundary_distance(original,actual)
                    if bound['maximum']>maximum_deviation:continue
                    event={'contour':ci,'point':_xy(s[0]),'lineEnd':_xy(s[-1]),
                           'length':abs(s[-1]-s[0]),'mergedInto':side,
                           'beforeAngles':angles,'afterAngle':new_angle,
                           'boundaryMovement':bound['maximum'],'crossingVerification':crossing_check}
                    accepted=candidate,actual,event;break
                if accepted:break
            if accepted:break
        if not accepted:break
        native,current,event=accepted;report['merges'].append(event);report['changed']=True
    report['reason']='bounded_short_facet_merge' if report['merges'] else 'no_safe_facet_merge'
    return native,report


def finalize_glyph(drawable,maximum_deviation=4.,minimum_angle=15.):
    """Return (integer TTGlyph, report); caller writes its native points to UFO."""
    original_native_pen=TTGlyphPen(None);drawable.draw(original_native_pen)
    original_native=original_native_pen.glyph()
    native_cleanup=remove_zero_length_segments(original_native)
    original_pen=ContourPen();original_native.draw(original_pen,None);original=original_pen.contours
    before_crossings=_crossings(original)
    before_joins=_join_flags(original,minimum_angle)
    report={'changed':native_cleanup['changed'],'nativeCleanup':native_cleanup,
            'beforeCrossings':before_crossings,'beforeJoins':before_joins,
            'beforeTopology':_topology(original),'attempts':[]}
    if not before_crossings and not before_joins:
        report['reason']='no_finalization_needed'
        return original_native,report
    cleaned=_simplify(original) if before_crossings else original
    before_topology=report['beforeTopology']
    best=None
    for trim in (8.,6.,4.,2.):
        rounded,fillets=_fillet(cleaned,trim,minimum_angle)
        for use_g1 in (True,False):
            glyph,candidate,g1=_compile(rounded,use_g1)
            applied_fillets=list(fillets)
            # Integer rounding can expose a new collapsed-handle corner after
            # removing a sub-unit loop. Round that actual delivered corner,
            # while retaining the original whole-boundary acceptance guard.
            for local_trim in (4.,2.):
                remaining_count=len(_join_flags(candidate,minimum_angle))
                if not remaining_count:break
                local,local_events=_fillet(candidate,local_trim,minimum_angle)
                alternative,alternative_contours,alternative_g1=_compile(local,use_g1)
                if (not _crossings(alternative_contours) and
                    len(_join_flags(alternative_contours,minimum_angle))<remaining_count):
                    glyph,candidate,g1=alternative,alternative_contours,alternative_g1
                    applied_fillets.extend(local_events)
            microloop_refit=False
            if before_crossings and _join_flags(candidate,minimum_angle):
                class Drawable:
                    def draw(self,pen):_draw_preserving_implied(candidate,pen)
                rec,_=smooth_glyph(Drawable(),options=SmoothingOptions(
                    maximum_error=1.5,fit_error=.6,tangent_radius=6.))
                refit_pen=ContourPen();rec.replay(refit_pen)
                alternative,alternative_contours,alternative_g1=_compile(refit_pen.contours,use_g1)
                if (not _crossings(alternative_contours) and
                    len(_join_flags(alternative_contours,minimum_angle))<len(_join_flags(candidate,minimum_angle))):
                    glyph,candidate,g1=alternative,alternative_contours,alternative_g1
                    microloop_refit=True
            after_crossings=_crossings(candidate)
            after_topology=_topology(candidate)
            remaining=_join_flags(candidate,minimum_angle)
            topology_ok=all(before_topology[k]==after_topology[k]
                for k in ('substantialPositive','substantialNegative'))
            regions=[complex(*x['point']) for x in before_crossings]
            distances=_boundary_distance(original,candidate,regions) if not after_crossings and topology_ok else None
            error=distances['maximum'] if distances else None
            attempt={'trim':trim,'quantizedG1':use_g1,'crossings':len(after_crossings),
                'remainingJoins':len(remaining),'boundaryMovement':error,'distances':distances,
                'microloopRefit':microloop_refit,'topologyOK':topology_ok}
            report['attempts'].append(attempt)
            if error is None or distances['outsideCrossingRegions']>maximum_deviation or error>(12. if regions else maximum_deviation):
                continue
            score=(len(remaining),error)
            if best is None or score<best[0]:
                best=(score,glyph,candidate,g1,applied_fillets,remaining,after_topology,trim)
            if not remaining:break
        if best is not None and not best[5]:break
    if best is None:
        report['reason']='bounded_topology_guard_rejected'
        report['remainingCrossings']=before_crossings
        report['remainingJoins']=before_joins
        return original_native,report
    _,glyph,candidate,g1,fillets,remaining,after_topology,trim=best
    report.update(changed=True,reason='bounded_final_contour_repair',trim=trim,
        fillets=fillets,g1Repairs=g1,boundaryMovement=best[0][1],
        remainingCrossings=[],remainingJoins=remaining,afterTopology=after_topology)
    return glyph,report


def retry_glyph(drawable,italic_angle=0.,maximum_deviation=4.,minimum_angle=15.):
    """Search bounded quantization variants only for unresolved body outlines.

    Different curve conversion tolerances put integer control points on
    different lattice locations. A finer approximation can paradoxically have
    a rougher tangent after rounding. Every trial below retains the same strict
    boundary and topology guards; an accepted result must have zero remaining
    measured curved corners and zero crossings at four subdivision tolerances.
    This is a geometry criterion, never a glyph-name exception list.
    """
    native_pen=TTGlyphPen(None);drawable.draw(native_pen);native=native_pen.glyph()
    native_cleanup=remove_zero_length_segments(native)
    pen=ContourPen();native.draw(pen,None);original=pen.contours
    original_crossings=_crossings(original)
    original_joins=_join_flags(original,minimum_angle)
    topology=_topology(original)
    report={'changed':native_cleanup['changed'],'nativeCleanup':native_cleanup,
            'beforeCrossings':original_crossings,'beforeJoins':original_joins,
            'beforeTopology':topology,'attempts':[]}
    if not original_crossings and not original_joins:
        report['reason']='no_retry_needed'
        return native,report
    regions=[complex(*x['point']) for x in original_crossings]
    for fit_error,radius in ((.6,3.),(.6,6.),(.6,10.),(1.3,6.)):
        rec,fit_report=smooth_glyph(drawable,italic_angle=italic_angle,
            options=SmoothingOptions(maximum_error=1.5,fit_error=fit_error,tangent_radius=radius))
        refit_pen=ContourPen();rec.replay(refit_pen)
        for quad_error in (.2,.3,.5,.8,1.):
            for use_g1 in (False,True):
                fitted,fitted_contours,g1=_compile(refit_pen.contours,use_g1,quad_error)
                for trim in (0.,2.,4.,8.):
                    if trim:
                        rounded,fillets=_fillet(fitted_contours,trim,minimum_angle)
                        glyph,candidate,g1=_compile(rounded,use_g1,quad_error)
                    else:
                        glyph,candidate=fitted,fitted_contours;fillets=[]
                    remaining=_join_flags(candidate,minimum_angle)
                    crossed=_crossings(candidate)
                    params={'fitError':fit_error,'tangentRadius':radius,
                            'quadraticError':quad_error,'quantizedG1':use_g1,'trim':trim}
                    trial=dict(params,remainingJoins=len(remaining),crossings=len(crossed))
                    report['attempts'].append(trial)
                    if remaining or crossed:continue
                    candidate_topology=_topology(candidate)
                    topology_ok=all(topology[k]==candidate_topology[k]
                        for k in ('substantialPositive','substantialNegative'))
                    trial['topologyOK']=topology_ok
                    if not topology_ok:continue
                    bound=_boundary_distance(original,candidate,regions)
                    trial['distances']=bound
                    if (bound['outsideCrossingRegions']>maximum_deviation or
                        bound['maximum']>(12. if regions else maximum_deviation)):
                        continue
                    verification={str(t):len(_crossings(candidate,t)) for t in (.25,.1,.05,.01)}
                    trial['crossingVerification']=verification
                    if any(verification.values()):continue
                    report.update(changed=True,reason='bounded_quantization_retry',
                        selectedParameters=params,remainingCrossings=[],remainingJoins=[],
                        afterTopology=candidate_topology,boundaryMovement=bound['maximum'],
                        boundaryDistances=bound,crossingVerification=verification,
                        fillets=fillets,g1Repairs=g1,refit=fit_report)
                    return glyph,report
    report.update(reason='no_safe_retry',remainingCrossings=original_crossings,
                  remainingJoins=original_joins)
    return native,report
