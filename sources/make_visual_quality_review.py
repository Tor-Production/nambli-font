# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Build a local, interactive Ukrainian review of actual before/after TTFs.

Per-face SVG data loads through ordinary local script assets, so the review
works from file:// without a server, external fonts, or fetch permissions.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import unicodedata
from urllib.parse import quote

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont


FOCUS = ['e', 'r', 'k', 's', '\u013d', '\u013e', '\u010f', '\u0165',
         '\u00c5', '\u01fa', '\u1ecd', 'o', 'O', '.notdef']
MARK_NAMES = ('acute', 'grave', 'caron', 'breve', 'circumflex', 'dieresis',
              'tilde', 'macron', 'cedilla', 'ogonek', 'dotaccent', 'dotbelow',
              'hookabove', 'ringabove', 'horn', 'commaaccent', 'doubleacute')


def read_font(path):
    with TTFont(path) as font:
        glyph_set = font.getGlyphSet()
        unicodes = defaultdict(list)
        for codepoint, name in font.getBestCmap().items():
            unicodes[name].append(codepoint)
        glyphs = {}
        for name in font.getGlyphOrder():
            pen = SVGPathPen(glyph_set)
            glyph_set[name].draw(pen)
            bounds = BoundsPen(glyph_set)
            glyph_set[name].draw(bounds)
            glyphs[name] = {'path': pen.getCommands(), 'bounds': bounds.bounds,
                            'width': font['hmtx'][name][0], 'unicodes': unicodes.get(name, [])}
        xheight = getattr(font['OS/2'], 'sxHeight', 0) or (
            glyphs.get('x', {}).get('bounds', [0, 0, 0, 530]) or [0, 0, 0, 530])[3]
        return {'glyphs': glyphs, 'version': f"{font['head'].fontRevision:.3f}",
                'upm': font['head'].unitsPerEm, 'xheight': xheight,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def is_diacritic(name, codepoints):
    if any(part in name.lower() for part in MARK_NAMES):
        return True
    return any(unicodedata.category(chr(cp)).startswith('M') or
               any(unicodedata.category(char).startswith('M')
                   for char in unicodedata.normalize('NFD', chr(cp))) for cp in codepoints)


def make_face(before_path, after_path, reports, audit_reports=None):
    old, new = read_font(before_path), read_font(after_path)
    report_path = reports / (after_path.stem + '.json') if reports else None
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path and report_path.exists() else {}
    audit = report if isinstance(report.get('glyphs'), dict) else {}
    if audit_reports:
        audit_path = audit_reports / (after_path.stem + '.json')
        if audit_path.exists():
            audit = json.loads(audit_path.read_text(encoding='utf-8'))
    changed_diacritics = report.get('diacritics', {}).get('changedGlyphs', {})
    preserved_glyphs = report.get('diacritics', {}).get('preservedGlyphs', report.get('preservedGlyphs', {}))
    operation_details = report.get('details', {})
    audit_glyphs = audit.get('glyphs', {})
    names = list(old['glyphs']) + [n for n in new['glyphs'] if n not in old['glyphs']]
    records = []
    for name in names:
        before, after = old['glyphs'].get(name), new['glyphs'].get(name)
        codepoints = sorted(set((before or {}).get('unicodes', []) + (after or {}).get('unicodes', [])))
        outline_changed = (before or {}).get('path') != (after or {}).get('path')
        metric_changed = (before or {}).get('width') != (after or {}).get('width')
        changed = outline_changed or metric_changed or (before or {}).get('unicodes') != (after or {}).get('unicodes')
        categories = ['all']
        reasons = []
        operations = operation_details.get(name, {})
        preservation = preserved_glyphs.get(name, {})
        finalization = operations.get('finalization', {})
        remaining_joins = finalization.get('remainingJoins', [])
        remaining_crossings = finalization.get('remainingCrossings', [])
        join_count = len(remaining_joins) if isinstance(remaining_joins, (list, dict)) else int(remaining_joins or 0)
        crossing_count = len(remaining_crossings) if isinstance(remaining_crossings, (list, dict)) else int(remaining_crossings or 0)
        pending = bool(preservation) or bool(join_count or crossing_count)
        body_changed = changed and not preservation.get('wholeGlyph', False)
        pending_reasons = []
        if preservation:
            if preservation.get('wholeGlyph'):
                pending_reasons.append('Діакритику відкладено; весь символ збережено без змін.')
            elif body_changed:
                pending_reasons.append('Тіло виправлено; діакритику відкладено.')
            else:
                pending_reasons.append('Діакритику відкладено; оригінальні контури збережено.')
        if join_count or crossing_count:
            pending_reasons.append(f'Потрібна подальша перевірка: {join_count} з’єднань, {crossing_count} перетинів.')
        if is_diacritic(name, codepoints) or name in changed_diacritics or preservation:
            categories.append('diacritics')
        if name in changed_diacritics:
            reasons.append('Товщина / положення діакритики')
        if name == '.notdef':
            categories.append('notdef')
        smoothed = operations.get('smoothing', {}).get('changed') or operations.get('quantizedG1', {}).get('changed') or finalization.get('changed')
        if smoothed or (outline_changed and not operation_details):
            categories.append('contours')
        if smoothed:
            reasons.append('Плавність контурів')
        ob, nb = (before or {}).get('bounds'), (after or {}).get('bounds')
        if ob and nb and name != '.notdef' and not all(unicodedata.category(chr(cp)).startswith('M') for cp in codepoints or [65]):
            at_baseline = abs(ob[1]) <= 3 and nb[1] < ob[1] - 2
            at_xheight = abs(ob[3] - old['xheight']) <= 3 and nb[3] > ob[3] + 2
            if operations.get('optical', {}).get('overshoot') or ((at_baseline or at_xheight) and not operation_details):
                categories.append('optical')
                reasons.append('Оптичні виноси')
        if operations.get('optical', {}).get('missingGlyph'):
            reasons.append('Новий знак відсутнього символу')
        flags = audit_glyphs.get(name, {}).get('flags', [])
        positioned_flags = [f for f in flags if 'point' in f and f.get('severity') != 'intentional_corner_review']
        positioned_flags.sort(key=lambda f: (f.get('severity') != 'high', -f.get('angle_beyond_allowance_degrees', 0)))
        records.append({'name': name, 'unicodes': codepoints,
                        'description': ' / '.join(unicodedata.name(chr(cp), 'UNNAMED') for cp in codepoints),
                        'changed': changed, 'outlineChanged': outline_changed, 'metricChanged': metric_changed,
                        'categories': categories, 'reasons': reasons, 'before': before, 'after': after,
                        'bodyChanged': body_changed, 'pending': pending, 'pendingReasons': pending_reasons,
                        'deferredDiacritics': bool(preservation),
                        'preservedWholeGlyph': preservation.get('wholeGlyph', False),
                        'remainingJoins': join_count, 'remainingCrossings': crossing_count,
                        'flagCount': len(flags), 'flags': positioned_flags[:40]})
    return {'name': after_path.stem, 'beforeVersion': old['version'], 'afterVersion': new['version'],
            'beforeSha256': old['sha256'], 'afterSha256': new['sha256'],
            'upm': new['upm'], 'xheight': new['xheight'], 'hasAudit': bool(audit),
            'glyphs': records, 'changedCount': sum(r['changed'] for r in records),
            'doneCount': sum(r['bodyChanged'] for r in records), 'pendingCount': sum(r['pending'] for r in records)}


PAGE = r'''<!doctype html>
<html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nambli · перевірка плавності контурів</title>
<style>
:root{font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;color:#27243b;background:#f6f5fb;--old:#9a94a8;--new:#6756df;--glyph-height:215px}
*{box-sizing:border-box}body{margin:0}button,input,select{font:inherit}button,select,input[type=search]{border:1px solid #d5cfe5;border-radius:9px;background:white;color:inherit;padding:8px 11px}button{cursor:pointer}button:hover{background:#f0ecff}button:disabled{opacity:.42;cursor:default}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #b8adff;outline-offset:2px}header,main,footer{max-width:1500px;margin:auto;padding:22px 28px}header{padding-top:36px;padding-bottom:15px}h1{font-size:clamp(27px,4vw,43px);line-height:1.16;margin:0 0 12px;letter-spacing:-1px}h2{font-size:21px;margin:5px 0 13px}p{margin:8px 0}.eyebrow{font-size:12px;color:#6756b5;letter-spacing:1.6px;text-transform:uppercase;font-weight:700}.lead{max-width:920px;color:#645b78}.toolbar{position:sticky;top:0;z-index:4;border-top:1px solid #e4deef;border-bottom:1px solid #ded6ee;background:#f6f5fbf5;backdrop-filter:blur(12px);padding:13px 28px}.toolbar-inner{max-width:1444px;margin:auto;display:flex;gap:12px 16px;align-items:center;flex-wrap:wrap}.control{display:flex;gap:7px;align-items:center;white-space:nowrap;font-size:13px}.control.stack{display:grid;gap:4px}.grow{flex:1;min-width:210px}input[type=search]{width:100%}input[type=range]{width:125px;accent-color:var(--new)}input[type=checkbox]{accent-color:var(--new);width:16px;height:16px}select{max-width:245px}.stats{display:flex;gap:9px;flex-wrap:wrap;margin:16px 0}.badge{background:#eeebfa;border:1px solid #e0d9f4;color:#5c5279;border-radius:100px;padding:4px 11px;font-size:12px}.legend{display:flex;gap:18px;flex-wrap:wrap;color:#766b88;font-size:13px}.swatch{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px;background:var(--old)}.swatch.new{background:var(--new)}.swatch.guide{background:#9caaa7}.swatch.flag{background:#e49b2f}.section{margin:24px 0 34px}.section-head{display:flex;align-items:center;justify-content:space-between;gap:15px;flex-wrap:wrap}.small{font-size:12px;color:#827790}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(325px,1fr));gap:14px}.focus-grid{grid-template-columns:repeat(auto-fill,minmax(265px,1fr))}.card{background:white;border:1px solid #ded7ed;border-radius:15px;overflow:hidden;min-width:0;cursor:zoom-in;box-shadow:0 2px 8px #45317103}.card:focus-visible{outline:3px solid #b8adff;outline-offset:2px}.card-head{display:flex;justify-content:space-between;gap:6px;padding:14px 15px 7px;font-size:12px;color:#66577d}.glyph-name{font-weight:650;color:#3c3255;word-break:break-word}.glyph-codes{font-variant-numeric:tabular-nums;font-size:11px}.tag{font-size:10px;background:#f0ecfd;color:#6c58b8;border-radius:10px;padding:2px 6px;white-space:nowrap;align-self:flex-start}.tag.unchanged{background:#f2f2f4;color:#898190}.comparison{display:grid;grid-template-columns:1fr 1fr;gap:0;position:relative}.comparison.overlay{display:block}.side{min-width:0}.side-label{text-align:center;font-size:10px;letter-spacing:.3px;color:#8a8097}.side-label.after{color:#7761c9}.glyph-svg{display:block;width:100%;height:var(--glyph-height);overflow:visible}.card-foot{padding:7px 15px 12px;color:#8b8099;font-size:10px;border-top:1px solid #f3eff9;min-height:33px;word-break:break-word}.guide-line{stroke:#9eaca8;stroke-width:1;vector-effect:non-scaling-stroke;stroke-dasharray:4 4;opacity:.55}.guide-label{font-size:28px;fill:#899994;font-family:system-ui;opacity:.8}.before-path{fill:var(--old)}.after-path{fill:var(--new)}.overlay .before-path{fill:#ea9778;opacity:.56}.overlay .after-path{fill:#6756df;opacity:.66}.flag-dot{fill:#ffbf3f90;stroke:#9f6717;stroke-width:1;vector-effect:non-scaling-stroke}.empty{padding:45px;text-align:center;border:1px dashed #cdc4e1;border-radius:15px;color:#7b6c90;background:#ffffff6b;grid-column:1/-1}.pagination{display:flex;justify-content:center;align-items:center;gap:14px;margin:20px 0;flex-wrap:wrap}.busy{opacity:.4;pointer-events:none}#message{min-height:23px;margin:10px 0;color:#705b91;font-size:13px}.error{color:#b22b3a!important}.focus-hint{margin:0 0 14px;color:#847791;font-size:12px}.footer-note{max-width:1050px;color:#8b8199;font-size:12px}dialog{border:1px solid #d5ccec;border-radius:20px;padding:22px;max-width:min(1150px,96vw);width:100%;max-height:95vh;overflow:auto;box-shadow:0 30px 120px #33244b50;background:#fff}dialog::backdrop{background:#21183188;backdrop-filter:blur(4px)}.modal-head{display:flex;align-items:center;justify-content:space-between;gap:20px}.modal-head h2{margin:0;word-break:break-word}.modal-compare .glyph-svg{height:min(57vh,610px)}.modal-meta{background:#f8f6fc;border-radius:10px;padding:12px;font-size:12px;color:#6d5f80}.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;word-break:break-all}#modal-flags{font-size:11px;color:#8a713f;max-height:140px;overflow:auto;margin-top:12px}.review-link{color:#6756df;text-decoration:none}.review-link:hover{text-decoration:underline}.loading{padding:50px;color:#7d6e91;text-align:center}kbd{font-size:10px;border:1px solid #dcd4e9;border-radius:4px;padding:1px 4px;background:#f8f6fc}@media(max-width:700px){header,main,footer{padding-left:14px;padding-right:14px}.toolbar{padding:10px 14px}.toolbar-inner{gap:9px}.grid,.focus-grid{grid-template-columns:repeat(auto-fill,minmax(265px,1fr))}.control{font-size:12px}.control.stack{max-width:48%}select{max-width:100%;min-width:0}.grow{min-width:100%}.section{margin-top:15px}h1{letter-spacing:-.5px}.glyph-svg{height:180px}.modal-compare .glyph-svg{height:320px}dialog{padding:15px}}
.specimen-input{width:100%;min-height:83px;border:1px solid #d5cfe5;border-radius:10px;padding:12px;font:14px/1.5 system-ui;color:#443654;background:#fff;resize:vertical}.text-pair{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:13px}.text-block{border:1px solid #ded7ed;border-radius:14px;padding:18px;background:#fff;overflow:auto}.specimen{font-size:36px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere;font-synthesis:none}.specimen.old{color:var(--old)}.specimen.new{color:var(--new)}.text-pair.loading-font .specimen{visibility:hidden}.reason{color:#7962b2;font-size:10px;margin-top:3px}.pending-note{color:#946222;font-size:11px;padding-top:5px}.tabs{display:flex;gap:7px;margin:15px 0 8px}.tabs button{padding:10px 21px;border-radius:10px;font-weight:650}.tabs button[aria-selected=true]{background:#6756df;color:white;border-color:#6756df}.tab-explanation{color:#7e708e;font-size:12px;margin:5px 0 15px}.tag.pending{background:#fff0d6;color:#916121}.tag.partial{background:#eaf1ff;color:#586f9f}@media(max-width:700px){.text-pair{grid-template-columns:1fr}.specimen{font-size:29px}}
</style></head><body>
<header><div class="eyebrow">Nambli · візуальний перегляд</div><h1>Плавні контури.<br>Усі зміни поруч.</h1><p class="lead">Порівняйте попередню та нову форму в кожному накресленні. Почніть із прикладів нижче, а потім перевірте решту символів. Клік по картці відкриває збільшений перегляд.</p><p class="lead" id="scope-status"></p><div class="legend"><span><i class="swatch"></i>До</span><span><i class="swatch new"></i>Після · кандидат</span><span><i class="swatch guide"></i>Базова лінія та x-height</span></div></header>
<div class="toolbar"><div class="toolbar-inner">
<label class="control stack">Накреслення<select id="face"></select></label>
<label class="control stack">Група<select id="category"><option value="all">Усі символи</option><option value="diacritics">Діакритика та літери з нею</option><option value="contours">Змінені контури</option><option value="optical">Оптичні виноси</option><option value="notdef">Знак відсутнього символу</option></select></label>
<label class="control grow"><input id="search" type="search" placeholder="Пошук: літера, U+013D, .notdef, caron…" aria-label="Пошук символу"></label>
<label class="control"><input type="checkbox" id="changed" checked>Лише змінені</label>
<label class="control"><input type="checkbox" id="overlay">Накладання</label>
<label class="control"><input type="checkbox" id="guides" checked>Лінії</label>
<label class="control"><input type="checkbox" id="flags">Позначки аудиту</label>
<label class="control">Масштаб<input type="range" id="zoom" min="120" max="410" value="215" step="5"><output id="zoom-value">215</output></label>
</div></div>
<main><div id="message" role="status" aria-live="polite"></div><div class="stats" id="stats"></div>
<section class="section"><h2>У тексті</h2><p class="focus-hint">Тут використовуються самі файли шрифту: можна перевірити акценти, інтервали та поєднання знаків. Текст можна змінювати.</p><textarea id="specimen-input" class="specimen-input" aria-label="Текст для порівняння">Ľavý ľad ďalej ťava · ľľ ďd ťt
Å Ǻ Ǻ Ǟ ắ ǘ · e r k s · Україна
Намблі — округлі літери, плавні лінії.</textarea><p id="specimen-status" class="small" role="status"></p><div class="text-pair loading-font" id="text-pair"><div class="text-block"><div class="side-label">До</div><div id="specimen-before" class="specimen old"></div></div><div class="text-block"><div class="side-label after">Після · кандидат</div><div id="specimen-after" class="specimen new"></div></div></div></section>
<section class="section"><div class="section-head"><h2 id="focus-title">Основні приклади</h2><button id="more-focus" type="button">Усі приклади</button></div><p class="focus-hint">Добірка для вибраного розділу; повний список символів — нижче.</p><div id="focus-grid" class="grid focus-grid"></div></section>
<section class="section"><div class="tabs" role="tablist" aria-label="Стан роботи"><button type="button" id="tab-done" role="tab" aria-selected="true">Зроблено</button><button type="button" id="tab-pending" role="tab" aria-selected="false">Залишилося</button></div><p class="tab-explanation" id="tab-explanation"></p><div class="section-head"><h2 id="results-title">Зроблено · змінені контури</h2><span class="small" id="result-count"></span></div><div id="glyph-grid" class="grid"><div class="loading">Завантаження контурів…</div></div><div class="pagination"><button type="button" id="previous">← Попередні</button><span id="page-label" class="small"></span><button type="button" id="next">Наступні →</button><select id="page-size" aria-label="Кількість на сторінці"><option value="24">24 на сторінці</option><option value="48">48 на сторінці</option><option value="96">96 на сторінці</option></select></div></section>
</main><footer><p class="footer-note">Контури зчитано безпосередньо з файлів TTF. Для знаків із нульовою шириною використано центрування за видимим контуром. Оптичні виноси визначено за зміною меж біля базової лінії та x-height. Позначки аудиту вказують місця для візуальної оцінки; природні з’єднання та округлення також можуть потрапляти до них.</p><p class="footer-note"><a class="review-link" href="review-manifest.json">Дані збірки та SHA-256</a></p></footer>
<dialog id="detail"><div class="modal-head"><h2 id="modal-title"></h2><button id="close-modal" type="button" aria-label="Закрити">Закрити <kbd>Esc</kbd></button></div><p class="small" id="modal-description"></p><div id="modal-art" class="modal-compare"></div><div id="modal-meta" class="modal-meta"></div><div id="modal-flags"></div></dialog>
<script>
const MANIFEST=__MANIFEST__;
const FOCUS=__FOCUS__;
const $=id=>document.getElementById(id);
$('scope-status').textContent=MANIFEST.diacriticsStatus==='deferred'?'Контури, оптичні виноси та знак відсутнього символу підготовлено для перегляду. Збільшення товщини діакритики відкладено.':'Цей кандидат також містить зміни товщини діакритики для візуального погодження.';
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cache=new Map();let active=null,currentFace=0,page=0,allFocus=false,selected=null,loadToken=0,activeTab='done',savedChangedOnly=true;
const code=cp=>'U+'+cp.toString(16).toUpperCase().padStart(4,'0');
function viewBox(record){
 const both=[record.before,record.after].filter(Boolean),ink=both.map(v=>v.bounds).filter(Boolean),upm=active.upm;
 if(!ink.length)return[-upm*.15,-upm*.85,upm*.8,upm*1.1];
 let left=Math.min(...ink.map(b=>b[0])),right=Math.max(...ink.map(b=>b[2]));
 const zero=both.every(v=>v.width===0);
 if(!zero){left=Math.min(left,0);right=Math.max(right,...both.map(v=>v.width));}
 const top=Math.max(upm*.84,...ink.map(b=>b[3])),bottom=Math.min(-upm*.18,...ink.map(b=>b[1]));
 const pad=upm*.065,width=Math.max(right-left,upm*.2);
 return[left-pad,-top-pad,width+pad*2,top-bottom+pad*2];
}
function guides(box){if(!$('guides').checked)return'';return[0,active.xheight].map((y,i)=>'<line class="guide-line" x1="'+box[0]+'" x2="'+(box[0]+box[2])+'" y1="'+(-y)+'" y2="'+(-y)+'"/><text class="guide-label" x="'+(box[0]+5)+'" y="'+(-y-8)+'">'+(i?'x':'0')+'</text>').join('');}
function markers(record){if(!$('flags').checked||!record.flags.length)return'';return record.flags.map(f=>'<circle class="flag-dot" cx="'+f.point[0]+'" cy="'+(-f.point[1])+'" r="'+(active.upm*.012)+'"><title>'+esc(f.kind+' · '+f.point.join(', '))+'</title></circle>').join('');}
function svg(record,mode){const box=viewBox(record);let paths='';if(mode==='before'||mode==='overlay')paths+='<path class="before-path" transform="scale(1 -1)" d="'+esc(record.before?.path??'')+'"/>';if(mode==='after'||mode==='overlay')paths+='<path class="after-path" transform="scale(1 -1)" d="'+esc(record.after?.path??'')+'"/>';return'<svg class="glyph-svg" viewBox="'+box.join(' ')+'" aria-label="'+esc(record.name+' '+mode)+'" role="img">'+guides(box)+paths+(mode!=='before'?markers(record):'')+'</svg>';}
function art(record){if($('overlay').checked)return'<div class="comparison overlay"><div class="side-label">До · помаранчевий / після · фіолетовий</div>'+svg(record,'overlay')+'</div>';return'<div class="comparison"><div class="side"><div class="side-label">До · '+esc(active.beforeVersion)+'</div>'+svg(record,'before')+'</div><div class="side"><div class="side-label after">Після · '+esc(active.afterVersion)+'</div>'+svg(record,'after')+'</div></div>';}
function card(record){const status=record.pending?(record.bodyChanged?'Частково зроблено':record.deferredDiacritics?'Відкладено':'Доопрацювати'):record.changed?(record.metricChanged?'Контур / метрики':'Зроблено'):'Без змін';const tagClass=record.pending?(record.bodyChanged?'partial':'pending'):(record.changed?'':'unchanged');return'<article class="card" tabindex="0" role="button" data-glyph="'+esc(record.name)+'" aria-label="Відкрити '+esc(record.name)+'"><div class="card-head"><div><div class="glyph-name">'+esc(record.name)+'</div><div class="glyph-codes">'+(record.unicodes.map(code).join(' · ')||'Не закодований у Unicode')+'</div></div><span class="tag '+tagClass+'">'+status+'</span></div>'+art(record)+'<div class="card-foot">'+esc(record.description||record.name)+(record.reasons.length?'<div class="reason">'+esc(record.reasons.join(' · '))+'</div>':'')+(record.pendingReasons.length?'<div class="pending-note">'+esc(record.pendingReasons.join(' '))+'</div>':'')+(active.hasAudit&&record.flagCount?' · '+record.flagCount+' позначок аудиту':'')+'</div></article>';}
function focusRecords(){return FOCUS.map(symbol=>symbol==='.notdef'?active.glyphs.find(g=>g.name==='.notdef'):active.glyphs.find(g=>g.unicodes.includes(symbol.codePointAt(0)))).filter(Boolean);}
function renderFocus(){const records=focusRecords().filter(g=>activeTab==='pending'?g.pending:g.bodyChanged);$('focus-title').textContent=activeTab==='pending'?'Приклади відкладеного':'Приклади зробленого';$('focus-grid').innerHTML=records.slice(0,allFocus?records.length:8).map(card).join('');$('more-focus').textContent=allFocus?'Згорнути приклади':'Усі '+records.length+' прикладів';}
function filtered(){const query=$('search').value.trim().toLowerCase(),category=$('category').value;return active.glyphs.filter(g=>(activeTab==='pending'?g.pending:(!$('changed').checked||g.bodyChanged))&&g.categories.includes(category)&&(!query||g.name.toLowerCase().includes(query)||g.description.toLowerCase().includes(query)||g.unicodes.some(cp=>code(cp).toLowerCase().includes(query)||String.fromCodePoint(cp).toLowerCase()===query)));}
function renderGrid(){if(!active)return;const records=filtered(),size=Number($('page-size').value),pages=Math.max(1,Math.ceil(records.length/size));page=Math.min(page,pages-1);$('glyph-grid').innerHTML=records.length?records.slice(page*size,(page+1)*size).map(card).join(''):'<div class="empty">За цими умовами символів немає. Спробуйте іншу групу чи пошуковий запит.</div>';$('result-count').textContent='Знайдено '+records.length+' із '+active.glyphs.length;$('results-title').textContent=activeTab==='pending'?'Залишилося · відкладені та незавершені':$('changed').checked?'Зроблено · змінені контури':'Увесь шрифт · включно з контрольними символами';$('tab-done').textContent='Зроблено · '+active.doneCount;$('tab-pending').textContent='Залишилося · '+active.pendingCount;$('tab-explanation').textContent=activeTab==='pending'?'Тут показано також незмінені символи. Літера може бути в обох розділах, якщо тіло виправлено, а діакритику відкладено.':'Змінені тіла літер, оптичні виноси та .notdef. Щоб додати незмінені символи для контролю, вимкніть «Лише змінені».';$('page-label').textContent='Сторінка '+(page+1)+' / '+pages;$('previous').disabled=page===0;$('next').disabled=page===pages-1;}
function selectTab(tab){if(tab===activeTab)return;if(tab==='pending'){savedChangedOnly=$('changed').checked;$('changed').checked=false;$('changed').disabled=true;}else{$('changed').checked=savedChangedOnly;$('changed').disabled=false;}activeTab=tab;page=0;$('tab-done').setAttribute('aria-selected',String(tab==='done'));$('tab-pending').setAttribute('aria-selected',String(tab==='pending'));$('category').value='all';$('search').value='';renderAll();}
function renderAll(){if(!active)return;renderFocus();renderGrid();if(selected)renderModal();}
function specimenText(){const text=$('specimen-input').value;$('specimen-before').textContent=text;$('specimen-after').textContent=text;}
async function loadSpecimen(){const index=currentFace,token=loadToken;const before='nambli-before-'+index,after='nambli-after-'+index;if(!document.getElementById('font-style-'+index)){const style=document.createElement('style');style.id='font-style-'+index;style.textContent='@font-face{font-family:"'+before+'";src:url("'+active.beforeFontUrl+'") format("truetype");font-display:block}@font-face{font-family:"'+after+'";src:url("'+active.afterFontUrl+'") format("truetype");font-display:block}';document.head.appendChild(style);}$('specimen-before').style.fontFamily='"'+before+'"';$('specimen-after').style.fontFamily='"'+after+'"';$('text-pair').classList.add('loading-font');$('specimen-status').textContent='Завантаження файлів шрифту для тексту…';specimenText();try{const loaded=await Promise.all([document.fonts.load('36px "'+before+'"'),document.fonts.load('36px "'+after+'"')]);if(token!==loadToken)return;if(!loaded.every(list=>list.length))throw Error('Missing local font');$('text-pair').classList.remove('loading-font');$('specimen-status').textContent='Текст відображається завантаженими файлами '+active.name+'.';}catch(error){if(token===loadToken)$('specimen-status').textContent='Текстові файли шрифту недоступні. Перевірте їх розташування; SVG-картки нижче залишаються доступними.';}}
function updateFace(){const info=MANIFEST.faces[currentFace];$('stats').innerHTML='<span class="badge">'+esc(active.name)+'</span><span class="badge">'+active.changedCount+' змінених із '+active.glyphs.length+'</span><span class="badge">'+esc(active.beforeVersion)+' → '+esc(active.afterVersion)+'</span><span class="badge">'+MANIFEST.faces.length+' накреслень</span>';$('flags').disabled=!active.hasAudit;if(!active.hasAudit)$('flags').checked=false;$('message').textContent=active.hasAudit?'Позначки аудиту доступні. Вони показують місця для перевірки, зокрема можливі природні з’єднання.':'Контури завантажено. У цьому наборі немає під’єднаних позначок автоматичного аудиту.';$('message').className='';page=0;selected=null;if($('detail').open)$('detail').close();renderAll();loadSpecimen();document.querySelector('main').classList.remove('busy');}
window.registerNambliFace=(index,data)=>{cache.set(index,data);if(index===currentFace){active=data;updateFace();}};
function loadFace(index){currentFace=index;++loadToken;$('message').textContent='Завантаження накреслення…';document.querySelector('main').classList.add('busy');if(cache.has(index)){active=cache.get(index);updateFace();return;}const script=document.createElement('script');script.src=MANIFEST.faces[index].asset;script.onerror=()=>{if(currentFace===index){$('message').textContent='Не вдалося відкрити файл '+script.src+'. Тримайте HTML і папку data поруч.';$('message').className='error';document.querySelector('main').classList.remove('busy');}};document.head.appendChild(script);}
function renderModal(){if(!selected)return;$('modal-title').textContent=selected.name+' · '+active.name;$('modal-description').textContent=selected.unicodes.map(code).join(' · ')+' '+selected.description+' '+selected.pendingReasons.join(' ');$('modal-art').innerHTML=art(selected);const bounds=v=>v?.bounds?v.bounds.map(n=>Number(n.toFixed(2))).join(', '):'порожній контур';$('modal-meta').innerHTML='<strong>До:</strong> межі ['+bounds(selected.before)+'], ширина '+(selected.before?.width??'—')+'<br><strong>Після:</strong> межі ['+bounds(selected.after)+'], ширина '+(selected.after?.width??'—')+'<br><span class="small">Межі: xMin, yMin, xMax, yMax у координатах шрифту.</span>';$('modal-flags').innerHTML=selected.flagCount?'<strong>Позначки аудиту: '+selected.flagCount+'</strong><br>'+selected.flags.map(f=>esc(f.kind+' · ('+f.point.join(', ')+')'+(f.angle_degrees!==undefined?' · '+f.angle_degrees+'°':''))).join('<br>'):'';}
function openGlyph(name){selected=active.glyphs.find(g=>g.name===name);renderModal();$('detail').showModal();}
for(const container of [$('focus-grid'),$('glyph-grid')]){container.addEventListener('click',event=>{const target=event.target.closest('[data-glyph]');if(target)openGlyph(target.dataset.glyph);});container.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){const target=event.target.closest('[data-glyph]');if(target){event.preventDefault();openGlyph(target.dataset.glyph);}}});}
$('face').innerHTML=MANIFEST.faces.map((f,i)=>'<option value="'+i+'">'+esc(f.name.replace('Nambli-',''))+'</option>').join('');
$('face').addEventListener('change',()=>loadFace(Number($('face').value)));
$('specimen-input').addEventListener('input',specimenText);
$('tab-done').addEventListener('click',()=>selectTab('done'));
$('tab-pending').addEventListener('click',()=>selectTab('pending'));
for(const id of ['category','changed','search','page-size'])$(id).addEventListener(id==='search'?'input':'change',()=>{page=0;renderGrid();});
for(const id of ['overlay','guides','flags'])$(id).addEventListener('change',renderAll);
$('zoom').addEventListener('input',()=>{document.documentElement.style.setProperty('--glyph-height',$('zoom').value+'px');$('zoom-value').textContent=$('zoom').value;});
$('more-focus').addEventListener('click',()=>{allFocus=!allFocus;renderFocus();});
$('previous').addEventListener('click',()=>{page--;renderGrid();$('results-title').scrollIntoView({block:'center'});});
$('next').addEventListener('click',()=>{page++;renderGrid();$('results-title').scrollIntoView({block:'center'});});
$('close-modal').addEventListener('click',()=>{$('detail').close();selected=null;});
$('detail').addEventListener('close',()=>{selected=null;});
$('detail').addEventListener('click',event=>{if(event.target===$('detail')){const rect=$('detail').getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)$('detail').close();}});
if(location.hash==='#pending')selectTab('pending');
window.addEventListener('hashchange',()=>selectTab(location.hash==='#pending'?'pending':'done'));
const regular=MANIFEST.faces.findIndex(f=>f.name==='Nambli-Regular');$('face').value=String(regular<0?0:regular);loadFace(regular<0?0:regular);
</script></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reports', type=Path, help='Optional preparation or audit directory containing Nambli-STYLE.json files')
    parser.add_argument('--audit-reports', type=Path, help='Optional independent audit directory when --reports contains preparation records')
    parser.add_argument('--diacritics-status', choices=['deferred', 'included'], default='deferred',
                        help='Show whether separate accent strengthening is part of this candidate; default: deferred')
    args = parser.parse_args()
    paths = sorted(args.after.glob('*.ttf'))
    if not paths:
        parser.error('No candidate TTF files in --after')
    missing = [p.name for p in paths if not (args.before / p.name).is_file()]
    if missing:
        parser.error('Baseline is missing: ' + ', '.join(missing))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'data').mkdir(exist_ok=True)
    manifest = {'schema': 1, 'faces': [], 'allGlyphFacePairs': 0, 'changedGlyphFacePairs': 0,
                'diacriticsStatus': args.diacritics_status,
                'generatorSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'source': 'SVG paths read directly from compiled TTFs; no CSS fallback fonts',
                'visualApproval': 'NOT_DETERMINED_BY_THIS_REVIEW_PAGE'}
    for index, path in enumerate(paths):
        face = make_face(args.before / path.name, path, args.reports, args.audit_reports)
        face['beforeFontUrl'] = quote(os.path.relpath(args.before / path.name, args.output).replace('\\', '/'), safe='/:')
        face['afterFontUrl'] = quote(os.path.relpath(path, args.output).replace('\\', '/'), safe='/:')
        asset = f'data/face-{index:02d}.js'
        payload = json.dumps(face, separators=(',', ':'), ensure_ascii=True).replace('<', '\\u003c')
        (args.output / asset).write_text(f'window.registerNambliFace({index},{payload});\n', encoding='utf-8')
        manifest['faces'].append({k: v for k, v in face.items() if k != 'glyphs'} | {'asset': asset})
        manifest['allGlyphFacePairs'] += len(face['glyphs'])
        manifest['changedGlyphFacePairs'] += face['changedCount']
        print(json.dumps({'face': face['name'], 'glyphs': len(face['glyphs']), 'changed': face['changedCount']}), flush=True)
    page = PAGE.replace('__MANIFEST__', json.dumps(manifest, ensure_ascii=True).replace('<', '\\u003c')).replace('__FOCUS__', json.dumps(FOCUS))
    (args.output / 'Nambli-Visual-Quality-Review.html').write_text(page, encoding='utf-8')
    (args.output / 'review-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'faces': len(paths), 'allGlyphFacePairs': manifest['allGlyphFacePairs'],
                      'changedGlyphFacePairs': manifest['changedGlyphFacePairs'], 'html': str(args.output / 'Nambli-Visual-Quality-Review.html')}))


if __name__ == '__main__':
    main()
