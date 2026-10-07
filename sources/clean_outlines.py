"""Remove only mathematically redundant native outline points, never boolean-union ink.

Usage: python clean_outlines.py --input-dir INPUT --output-dir OUTPUT
FontTools is required; NAMBLI_PYTHON_DEPS can point to its local installation.
Outputs preserve relative font paths and include outline-cleanup-report.json.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
import os
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
if os.environ.get("NAMBLI_PYTHON_DEPS"):
    sys.path.insert(0, os.environ["NAMBLI_PYTHON_DEPS"])
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.t2CharStringPen import T2CharStringPen


def between(a, b, c):
    """Exact collinearity and betweenness; integers / dyadic values only."""
    return ((b[0]-a[0])*(c[1]-a[1]) == (b[1]-a[1])*(c[0]-a[0])
            and min(a[0], c[0]) <= b[0] <= max(a[0], c[0])
            and min(a[1], c[1]) <= b[1] <= max(a[1], c[1]))


class SegmentsPen(BasePen):
    """Expand implicit quadratic points without rounding; used only for proof."""
    def __init__(self, glyphset):
        super().__init__(glyphset)
        self.contours = []
        self.current = []
        self.start = None

    def _moveTo(self, p):
        self.start = tuple(p)
        self.current = []

    def _lineTo(self, p):
        self.current.append(("L", tuple(self._getCurrentPoint()), tuple(p)))

    def _qCurveToOne(self, p1, p2):
        self.current.append(("Q", tuple(self._getCurrentPoint()), tuple(p1), tuple(p2)))

    def _curveToOne(self, p1, p2, p3):
        self.current.append(("C", tuple(self._getCurrentPoint()), tuple(p1), tuple(p2), tuple(p3)))

    def _closePath(self):
        last = tuple(self._getCurrentPoint())
        if last != self.start:
            self.current.append(("L", last, self.start))
        self.contours.append(self.current)

    def _endPath(self):
        raise ValueError("Open outline contour is not supported")


def canonical_segments(segments):
    segments = [s for s in segments if not all(p == s[1] for p in s[2:])]
    changed = True
    while changed and len(segments) > 1:
        changed = False
        for i in range(len(segments)):
            j = (i + 1) % len(segments)
            a, b = segments[i], segments[j]
            if a[0] == b[0] == "L" and a[-1] == b[1] and between(a[1], a[-1], b[-1]):
                joined = ("L", a[1], b[-1])
                if j == 0:
                    segments = [joined] + segments[1:i]
                else:
                    segments = segments[:i] + [joined] + segments[j+1:]
                changed = True
                break
    if not segments:
        return ()
    return min(tuple(segments[i:] + segments[:i]) for i in range(len(segments)))


def geometry(font, name):
    gs = font.getGlyphSet()
    pen = SegmentsPen(gs)
    gs[name].draw(pen)
    return sorted(c for c in (canonical_segments(c) for c in pen.contours) if c)


def clean_glyf(font, name):
    glyph = font["glyf"][name]
    if glyph.isComposite() or glyph.numberOfContours <= 0:
        return []
    if getattr(glyph, "program", None) and glyph.program.getBytecode():
        raise ValueError(f"{name}: point-indexed hinting prevents safe cleanup")
    contours, events, start = [], [], 0
    for ci, end in enumerate(glyph.endPtsOfContours):
        points = [(tuple(glyph.coordinates[i]), int(glyph.flags[i])) for i in range(start, end+1)]
        start = end + 1
        while points:
            if all(p[0] == points[0][0] for p in points):
                events.append({"contour": ci, "kind": "zero_area_point_contour", "points": len(points)})
                points = []
                break
            removed = False
            for i, (b, bf) in enumerate(points):
                a, af = points[i-1]
                c, cf = points[(i+1) % len(points)]
                kind = None
                if af & 1 and bf & 1 and a == b:
                    kind = "zero_line"
                elif not bf & 1 and a == b == c:
                    kind = "zero_quadratic_control"
                elif len(points) > 2 and af & 1 and bf & 1 and cf & 1 and between(a, b, c):
                    kind = "collinear_line_point"
                if kind:
                    events.append({"contour": ci, "kind": kind, "a": a, "b": b, "c": c})
                    del points[i]
                    removed = True
                    break
            if not removed:
                break
        if points:
            contours.append(points)
    if events:
        from array import array
        flat = [p for contour in contours for p in contour]
        glyph.coordinates = GlyphCoordinates([p[0] for p in flat])
        glyph.flags = array("B", [p[1] for p in flat])
        glyph.endPtsOfContours = []
        count = 0
        for contour in contours:
            count += len(contour)
            glyph.endPtsOfContours.append(count-1)
        glyph.numberOfContours = len(contours)
        glyph.recalcBounds(font["glyf"])
    return events


def clean_cff(font, name, apply=True):
    top = font["CFF "].cff.topDictIndex[0]
    cs = top.CharStrings[name]
    cs.decompile()
    if any(x in {"hstem", "vstem", "hstemhm", "vstemhm", "hintmask", "cntrmask", "callsubr", "callgsubr"}
           for x in cs.program if isinstance(x, str)):
        raise ValueError(f"{name}: hinted/subroutinized CFF requires a separate preservation strategy")
    gs = font.getGlyphSet()
    pen = RecordingPen()
    gs[name].draw(pen)
    result, events, current = [], [], None
    for operation, args in pen.value:
        args = tuple(tuple(p) if p is not None else p for p in args)
        if operation == "moveTo":
            current = args[0]
            result.append((operation, args))
        elif operation in ("lineTo", "curveTo"):
            if all(p == current for p in args):
                events.append({"kind": "zero_cubic" if operation == "curveTo" else "zero_line", "point": current})
                continue
            if operation == "lineTo" and result and result[-1][0] == "lineTo":
                a = result[-2][1][-1]
                if between(a, current, args[0]):
                    events.append({"kind": "collinear_line_point", "a": a, "b": current, "c": args[0]})
                    result[-1] = (operation, args)
                    current = args[-1]
                    continue
            result.append((operation, args))
            current = args[-1]
        elif operation == "closePath":
            result.append((operation, args))
            current = None
        else:
            raise ValueError(f"{name}: unsupported CFF drawing operation {operation}")
    if events and apply:
        t2 = T2CharStringPen(font["hmtx"].metrics[name][0], gs, roundTolerance=0)
        for operation, args in result:
            getattr(t2, operation)(*args)
        top.CharStrings[name] = t2.getCharString(private=cs.private, globalSubrs=cs.globalSubrs)
    return events


def clean_font(source, destination):
    font = TTFont(source, recalcTimestamp=False)
    if "gvar" in font or "CFF2" in font:
        raise ValueError("Variable outlines need coordinated variation point cleanup")
    if "CFF " in font and not any(clean_cff(font, name, apply=False) for name in font.getGlyphOrder()):
        # The approved cubic sources generally have no redundant segments.
        # An exact file copy is stronger and faster proof than serializing them.
        font.close()
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        assert source.read_bytes() == destination.read_bytes()
        return {"font": str(source), "output": str(destination), "changed_glyphs": {},
                "changed_glyph_count": 0, "event_counts": {},
                "validation": {"entire_file_byte_identical": True},
                "proof_note": "Every cubic outline inspected; no removable segment. Output is a byte-identical copy."}
    originals = {name: geometry(font, name) for name in font.getGlyphOrder()}
    cmap, metrics = copy.deepcopy(font.getBestCmap()), copy.deepcopy(font["hmtx"].metrics)
    order = font.getGlyphOrder()[:]
    protected = {tag: font.getTableData(tag) for tag in font.keys()
                 if tag not in {"GlyphOrder", "glyf", "loca", "head", "maxp", "CFF "}}
    changed = {}
    cleaner = clean_glyf if "glyf" in font else clean_cff
    for name in order:
        events = cleaner(font, name)
        if events:
            if geometry(font, name) != originals[name]:
                raise ValueError(f"{source.name}/{name}: exact segment proof failed before serialization")
            changed[name] = {"events": events, "proof": "exact_native_local_equalities_and_normalized_segments"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    font.save(destination)
    font.close()
    reloaded = TTFont(destination, recalcTimestamp=False)
    assert reloaded.getGlyphOrder() == order, "Glyph order changed"
    assert reloaded.getBestCmap() == cmap, "cmap changed"
    assert reloaded["hmtx"].metrics == metrics, "Metrics changed"
    for name in order:
        if geometry(reloaded, name) != originals[name]:
            raise ValueError(f"{source.name}/{name}: exact segment proof failed after serialization")
    changed_tables = [tag for tag, original in protected.items() if reloaded.getTableData(tag) != original]
    if changed_tables:
        raise ValueError(f"Unrelated tables changed: {changed_tables}")
    reloaded.close()
    return {"font": str(source), "output": str(destination), "changed_glyphs": changed,
            "changed_glyph_count": len(changed),
            "event_counts": dict(Counter(e["kind"] for g in changed.values() for e in g["events"])),
            "validation": {"all_glyphs_exact_normalized_segments_after_reload": True,
                           "metrics_cmap_glyph_order_unchanged": True,
                           "unrelated_tables_byte_identical": True},
            "proof_note": "Only zero-length segments and a point lying exactly between collinear line endpoints are removed. Quadratic implicit points are expanded without rounding solely for equality checks. No boolean operation, approximate tolerance, or contour rounding is used."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    src, dest = args.input_dir.resolve(), args.output_dir.resolve()
    if src == dest or src in dest.parents or dest in src.parents:
        parser.error("Input and output must be distinct, non-nested directories")
    files = sorted(p for p in src.rglob("*") if p.suffix.lower() in {".ttf", ".otf", ".woff2"})
    if not files:
        parser.error("No supported fonts found")
    reports = []
    for path in files:
        report = clean_font(path, dest / path.relative_to(src))
        reports.append(report)
        print(json.dumps({"font": path.name, "changed_glyphs": report["changed_glyph_count"], "events": report["event_counts"]}), flush=True)
    (dest / "outline-cleanup-report.json").write_text(json.dumps({"fonts": reports}, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
