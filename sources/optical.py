# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
"""Separate construction for mixed stroke widths and attached diacritics.

These letters cannot use a single boundary offset: their attached secondary
strokes are deliberately thinner in the approved design. Keeping each
stroke's proportion protects horns, ogoneks and small historical bowls.
"""
import math
import unicodedata as ud
from primitives import stroke,line,ring,bar,soft_vertical
from outline_polish import polish


def refine(paths,master,target,combine,italic=False):
    cmap=master.getBestCmap(); ratio=target/132
    from design import refine_design,dje_parts,tje_parts
    changed=refine_design(paths,master,target,combine,italic)
    def get(ch): return paths[cmap[ord(ch)]]
    def put(ch,p):
        name=cmap[ord(ch)]
        paths[name]=polish(combine([p]),distance=12*ratio)[0]
        changed.add(name)
    def add(ch,base,parts): put(ch,combine([get(base)]+parts))
    def b(x,y,w,h,nominal): return bar(x,y,w,h,nominal*ratio)
    def s(commands,nominal=132): return stroke(commands,nominal*ratio)
    def v(cx,top=712,bottom=0,nominal=132):
        w=nominal*ratio
        return soft_vertical(cx-w/2,bottom,w,top-bottom,52*w/132)

    # Native secondary strokes; their thickness follows the body weight.
    add('Ø','O',[line([(130,62),(568,678)],94*ratio)])
    add('ø','o',[line([(139,66),(481,464)],80*ratio)])
    add('Ł','L',[line([(47,245),(318,471)],80*ratio)])
    add('ł','l',[line([(30,251),(221,446)],73*ratio)])
    for ch,base,rectangle,nominal in [
        ('Ð','D',(6,310,313,106),106),('Đ','D',(6,310,313,106),106),
        ('đ','d',(338,559,325,86),86),('Ħ','H',(15,530,654,90),90),
        ('ħ','h',(8,550,302,82),82),('Ŧ','T',(144,304,362,91),91),
        ('ŧ','t',(47,230,345,85),85),('Ɨ','I',(42,304,294,94),94),
        ('ɨ','i',(2,204,246,80),80),('Ʉ','U',(12,304,640,88),88),
        ('ʉ','u',(8,209,604,83),83),('Ǥ','G',(355,205,335,85),85),
        ('ǥ','g',(343,-22,284,79),79),('Ѣ','Ь',(22,576,316,108),108),
        ('ѣ','ь',(24,474,256,90),90)]:
        add(ch,base,[b(*rectangle,nominal)])
    paths[cmap[ord('Ɖ')]]=paths[cmap[ord('Đ')]];changed.add(cmap[ord('Ɖ')])
    right=get('o').bounds[2]-target/2
    add('ð','o',[s([('moveTo',(right,265)),('cubicTo',(right+18,484,318,617,169,683))],112),
                 line([(135,482),(409,649)],76*ratio)])
    add('ɬ','l',[s([('moveTo',(127,226)),('cubicTo',(-43,288,-13,402,103,365)),
                 ('lineTo',(282,281))],76)])
    put('Ɬ',get('ɬ').transform(1,0,0,740/get('ɬ').bounds[3],0,0))
    # The little closed upper cups keep a proportional 90 / 70-unit stroke.
    for ch,cx,cy,radius,nominal,leg_x,apex,stem_x,stem_h in [
        ('Ѫ',330,611,141,90,112,482,264,530),
        ('ѫ',287,434,111,70,107,315,221,364)]:
        legs=line([(leg_x,target/2),(cx,apex),(2*cx-leg_x,target/2)],target)
        centre=soft_vertical(stem_x+(132-target)/2,0,target,stem_h,52*ratio)
        bowl=ring(cx,cy,radius,radius,nominal*ratio)
        put(ch,combine([legs,centre,bowl]))
    # Keep the crossbar's free tip separate from the rounded shoulder.
    put('ђ',combine(dje_parts(target)))
    put('ћ',combine(tje_parts(target)))
    put('Ћ',combine(tje_parts(target,capital=True)))
    put('Ђ',combine(tje_parts(target,capital=True,dje=True)))
    # Narrow click / glottal stems and currency crossbars must not lose
    # most of their ink when the alphabet's thicker stem is lightened.
    put('ǀ',v(150,740,0,100))
    put('ǁ',combine([v(132.5,740,0,95),v(307.5,740,0,95)]))
    put('ǂ',combine([v(196,740,0,100),b(26,420,340,82,82),b(26,240,340,82,82)]))
    put('Ꞌ',v(125,740,186,92));put('ꞌ',v(125,530,164,92))
    put('$',combine([get('S').transform(.84,0,0,1,16,0),b(281,-72,74,883,74)]))
    put('€',combine([get('C').transform(.90,0,0,1,15,0),b(20,404,394,83,83),b(20,231,354,83,83)]))
    put('₴',combine([get('S').transform(.84,0,0,1,16,0),b(27,428,560,82,82),b(27,235,560,82,82)]))
    put('£',combine([s([('moveTo',(489,618)),('cubicTo',(323,761,125,645,159,435)),
                        ('cubicTo',(185,257,180,154,102,66)),('lineTo',(505,66))],116),
                     b(51,294,345,100,100)]))
    add('¥','Y',[b(136,231,391,90,90),b(136,99,391,90,90)])
    put('%',combine([ring(155,560,114,178,72*ratio),ring(495,180,114,178,72*ratio),
                     line([(153,66),(497,674)],90*ratio)]))
    for ch,base in [('©','C'),('®','R')]:
        put(ch,combine([ring(390,370,343,380,73*ratio),
                        get(base).transform(.47,0,0,.47,222,195)]))
    put('™',combine([get('T').transform(.48,0,0,.43,20,449),
                     get('M').transform(.43,0,0,.43,353,449)]))
    put('№',combine([get('N').transform(.83,0,0,1,0,0),ring(732,498,149,193,78*ratio),
                     b(583,160,298,81,81)]))
    put('°',ring(191,628,112,112,68*ratio))
    # Separate digraph letters may naturally separate in lighter weights.
    joined=[('Ĳ','I','J',335),('ĳ','i','j',229),('ʣ','d','z',450),('ʦ','t','s',337),
            ('Æ','A','E',443),('æ','a','e',446),('Œ','O','E',518),('œ','o','e',447)]
    for ch,a,b,dx in joined:
        first=get(a).transform(.80,0,0,1,0,0) if ch=='Æ' else get(a)
        put(ch,combine([first,get(b).transform(1,0,0,1,dx,0)]))
    for ch,a,b in [('Ǆ','D','Ž'),('ǅ','D','ž'),('ǆ','d','ž'),('Ǉ','L','J'),
                   ('ǈ','L','j'),('ǉ','l','j'),('Ǌ','N','J'),('ǋ','N','j'),
                   ('ǌ','n','j'),('Ǳ','D','Z'),('ǲ','D','z'),('ǳ','d','z')]:
        dx=master['hmtx'].metrics[cmap[ord(a)]][0]-30
        put(ch,combine([get(a),get(b).transform(1,0,0,1,dx,0)]))

    # Read canonical anchors from the accepted layout table.
    pos=next(l.SubTable[0] for l in master['GPOS'].table.LookupList.Lookup if l.LookupType==4)
    marks={n:(r.Class,r.MarkAnchor.XCoordinate,r.MarkAnchor.YCoordinate)
           for n,r in zip(pos.MarkCoverage.glyphs,pos.MarkArray.MarkRecord)}
    anchors={n:[(a.XCoordinate,a.YCoordinate) if a else None for a in r.BaseAnchor]
             for n,r in zip(pos.BaseCoverage.glyphs,pos.BaseArray.BaseRecord)}
    def mark_kind(cp):
        if cp==0x31b:return 'HORN'
        if cp==0x328:return 'OGONEK'
        return 'BOTTOM' if ud.combining(chr(cp)) in {202,220} else 'TOP'
    def horn(base,body):
        if base not in 'Oo':return None
        x0,y0,x1,y1=body.bounds
        cx,cy=(x0+x1)/2,(y0+y1)/2;rx,ry=(x1-x0)/2,(y1-y0)/2
        angle=math.radians(55)
        q=(cx+(rx-target/2)*math.cos(angle),cy+(ry-target/2)*math.sin(angle))
        tx,ty=rx*math.sin(angle),-ry*math.cos(angle);length=math.hypot(tx,ty)
        feature=s([('moveTo',q),('cubicTo',(q[0]+60*tx/length,q[1]+60*ty/length,
                  cx+rx*.98,cy+ry*.59,cx+rx*1.04,cy+ry*.81)),
                  ('cubicTo',(cx+rx*1.12,cy+ry*.92,cx+rx*1.07,cy+ry*1.12,
                              cx+rx*.99,cy+ry*1.10))],65)
        return polish(combine([body,feature]),distance=24*ratio)[0]
    composed=[]
    for cp,name in cmap.items():
        nfd=ud.normalize('NFD',chr(cp))
        if len(nfd)>1 and ord(nfd[0]) in cmap and all(ord(c) in cmap and cmap[ord(c)] in marks for c in nfd[1:]):
            composed.append((cp,name,nfd))
    for cp,name,nfd in composed:
        base=nfd[0];base_name=cmap[ord(base)]
        top_mark=any(mark_kind(ord(c))=='TOP' for c in nfd[1:])
        if base=='i' and top_mark:base_name='idotless.alt'
        if base=='і' and top_mark:base_name='uni0456.dotless'
        if base=='j' and top_mark:base_name=cmap[0x237]
        body=paths[base_name];pieces=[body]
        row=anchors.get(base_name,anchors[cmap[ord(base)]])
        point_by_kind={}
        for mark_name,(kind,mx,my) in marks.items():
            cp_mark=next((k for k,v in cmap.items() if v==mark_name),None)
            if cp_mark is not None and row[kind]:point_by_kind[mark_kind(cp_mark)]=row[kind]
        if nfd[1:]=='\u030c' and base in 'dtlL':
            x=292 if base=='L' else body.bounds[2]+69
            pieces.append(get('\u0313').transform(.75,0,0,1.1,x,body.bounds[3]-181))
        elif nfd[1:]=='\u0327' and base in 'GgKkLlNnRr':
            mark='\u0313' if base=='g' else '\u0326'
            x,y=point_by_kind['TOP' if base=='g' else 'BOTTOM']
            pieces.append(get(mark).transform(1,0,0,1,x,y))
        else:
            for mark in nfd[1:]:
                kind=mark_kind(ord(mark));x,y=point_by_kind[kind]
                if kind=='HORN' and base in 'Oo':
                    pieces[0]=horn(base,body)
                    continue
                # Ogonek reaches into the new stem rather than ending at
                # the old Bold edge. The reference mark has a round cap.
                if kind=='OGONEK':
                    x -= (132-target)/2
                p=get(mark).transform(1,0,0,1,x,y)
                pieces.append(p)
                if kind=='TOP':point_by_kind[kind]=(x,p.bounds[3]+24)
                if kind=='BOTTOM':point_by_kind[kind]=(x,p.bounds[1]-24)
        paths[name]=polish(combine(pieces),distance=12*ratio)[0]
        changed.add(name)
    # Compatibility digraphs with a caron must use the recomposed face.
    for ch,a,b in [('Ǆ','D','Ž'),('ǅ','D','ž'),('ǆ','d','ž')]:
        dx=master['hmtx'].metrics[cmap[ord(a)]][0]-30
        put(ch,combine([get(a),get(b).transform(1,0,0,1,dx,0)]))
    return changed
