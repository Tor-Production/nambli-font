# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Limited optical overshoot of established lowercase bowl families; distinct .notdef."""
import math
import unicodedata
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import RecordingPen

ROUNDED_BASES=set('abcdegopq'+'абвеорсфэюя')
class Segments(BasePen):
    def __init__(self):super().__init__(None);self.contours=[];self.current=[]
    def _moveTo(self,p):self.current=[];self.start=p
    def _lineTo(self,p):self.current.append((self._getCurrentPoint(),p))
    def _qCurveToOne(self,c,p):self.current.append((self._getCurrentPoint(),c,p))
    def _curveToOne(self,c,d,p):self.current.append((self._getCurrentPoint(),c,d,p))
    def _closePath(self):
        if self._getCurrentPoint()!=self.start:self.current.append((self._getCurrentPoint(),self.start))
        self.contours.append(self.current)
    def _endPath(self):raise ValueError('Open outline')

def point(s,t):
    s=list(s)
    while len(s)>1:s=[tuple(a+(b-a)*t for a,b in zip(p,q)) for p,q in zip(s,s[1:])]
    return s[0]
def derivative(s,t):
    n=len(s)-1
    return point([tuple(n*(b-a) for a,b in zip(p,q)) for p,q in zip(s,s[1:])],t)
def roots(s):
    if len(s)==3:
        a=s[0][1]-2*s[1][1]+s[2][1]
        return [0.,1.]+([(s[0][1]-s[1][1])/a] if abs(a)>1e-9 else [])
    if len(s)==4:
        a=-s[0][1]+3*s[1][1]-3*s[2][1]+s[3][1];b=2*(s[0][1]-2*s[1][1]+s[2][1]);c=s[1][1]-s[0][1]
        if abs(a)<1e-9:return [0.,1.]+([-c/b] if abs(b)>1e-9 else [])
        d=b*b-4*a*c
        return [0.,1.]+([(-b-math.sqrt(d))/(2*a),(-b+math.sqrt(d))/(2*a)] if d>=0 else [])
    return []
def round_bowl_overshoot(glyph,unicodes,italic_angle=0,stroke=100,protected_lines=()):
    enabled=any(unicodedata.normalize('NFD',chr(cp))[0] in ROUNDED_BASES for cp in unicodes)
    result=RecordingPen()
    if not enabled:glyph.draw(result);return result,[]
    pen=Segments();glyph.draw(pen)
    shear=math.tan(math.radians(-italic_angle));fields=[]
    for ci,contour in enumerate(pen.contours):
        for segment in contour:
            if len(segment)==2:continue
            unskew=[(x-shear*y,y) for x,y in segment]
            for t in roots(unskew):
                if not 0<=t<=1:continue
                x,y=point(unskew,t);v=derivative(unskew,t)
                if abs(v[1])>max(.2,abs(v[0])*.06):continue
                a=derivative([tuple((len(unskew)-1)*(b-a) for a,b in zip(p,q)) for p,q in zip(unskew,unskew[1:])],t)
                denom=abs(v[0]*a[1]-v[1]*a[0])
                radius=math.hypot(*v)**3/denom if denom>1e-9 else 0
                if radius<max(140,stroke):continue
                line=0 if abs(y)<=4 else 530 if abs(y-530)<=4 else None
                if line is None:continue
                if line in protected_lines:continue
                if (line==0 and a[1]<=0) or (line==530 and a[1]>=0):continue
                if any(abs(f['x']-x)<15 and f['line']==line for f in fields):continue
                fields.append({'contour':ci,'x':x,'line':line,'delta':(-10 if line==0 else 540)-y,'radius':radius,'width':max(95,min(180,radius*.7))})
    def mapped(p):
        x,y=p;u=x-shear*y;delta=0
        for f in fields:
            wx=max(0,1-((u-f['x'])/f['width'])**2)**2 if abs(u-f['x'])<f['width'] else 0
            wy=max(0,1-((y-f['line'])/105)**2)**2 if abs(y-f['line'])<105 else 0
            d=f['delta']*wx*wy
            if abs(d)>abs(delta):delta=d
        return x+shear*delta,y+delta
    for contour in pen.contours:
        if not contour:continue
        result.moveTo(mapped(contour[0][0]))
        for s in contour:
            p=tuple(mapped(v) for v in s[1:])
            if len(s)==2:result.lineTo(*p)
            elif len(s)==3:result.qCurveTo(*p)
            else:result.curveTo(*p)
        result.closePath()
    return result,fields

def missing_glyph(advance=620,stroke=100,italic_angle=0):
    """Rounded rectangle crossed by two round diagonals, distinguishable from O."""
    import pathops
    from primitives import line
    margin=55;width=advance-2*margin;left=margin;right=advance-margin;bottom=0;top=740
    ink=max(45,min(88,stroke*.66));r=max(45,ink*.65);k=.5522847498307936
    def rect(x0,y0,x1,y1,rad):
        p=pathops.Path();p.moveTo(x0+rad,y0);p.lineTo(x1-rad,y0)
        p.cubicTo(x1-rad+k*rad,y0,x1,y0+rad-k*rad,x1,y0+rad);p.lineTo(x1,y1-rad)
        p.cubicTo(x1,y1-rad+k*rad,x1-rad+k*rad,y1,x1-rad,y1);p.lineTo(x0+rad,y1)
        p.cubicTo(x0+rad-k*rad,y1,x0,y1-rad+k*rad,x0,y1-rad);p.lineTo(x0,y0+rad)
        p.cubicTo(x0,y0+rad-k*rad,x0+rad-k*rad,y0,x0+rad,y0);p.close();return p
    p=pathops.op(rect(left,bottom,right,top,r),rect(left+ink,bottom+ink,right-ink,top-ink,max(16,r*.45)),pathops.PathOp.DIFFERENCE,clockwise=True)
    pad=ink*1.7
    for points in [[(left+pad,bottom+pad),(right-pad,top-pad)],[(right-pad,bottom+pad),(left+pad,top-pad)]]:
        p=pathops.op(p,line(points,ink*.62),pathops.PathOp.UNION,clockwise=True)
    p=p.transform(1,0,math.tan(math.radians(-italic_angle)),1,0,0)
    out=RecordingPen();p.draw(out);return out
