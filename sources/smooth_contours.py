# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
"""Bounded refitting of quantized, faceted round font contours.

The accepted 1.001 outlines contain many very short quadratics. Rounding their
one- or two-unit handles independently creates visibly angular round terminals.
This module refits their *existing boundary* with longer cubic Beziers whose
shared endpoints have a common tangent. Genuine corners between long straight
edges remain corners. It does not change advances, anchors, contour count or
contour direction. Call ``smooth_glyph(glyph, upem=1000, italic_angle=-10)`` on
any object exposing ``draw(pen)``; replay the returned RecordingPen yourself.

The error limit is a sampled bidirectional boundary-distance limit, not a
claim of an analytic Hausdorff proof. Curves are flattened to 0.025 UPM units
for the final acceptance check. All rejected contours retain their exact
original drawing operations and have an explicit report entry. The caller
must independently audit the final compiled, integer-quantized TTF outlines.
"""
from __future__ import annotations

import math
import copy
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import RecordingPen


def _z(p):
    return complex(*p)


def _xy(z):
    return (float(z.real), float(z.imag))


def _unit(z):
    return z / abs(z) if abs(z) > 1e-12 else 0j


def _dot(a, b):
    return (a.conjugate() * b).real


def _angle(a, b):
    if not abs(a) or not abs(b):
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, _dot(_unit(a), _unit(b))))))


def _point(s, t):
    # These are the same de Casteljau operations as the generic loop below,
    # expanded to avoid allocating six temporary lists for every Newton step.
    if len(s)==2:
        return s[0]+(s[1]-s[0])*t
    if len(s)==3:
        a=s[0]+(s[1]-s[0])*t
        b=s[1]+(s[2]-s[1])*t
        return a+(b-a)*t
    if len(s)==4:
        a=s[0]+(s[1]-s[0])*t
        b=s[1]+(s[2]-s[1])*t
        c=s[2]+(s[3]-s[2])*t
        d=a+(b-a)*t
        e=b+(c-b)*t
        return d+(e-d)*t
    row = list(s)
    while len(row) > 1:
        row = [a + (b - a) * t for a, b in zip(row, row[1:])]
    return row[0]


def _derivative(s, t):
    n = len(s) - 1
    return _point(tuple(n * (b-a) for a, b in zip(s, s[1:])), t)


def _tangent(s, end=False):
    origin = s[-1] if end else s[0]
    others = reversed(s[:-1]) if end else s[1:]
    for p in others:
        d = origin-p if end else p-origin
        if abs(d) > 1e-9:
            return d
    return 0j


def _split(s):
    rows = [list(s)]
    while len(rows[-1]) > 1:
        rows.append([(a+b)/2 for a, b in zip(rows[-1], rows[-1][1:])])
    return tuple(r[0] for r in rows), tuple(r[-1] for r in reversed(rows))


def _distance_to_line(p, a, b):
    d = b-a
    if not abs(d):
        return abs(p-a)
    t = max(0., min(1., _dot(p-a, d)/abs(d)**2))
    return abs(p-(a+t*d))


def _flatten(s, tolerance, max_step=4., depth=0):
    chord = abs(s[-1]-s[0])
    flat = max((_distance_to_line(p, s[0], s[-1]) for p in s[1:-1]), default=0.)
    if depth >= 18 or (flat <= tolerance and chord <= max_step):
        return [s[0], s[-1]]
    a, b = _split(s)
    return _flatten(a, tolerance, max_step, depth+1)[:-1] + _flatten(b, tolerance, max_step, depth+1)


def _area(points):
    return sum((a.conjugate()*b).imag for a, b in zip(points, points[1:]+points[:1]))/2


