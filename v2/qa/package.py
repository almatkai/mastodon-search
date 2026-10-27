#!/usr/bin/env python3
"""Fresh HTTPS SDK build and deterministic closed development ZIP; no install."""
from pathlib import Path
import hashlib
import io
import json
import os
import stat
import subprocess
import tempfile
import zipfile
from env import ROOT,WORK,environment

sha=lambda b:hashlib.sha256(b).hexdigest()
fresh_home=Path(tempfile.mkdtemp(prefix='fresh-cargo-',dir=WORK))
fresh_target=Path(tempfile.mkdtemp(prefix='fresh-target-',dir=WORK))
assert fresh_home!=fresh_target and not list(fresh_home.iterdir()) and not list(fresh_target.iterdir())
env=environment(cargo=fresh_home.name,target=fresh_target.name)
lock_before=(ROOT/'Cargo.lock').read_bytes()
source_before={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in [ROOT/'Cargo.toml',ROOT/'Cargo.lock',*sorted((ROOT/'src').glob('*.rs'))]}
with (WORK/'fresh-release.log').open('wb') as log:
    subprocess.run(['cargo','build','--locked','--release','--target','aarch64-apple-darwin','--bin','mastodon-search'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
(ROOT/'qa/evidence/fresh-release.txt').write_bytes((WORK/'fresh-release.log').read_bytes())
assert lock_before==(ROOT/'Cargo.lock').read_bytes()
assert all(sha((ROOT/p).read_bytes())==h for p,h in source_before.items())
binary=fresh_target/'aarch64-apple-darwin/release/mastodon-search'
assert binary.is_file()
# Fetch cache must contain the real pinned Git SDK. No path patch/replacement.
sdk=list((fresh_home/'git/checkouts').glob('*/e955911'))
assert len(sdk)==1,sdk
for relative in ['src/lib.rs','src/runner.rs','src/context.rs','src/stdio.rs','Cargo.toml','LICENSE','NOTICE']:
    assert (sdk[0]/relative).read_bytes()==(ROOT/'qa/fixtures/sdk'/relative).read_bytes(),relative
contents={'bin/mastodon-search':binary.read_bytes(),'resources/command-icon.png':(ROOT/'assets/command-icon.png').read_bytes(),'LICENSE':(ROOT/'LICENSE').read_bytes(),'NOTICE':(ROOT/'NOTICE').read_bytes()}
for p in sorted((ROOT/'licenses').rglob('*')):
    if p.is_file() and not p.relative_to(ROOT/'licenses').parts[0].startswith('qa-'):
        contents['resources/licenses/'+str(p.relative_to(ROOT/'licenses'))]=p.read_bytes()
manifest=json.loads((ROOT/'extension.json').read_text());assert manifest['artifacts']=={}
manifest['files']={name:sha(data) for name,data in sorted(contents.items())}
contents['extension.json']=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()


def archive():
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_STORED) as z:
        for name,data in sorted(contents.items()):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.create_system=3
            mode=0o755 if name.startswith('bin/') else 0o644
            info.external_attr=(stat.S_IFREG|mode)<<16
            z.writestr(info,data)
    return stream.getvalue()


data=archive();assert data==archive()
package=WORK/'mastodon-search-aarch64-apple-darwin-dev.zip';package.write_bytes(data)
extracted=Path(tempfile.mkdtemp(prefix='extracted-',dir=WORK))
with zipfile.ZipFile(package) as z:
    assert sorted(z.namelist())==sorted(contents)
    for info in z.infolist():
        assert info.filename in contents and not info.is_dir()
        assert z.read(info)==contents[info.filename]
        out=extracted/info.filename;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(info));out.chmod((info.external_attr>>16)&0o777)
        assert stat.S_IMODE(out.stat().st_mode)==(0o755 if info.filename.startswith('bin/') else 0o644)
        assert info.filename=='extension.json' or manifest['files'][info.filename]==sha(out.read_bytes())
entry=extracted/'bin/mastodon-search'
info=json.loads(subprocess.check_output([str(entry),'--protocol-info'],env=env,cwd=extracted,text=True))
assert info==dict(protocol=1,id='com.tezbar.native.mastodon-search',version='2.0.0',sdkVersion='0.1.1',commands=['search'])
assert sha(entry.read_bytes())==sha(binary.read_bytes())
report=dict(sourceFilesBeforeAndAfterBuild=source_before,freshCargoHome=str(fresh_home.relative_to(ROOT)),freshTarget=str(fresh_target.relative_to(ROOT)),initialBothEmpty=True,distinct=True,httpsSdkPin='e955911f0bf5b558f9d3eb5183df0adc95c22af2',cargoLockSha256=sha(lock_before),productionSha256=sha(binary.read_bytes()),zip=str(package.relative_to(ROOT)),zipSha256=sha(data),zipSize=len(data),extracted=str(extracted.relative_to(ROOT)),deterministicTwice=True,protocolInfo=info,files={name:dict(sha256=sha(b),mode='0755' if name.startswith('bin/') else '0644') for name,b in sorted(contents.items())},nativeAcceptance='not-run; extracted genuine executable protocol/pipe QA only; source artifacts remain empty')
(ROOT/'qa/evidence/package.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['productionSha256','zipSha256','zipSize','extracted']},indent=2))
