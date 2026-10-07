# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Run the official NAM preprocessor against a verified, frozen Unicode ZIP.

Use --check before applying the patch to prove no Unicode-refresh churn.
The same check after regeneration proves the generated patch is reproducible.
"""
import argparse, hashlib, importlib.metadata, json, os, runpy, sys, zipfile
from pathlib import Path
SUBSETS=['latin','latin-ext','vietnamese','cyrillic']
UCD_SHA256='7b3e555514060b92290d154f53655c5eb0fa62b16eb04c03434ff72d1a66a0d8'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['nam-repo','ucd-zip','ucd-dir']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--check',action='store_true');a=p.parse_args()
    a.nam_repo=a.nam_repo.resolve();a.ucd_zip=a.ucd_zip.resolve();a.ucd_dir=a.ucd_dir.resolve()
    assert hashlib.sha256(a.ucd_zip.read_bytes()).hexdigest()==UCD_SHA256
    assert importlib.metadata.version('youseedee')=='0.7.0'
    a.ucd_dir.mkdir(parents=True,exist_ok=True)
    # Verify contents even when a pre-existing cache is supplied.
    with zipfile.ZipFile(a.ucd_zip) as archive:
        for info in archive.infolist():
            target=(a.ucd_dir/info.filename).resolve()
            assert target.is_relative_to(a.ucd_dir), info.filename
            if info.is_dir(): target.mkdir(parents=True,exist_ok=True);continue
            content=archive.read(info)
            if target.exists(): assert target.read_bytes()==content,info.filename
            else: target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    import youseedee
    youseedee.ucd_dir=lambda:a.ucd_dir
    youseedee.ensure_files=lambda:None  # no network refresh of pinned data
    os.chdir(a.nam_repo)
    paths=[Path(f'Lib/gfsubsets/data/{s}_unique-glyphs.nam') for s in SUBSETS]
    before={str(path):path.read_bytes() for path in paths}
    try:
        sys.argv=['scripts/preprocess_namfile.py','--no-label',*[f'subsets-input/{s}_unique-glyphs.nam' for s in SUBSETS]]
        runpy.run_path(sys.argv[0],run_name='__main__')
        after={str(path):path.read_bytes() for path in paths}
    finally:
        if a.check:
            for path in paths:path.write_bytes(before[str(path)])
    equal={key:before[key]==after[key] for key in before}
    print(json.dumps({'unicode':'18.0.0','ucd_zip_sha256':UCD_SHA256,
        'check':a.check,'byte_identical':equal,'output_sha256':{
            key:hashlib.sha256(content).hexdigest() for key,content in after.items()}},indent=2))
    if a.check: assert all(equal.values()),'Unexpected generated NAM differences'

if __name__=='__main__':main()