class ContourPen(BasePen):
    """Native closed segments, with explicit quadratic on-curve points."""
    def __init__(self):
        super().__init__(None)
        self.contours = []
        self.current = []
        self.start = None

    def _moveTo(self, p):
        self.start = _z(p)
        self.current = []

    def _lineTo(self, p):
        self.current.append((_z(self._getCurrentPoint()), _z(p)))

    def _qCurveToOne(self, p1, p2):
        self.current.append((_z(self._getCurrentPoint()), _z(p1), _z(p2)))

    def _curveToOne(self, p1, p2, p3):
        self.current.append((_z(self._getCurrentPoint()), _z(p1), _z(p2), _z(p3)))

    def _closePath(self):
        current = _z(self._getCurrentPoint())
        if current != self.start:
            self.current.append((current, self.start))
        self.contours.append(self.current)

    def _endPath(self):
        raise ValueError('Open contour: automatic smoothing requires closed outlines')


def draw_contours(contours, pen):
    """Draw curves while preserving TrueType's exact implied on-curve points.

    Expanding an implied half-unit midpoint to an explicit point, then rounding
    it during TTF compilation, can create a new corner or a micro-loop. Merge
    native quadratic chains before passing them to the destination pen.
    """
    for contour in contours:
        if not contour:
            continue
        if all(len(s)==3 and s[-1]==(s[1]+contour[(i+1)%len(contour)][1])/2
               for i,s in enumerate(contour)):
            pen.qCurveTo(*[_xy(s[1]) for s in contour],None)
            pen.closePath()
            continue
        for start,s in enumerate(contour):
            previous=contour[start-1]
            if not(len(s)==len(previous)==3 and s[0]==(s[1]+previous[1])/2):
                break
        contour=contour[start:]+contour[:start]
        pen.moveTo(_xy(contour[0][0]))
        i=0
        while i<len(contour):
            s=contour[i]
            if len(s)==3:
                controls=[s[1]];end=s[-1];j=i+1
                while j<len(contour) and len(contour[j])==3 and end==(controls[-1]+contour[j][1])/2:
                    controls.append(contour[j][1]);end=contour[j][-1];j+=1
                pen.qCurveTo(*[_xy(p) for p in controls],_xy(end));i=j
            else:
                getattr(pen,'lineTo' if len(s)==2 else 'curveTo')(*[_xy(p) for p in s[1:]])
                i+=1
        pen.closePath()


def audit_contours(contours, upem=1000):
    """Unfiltered measurements; native rounding noise is never hidden."""
    scale = upem/1000
    findings = []
    for ci, contour in enumerate(contours):
        for i, a in enumerate(contour):
            b = contour[(i+1) % len(contour)]
            va, vb = _tangent(a, True), _tangent(b)
            angle = _angle(va, vb)
            length_a = sum(abs(y-x) for x,y in zip(a,a[1:]))
            if not length_a:
                findings.append(dict(contour=ci, segment=i, kind='zero_length', point=_xy(a[-1])))
            if angle >= 3:
                findings.append(dict(contour=ci, segment=i,
                    kind='straight_corner' if len(a) == len(b) == 2 else 'tangent_break',
                    point=_xy(a[-1]), angle_degrees=round(angle, 4),
                    handle_lengths=[round(abs(va),4),round(abs(vb),4)]))
            if len(a) == 2 and length_a < 12*scale and len(contour) > 2:
                before = contour[i-1]
                if len(before) > 2 and len(b) > 2:
                    findings.append(dict(contour=ci, segment=i, kind='short_line_between_curves',
                        point=_xy(a[-1]), length=round(length_a,4)))
    return findings


def _polyline(contour, tolerance=.05, step=3.):
    points = []
    knots = []
    for s in contour:
        knots.append(len(points))
        points.extend(_flatten(s, tolerance, step)[:-1])
    # Quantized paths occasionally contain exactly repeated coordinates.
    return points, knots


def _chord_parameters(points):
    distances = [0.]
    for a,b in zip(points, points[1:]):
        distances.append(distances[-1]+abs(b-a))
    return [d/distances[-1] for d in distances] if distances[-1] else [0.]*len(points)


