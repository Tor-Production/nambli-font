# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Review the owner's selective 1.003 revision without altering the 1.002 review.

Reuses the offline SVG viewer, but distinguishes newly changed glyphs from
deliberately retained accent designs. Counts come from compiled fonts/reports.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote

from make_visual_quality_review import PAGE, read_font, is_diacritic

FOCUS = list('ĽľďťaeoЯ@ÇĞİÖŞÜçğıöşü') + ['.notdef']
MARKS = {'uni013D', 'uni013E', 'uni010F', 'uni0165', 'uni030C.alt'}
TURKISH = set(map(ord, 'ÇĞİÖŞÜçğıöşü'))


def face_data(before_path, after_path, body_dir, mark_dir, preservation_dir, audit_dir):
    before, after = read_font(before_path), read_font(after_path)
    load = lambda directory: json.loads((directory / (after_path.stem + '.json')).read_text(encoding='utf-8'))
    body, mark, preservation = load(body_dir), load(mark_dir), load(preservation_dir)
    audit = load(audit_dir) if audit_dir else {}
    selected = set(body['selectedGlyphs'])
    strengthened = set(mark['changedGlyphs'])
    assert strengthened == MARKS
    retained = preservation.get('diacritics', {}).get('preservedGlyphs', preservation.get('preservedGlyphs', {}))
    records = []
    for name, new in after['glyphs'].items():
        old = before['glyphs'][name]
        cps = new['unicodes']
        changed = old['path'] != new['path']
        assert old['width'] == new['width'] and old['unicodes'] == cps
        assert not changed or name in selected | strengthened, name
        diacritic = name in retained or is_diacritic(name, cps) or name in strengthened
        keep = diacritic and name not in strengthened
        reasons = []
        categories = ['all']
        if name in selected:
            categories.append('optical')
            reasons.append('Прибрано додані оптичні виноси; згладжування збережено')
        if name in strengthened:
            categories.append('selective')
            reasons.append('Бічний гачок: штрих +30%, початковий вигин збережено')
        if diacritic:
            categories.append('diacritics')
        if keep:
            reasons.append('Дизайн діакритики збережено')
        if TURKISH.intersection(cps):
            categories.append('turkish')
        if name == '.notdef':
            categories.append('notdef')
        flags = audit.get('glyphs', {}).get(name, {}).get('flags', [])
        positioned = [f for f in flags if 'point' in f and f.get('severity') != 'intentional_corner_review']
        import unicodedata
        records.append(dict(name=name, unicodes=cps,
            description=' / '.join(unicodedata.name(chr(cp), 'UNNAMED') for cp in cps),
            before=old, after=new, changed=changed, outlineChanged=changed, metricChanged=False,
            categories=categories, reasons=reasons, bodyChanged=changed,
            retainedDiacritics=keep, selectivelyStrengthened=name in strengthened,
            pending=False, pendingReasons=[], deferredDiacritics=False,
            flagCount=len(flags), flags=positioned[:40]))
    return dict(name=after_path.stem, beforeVersion=before['version'], afterVersion=after['version'],
                beforeSha256=before['sha256'], afterSha256=after['sha256'],
                upm=after['upm'], xheight=after['xheight'], hasAudit=bool(audit), glyphs=records,
                changedCount=sum(g['changed'] for g in records),
                retainedCount=sum(g['retainedDiacritics'] for g in records),
                selectedMarkCount=len(strengthened), bodyRevisionCount=len(selected))


def replace_line(page, prefix, replacement):
    lines = page.splitlines()
    matches = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f'Expected one template line for {prefix}: {matches}')
    lines[matches[0]] = replacement
    return '\n'.join(lines)


