# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
"""Fair genuine tangent breaks after boolean outline construction.

Connected stems are designed without overlapping end caps. This small,
bounded rounding pass then blends the remaining interior intersections;
already tangent-continuous terminals and bowls are left unchanged.
"""
import math
import pathops
from fontTools.pens.basePen import BasePen


class ContourPen(BasePen):
    def __init__(self):
        super().__init__(None); self.contours=[]; self.segments=[]; self.start=None
    def _moveTo(self,p): self.start=p; self.segments=[]
    def _lineTo(self,p): self.segments.append((self._getCurrentPoint(),p))
    def _curveToOne(self,p1,p2,p3): self.segments.append((self._getCurrentPoint(),p1,p2,p3))
    def _closePath(self):
        if self._getCurrentPoint()!=self.start: self._lineTo(self.start)
        self.contours.append(self.segments)
    def _endPath(self): raise ValueError('Font outline contains an open contour')


def mix(a,b,t): return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
def sub(a,b): return (a[0]-b[0],a[1]-b[1])
def cross(a,b): return a[0]*b[1]-a[1]*b[0]
def dot(a,b): return a[0]*b[0]+a[1]*b[1]
def length(a): return math.hypot(*a)


def split(points,t):
    levels=[list(points)]
    while len(levels[-1])>1:
        row=levels[-1]; levels.append([mix(a,b,t) for a,b in zip(row,row[1:])])
    return tuple(row[0] for row in levels),tuple(row[-1] for row in reversed(levels))


def point(points,t):
    row=list(points)
    while len(row)>1: row=[mix(a,b,t) for a,b in zip(row,row[1:])]
    return row[0]


def tangent(points,end=False):
    origin=points[-1] if end else points[0]
    controls=list(reversed(points[:-1])) if end else points[1:]
    for control in controls:
        v=sub(origin,control) if end else sub(control,origin)
        if length(v)>1e-6: return v
    return (0,0)


def trim(points,t0,t1):
    left=split(points,t1)[0] if t1<1 else points
    return split(left,t0/t1)[1] if t0>0 else left


def arc_table(points):
    previous=points[0]; table=[0]
    for i in range(1,25):
        p=point(points,i/24); table.append(table[-1]+length(sub(p,previous))); previous=p
    return table


def parameter(table,distance):
    distance=max(0,min(table[-1],distance))
    for i in range(1,len(table)):
        if table[i]>=distance:
            span=table[i]-table[i-1]
            return (i-1+(distance-table[i-1])/span)/24 if span else (i-1)/24
    return 1


def connector(a,b,angle):
    p0=a[-1]; p3=b[0]; va=tangent(a,True); vb=tangent(b)
    va=(va[0]/length(va),va[1]/length(va)); vb=(vb[0]/length(vb),vb[1]/length(vb))
    determinant=cross(va,vb); delta=sub(p3,p0)
    alpha=(4/3)*math.cos(angle/2)/(1+math.cos(angle/2))
    if abs(determinant)>1e-6:
        before=cross(delta,vb)/determinant; after=cross(va,delta)/determinant
    else: before=after=-1
    if 0<before<length(delta)*5 and 0<after<length(delta)*5:
        h0=alpha*before; h1=alpha*after
    else: h0=h1=length(delta)/3
    return (p0,(p0[0]+h0*va[0],p0[1]+h0*va[1]),(p3[0]-h1*vb[0],p3[1]-h1*vb[1]),p3)


def polish(outline,distance=12,minimum_angle=8):
    pen=ContourPen(); outline.draw(pen); result=pathops.Path(); rounded=0
    for original in pen.contours:
        # Identical consecutive endpoints are never meaningful contours.
        segments=[s for s in original if
                  sum(length(sub(a,b)) for a,b in zip(s,s[1:])) >= .1]
        if not segments: continue
        # Boolean offsets can leave microscopic edges at intersections.
        # Their length limits a fillet to almost zero, leaving a cusp.
        # Absorb sub-0.1-unit edges before fairing the real neighbours.
        segments=[(segments[(i-1)%len(segments)][-1],)+s[1:]
                  for i,s in enumerate(segments)]
        tables=[arc_table(s) for s in segments]; begin=[0.0]*len(segments); end=[1.0]*len(segments); angles={}
        for i,a in enumerate(segments):
            j=(i+1)%len(segments); b=segments[j]; va=tangent(a,True); vb=tangent(b)
            if length(va)==0 or length(vb)==0: continue
            cosine=max(-1,min(1,dot(va,vb)/(length(va)*length(vb))))
            angle=math.acos(cosine)
            if math.degrees(angle)<=minimum_angle: continue
            # Limiting each end to 24% prevents adjacent fillets from
            # swallowing a short segment or reducing a small counter.
            da=min(distance,tables[i][-1]*.24); db=min(distance,tables[j][-1]*.24)
            if min(da,db)<.01: continue
            end[i]=parameter(tables[i],tables[i][-1]-da)
            begin[j]=parameter(tables[j],db); angles[i]=angle; rounded+=1
        trimmed=[trim(s,t0,t1) for s,t0,t1 in zip(segments,begin,end)]
        result.moveTo(*trimmed[0][0])
        for i,s in enumerate(trimmed):
            if len(s)==2: result.lineTo(*s[-1])
            else: result.cubicTo(*(v for p in s[1:] for v in p))
            if i in angles:
                c=connector(s,trimmed[(i+1)%len(trimmed)],angles[i])
                result.cubicTo(*(v for p in c[1:] for v in p))
        result.close()
    return result,rounded
