# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
"""Nambli 0.7: native weight-aware e, compact Ya bowls and cursive forms."""
import math
import pathops
from primitives import path,stroke,line,ring,ellipse,soft_vertical,bar


def arc(cx,cy,rx,ry,start,end,width):
    a=math.radians(start);b=math.radians(end)
    segments=max(1,math.ceil(abs(b-a)/(math.pi/2)));step=(b-a)/segments
    commands=[('moveTo',(cx+rx*math.cos(a),cy+ry*math.sin(a)))]
    for i in range(segments):
        t=a+i*step;u=t+step;k=4/3*math.tan(step/4)
        commands.append(('cubicTo',(
            cx+rx*(math.cos(t)-k*math.sin(t)),cy+ry*(math.sin(t)+k*math.cos(t)),
            cx+rx*(math.cos(u)+k*math.sin(u)),cy+ry*(math.sin(u)-k*math.cos(u)),
            cx+rx*math.cos(u),cy+ry*math.sin(u))))
    return stroke(commands,width)


def e_shape(width,combine,height=530):
    cx,cy=310,height/2;rx=264-width/2;ry=height/2-width/2
    end=360-(48+(width-80)*.24)
    bowl=arc(cx,cy,rx,ry,0,end,width)
    cross=line([(cx-rx,cy),(cx+rx,cy)],width)
    return combine([bowl,cross])


def ya_shape(width,combine,lower=False):
    diameter=380 if lower else 488
    right=457.84 if lower else 574
    height=530 if lower else 740
    w=width*.90 if lower else width
    radius=diameter/2;cx=right-radius;cy=height-radius;bottom=height-diameter
    bowl=ring(cx,cy,radius,radius,w)
    foot=(46+w/2,w/2);join=(cx,bottom+.38*w)
    vx,vy=join[0]-foot[0],join[1]-foot[1];length=math.hypot(vx,vy)
    # Clip the hidden lower arc along the leg's inner edge. Keeping the
    # complete circular counter prevents a hanging fragment below the leg.
    slope=vy/vx
    y_at=lambda x: join[1]+slope*(x-join[0])-w/2*math.sqrt(1+slope*slope)
    halfplane=path([('moveTo',(-2500,-3500)),('lineTo',(3000,-3500)),
                    ('lineTo',(3000,y_at(3000))),('lineTo',(-2500,y_at(-2500))),('close',())])
    bowl=pathops.op(bowl,halfplane,pathops.PathOp.DIFFERENCE,clockwise=True)
    stem=soft_vertical(right-w,0,w,cy,52*w/132,cap_top=False)
    return combine([bowl,stem,line([foot,join],w)])


AT_END=298


def at_geometry(target):
    w=94*target/132
    return w,339-w/2,366-w/2


def at_parts(target):
    """An open spiral; the free terminal clears the inner return in every weight."""
    ratio=target/132;w,rx,ry=at_geometry(target);right=404+rx
    # The old 316-degree end touched the low returning tail. Ending at
    # 298 degrees and lifting that return opens a generous white channel.
    # Keep the original 678 x 732-unit outer frame in every weight.
    outer=arc(404,345,rx,ry,0,AT_END,w)
    bowl=ring(391,320,152,178,92*ratio)
    returning=stroke([('moveTo',(497,452)),('lineTo',(497,253)),
        ('cubicTo',(497,198,570,192,620,231)),
        ('cubicTo',(right-28,268,right,296,right,345))],w)
    return outer,bowl,returning


def dje_parts(target):
    """The dje crossbar clears its shoulder, including ExtraBold Italic.

    Start the bar inside the upright so lighter stems do not acquire a
    left-side bump. The shoulder and descending hook retain their approved
    centreline; only the crossbar is raised from 556 to 600 units.
    """
    ratio=target/132
    stem=soft_vertical(112-target/2,0,target,712,52*ratio)
    crossbar=bar(112,545,259,110,110*ratio)
    shoulder=stroke([('moveTo',(112,270)),
        ('cubicTo',(112,403,508,569,508,277)),('lineTo',(508,1)),
        ('cubicTo',(508,-169,406,-206,312,-161))],target)
    return stem,crossbar,shoulder


