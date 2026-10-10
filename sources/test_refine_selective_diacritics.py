# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Check the deliberately narrow side-caron change against a 1.002 baseline.

NAMBLI_SELECTIVE_BASELINE_UFOS can select a saved 1.002 UFO directory or ZIP.
Otherwise the current source directory is used only while it is version
1.002; later versions fall back to fonts/candidates/1.002/sources-1.002.zip.
Only four required UFOs are extracted, with paths and SHA-256 hashes checked.
NAMBLI_QA_TMPDIR selects their temporary parent directory on Windows.
"""
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import stat
import tempfile
import unittest
import zipfile

import runtime
from ufoLib2 import Font
from refine_selective_diacritics import TARGETS,refine_font,path_of,_record,topology

STYLES=('Light','Regular','Bold','ExtraBoldItalic')


def _is_reference_directory(root):
    for style in STYLES:
        try:
            with (root/f'Nambli-{style}.ufo/fontinfo.plist').open('rb') as stream:
                info=plistlib.load(stream)
        except (OSError,ValueError,plistlib.InvalidFileException):
            return False
        if (info.get('versionMajor'),info.get('versionMinor'))!=(1,2):
            return False
    return True


def _extract_reference(archive,destination):
    folders={f'Nambli-{style}.ufo' for style in STYLES}
    destination=destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        manifest=json.loads(bundle.read('SOURCE-SHA256.json'))
        seen=set()
        extracted=set()
        for member in bundle.infolist():
            name=member.filename
            path=PurePosixPath(name)
            if (path.is_absolute() or not path.parts or '\\' in name
                    or any(p in {'.','..'} or ':' in p for p in path.parts)):
                raise ValueError(f'Unsafe baseline archive path: {name!r}')
            if path.parts[0] not in folders:
                continue
            if stat.S_IFMT(member.external_attr >> 16)==stat.S_IFLNK:
                raise ValueError(f'Baseline archive contains a symbolic link: {name!r}')
            target=destination.joinpath(*path.parts).resolve()
            if not target.is_relative_to(destination):
                raise ValueError(f'Baseline archive escapes its temporary folder: {name!r}')
            key=str(target).casefold()
            if key in seen:raise ValueError(f'Duplicate baseline archive path: {name!r}')
            seen.add(key)
            if member.is_dir():
                target.mkdir(parents=True,exist_ok=True)
                continue
            payload=bundle.read(member)
            if hashlib.sha256(payload).hexdigest()!=manifest.get(name):
                raise ValueError(f'Baseline archive checksum mismatch: {name!r}')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(payload)
            extracted.add(name)
        required={name for name in manifest if PurePosixPath(name).parts[0] in folders}
        if extracted!=required or not _is_reference_directory(destination):
            raise ValueError('Baseline archive is incomplete or is not version 1.002')
    return destination


def _baseline_root(testcase):
    explicit=os.environ.get('NAMBLI_SELECTIVE_BASELINE_UFOS')
    if explicit:
        selected=Path(explicit)
        if selected.is_dir():
            if not _is_reference_directory(selected):
                raise ValueError('NAMBLI_SELECTIVE_BASELINE_UFOS must contain unchanged 1.002 sources')
            return selected
        archive=selected
    else:
        current=Path(__file__).parent/'ufos'
        if _is_reference_directory(current):return current
        archive=Path(__file__).resolve().parents[1]/'fonts/candidates/1.002/sources-1.002.zip'
    if not archive.is_file():
        raise FileNotFoundError(f'1.002 baseline archive not found: {archive}')
    temporary_parent=Path(os.environ.get('NAMBLI_QA_TMPDIR',tempfile.gettempdir())).resolve()
    temporary_parent.mkdir(parents=True,exist_ok=True)
    temporary=tempfile.TemporaryDirectory(prefix='nambli-sidecaron-reference-',dir=temporary_parent)
    extracted=Path(temporary.name).resolve()
    if not extracted.is_relative_to(temporary_parent):
        raise ValueError('Temporary baseline extraction escaped its configured parent')
    testcase.addClassCleanup(temporary.cleanup)
    return _extract_reference(archive,extracted)


class SelectiveDiacriticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=_baseline_root(cls)
        cls.cases=[]
        for style in STYLES:
            baseline=Font.open(root/f'Nambli-{style}.ufo')
            if (baseline.info.versionMajor,baseline.info.versionMinor)!=(1,2):
                raise ValueError('The selected baseline must contain unchanged 1.002 sources')
            candidate=copy.deepcopy(baseline)
            report=refine_font(candidate)
            cls.cases.append((baseline,candidate,report))

    def test_only_shared_sidecaron_and_four_precomposed_forms_change(self):
        for before,after,report in self.cases:
            actual={g.name for g in after if g!=before[g.name]}
            with self.subTest(style=report['style']):
                self.assertEqual(actual,TARGETS)
                self.assertEqual(after.features.text,before.features.text)
                self.assertEqual(after.kerning,before.kerning)
                self.assertEqual(after.info,before.info)
                for glyph in after:
                    self.assertEqual(glyph.width,before[glyph.name].width)
                    self.assertEqual(glyph.unicodes,before[glyph.name].unicodes)

    def test_turkish_alphabet_and_its_marks_are_exactly_preserved(self):
        for before,after,report in self.cases:
            cmap={cp:g.name for g in after for cp in g.unicodes}
            with self.subTest(style=report['style']):
                for char in 'ÇĞİÖŞÜçğıöşü\u0306\u0307\u0308\u0327':
                    name=cmap[ord(char)]
                    self.assertEqual(after[name],before[name])

    def test_original_body_contours_and_layout_survive(self):
        for before,after,report in self.cases:
            with self.subTest(style=report['style']):
                for row in report['placements']:
                    name,index=row['glyph'],row['contour']
                    self.assertGreaterEqual(row['baseClearance'],12)
                    # Italic accents already overhang their advance in 1.002.
                    # This change consumes only its small normal expansion,
                    # rather than widening text or moving the shared anchor.
                    self.assertLessEqual(row['beforeRightSidebearing']-row['rightSidebearing'],
                                         report['normalExpansionPerSide']*1.2+2)
                    for i,contour in enumerate(after[name].contours):
                        if i!=index:self.assertEqual(_record(contour),_record(before[name].contours[i]))
                    local=copy.deepcopy(after[name].contours[index])
                    dx,dy=row['translation'];local.move((-dx,-dy))
                    self.assertEqual(_record(local),_record(after['uni030C.alt'].contours[0]))
                for base,precomposed in [('L','uni013D'),('l','uni013E'),('d','uni010F'),('t','uni0165')]:
                    self.assertIn(f'sub {base} uni030C by {precomposed};',after.features.text)

    def test_moderate_expansion_keeps_a_single_open_curl(self):
        for before,after,report in self.cases:
            with self.subTest(style=report['style']):
                self.assertAlmostEqual(report['nominalStrokeTarget']/report['nominalStrokeBefore'],1.30)
                self.assertEqual(topology(path_of(after['uni030C.alt'])),(1,0))
                for name in TARGETS:
                    for contour in after[name].contours:
                        for p in contour:
                            self.assertNotEqual(p.type,'curve')
                            self.assertEqual(p.x,int(p.x));self.assertEqual(p.y,int(p.y))


if __name__=='__main__':unittest.main()
