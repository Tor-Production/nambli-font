# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Keep deferred diacritics exactly intact while repairing separate letter bodies."""
import unicodedata as ud
from smooth_contours import ContourPen,_area,_polyline
SPACING={0x60,0xB4,0xA8,0xAF,0xB8,0x2C6,0x2C7,0x2D8,0x2D9,0x2DA,0x2DB,0x2DC,0x2DD}

def _descriptor(contour):
    points=[p for segment in contour for p in segment]
    return (min(p.real for p in points),min(p.imag for p in points),
            max(p.real for p in points),max(p.imag for p in points),
            abs(_area(_polyline(contour,.1,5)[0]))**.5)

def preserved_contours(font,glyph,cmap):
    """Return original contour indices to retain, plus a review disposition.

    Disconnected accents stay byte-for-byte in the editable source. Connected
    accents are deferred as whole glyphs because changing their outer boundary
    would also change the paused diacritic design. Matching is conservative;
    uncertain decompositions are deferred instead of guessed.
    """
    all_indices=list(range(len(glyph.contours)))
    cps=glyph.unicodes
    if any(cp in {0x1C4,0x1C5,0x1C6} for cp in cps):
        return all_indices,{'status':'DEFERRED','reason':'accented_digraph','wholeGlyph':True}
    if glyph.name=='uni030C.alt' or any(ud.category(chr(cp)).startswith('M') or cp in SPACING for cp in cps):
        return all_indices,{'status':'DEFERRED','reason':'standalone_diacritic','wholeGlyph':True}
    if glyph.name in {'uni012F.dotless','uni1E2D.dotless','uni1ECB.dotless','uni0439.loclBGR'}:
        return all_indices,{'status':'DEFERRED','reason':'diacritic_alternate','wholeGlyph':True}
    sequences=[ud.normalize('NFD',chr(cp)) for cp in cps]
    nfd=next((s for s in sequences if len(s)>1 and all(ud.category(c).startswith('M') for c in s[1:])),None)
    if nfd is None:return [],{}
    if any(ord(c) in {0x327,0x328,0x31B} for c in nfd[1:]):
        return all_indices,{'status':'DEFERRED','reason':'connected_diacritic','wholeGlyph':True}
    base_name=cmap.get(ord(nfd[0]))
    if nfd[0]=='i' and any(ud.combining(c)==230 for c in nfd[1:]):base_name='idotless.alt'
    if nfd[0]=='j' and any(ud.combining(c)==230 for c in nfd[1:]):base_name=cmap.get(0x237)
    if nfd[0]=='і' and any(ud.combining(c)==230 for c in nfd[1:]):base_name='uni0456.dotless'
    if not base_name or base_name not in font:
        return all_indices,{'status':'DEFERRED','reason':'unresolved_base','wholeGlyph':True}
    base=ContourPen();font[base_name].draw(base)
    combined=ContourPen();glyph.draw(combined)
    if len(combined.contours)<=len(base.contours):
        return all_indices,{'status':'DEFERRED','reason':'inseparable_contours','wholeGlyph':True}
    available=set(range(len(combined.contours)));selected=[];scores=[]
    descriptions=[_descriptor(c) for c in combined.contours]
    for contour in base.contours:
        d=_descriptor(contour)
        best=min(available,key=lambda i:sum(abs(a-b) for a,b in zip(d,descriptions[i])))
        score=sum(abs(a-b) for a,b in zip(d,descriptions[best]))
        if score>30:
            return all_indices,{'status':'DEFERRED','reason':'uncertain_body_match','wholeGlyph':True,'score':score}
        selected.append(best);scores.append(score);available.remove(best)
    return sorted(available),{'status':'DIACRITICS_DEFERRED_BODY_REPAIRED','base':base_name,
                             'preservedContours':sorted(available),'matchingScores':scores,'wholeGlyph':False}