def _fit(points, params, left, right):
    a00=a01=a11=b0=b1=0.
    p0,p3=points[0],points[-1]
    for p,t in zip(points,params):
        u=1-t; b_0=u*u*u; b_1=3*u*u*t; b_2=3*u*t*t; b_3=t*t*t
        a,b=left*b_1,right*b_2
        delta=p-(p0*(b_0+b_1)+p3*(b_2+b_3))
        a00+=_dot(a,a);a01+=_dot(a,b);a11+=_dot(b,b)
        b0+=_dot(a,delta);b1+=_dot(b,delta)
    det=a00*a11-a01*a01
    alpha=(b0*a11-b1*a01)/det if abs(det)>1e-12 else -1
    beta=(a00*b1-a01*b0)/det if abs(det)>1e-12 else -1
    chord=abs(p3-p0)
    if min(alpha,beta)<chord*1e-5 or max(alpha,beta)>max(chord*3,1.):
        alpha=beta=chord/3
    return (p0,p0+left*alpha,p3+right*beta,p3)


def _reparameterize(points, params, curve):
    derivative=tuple(3*(b-a) for a,b in zip(curve,curve[1:]))
    second=tuple(2*(b-a) for a,b in zip(derivative,derivative[1:]))
    result=[0.]
    for p,t in zip(points[1:-1],params[1:-1]):
        d=_point(curve,t)-p; d1=_point(derivative,t); d2=_point(second,t)
        divisor=abs(d1)**2+_dot(d,d2)
        value=t-_dot(d,d1)/divisor if abs(divisor)>1e-12 else t
        result.append(max(0.,min(1.,value)))
    result.append(1.)
    return result if all(a<=b for a,b in zip(result,result[1:])) else params


def _fit_recursive(points, tangents, tolerance, depth=0):
    """Least-squares cubic fits, splitting with a shared precomputed tangent."""
    if len(points)==2:
        distance=abs(points[-1]-points[0])/3
        return [(points[0],points[0]+tangents[0]*distance,
                 points[-1]-tangents[-1]*distance,points[-1])]
    params=_chord_parameters(points)
    best=None
    for _ in range(6):
        curve=_fit(points,params,tangents[0],-tangents[-1])
        errors=[abs(_point(curve,t)-p) for p,t in zip(points,params)]
        maximum=max(errors)
        if best is None or maximum<best[0]:
            best=(maximum,curve,errors)
        if maximum <= tolerance:
            return [curve]
        params=_reparameterize(points,params,curve)
    if depth>=18:
        return [best[1]]
    split=max(range(1,len(points)-1),key=lambda i:best[2][i])
    return (_fit_recursive(points[:split+1],tangents[:split+1],tolerance,depth+1)+
            _fit_recursive(points[split:],tangents[split:],tolerance,depth+1))


def _point_at(points, cumulative, distance):
    length=cumulative[-1]
    distance=distance % length
    index=min(bisect_right(cumulative,distance)-1,len(points)-1)
    a,b=points[index],points[(index+1)%len(points)]
    span=cumulative[index+1]-cumulative[index]
    return a+(b-a)*((distance-cumulative[index])/span) if span else a


def _shared_tangents(points, radius):
    cumulative=[0.]
    for a,b in zip(points,points[1:]+points[:1]):
        cumulative.append(cumulative[-1]+abs(b-a))
    result=[]
    for distance in cumulative[:-1]:
        # A symmetric arc-length secant removes one-unit handle jitter without
        # preferentially tilting the tangent toward longer native segments.
        before=_point_at(points,cumulative,distance-radius)
        after=_point_at(points,cumulative,distance+radius)
        result.append(_unit(after-before))
    return result


