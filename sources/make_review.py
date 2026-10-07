"""Proof every added/changed outline and language substitution in all faces."""
import argparse, base64, html, json, shutil, sys, unicodedata
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import runtime
from clean_outlines import geometry
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
ap=argparse.ArgumentParser()
for key in ('fonts','baseline','output'):ap.add_argument('--'+key,type=Path,required=True)
args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
(args.output/'fonts').mkdir(exist_ok=True)
weights={'Light':0,'Regular':1,'Medium':2,'SemiBold':3,'Bold':4,'ExtraBold':5}
faces=[];styles=[];sections=[];audit={}
def svg(font,name):
    gs=font.getGlyphSet();pen=SVGPathPen(gs);gs[name].draw(pen)
    adv=font['hmtx'][name][0];tx=300 if not adv else 0;width=max(adv,650)
    box=BoundsPen(gs);gs[name].draw(box)
    x0,y0,x1,y1=box.bounds or (0,0,0,0)
    left=min(-140,tx+x0-80);right=max(width+140,tx+x1+80)
    top=min(-280,1000-y1-80);bottom=max(1400,1000-y0+80)
    return f'<svg viewBox="{left} {top} {right-left} {bottom-top}" aria-label="{html.escape(name)}"><path transform="translate({tx} 1000) scale(1 -1)" d="{pen.getCommands()}"/></svg>'
for path in sorted(args.fonts.glob('*.ttf'),key=lambda p:('Italic' in p.stem,weights[p.stem.removeprefix('Nambli-').removesuffix('Italic') or 'Regular'])):
    with TTFont(path,recalcTimestamp=False) as font, TTFont(args.baseline/path.name,recalcTimestamp=False) as old:
        face=path.stem;faces.append(face);cmap=font.getBestCmap();oldcmap=old.getBestCmap();oldnames=set(old.getGlyphOrder());reverse={}
        for cp,name in cmap.items():reverse.setdefault(name,[]).append(cp)
        for prefix,webfont in (('new',font),('old',old)):
            webfont.flavor='woff2';webfont.save(args.output/'fonts'/f'{prefix}-{face}.woff2')
            data=base64.b64encode((args.output/'fonts'/f'{prefix}-{face}.woff2').read_bytes()).decode('ascii')
            styles.append(f'@font-face{{font-family:"{prefix}-{face}";src:url("data:font/woff2;base64,{data}") format("woff2")}}')
        shutil.copy2(path,args.output/'fonts'/path.name)
        cards=[];rows=[]
        for name in font.getGlyphOrder():
            cps=reverse.get(name,[]);new_cps=[cp for cp in cps if cp not in oldcmap]
            changed=name in oldnames and (geometry(font,name)!=geometry(old,name) or font['hmtx'][name]!=old['hmtx'][name])
            if name in oldnames and not new_cps and not changed:continue
            kind='changed' if changed else ('new' if cps else 'alternate')
            code=' / '.join(f'U+{cp:04X}' for cp in cps) or name
            desc='; '.join(unicodedata.name(chr(cp),'UNICODE CHARACTER') for cp in cps) or 'Службова форма для мовних підстановок'
            note={'changed':'Змінений наявний символ','new':'Доданий символ','alternate':'Нова альтернативна форма'}[kind]
            if set(cps)&{0x2028,0x2029}:note='Невидимий роздільник · нульова ширина'
            before=svg(old,name) if name in oldnames else '<div class="absent">Не було у 0.7.4</div>'
            cards.append(f'<article data-code="{html.escape((code+" "+name+(" @" if 0x40 in cps else "")).upper())}" data-kind="{kind}"><h3>{html.escape(code)}</h3><div class="compare"><div class="before"><small>До · 0.7.4</small>{before}</div><div class="after"><small>Після · кандидат</small>{svg(font,name)}</div></div><p>{html.escape(desc)}</p><small>{note}</small></article>')
            rows.append({'glyph':name,'codepoints':cps,'kind':kind})
        samples=[('en','Круглі чаші','a b @'),('uk','Українська','Її Ґґ Йй Яя — і́ ї і̄'),('ca','Català','L·L l·l col·lecció'),('tr','Türkçe','i ı İ I — iki şehir'),('cs','Čeština / Slovenčina','ď ľ ť Ľ Ď Ť'),('yo','Yorùbá','ẹ́ ọ̀ ṣ — é̩ ò̩'),('en','Знаки над і під літерою','i̇́ j̄́ ḭ́ — á̩ ò̤ ń̰'),('en','Адреса та виправлені отвори','@ hello@nambli.font ɬ Ɬ')]
        sample_html=''
        for lang,label,text in samples:
            sample_html+=f'<div class="sample"><small>{label}</small>'
            size=64 if label=='Круглі чаші' else 29
            for prefix,caption in (('old','До'),('new','Після')):sample_html+=f'<p lang="{lang}" class="{prefix}" style="font-family:\'{prefix}-{face}\';font-size:{size}px"><span>{caption}</span>{text}</p>'
            sample_html+='</div>'
        sections.append(f'<section data-face="{face}"><h2>{face} · {len(rows)} карток</h2><div class="samples">{sample_html}</div><div class="grid">'+''.join(cards)+'</div></section>');audit[face]=rows
