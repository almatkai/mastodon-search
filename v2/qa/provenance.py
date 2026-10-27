#!/usr/bin/env python3
"""Read-only Git boundaries and immutable fixture hashes. Never stages files."""
from pathlib import Path
import hashlib
import json
import subprocess
from env import ROOT

REPO=ROOT.parent
sha=lambda b:hashlib.sha256(b).hexdigest()
git=lambda *args:subprocess.check_output(['git','-C',str(REPO),*args])
head='dd73024af23ed7d716421592aac26c323500206d'
assert git('rev-parse','--show-toplevel').decode().strip()==str(REPO)
assert git('rev-parse','HEAD').decode().strip()==head
assert git('branch','--show-current').decode().strip()=='feat/native-v2-rust'
assert git('diff','--cached','--name-only')==b''
original={}
for name in git('ls-tree','-r','--name-only',head).decode().splitlines():
    before=git('show',head+':'+name);actual=(REPO/name).read_bytes()
    if name=='README.md':
        assert actual==before+b'\nStandalone Rust version: [V2 implementation and verification](v2/README.md).\n'
    else: assert actual==before,name
    assert (ROOT/'qa/fixtures/source'/name).read_bytes()==before,name
    original[name]=sha(before)

fixtures={}
for folder,repo,pin in [('source',REPO,head),('sdk',REPO.parent/'tezbar-extension-sdk-rust','e955911f0bf5b558f9d3eb5183df0adc95c22af2'),('host',REPO.parent.parent/'Tezbar','ea100cee3f69711de12485ba061950c5fc65258f')]:
    for path in sorted((ROOT/'qa/fixtures'/folder).rglob('*')):
        if not path.is_file():continue
        name=path.relative_to(ROOT/'qa/fixtures'/folder).as_posix()
        expected=subprocess.check_output(['git','-C',str(repo),'show',pin+':'+name])
        assert path.read_bytes()==expected,str(path)
        fixtures[str(path.relative_to(ROOT))]=dict(pin=pin,gitPath=name,sha256=sha(expected))

icon='cf8072956e54114ab4044849f5e5441577ec56676a942c9d8aced00648169c09'
assert sha((ROOT/'assets/command-icon.png').read_bytes())==icon==original['assets/command-icon.png']
report=dict(selectedRoot=str(REPO),branch='feat/native-v2-rust',head=head,remote=git('remote','get-url','origin').decode().strip(),indexEmpty=True,originalV1=original,fixtures=fixtures,icon=dict(upstream='https://raw.githubusercontent.com/raycast/extensions/6734d85992290066fd31a7f5bee3cca3d3545a1a/extensions/mastodon-search/assets/command-icon.png',sha256=icon,comparison='fresh pinned HTTP fetch, own Git blob, root asset and V2 asset identical'),temporaryRegistration='mcp:66119403-0acd-46af-b333-f17db1a00bde',xerj=dict(prefix='ax-6d9e093035a8',stateDirectory='/Users/almat/.local/share/xerj/workspaces/ax-6d9e093035a8',result='initial generation 1: 18 indexed files/97 records, all 11 original code files indexed, exit 3 completed-with-junk. Final bounded refresh aborted in 0.6 s on v2/Cargo.toml: no frozen dataset accepts family docs; unsupported schema evolution. Adapter search returned no match because V2 indexing is incomplete. Full source/Git/rg/hash fallback used. No new prefix, settings/schema/server changes, bypass or restart'))
(ROOT/'qa/evidence/provenance.json').write_text(json.dumps(report,indent=2)+'\n')
print('V1 byte boundary, pinned immutable fixtures, exact icon and empty index verified')