class _Grid:
    def __init__(self, points, cell):
        self.cell=cell
        self.lines=list(zip(points,points[1:]+points[:1]))
        self.prepared=[(a,b-a,abs(b-a)**2) for a,b in self.lines]
        self.buckets={}
        for i,(a,b) in enumerate(self.lines):
            x0,x1=sorted((math.floor(a.real/cell),math.floor(b.real/cell)))
            y0,y1=sorted((math.floor(a.imag/cell),math.floor(b.imag/cell)))
            for x in range(x0,x1+1):
                for y in range(y0,y1+1):
                    self.buckets.setdefault((x,y),[]).append(i)

    def distance(self,p):
        x,y=math.floor(p.real/self.cell),math.floor(p.imag/self.cell)
        ids=set()
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                ids.update(self.buckets.get((x+dx,y+dy),()))
        best=float('inf')
        for i in ids:
            a,d,square=self.prepared[i]
            if not square:
                distance=abs(p-a)
            else:
                t=max(0.,min(1.,_dot(p-a,d)/square))
                distance=abs(p-(a+t*d))
            if distance<best:best=distance
        return best


def boundary_error(original,candidate,scale=1.):
    """Sampled bidirectional distance with at most 0.025-unit flatten error."""
    a,_=_polyline(original,.025*scale,2*scale)
    b,_=_polyline(candidate,.025*scale,2*scale)
    ga,gb=_Grid(a,4*scale),_Grid(b,4*scale)
    return max(max((gb.distance(p) for p in a),default=0.),
               max((ga.distance(p) for p in b),default=0.))


@dataclass(frozen=True)
class SmoothingOptions:
    maximum_error: float=1.5
    fit_error: float=1.3
    tangent_radius: float=6.
    corner_angle: float=55.
    minimum_corner_edge: float=12.