css='''*{box-sizing:border-box}body{margin:0;padding:28px;font:16px/1.5 system-ui;background:#f8f7ff;color:#35354f}h1{font-size:28px}h2{font-size:20px}header>p{max-width:1000px}.toolbar{position:sticky;top:0;background:#f8f7fff5;padding:14px 0;z-index:1;display:flex;gap:16px;flex-wrap:wrap}select,input{font:inherit;padding:8px;border:1px solid #bfb6df;border-radius:7px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}article,.sample{background:white;border:1px solid #ddd7f4;border-radius:14px;padding:16px}article h3{margin:0;font-size:13px;font-weight:500}.compare{display:grid;grid-template-columns:1fr 1fr;gap:8px;text-align:center}.compare svg{width:100%;height:190px}.before svg{fill:#aaa3b7}.after svg{fill:#6b5bdf}article p{font-size:11px;min-height:34px}.absent{height:190px;display:grid;place-content:center;color:#aaa3b7;font-size:13px}small{color:#74708a;font-size:12px}section[hidden],article[hidden]{display:none}.samples{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:14px;margin-bottom:24px}.sample p{font-size:29px;overflow-wrap:anywhere;margin:10px 0}.sample p span{display:block;font:11px system-ui;color:#74708a}.old{color:#aaa3b7}.new{color:#6b5bdf}@media(max-width:480px){body{padding:12px}.samples{grid-template-columns:1fr}}'''
doc='''<!doctype html><html lang="uk"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nambli — усі зміни</title><style>'''+css+''.join(styles)+'''</style><header><h1>Nambli: усі зміни для перевірки</h1><p>Кандидат 1.000 у всіх 12 накресленнях. Сірим показано публічну версію 0.7.4, фіолетовим — нову. Картки охоплюють усі додані символи, змінені контури й альтернативні форми. Оригінальна геометрія решти символів перевірена окремо.</p><p>Перевірте насамперед @, отвори ɬ / Ɬ у насичених накресленнях і нові літери. Рядки вище карток показують мовні підстановки та діакритику. Це матеріал для перегляду перед релізом.</p></header><div class="toolbar"><label>Накреслення <select id="face">'''+''.join(f'<option>{face}</option>'for face in faces)+'''</select></label><label>Показати <select id="kind"><option value="all">Усі зміни</option><option value="changed">Змінені наявні символи</option><option value="new">Додані символи</option><option value="alternate">Альтернативні форми</option></select></label><label>Код / назва <input id="filter" placeholder="0040 або @"></label></div>'''+''.join(sections)+'''<script>const face=document.querySelector('#face'),kind=document.querySelector('#kind'),filter=document.querySelector('#filter');function show(){document.querySelectorAll('section').forEach(s=>s.hidden=s.dataset.face!==face.value);let q=filter.value.trim().toUpperCase().replace('U+','');document.querySelectorAll('article').forEach(a=>a.hidden=!a.dataset.code.includes(q)||(kind.value!=='all'&&a.dataset.kind!==kind.value))}face.value='Nambli-Regular';[face,kind].forEach(e=>e.addEventListener('change',show));filter.addEventListener('input',show);show()</script></html>'''
(args.output/'Nambli-Technical-Review.html').write_text(doc,encoding='utf-8')
(args.output/'review-manifest.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps({'faces':len(faces),'cards':sum(map(len,audit.values())),'html':str(args.output/'Nambli-Technical-Review.html')}))