def tje_parts(target,capital=False,dje=False):
    """Round tje / capital dje bodies with a visibly separated crossbar.

    The lowercase uses the n/h shoulder. Capitals keep the approved narrow
    n proportions. Their bars have independent proportional strokes and
    start inside the upright, avoiding a left-side bump in lighter weights.
    """
    ratio=target/132
    left=46+target/2;right=574-target/2;mid=(left+right)/2
    y=270;peak=530-target/2
    shoulder=stroke([('moveTo',(left,y)),
        ('cubicTo',(left,y+(peak-y)*119/194,left+(mid-left)*79/198,peak,mid,peak)),
        ('cubicTo',(right-(right-mid)*79/198,peak,right,y+(peak-y)*119/194,right,y))],
        target,cap=pathops.LineCap.BUTT_CAP)
    # Overlap the hidden butt join by four units so both font encodings
    # remain a single contour after curve conversion and quantization.
    right_stem=soft_vertical(574-target,0,target,274,52*ratio,cap_top=False)
    if capital:
        # Preserve the existing .86 x 1.02 capital bowl/shoulder frame.
        shoulder=shoulder.transform(.86,0,0,1.02,0,0)
        frame=path([('moveTo',(46,-400)),('lineTo',(1200,-400)),
                    ('lineTo',(1200,800)),('lineTo',(46,800)),('close',())])
        shoulder=pathops.op(shoulder,frame,pathops.PathOp.INTERSECTION,clockwise=True)
        right_stem=right_stem.transform(.86,0,0,1.02,0,0)
        stem=soft_vertical(46,0,target,740,52*ratio)
        crossbar=bar(left,580,418-left,120,120*ratio)
        parts=[stem,crossbar,shoulder,right_stem]
        if dje:
            cx=.86*right
            parts.append(stroke([('moveTo',(cx,190)),('lineTo',(cx,2)),
                ('cubicTo',(cx,-141,cx-99.88,-169,cx-159.88,-119))],112*ratio))
    else:
        stem=soft_vertical(46,0,target,712,52*ratio)
        crossbar=bar(left,565,371-left,110,110*ratio)
        parts=[stem,crossbar,shoulder,right_stem]
    return parts


