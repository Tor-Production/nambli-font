# Copyright 2026 The Nambli Project Authors
# SPDX-License-Identifier: OFL-1.1
"""Run unsuppressed binary QA or complete Google Fonts package QA.

Artifacts are immutable per run. Exit zero requires native success, unchanged
inputs, a parsed raw report, and (for package scope) an executed tofu check.
No patched tool or binary-only result is represented as stock package QA.
"""
from __future__ import annotations
import argparse
import collections
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

SEVERITIES = ('FAIL', 'ERROR', 'FATAL')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def collect_inputs(scope, family, expected_faces=12):
    family = Path(family).resolve()
    fonts = sorted(family.glob('*.ttf'))
    if len(fonts) != expected_faces:
        raise ValueError(f'Expected {expected_faces} TTFs, found {len(fonts)}')
    inputs = list(fonts)
    if scope == 'package':
        extra = [family/'METADATA.pb', family/'OFL.txt', family/'article/ARTICLE.en_us.html']
        for p in extra:
            if not p.is_file() or not p.stat().st_size:
                raise ValueError(f'Missing or empty full-package input: {p.name}')
        filenames = re.findall(r'\bfilename:\s*"([^"]+)"', extra[0].read_text(encoding='utf-8'))
        if sorted(filenames) != [p.name for p in fonts]:
            raise ValueError('METADATA.pb must enumerate exactly the supplied TTF filenames')
        if not re.search(r'\bsubsets:\s*"',extra[0].read_text(encoding='utf-8')):
            raise ValueError('Package metadata has no declared serving subsets')
        inputs.extend(extra)
        for src in re.findall(r'<img\b[^>]*\bsrc=[\'"]([^\'"]+)',extra[2].read_text(encoding='utf-8'),re.I):
            asset=(extra[2].parent/src).resolve()
            if not asset.is_relative_to(family) or not asset.is_file() or not asset.stat().st_size:
                raise ValueError(f'Missing or invalid article image input: {src}')
            if asset not in inputs: inputs.append(asset)
    return inputs

def assess(raw, scope):
    groups = collections.defaultdict(collections.Counter)
    issues, tofu = [], []
    for file, sections in raw['results'].items():
        for checks in sections.values():
            for check in checks:
                for sub in check['subresults']:
                    groups[check['check_id']][sub['severity']] += 1
                    if check['check_id'] == 'googlefonts/tofu':
                        tofu.append(sub)
                    if sub['severity'] in SEVERITIES:
                        issues.append({'file':Path(file).name,'check_id':check['check_id'],**sub})
    counts = collections.Counter()
    for g in groups.values(): counts.update(g)
    if dict(counts) != dict(raw['summary']):
        raise ValueError('Raw summary differs from actual subresults')
    tofu_executed = bool(tofu) and all(s['severity'] != 'SKIP' for s in tofu)
    return {'summary':dict(counts), 'by_check':{k:dict(v) for k,v in sorted(groups.items())},
        'failures_and_errors':issues, 'tofu_executed':tofu_executed,
        'scope_gate_passed': scope=='binary' or tofu_executed,
        'zero_fail_error_fatal':not issues}

def run(scope, family, executable, output, mode='network', tool_kind='stock', expected_faces=12):
    inputs = collect_inputs(scope,family,expected_faces)
    family, output, executable = Path(family).resolve(),Path(output).resolve(),Path(executable).resolve()
    if output.exists(): raise FileExistsError('Use a new per-run output directory')
    output.mkdir(parents=True)
    # Include every family file in the manifest and pass article images to the
    # CLI explicitly: its article check resolves assets through the collection.
    files = sorted(p for p in family.rglob('*') if p.is_file())
    hashes = {p.relative_to(family).as_posix():sha(p) for p in files}
    raw_path = output/'fontspector.json'
    command=[str(executable),'-p','googlefonts','-J','4','--timeout','10','--json',str(raw_path)]
    if mode=='offline': command.append('--skip-network')
    command.extend(str(p) for p in inputs)
    version=subprocess.run([str(executable),'--version'],capture_output=True)
    result=subprocess.run(command,capture_output=True)
    (output/'stdout.log').write_bytes(result.stdout)
    (output/'stderr.log').write_bytes(result.stderr)
    summary={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope':scope,'profile':'googlefonts','mode':mode,'tool_kind':tool_kind,
        'tool_version':version.stdout.decode('utf-8',errors='replace').strip(),
        'executable_sha256':sha(executable),'native_exit_code':result.returncode,
        'command':command,'check_exclusions':[],
        'explicit_inputs':[p.relative_to(family).as_posix() for p in inputs],
        'input_sha256':hashes,'final_input_sha256':{p.relative_to(family).as_posix():sha(p) for p in sorted(family.rglob('*')) if p.is_file()},
        'raw_report_sha256':sha(raw_path) if raw_path.is_file() else None,
        'qa_passed':False}
    try:
        raw=json.loads(raw_path.read_text(encoding='utf-8'))
        summary.update(assess(raw,scope))
        summary['all_files_unchanged']=summary['input_sha256']==summary['final_input_sha256']
        summary['qa_passed']=(result.returncode==0 and summary['all_files_unchanged']
            and summary['scope_gate_passed'] and summary['zero_fail_error_fatal'])
    except (OSError,ValueError,KeyError,TypeError) as e:
        summary['report_error']=str(e)
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:summary.get(k) for k in ['scope','tool_kind','native_exit_code','summary','tofu_executed','qa_passed']}))
    return 0 if summary['qa_passed'] else 1

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope',choices=['binary','package'],required=True)
    parser.add_argument('--family',type=Path,required=True)
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=['network','offline'],default='network')
    parser.add_argument('--tool-kind',choices=['stock','patched-candidate'],default='stock')
    args=parser.parse_args()
    try:
        return run(args.scope,args.family,args.executable,args.output,args.mode,args.tool_kind)
    except (ValueError,OSError) as e:
        parser.exit(2,f'{e}\n')

if __name__=='__main__': raise SystemExit(main())
