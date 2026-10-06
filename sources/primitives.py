# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
"""Nambli primitives: rounded strokes and the approved smooth stem caps."""
import math
import pathops

K = .5522847498307936

def path(commands):
    p=pathops.Path()
    for op,args in commands: getattr(p,op)(*args)
    return p

def stroke(commands,width,cap=pathops.LineCap.ROUND_CAP):
    p=path(commands)
    p.stroke(width,cap,pathops.LineJoin.ROUND_JOIN,4)
    p.convertConicsToQuads(.025)
    return pathops.simplify(p,clockwise=True)

def line(points,width):
    return stroke([('moveTo',points[0])]+[('lineTo',p) for p in points[1:]],width)

def ellipse(cx,cy,rx,ry):
    return path([('moveTo',(cx+rx,cy)),
                 ('cubicTo',(cx+rx,cy+K*ry,cx+K*rx,cy+ry,cx,cy+ry)),
                 ('cubicTo',(cx-K*rx,cy+ry,cx-rx,cy+K*ry,cx-rx,cy)),
                 ('cubicTo',(cx-rx,cy-K*ry,cx-K*rx,cy-ry,cx,cy-ry)),
                 ('cubicTo',(cx+K*rx,cy-ry,cx+rx,cy-K*ry,cx+rx,cy)),
                 ('close',())])

def ring(cx,cy,rx,ry,width):
    return pathops.op(ellipse(cx,cy,rx,ry),ellipse(cx,cy,rx-width,ry-width),
                      pathops.PathOp.DIFFERENCE,clockwise=True)

def curvature(points):
    p0,p1,p2,p3=points
    vx,vy=p1[0]-p0[0],p1[1]-p0[1]
    ax,ay=p2[0]-2*p1[0]+p0[0],p2[1]-2*p1[1]+p0[1]
    return (2/3)*abs(vx*ay-vy*ax)/(vx*vx+vy*vy)**1.5

def soft_vertical(x,y,w,h,depth,cap_top=True,cap_bottom=True):
    depth=min(depth,h/3.04)
    a=w/2; t=math.sqrt(.5); k=4/3*math.tan(math.pi/16)
    m=(a*t,depth*(1-t))
    second=(m,(a*t*(1-k),depth*(1-t)-k*depth*t),(k*a,0),(0,0))
    s,d=a-m[0],m[1]
    rise=depth*1.52
    first=((a,rise),(a,2*d+1.5*curvature(second)*(s*s+d*d)**1.5/s),(a,2*d),m)
    quarter=(first,second);cx=x+w/2;top=y+h
    commands=[('moveTo',(x+w,y+rise if cap_bottom else y)),
              ('lineTo',(x+w,top-rise if cap_top else top))]
    def add(mapper,reverse=False):
        segments=[tuple(reversed(q)) for q in reversed(quarter)] if reverse else quarter
        for segment in segments:
            commands.append(('cubicTo',tuple(v for p in segment[1:] for v in mapper(*p))))
    if cap_top:
        add(lambda u,v:(cx+u,top-v));add(lambda u,v:(cx-u,top-v),True)
    else: commands.append(('lineTo',(x,top)))
    commands.append(('lineTo',(x,y+rise if cap_bottom else y)))
    if cap_bottom:
        add(lambda u,v:(cx-u,y+v));add(lambda u,v:(cx+u,y+v),True)
    else: commands.append(('lineTo',(x+w,y)))
    return path(commands+[('close',())])

def bar(x,y,w,h,thickness):
    """An optical crossbar centred in its original design rectangle."""
    if w>=h:
        p=soft_vertical(0,0,thickness,w,max(thickness*.37,thickness*.4))
        return p.transform(0,-1,1,0,x,y+h/2+thickness/2)
    return soft_vertical(x+w/2-thickness/2,y,thickness,h,thickness*.4)