@lru_cache(maxsize=24000)
def _smooth_canonical(original, options, upem):
    original=list(original)
    scale=upem/1000
    findings=audit_contours([original],upem)
    report={'before_segments':len(original),'before_findings':findings,
            'changed':False,'reason':'already_smooth'}
    if not findings:
        return original,report
    if all(len(s)==2 for s in original) and not any(f['kind']=='zero_length' for f in findings):
        report['reason']='straight_polygon_preserved'
        return original,report
    points,knots=_polyline(original,.05*scale,3*scale)
    if len(points)<4 or abs(_area(points))<16*scale**2:
        report['reason']='tiny_contour_preserved'
        return original,report
    tangents=_shared_tangents(points,options.tangent_radius*scale)
    corners={}
    line_spans={}
    for i,segment in enumerate(original):
        following=original[(i+1)%len(original)]
        incoming,outgoing=_tangent(segment,True),_tangent(following)
        # Preserve intentional straight corners and larger sharp curve joins.
        # Tiny noisy handles never turn an intended round cap into a corner.
        angle=_angle(incoming,outgoing)
        incoming_length=sum(abs(b-a) for a,b in zip(segment,segment[1:]))
        outgoing_length=sum(abs(b-a) for a,b in zip(following,following[1:]))
        if angle>=options.corner_angle and min(incoming_length,outgoing_length)>=options.minimum_corner_edge*scale:
            corners[knots[(i+1)%len(original)]]=(_unit(incoming),_unit(outgoing))
    sharp_corners=len(corners)
    # Long straight stems and diagonals are exact design geometry. Fit only
    # their neighbouring curves and force those curves to join tangentially.
    for i,segment in enumerate(original):
        if len(segment)==2 and abs(segment[-1]-segment[0])>=30*scale:
            start,end=knots[i],knots[(i+1)%len(original)]
            direction=_unit(segment[-1]-segment[0])
            line_spans[(start,end)]=segment
            for boundary in (start,end):
                if boundary not in corners:
                    corners[boundary]=(direction,direction)
    # Two well-separated artificial breaks stabilize fitting closed smooth
    # curves. Their common tangents still agree on both sides.
    breaks=sorted(corners) if corners else [0,len(points)//2]
    if len(breaks)==1:
        breaks=sorted([breaks[0],(breaks[0]+len(points)//2)%len(points)])
    result=[]
    for i,start in enumerate(breaks):
        end=breaks[(i+1)%len(breaks)]
        if (start,end) in line_spans:
            result.append(line_spans[(start,end)])
            continue
        indices=list(range(start,end+1)) if end>start else list(range(start,len(points)))+list(range(end+1))
        p=[points[j] for j in indices]
        t=[tangents[j] for j in indices]
        if start in corners:t[0]=corners[start][1]
        if end in corners:t[-1]=corners[end][0]
        result.extend(_fit_recursive(p,t,options.fit_error*scale))
    error=boundary_error(original,result,scale)
    newpoints,_=_polyline(result,.05*scale,3*scale)
    report.update(after_segments=len(result),boundary_error=round(error,6),
        retained_corners=sharp_corners,protected_straight_edges=len(line_spans),
        after_findings=audit_contours([result],upem))
    if error>options.maximum_error*scale:
        report['reason']='boundary_limit_rejected'
        return original,report
    if _area(points)*_area(newpoints)<=0:
        report['reason']='orientation_rejected'
        return original,report
    report.update(changed=True,reason='bounded_shared_tangent_refit')
    return result,report


def smooth_contour(original, options=None, upem=1000):
    """Translation-normalized cache shares repairs among accented base forms."""
    options=options or SmoothingOptions()
    if not original:
        return original,{'before_segments':0,'before_findings':[],
            'changed':False,'reason':'empty_contour'}
    origin=original[0][0]
    canonical=tuple(tuple(complex(round((p-origin).real,8),round((p-origin).imag,8))
                          for p in s) for s in original)
    candidate,cached_report=_smooth_canonical(canonical,options,upem)
    report=copy.deepcopy(cached_report)
    for key in ('before_findings','after_findings'):
        for finding in report.get(key,[]):
            if 'point' in finding:
                finding['point']=_xy(_z(finding['point'])+origin)
    if not report['changed']:
        return original,report
    return [tuple(p+origin for p in s) for s in candidate],report


def cache_info():
    """Expose cache performance for reproducible whole-family reports."""
    return _smooth_canonical.cache_info()._asdict()


_PRIMITIVE_VECTORS=tuple(complex(x,y) for x in range(-12,13) for y in range(-12,13)
    if (x or y) and math.gcd(abs(x),abs(y))==1)


def _integer_g1_controls(p,a,b,maximum_shift,locked_a=False,locked_b=False):
    best=None
    direction=_unit(b-a)
    for v in _PRIMITIVE_VECTORS:
        if _dot(_unit(v),direction)<.85:
            continue
        square=abs(v)**2
        ka=max(1,round(_dot(p-a,v)/square))
        kb=max(1,round(_dot(b-p,v)/square))
        aa,bb=p-ka*v,p+kb*v
        da,db=abs(aa-a),abs(bb-b)
        if da>maximum_shift or db>maximum_shift or (locked_a and da) or (locked_b and db):
            continue
        score=da*da+db*db
        if best is None or score<best[0]:
            best=(score,aa,bb,da,db)
    return best


def repair_quantized_g1(glyph, glyf_table=None, maximum_shift=3., minimum_angle=1.0,
                        maximum_control_shift=3.):
    """Restore exact G1 joins after final TrueType integer-coordinate rounding.

    A TrueType implied on-curve point is *exactly* the midpoint of its two
    neighbouring off-curve controls. Replacing an explicit rounded join by that
    implied point restores collinearity without moving either control. Every
    changed endpoint has a measured shift <= maximum_shift; the displacement
    of either adjacent quadratic is bounded by that same shift because its
    Bernstein coefficient lies in [0,1]. Where unequal handle lengths prevent
    that replacement, nearby integer controls on a common primitive lattice
    vector give exact collinearity with the original on-curve point. Their
    displacement is separately limited by maximum_control_shift. Controls are
    locked once repaired so another join cannot silently break the constraint.
    Intentional substantial corners are retained. This helper changes only
    unhinted simple glyph outlines.

    This local mathematical error bound does not prove absence of collisions
    with another contour. Run the independent crossing/winding audit afterwards.
    """
    from array import array
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
    if glyph.isComposite() or glyph.numberOfContours<=0:
        return {'changed':False,'joins':[],'reason':'no_simple_outline'}
    if getattr(glyph,'program',None) and glyph.program.getBytecode():
        raise ValueError('Cannot reindex point-hinted glyphs during G1 repair')
    contours=[];events=[];start=0
    for ci,end in enumerate(glyph.endPtsOfContours):
        coordinates=[complex(*glyph.coordinates[i]) for i in range(start,end+1)]
        flags=[int(glyph.flags[i]) for i in range(start,end+1)]
        remove=set()
        locked=set()
        if len(coordinates)>3:
            candidates=[]
            for i,p in enumerate(coordinates):
                before=(i-1)%len(coordinates);after=(i+1)%len(coordinates)
                if not flags[i]&1 or flags[before]&1 or flags[after]&1:
                    continue
                a,b=coordinates[before],coordinates[after]
                incoming,outgoing=p-a,b-p
                # Rounding can collapse a handle onto the on-curve point.
                # The limiting tangent then comes from the preceding/following
                # noncoincident control, just as BasePen's curve expansion does.
                if not abs(incoming):
                    incoming=p-coordinates[(i-2)%len(coordinates)]
                if not abs(outgoing):
                    outgoing=coordinates[(i+2)%len(coordinates)]-p
                angle=_angle(incoming,outgoing)
                if angle<.001 and abs(p-a)>0 and abs(b-p)>0:
                    locked.update((before,after))
                candidates.append((angle,i))
            # Fix the most visible corners first. Low-angle joins cannot steal
            # a control required by a higher-angle repair.
            for _,i in sorted(candidates,reverse=True):
                p=coordinates[i]
                before=(i-1)%len(coordinates);after=(i+1)%len(coordinates)
                a,b=coordinates[before],coordinates[after]
                incoming=p-a or p-coordinates[(i-2)%len(coordinates)]
                outgoing=b-p or coordinates[(i+2)%len(coordinates)]-p
                angle=_angle(incoming,outgoing)
                midpoint=(a+b)/2
                shift=abs(midpoint-p)
                if angle<minimum_angle or abs(b-a)<1e-7:
                    continue
                if angle>=55 and min(abs(incoming),abs(outgoing))>=12:
                    continue
                if shift<=maximum_shift:
                    remove.add(i)
                    locked.update((before,after))
                    events.append({'kind':'implicit_midpoint','contour':ci,
                        'original_point_index':start+i,
                        'before':_xy(p),'after_implicit_midpoint':_xy(midpoint),
                        'endpoint_shift':round(shift,6),'angle_before':round(angle,6),
                        'angle_after':0.0})
                else:
                    fit=_integer_g1_controls(p,a,b,maximum_control_shift,
                        before in locked,after in locked)
                    if fit is not None:
                        _,aa,bb,da,db=fit
                        coordinates[before],coordinates[after]=aa,bb
                        locked.update((before,after))
                        events.append({'kind':'integer_control_snap','contour':ci,
                            'original_point_index':start+i,'before':_xy(p),'after':_xy(p),
                            'controls_before':[_xy(a),_xy(b)],'controls_after':[_xy(aa),_xy(bb)],
                            'control_shifts':[round(da,6),round(db,6)],
                            'endpoint_shift':0.,'angle_before':round(angle,6),'angle_after':0.})
            # At an exact straight edge the integer lattice may contain no
            # nearby point lying exactly on its non-axis-aligned tangent.
            # Select the closest angular match within the same bounded control
            # displacement; report the remaining measured angle explicitly.
            for i,p in enumerate(coordinates):
                if i in remove or not flags[i]&1:
                    continue
                before=(i-1)%len(coordinates);after=(i+1)%len(coordinates)
                if flags[before]&1 and not flags[after]&1:
                    control=after;direction=p-coordinates[before];sign=1
                elif not flags[before]&1 and flags[after]&1:
                    control=before;direction=coordinates[after]-p;sign=-1
                else:
                    continue
                if control in locked or not abs(direction):
                    continue
                original_control=coordinates[control]
                handle=(original_control-p)*sign
                oldangle=_angle(direction,handle)
                if oldangle<minimum_angle or (oldangle>=55 and abs(handle)>=12):
                    continue
                best=None
                bound=math.ceil(maximum_control_shift)
                for dx in range(-bound,bound+1):
                    for dy in range(-bound,bound+1):
                        shift=complex(dx,dy)
                        if abs(shift)>maximum_control_shift:
                            continue
                        candidate=original_control+shift
                        v=(candidate-p)*sign
                        if not abs(v) or _dot(v,direction)<=0:
                            continue
                        angle=_angle(v,direction)
                        score=angle+abs(shift)*.01
                        if best is None or score<best[0]:
                            best=(score,candidate,angle,abs(shift))
                if best and best[2]<oldangle-.1:
                    _,candidate,newangle,shift=best
                    coordinates[control]=candidate;locked.add(control)
                    events.append({'kind':'line_curve_control_alignment','contour':ci,
                        'original_point_index':start+i,'before':_xy(p),'after':_xy(p),
                        'controls_before':[_xy(original_control)],'controls_after':[_xy(candidate)],
                        'control_shifts':[round(shift,6)],'endpoint_shift':0.,
                        'angle_before':round(oldangle,6),'angle_after':round(newangle,6)})
        contours.append([(p,flag) for i,(p,flag) in enumerate(zip(coordinates,flags)) if i not in remove])
        start=end+1
    if events:
        flattened=[p for contour in contours for p in contour]
        glyph.coordinates=GlyphCoordinates([_xy(p) for p,flag in flattened])
        glyph.flags=array('B',[flag for p,flag in flattened])
        total=0;glyph.endPtsOfContours=[]
        for contour in contours:
            total+=len(contour);glyph.endPtsOfContours.append(total-1)
        glyph.recalcBounds(glyf_table)
    return {'changed':bool(events),'joins':events,
        'maximum_endpoint_shift':max((e['endpoint_shift'] for e in events),default=0.),
        'maximum_control_shift':max((max(e.get('control_shifts',[0.])) for e in events),default=0.),
        'reason':'exact_implied_midpoint_G1' if events else 'no_eligible_join'}


def smooth_glyph(glyph, upem=1000, italic_angle=0, options=None):
    """Return (RecordingPen, report); caller controls applying the result.

    Italic designs are unsheared for measurements and curve fitting, then
    restored. Error is checked again in final italic coordinates. This avoids
    treating a circular terminal sheared into an ellipse as an asymmetry.
    """
    options=options or SmoothingOptions()
    pen=ContourPen();glyph.draw(pen)
    shear=math.tan(math.radians(-italic_angle))
    def transform(contour, amount):
        return [tuple(complex(p.real+amount*p.imag,p.imag) for p in s) for s in contour]
    output=[];reports=[]
    for ci,original in enumerate(pen.contours):
        unskewed=transform(original,-shear) if shear else original
        candidate,report=smooth_contour(unskewed,options,upem)
        if shear and report['changed']:
            candidate=transform(candidate,shear)
            final_error=boundary_error(original,candidate,upem/1000)
            report['final_coordinate_error']=round(final_error,6)
            if final_error>options.maximum_error*upem/1000:
                candidate=original
                report.update(changed=False,reason='italic_boundary_limit_rejected')
        elif shear:
            candidate=original
        report['contour']=ci
        output.append(candidate);reports.append(report)
    recording=RecordingPen();draw_contours(output,recording)
    return recording,{'changed':any(r['changed'] for r in reports),
        'contour_count':len(output),'contours':reports,
        'reasons':dict(Counter(r['reason'] for r in reports))}
