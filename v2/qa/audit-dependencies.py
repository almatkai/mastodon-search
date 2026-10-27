#!/usr/bin/env python3
"""Audit real locked registry archives and preserve authentic grants/notices."""
from pathlib import Path
import hashlib
import json
import tarfile
import tomllib
import subprocess
import base64
from env import ROOT,environment

sha=lambda b:hashlib.sha256(b).hexdigest()
home=Path(environment()['CARGO_HOME'])
lock=tomllib.loads((ROOT/'Cargo.lock').read_text())
dest=ROOT/'licenses';dest.mkdir(exist_ok=True)
rows=[]
for package in lock['package']:
    if not package.get('source','').startswith('registry+'):
        continue
    name,version=package['name'],package['version']
    matches=list((home/'registry/cache').glob(f'*/{name}-{version}.crate'))
    assert len(matches)==1,(name,version,matches)
    archive=matches[0];assert sha(archive.read_bytes())==package['checksum'],name
    grants=[];meta=None
    with tarfile.open(archive) as t:
        for member in t.getmembers():
            if not member.isfile():continue
            relative=Path(member.name).relative_to(f'{name}-{version}')
            if relative.as_posix()=='Cargo.toml':meta=tomllib.loads(t.extractfile(member).read().decode())['package']
            upper=relative.name.upper()
            if upper.startswith(('LICENSE','COPYING','COPYRIGHT','NOTICE','AUTHORS')):
                p=dest/f'{name}-{version}'/relative;p.parent.mkdir(parents=True,exist_ok=True);data=t.extractfile(member).read();p.write_bytes(data);grants.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(data)))
    assert meta is not None
    license_file=meta.get('license-file')
    if license_file and not any(g['path'].endswith('/'+license_file) for g in grants):
        with tarfile.open(archive) as t:
            try:data=t.extractfile(f'{name}-{version}/{license_file}').read()
            except (KeyError,AttributeError):data=None
        if data is not None:
            p=dest/f'{name}-{version}'/license_file;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);grants.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(data)))
    # Some crates put grant text in AUTHORS rather than a LICENSE file.
    grant=any(any(token in (ROOT/g['path']).read_text(errors='replace') for token in ['Permission is hereby granted','Apache License','Mozilla Public License','Permission to use, copy, modify','MIT License','ISC License','Unicode License','Redistribution and use in source and binary','Community Data License Agreement - Permissive - Version 2.0']) for g in grants)
    rows.append(dict(name=name,version=version,archiveSha256=package['checksum'],declaredLicense=meta.get('license'),declaredLicenseFile=license_file,authenticFiles=grants,grantTextFound=grant))

# Preserve SDK license and notice from the immutable object, not a live checkout.
for name in ['LICENSE','NOTICE']:
    data=(ROOT/'qa/fixtures/sdk'/name).read_bytes();p=dest/'tezbar-extension-sdk-0.1.1'/name;p.parent.mkdir(exist_ok=True);p.write_bytes(data)

# NPM QA dependency archives are checked against actual source lock SRI.
source_lock=json.loads((ROOT/'qa/fixtures/source/package-lock.json').read_text())
npm=[]
archives=ROOT/'.work/npm-archives';archives.mkdir(exist_ok=True)
for name in ['@raycast/utils','@raycast/api','react','dequal','typescript','tsx']:
    m=source_lock['packages']['node_modules/'+name];p=archives/(name.replace('/','-').replace('@','')+'.tgz')
    subprocess.run(['curl','--fail','--location','--max-time','60','--silent','--show-error','--output',str(p),m['resolved']],check=True,env=environment())
    data=p.read_bytes();alg,expected=m['integrity'].split('-',1);assert base64.b64encode(hashlib.new(alg,data).digest()).decode()==expected
    files=[]
    with tarfile.open(p) as t:
        for member in t.getmembers():
            if member.isfile() and Path(member.name).name.upper().startswith(('LICENSE','COPYING','NOTICE','AUTHORS')):
                out=dest/('qa-'+name.replace('/','-').replace('@','')+'-'+m['version'])/Path(member.name).relative_to('package');out.parent.mkdir(parents=True,exist_ok=True);content=t.extractfile(member).read();out.write_bytes(content);files.append(str(out.relative_to(ROOT)))
        if name=='@raycast/utils':
            assert t.extractfile('package/dist/main.js').read()==(ROOT/'qa/fixtures/locked-utils/main.js').read_bytes()
    npm.append(dict(name=name,version=m['version'],url=m['resolved'],sri=m['integrity'],archiveSha256=sha(data),authenticLicenseFiles=files,missingLicenseText=not files))

missing=[r['name']+' '+r['version'] for r in rows if not r['grantTextFound']]
report=dict(registry=rows,npm=npm,registryGrantTextNotDetected=missing,sdkPin='e955911f0bf5b558f9d3eb5183df0adc95c22af2',sourceLockSha256=sha((ROOT/'qa/fixtures/source/package-lock.json').read_bytes()))
(ROOT/'qa/evidence/dependencies.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'{len(rows)} crate archives checked; grants not detected: {missing}')
print('QA npm packages without license text:',[p['name'] for p in npm if p['missingLicenseText']])
assert any(r['name']=='r-efi' and any(g['path'].endswith('/AUTHORS') for g in r['authenticFiles']) and r['grantTextFound'] for r in rows)
