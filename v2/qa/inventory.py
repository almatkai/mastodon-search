#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import stat
import subprocess
from env import ROOT

REPO=ROOT.parent
EXCLUDE='v2/qa/evidence/candidate-inventory.json'
visible=subprocess.check_output(['git','-C',str(REPO),'ls-files','--cached','--others','--exclude-standard','-z','--','README.md','v2']).decode().split('\0')
rows={}
for name in sorted(set(visible)-{EXCLUDE,''}):
    path=REPO/name
    assert path.is_file() and not path.is_symlink(),name
    assert not any(part in ['node_modules','target','.work','__pycache__'] for part in path.relative_to(REPO).parts),name
    assert not name.endswith(('.zip','.crate','.tgz','.pyc')),name
    rows[name]=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size,mode=f'{stat.S_IMODE(path.stat().st_mode):04o}')
# Every durable fixture/evidence/script is visible; generated work is only .work
# or explicitly ignored Python bytecode / node_modules tooling installations.
for parent in ['qa/fixtures','qa/evidence','src','tests','assets','licenses','integration']:
    for path in (ROOT/parent).rglob('*'):
        if path.is_file():
            name=path.relative_to(REPO).as_posix()
            assert name in rows or name==EXCLUDE,('ignored fixture gap',name)
assert subprocess.check_output(['git','-C',str(REPO),'diff','--cached','--name-only'])==b''
report=dict(scope='all Git-visible README/v2 candidates except this inventory itself; parent must rehash STAGED blobs',indexEmpty=True,count=len(rows),files=rows)
(ROOT/'qa/evidence/candidate-inventory.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'{len(rows)} unstaged candidates hashed; no ignored fixture gap; index empty')
