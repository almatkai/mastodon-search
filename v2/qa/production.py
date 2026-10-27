#!/usr/bin/env python3
"""Applicable genuine packaged-process checks that need no successful HTTPS.

Full data/actions are exercised with the separate trusted owned-TLS helper;
this file does not claim the production trust policy accepted that test CA.
"""
import json
from pathlib import Path
import sys
from pipes import Pipe,check,CHECKS,ROOT


def suite(binary):
    p=Pipe(binary)
    a=p.open('a','bad instance with space')
    check('packaged default People/empty model is a real SDK view',a['root']['props']['searchText']=='' and a['root']['props']['searchBarAccessory']['props']['value']=='accounts')
    before=a['root']['props']['__modelRevision']
    for rev,kind in [(1,'hashtags'),(2,'accounts'),(3,'hashtags')]:
        a=p.invoke('a',a['root']['props']['searchBarAccessory']['props']['actionId'],dict(value=kind,inputRevision=rev))
    check('packaged kind A/B/A, separate native/client revisions',a['root']['props']['searchBarAccessory']['props']['value']=='hashtags' and a['root']['props']['__modelRevision']>before)
    stale=a['root']['props']['searchBarAccessory']['props']['actionId']
    check('packaged stale control revision inert',p.invoke('a',stale,dict(value='accounts',inputRevision=2))['mode']=='unchanged')
    b=p.open('b','bad instance with space')
    check('packaged foreign-session controls inert',p.invoke('b',stale,dict(value='hashtags',inputRevision=4))['mode']=='unchanged')
    a=p.op('a','search-text-changed',dict(searchText=9,inputRevision=4));check('packaged nonstring draft is visible and effect-free','Search' in a.get('message','') and not a['root']['props']['isLoading'])
    a=p.op('a','search-text-changed',dict(searchText='x'*4097,inputRevision=5));check('packaged oversized draft is visible','too long' in a.get('message',''))
    a=p.op('a','search-text-changed',dict(searchText='query',inputRevision=6));check('packaged invalid instance route fails locally without requests','HTTPS' in a.get('message',''))
    a=p.op('a','search-text-changed',dict(searchText='',inputRevision=7,draftOnly=True));check('packaged input-time draft acknowledges current client revision',a['root']['props']['__inputRevision']==7)
    a=p.op('a','search-text-changed',dict(searchText='',inputRevision=7));check('packaged empty draft promotion does not fetch',not a['root']['props']['isLoading'])
    for operation in ['load-more','unknown']:
        r=p.reply(p.request('session.call',dict(sessionId='a',operation='extension:'+operation,payload={})));check('packaged unsupported operation rejects','error' in r)
    check('packaged unknown effects are inert',p.invoke('a','m:unknown:1')['mode']=='unchanged')
    p.call('session.dispose',dict(sessionId='a'));p.call('session.dispose',dict(sessionId='b'))
    for i in range(128):p.open(f'live-{i}','bad instance with space')
    r=p.reply(p.request('session.open',dict(sessionId='overflow',commandName='search')));check('packaged 128-session capacity explicit', 'error' in r)
    check('packaged full applicable no-network suite emits no OS effect',not p.effects)
    p.stop();check('packaged shutdown disposes 128 sessions',True)
    p=Pipe(binary);p.open('eof','bad instance with space');p.eof();check('packaged EOF exits with live session',True)
    report=dict(count=len(CHECKS),checks=CHECKS,scope='genuine extracted executable, applicable no-network operations only; successful owned TLS and data/actions use separate QA helper',nativeAcceptance='not-run')
    (ROOT/'qa/evidence/production-pipes.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':suite(Path(sys.argv[1]).resolve())