def refine_design(paths,master,target,combine,italic=False):
    cmap=master.getBestCmap();changed=set();ratio=target/132
    def get(ch):return paths[cmap[ord(ch)]]
    def put(ch,p):
        if ord(ch) in cmap:
            paths[cmap[ord(ch)]]=combine([p]);changed.add(cmap[ord(ch)])
    def alias(chars,p):
        for ch in chars:put(ch,p)
    put('@',combine(at_parts(target)))
    alias('eе',e_shape(target,combine))
    backwards=get('e').transform(-1,0,0,-1,620,530)
    alias('əǝ',backwards)
    put('Ə',e_shape(target,combine,740).transform(-1,0,0,-1,620,740))
    put('ᵉ',get('e').transform(.51,0,0,.51,8,425))
    put('Я',ya_shape(target,combine));put('я',ya_shape(target,combine,True))
    # The gamma loop was 15.6 units in old Light (vs a main stroke of 80).
    # Independent loop construction preserves its intentional proportion.
    for ch,height,total,cx,apex,cy,rx,nominal in [
        ('Ɣ',740,700,350,270,130,150,88),('ɣ',530,620,310,230,110,134,76)]:
        legs=line([(103,height-66),(cx,apex),(total-103,height-66)],target)
        put(ch,combine([legs,ring(cx,cy,rx,cy,nominal*ratio)]))
    # Crossbars keep their optical proportion instead of losing a fixed
    # boundary distance intended for the heavier main stroke.
    for ch,base,rect,nominal in [('Є','C',(100,310,378,120),120),
                                ('є','c',(100,213,340,104),104)]:
        put(ch,combine([get(base),bar(*rect,nominal*ratio)]))
    put('Э',get('Є').transform(-1,0,0,1,670,0))
    put('э',get('є').transform(-1,0,0,1,590,0))
    cx=182
    stem=soft_vertical(cx-target/2,0,target,535,52*ratio,cap_top=False)
    hook=stroke([('moveTo',(cx,418)),('lineTo',(cx,528)),
                 ('cubicTo',(cx,645,270,694,363,634))],target)
    crossbar=bar(47,402,356,112,112*ratio)
    put('f',combine([stem,hook,crossbar]))
    put('t',combine([soft_vertical(182-target/2,244,target,416,52*ratio),
        stroke([('moveTo',(182,292)),('lineTo',(182,168)),
                ('cubicTo',(182,78,240,52,327,87))],target),
        bar(47,402,345,112,112*ratio)]))
    small_bar=132*530/740*ratio
    put('ɪ',combine([soft_vertical(189-target/2,0,target,530,52*ratio,False,False),
        bar(46,608*530/740,286,132*530/740,small_bar),bar(46,0,286,132*530/740,small_bar)]))
    # Small-cap upsilon has a round bottom with proportionate top bars.
    w=target*.85;lc=105;rc=515;cy=285
    cup=arc(310,cy,(rc-lc)/2,cy-w/2,180,360,w)
    uprights=line([(lc,530-target/2),(lc,cy)],w),line([(rc,cy),(rc,530-target/2)],w)
    put('ʊ',combine([cup,*uprights,bar(10,530-target,248,target,target),
                    bar(362,530-target,248,target,target)]))
    quote=combine([ellipse(138,638,60*ratio,60*ratio),
        stroke([('moveTo',(164,629)),('cubicTo',(165,571,140,531,91,514))],65*ratio)])
    alias('ʼ’',quote)
    left_quote=quote.transform(-1,0,0,-1,250,1225)
    alias('ʻ‘',left_quote)
    put('“',combine([left_quote,left_quote.transform(1,0,0,1,180,0)]))
    put('”',combine([quote,quote.transform(1,0,0,1,180,0)]))
    low_quote=left_quote.transform(1,0,0,1,0,-532)
    put('‚',low_quote);put('„',combine([low_quote,low_quote.transform(1,0,0,1,180,0)]))
    put('ʾ',arc(132,616,85,91,-75,75,55*ratio))
    put('ʿ',arc(132,616,85,91,105,255,55*ratio))
    if italic:
        # A continuous descender gives f a true cursive form.
        down=stroke([('moveTo',(cx,535)),('lineTo',(cx,-60)),
                     ('cubicTo',(cx,-158,cx-36,-196,cx-104,-157))],target)
        put('f',combine([down,hook,crossbar]))
        def exit_stem(x,top):
            return stroke([('moveTo',(x,top)),('lineTo',(x,125)),
                ('cubicTo',(x,82,x,target/2+5,x+14,target/2+5)),
                ('cubicTo',(x+32,target/2+5,x+38,target/2+14,x+44,target/2+30))],target)
        def shoulder(left,right,top=530):
            y=270;peak=top-target/2;mid=(left+right)/2
            return stroke([('moveTo',(left,y)),
                ('cubicTo',(left,y+(peak-y)*.62,left+(mid-left)*.40,peak,mid,peak)),
                ('cubicTo',(right-(right-mid)*.40,peak,right,y+(peak-y)*.62,right,y))],target,
                cap=pathops.LineCap.BUTT_CAP)
        left=46+target/2;right=574-target/2
        n=combine([soft_vertical(46,0,target,270,52*ratio,cap_top=False),
                   shoulder(left,right),exit_stem(right,270)])
        alias('nп',n)
        h=combine([soft_vertical(46,0,target,712,52*ratio),
                   shoulder(left,right),exit_stem(right,270)])
        alias('hһ',h)
        # m retains two round shoulders with the same vertical weight.
        last=837-target/2;middle=(left+last)/2
        m=combine([soft_vertical(46,0,target,270,52*ratio,cap_top=False),
                   shoulder(left,middle),shoulder(middle,last),
                   soft_vertical(middle-target/2,0,target,270,52*ratio,cap_top=False),
                   exit_stem(last,270)])
        alias('mт',m)
        a=combine([ring(310,265,264,265,target),exit_stem(right,530-target/2)])
        alias('aа',a)
    put('ŉ',combine([get('n').transform(1,0,0,1,131,0),get('ʼ').transform(.62,0,0,.71,6,265)]))
    return changed
