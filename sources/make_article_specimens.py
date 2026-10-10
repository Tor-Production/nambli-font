# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Render three original promotional specimens from the approved Nambli TTFs.

Requires Pillow with FreeType; no logo, stock photo, or simulated lettering.
The resulting images are CC BY-SA 4.0 (see documentation/image-license.txt).
"""
from pathlib import Path
import argparse,hashlib,json
from PIL import Image,ImageDraw,ImageFont,features

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fonts',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    purple='#6a5be8';cream='#f7f6ff';ink='#2a273e';records={}
    def font(face,size): return ImageFont.truetype(str(a.fonts/f'Nambli-{face}.ttf'),size)
    def save(image,name):
        path=a.output/name;image.save(path,'JPEG',quality=93,optimize=True,dpi=(72,72))
        assert image.size==(1600,900) and path.stat().st_size<800*1024
        records[name]={'width':1600,'height':900,'dpi':72,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    im=Image.new('RGB',(1600,900),purple);d=ImageDraw.Draw(im)
    d.text((100,62),'Nambli',font=font('Bold',238),fill=cream)
    d.text((110,385),'М’які форми.',font=font('Regular',116),fill=cream)
    d.text((110,556),'Сильний характер.',font=font('SemiBold',103),fill=cream)
    d.text((112,772),'Rounded display • Latin + Cyrillic',font=font('Medium',39),fill=cream)
    save(im,'nambli-rounded.jpg')
    im=Image.new('RGB',(1600,900),cream);d=ImageDraw.Draw(im)
    d.text((86,70),'Round by design',font=font('Medium',111),fill=purple)
    d.text((88,253),'Округлість у деталях',font=font('Italic',88),fill=ink)
    d.text((88,458),'a b @    Ґ Є Ї Я',font=font('Bold',111),fill=purple)
    d.text((92,722),'ă â č ñ ö  •  Україна',font=font('Regular',70),fill=ink)
    save(im,'nambli-multilingual.jpg')
    im=Image.new('RGB',(1600,900),ink);d=ImageDraw.Draw(im)
    weights=['Light','Regular','Medium','SemiBold','Bold','ExtraBold']
    for i,face in enumerate(weights):
        y=45+i*137
        d.text((72,y),face,font=font('Regular',28),fill='#c9c3ef')
        d.text((340,y-8),'Abc Україна',font=font(face,60),fill=cream)
        italic='Italic' if face=='Regular' else face+'Italic'
        d.text((941,y-8),'Abc Україна',font=font(italic,60),fill=cream)
    save(im,'nambli-12-styles.jpg')
    manifest={'renderer':'Pillow/FreeType','raqm_available':features.check('raqm'),
        'font_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(a.fonts.glob('*.ttf'))},'images':records}
    (a.output/'specimens-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(records,indent=2))
if __name__=='__main__':main()
