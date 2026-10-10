"""Raster proofs from supplied TTF/OTF files, with no outline transformation.

Example (PowerShell):
  & C:/Python312/python.exe render_ttf_comparison.py `
    --font '1.001 original' C:/proofs/1.001/Nambli-Regular.ttf `
    --font '1.002 overshoot' C:/proofs/1.002/Nambli-Regular.ttf `
    --font '1.003 revised' C:/proofs/1.003/Nambli-Regular.ttf `
    --title 'Nambli Regular' --output C:/proofs/Regular.png

Writes separate display/text sheets, a combined PNG, and a JSON manifest with
font hashes, strings, pixel sizes, and renderer details. Every version uses the
same pixel size and baseline for each sample. No resizing or font fallback is
applied to the specimen text. With RAQM available, Turkish rows use language
tr. Otherwise these are explicitly static precomposed-glyph proofs, not a test
of language-specific OpenType shaping.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform

from PIL import Image, ImageDraw, ImageFont, features
import PIL


DEFAULT_DISPLAY=('abeo@','Я Ľ ľ ď ť')
DEFAULT_TEXT='abeo@ ЯĽľďť — Nambli. A round form, a smooth edge.'
TURKISH='İ I ı i — Çağrı, İstanbul, ışık, küçük, düzgün.'
BACKGROUND='#f6f5fa'
INK='#292737'
PURPLE='#7054e8'
RAQM=features.check_feature('raqm')


def label_font(size,path=None):
    for candidate in (path,Path('C:/Windows/Fonts/segoeui.ttf')):
        if candidate and Path(candidate).is_file():return ImageFont.truetype(str(candidate),size)
    return ImageFont.load_default(size=size)


def specimen_font(path,size):
    engine=ImageFont.Layout.RAQM if RAQM else ImageFont.Layout.BASIC
    return ImageFont.truetype(str(path),size,layout_engine=engine)


def options(language):
    return {'language':language,'direction':'ltr'} if RAQM and language else {}


def sheet(fonts,samples,title,ui_path=None,min_width=1280,guides=True):
    ui=label_font(20,ui_path);small=label_font(15,ui_path);heading=label_font(29,ui_path)
    margin=32;label_width=max(220,int(max(ui.getlength(label) for label,_ in fonts))+40);left=margin+label_width
    prepared=[];width=min_width
    for sample in samples:
        loaded=[specimen_font(path,sample['size']) for _,path in fonts]
        args=options(sample.get('language'))
        boxes=[font.getbbox(sample['text'],anchor='ls',**args) for font in loaded]
        top=min(box[1] for box in boxes);bottom=max(box[3] for box in boxes)
        width=max(width,int(left+max(box[2] for box in boxes)+margin+20))
        row_height=max(74,int(bottom-top)+40)
        prepared.append((sample,loaded,boxes,top,bottom,row_height))
    height=100+sum(58+len(fonts)*row_height+24 for _,_,_,_,_,row_height in prepared)+54
    image=Image.new('RGB',(width,height),BACKGROUND);draw=ImageDraw.Draw(image)
    draw.text((margin,25),title,font=heading,fill=INK)
    draw.text((margin,63),'Actual compiled fonts · identical pixel sizes · baseline aligned',font=small,fill='#666273')
    y=100
    for sample,loaded,boxes,top,bottom,row_height in prepared:
        draw.text((margin,y+12),f"{sample['label']} · {sample['size']} px",font=ui,fill=INK)
        y+=58
        for (label,path),font,box in zip(fonts,loaded,boxes):
            draw.rounded_rectangle((margin-5,y,width-margin+5,y+row_height-6),12,fill='white')
            baseline=y+20-top
            draw.text((margin+10,y+16),label,font=ui,fill=PURPLE)
            family,style=font.getname()
            draw.text((margin+10,y+42),style,font=small,fill='#77717f')
            if guides:
                for x in range(left,width-margin,12):
                    draw.line((x,baseline,min(x+6,width-margin),baseline),fill='#dfdbe8',width=1)
            # Font pixels are rendered directly into the final bitmap.
            draw.text((left,baseline),sample['text'],font=font,fill=INK,anchor='ls',
                      **options(sample.get('language')))
            y+=row_height
        y+=24
    shaping='RAQM / language-aware shaping' if RAQM else 'BASIC / static precomposed glyphs; no language-specific shaping'
    draw.text((margin,height-35),f'Pillow {PIL.__version__} · FreeType {features.version_module("freetype2")} · {shaping}',
              font=small,fill='#77717f')
    return image


def render(args):
    fonts=[(label,Path(path).resolve()) for label,path in args.font]
    for _,path in fonts:
        if not path.is_file():raise FileNotFoundError(path)
        if path.suffix.lower() not in {'.ttf','.otf'}:raise ValueError(f'Use an actual compiled TTF/OTF: {path}')
    samples_display=[{'label':'Display / Latin','text':args.display_latin,'size':args.display_size},
        {'label':'Display / Cyrillic and side carons','text':args.display_marks,'size':args.display_size},
        {'label':'Turkish / encoded forms','text':'İ I ı i  Ğ ğ  Ş ş','size':args.display_size,'language':'tr'}]
    samples_text=[]
    for size in args.text_sizes:
        samples_text.extend([{'label':'Reading size','text':args.text,'size':size},
            {'label':'Turkish control','text':args.turkish,'size':size,'language':'tr'}])
    display=sheet(fonts,samples_display,args.title+' — display',args.ui_font,args.width,not args.no_guides)
    reading=sheet(fonts,samples_text,args.title+' — text',args.ui_font,args.width,not args.no_guides)
    out=args.output.resolve();out.parent.mkdir(parents=True,exist_ok=True)
    paths={'combined':out,'display':out.with_name(out.stem+'-display.png'),
           'text':out.with_name(out.stem+'-text.png')}
    display.save(paths['display']);reading.save(paths['text'])
    combined=Image.new('RGB',(max(display.width,reading.width),display.height+reading.height),BACKGROUND)
    combined.paste(display,(0,0));combined.paste(reading,(0,display.height));combined.save(out)
    manifest={'title':args.title,'fonts':[{'label':label,'path':str(path),
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'name':specimen_font(path,20).getname()} for label,path in fonts],
        'samples':{'display':samples_display,'text':samples_text},
        'renderer':{'python':platform.python_version(),'pillow':PIL.__version__,
            'freetype':features.version_module('freetype2'),'raqm':RAQM,
            'layout':'RAQM' if RAQM else 'BASIC',
            'languageShapingVerified':False,
            'note':'Raster comparison, not a substitute for browser/OS and OpenType shaping tests.'},
        'outputs':{key:{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                   for key,path in paths.items()}}
    out.with_suffix('.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'outputs':{key:str(path) for key,path in paths.items()},'raqm':RAQM},ensure_ascii=False))


def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--font',nargs=2,action='append',metavar=('LABEL','TTF_PATH'),required=True)
    p.add_argument('--title',default='Nambli comparison')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--display-size',type=int,default=144)
    p.add_argument('--text-sizes',type=int,nargs='+',default=[18,24,36])
    p.add_argument('--display-latin',default=DEFAULT_DISPLAY[0])
    p.add_argument('--display-marks',default=DEFAULT_DISPLAY[1])
    p.add_argument('--text',default=DEFAULT_TEXT)
    p.add_argument('--turkish',default=TURKISH)
    p.add_argument('--width',type=int,default=1280)
    p.add_argument('--ui-font',type=Path)
    p.add_argument('--no-guides',action='store_true')
    args=p.parse_args()
    if args.output.suffix.lower()!='.png':p.error('--output must end in .png')
    if args.display_size<8 or any(size<8 for size in args.text_sizes):p.error('Pixel sizes must be at least8')
    render(args)


if __name__=='__main__':main()