def review_page():
    page = PAGE.replace('Nambli · перевірка плавності контурів', 'Nambli 1.003 · уточнення дизайну')
    page = page.replace('Плавні контури.<br>Усі зміни поруч.', 'Знайомі форми.<br>Плавні контури.')
    page = page.replace('Порівняйте попередню та нову форму в кожному накресленні. Почніть із прикладів нижче, а потім перевірте решту символів. Клік по картці відкриває збільшений перегляд.', 'Порівняння 1.002 → 1.003 у всіх 12 накресленнях. Додані оптичні виноси прибрано. Бічні гачки у Ľ, ľ, ď, ť трохи потовщено. Клік по картці відкриває збільшений перегляд.')
    page = page.replace('<option value="contours">Змінені контури</option>', '<option value="selective">Потовщені бічні гачки</option><option value="turkish">Турецька абетка · контроль</option>')
    page = page.replace('<option value="optical">Оптичні виноси</option>', '<option value="optical">Прибрані виноси</option>')
    page = page.replace('aria-label="Стан роботи"', 'aria-label="Розділ перегляду"')
    page = page.replace('>Залишилося</button>', '>Збережена діакритика</button>')
    page = page.replace('>Зроблено</button>', '>Оновлено</button>')
    page = page.replace('Зроблено · змінені контури', 'Оновлено у 1.003')
    page = page.replace('Å Ǻ Ǻ Ǟ ắ ǘ · e r k s · Україна', 'ÇĞİÖŞÜ çğıöşü · Å Ǻ Ǟ ắ ǘ · Україна')
    page = page.replace('Оптичні виноси визначено за зміною меж біля базової лінії та x-height.', 'Групу прибраних виносів визначено за точним звітом змін. Збережена діакритика — свідоме рішення щодо дизайну, а не незавершений список робіт.')
    page = page.replace('<h2>У тексті</h2>', '<h2>У тексті</h2><p class="focus-hint">Три версії поруч у готових зразках: <a class="review-link" href="Light-1.003.png">Light</a> · <a class="review-link" href="Regular-1.003.png">Regular</a>. Також <a class="review-link" href="ExtraBoldItalic-1.003.png">ExtraBold Italic: до / після</a>.</p>')
    page = replace_line(page, "$('scope-status').textContent=", "$('scope-status').textContent='Згладжування збережено. Інші акценти, зокрема турецькі, залишено у попередньому дизайні. Тут можна окремо переглянути змінені символи та збережену діакритику.';")
    page = replace_line(page, 'function card(', "function card(g){const status=g.selectivelyStrengthened?'Гачок потовщено':g.changed?'Оновлено':'Збережено';return '<article class=\"card\" tabindex=\"0\" role=\"button\" data-glyph=\"'+esc(g.name)+'\" aria-label=\"Відкрити '+esc(g.name)+'\"><div class=\"card-head\"><div><div class=\"glyph-name\">'+esc(g.name)+'</div><div class=\"glyph-codes\">'+(g.unicodes.map(code).join(' · ')||'Не закодований у Unicode')+'</div></div><span class=\"tag '+(g.changed?'':'unchanged')+'\">'+status+'</span></div>'+art(g)+'<div class=\"card-foot\">'+esc(g.description||g.name)+'<div class=\"reason\">'+esc(g.reasons.join(' · '))+'</div></div></article>';}")
    page = replace_line(page, 'function renderFocus(', "function renderFocus(){const records=focusRecords().filter(g=>activeTab==='pending'?g.retainedDiacritics:g.changed);$('focus-title').textContent=activeTab==='pending'?'Приклади збереженої діакритики':'Приклади оновлень';$('focus-grid').innerHTML=records.slice(0,allFocus?records.length:8).map(card).join('');$('more-focus').textContent=allFocus?'Згорнути приклади':'Усі '+records.length+' прикладів';}")
    page = replace_line(page, 'function filtered(', "function filtered(){const query=$('search').value.trim().toLowerCase(),category=$('category').value;return active.glyphs.filter(g=>(activeTab==='pending'?g.retainedDiacritics:(!$('changed').checked||g.changed))&&g.categories.includes(category)&&(!query||g.name.toLowerCase().includes(query)||g.description.toLowerCase().includes(query)||g.unicodes.some(cp=>code(cp).toLowerCase().includes(query)||String.fromCodePoint(cp).toLowerCase()===query)));}")
    page = replace_line(page, 'function renderGrid(', "function renderGrid(){if(!active)return;const records=filtered(),size=Number($('page-size').value),pages=Math.max(1,Math.ceil(records.length/size));page=Math.min(page,pages-1);$('glyph-grid').innerHTML=records.length?records.slice(page*size,(page+1)*size).map(card).join(''):'<div class=\"empty\">За цими умовами символів немає. Змініть групу або вимкніть «Лише змінені».</div>';$('result-count').textContent='Знайдено '+records.length+' із '+active.glyphs.length;$('results-title').textContent=activeTab==='pending'?'Збережена діакритика':$('changed').checked?'Оновлено у 1.003':'Увесь шрифт';$('tab-done').textContent='Оновлено · '+active.changedCount;$('tab-pending').textContent='Збережена діакритика · '+active.retainedCount;$('tab-explanation').textContent=activeTab==='pending'?'Акценти у цих символах залишено у попередній формі. У частини літер прибрано додані виноси тіла — це видно у порівнянні.':'Прибрані виноси та вибірково потовщені гачки. Для контрольних символів вимкніть «Лише змінені».';$('page-label').textContent='Сторінка '+(page+1)+' / '+pages;$('previous').disabled=page===0;$('next').disabled=page===pages-1;}")
    page = page.replace("location.hash==='#pending'", "location.hash==='#retained'")
    page = replace_line(page, "for(const id of ['category','changed','search','page-size'])", "for(const id of ['category','changed','search','page-size'])$(id).addEventListener(id==='search'?'input':'change',()=>{if(id==='category'&&activeTab==='done'&&['turkish','notdef'].includes($('category').value))$('changed').checked=false;page=0;renderGrid();});")
    return page


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'body-reports', 'mark-reports', 'preservation-reports', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--audit-reports', type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output / 'data').mkdir(exist_ok=True)
    manifest = dict(schema=2, version='1.003', faces=[], allGlyphFacePairs=0, changedGlyphFacePairs=0,
                    source='SVG outlines from actual compiled TTFs', visualApproval='PENDING_OWNER_REVIEW',
                    diacriticsStatus='SELECTIVE_REFINEMENT_OTHER_DESIGNS_RETAINED',
                    generatorSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    paths = sorted(a.after.glob('Nambli-*.ttf'))
    assert len(paths) == 12
    for index, path in enumerate(paths):
        face = face_data(a.before / path.name, path, a.body_reports, a.mark_reports, a.preservation_reports, a.audit_reports)
        for label, folder in [('before', a.before), ('after', a.after)]:
            face[label + 'FontUrl'] = quote(os.path.relpath(folder / path.name, a.output).replace('\\', '/'), safe='/:')
        asset = f'data/face-{index:02d}.js'
        payload = json.dumps(face, ensure_ascii=True, separators=(',', ':')).replace('<', '\\u003c')
        (a.output / asset).write_text(f'window.registerNambliFace({index},{payload});\n', encoding='utf-8')
        manifest['faces'].append({k:v for k,v in face.items() if k != 'glyphs'} | {'asset':asset})
        manifest['allGlyphFacePairs'] += len(face['glyphs'])
        manifest['changedGlyphFacePairs'] += face['changedCount']
    page = review_page().replace('__MANIFEST__', json.dumps(manifest, ensure_ascii=True)).replace('__FOCUS__', json.dumps(FOCUS))
    target = a.output / 'Nambli-Design-Review.html'
    target.write_text(page, encoding='utf-8')
    (a.output / 'review-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(html=str(target), faces=len(paths), changedGlyphFacePairs=manifest['changedGlyphFacePairs'])))


if __name__ == '__main__':
    main()
