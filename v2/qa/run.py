#!/usr/bin/env python3
"""Reproduce finite QA in the selected clone. Never installs a toolchain/host."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from env import ROOT,WORK,environment

env=environment();env['PYTHONDONTWRITEBYTECODE']='1'
evidence=ROOT/'qa/evidence';evidence.mkdir(exist_ok=True)


def run(name,args,expected_failure=False,toolchain='stable'):
    target=evidence/(name+'.txt')
    with target.open('wb') as f:
        result=subprocess.run(args,cwd=ROOT,env=dict(environment(toolchain=toolchain),PYTHONDONTWRITEBYTECODE='1'),stdout=f,stderr=subprocess.STDOUT)
    if expected_failure:
        if result.returncode:
            text=target.read_text(errors='replace')
            assert 'x86_64-w64-mingw32-gcc' in text or 'target may not be installed' in text, f'Unexpected code/tool failure: {target}'
        print(name, 'blocked by compiler/target' if result.returncode else 'checked; no native acceptance',flush=True)
    else:
        assert result.returncode==0,f'{args} failed: {target}'
        print(name,'passed',flush=True)


v1=WORK/'v1'
if not (v1/'package.json').exists():shutil.copytree(ROOT/'qa/fixtures/source',v1,dirs_exist_ok=True)
run('v1-install',['npm','ci','--prefix',str(v1),'--ignore-scripts','--no-audit','--no-fund'])
run('v1-test',['npm','test','--prefix',str(v1)])
run('v1-typecheck',['npm','run','typecheck','--prefix',str(v1)])
run('source-oracle',['node','qa/source-oracle.cjs'])
run('schema-install',['npm','ci','--prefix','qa/schema','--ignore-scripts','--no-audit','--no-fund'])
run('schema',['node','qa/schema/check.cjs'])
run('producer-extraction',[sys.executable,'qa/prepare-producers.py'])
run('rust-fmt',['cargo','fmt','--','--check'])
for toolchain in ['stable','1.85.0']:
    name='stable' if toolchain=='stable' else '1.85'
    run('rust-'+name+'-test',['cargo','test','--locked'],toolchain=toolchain)
    run('rust-'+name+'-clippy',['cargo','clippy','--locked','--all-targets','--','-D','warnings'],toolchain=toolchain)
run('windows-gnu-check',['cargo','check','--locked','--target','x86_64-pc-windows-gnu'],expected_failure=True)
run('windows-gnu-clippy',['cargo','clippy','--locked','--all-targets','--target','x86_64-pc-windows-gnu','--','-D','warnings'],expected_failure=True)
run('fetch-all',['cargo','fetch','--locked'])
run('dependency-audit',['python3.14','qa/audit-dependencies.py'])
run('helper-fmt',['cargo','fmt','--manifest-path','qa/transport-helper/Cargo.toml','--','--check'])
run('helper-clippy',['cargo','clippy','--locked','--all-targets','--manifest-path','qa/transport-helper/Cargo.toml','--','-D','warnings'])
run('helper-1.85-clippy',['cargo','clippy','--locked','--all-targets','--manifest-path','qa/transport-helper/Cargo.toml','--','-D','warnings'],toolchain='1.85.0')
run('helper-build',['cargo','build','--locked','--manifest-path','qa/transport-helper/Cargo.toml'])
run('fresh-package',[sys.executable,'qa/package.py'])
package=json.loads((evidence/'package.json').read_text());binary=str(ROOT/package['extracted']/'bin/mastodon-search')
run('owned-tls-pipes',[sys.executable,'qa/pipes.py',binary,str(WORK/'target/debug/mastodon-owned-transport-helper')])
run('production-pipes',[sys.executable,'qa/production.py',binary])
run('host-patch',[sys.executable,'qa/prepare-host-patch.py'])
run('renderer',['node','qa/renderer.cjs'])
run('host-types',['node','qa/typecheck-host.cjs'])
run('provenance',[sys.executable,'qa/provenance.py'])
# Inventory is deliberately last and excludes its own output.
with (WORK/'inventory.log').open('wb') as f:
    subprocess.run([sys.executable,'qa/inventory.py'],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
print('inventory passed',flush=True)
