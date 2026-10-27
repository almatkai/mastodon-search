#!/usr/bin/env python3
"""Actual SDK JSONL subprocess + owned TLS fixture. Never uses a user service.

Usage: python3 qa/pipes.py <production-bin> <test-only-trusted-helper>
The helper gets an ephemeral CA as argv[1]. Production is tested without it.
"""
import collections
import hashlib
import http.server
import json
import os
from pathlib import Path
import queue
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.work/pipes'
WORK.mkdir(parents=True, exist_ok=True)
ACCOUNT = dict(id='109912345678901234', display_name='Owned A', acct='local', avatar='https://avatar.invalid/a.png', url='https://social.invalid/@local', followers_count=42, bot=True)
PAYLOAD = dict(accounts=[ACCOUNT, dict(ACCOUNT, id=7, acct='r@else.invalid', bot=False), ACCOUNT], hashtags=[dict(name='z', url='https://social.invalid/t/z'), dict(name='z', url='https://social.invalid/t/z2')])
CHECKS = []


def check(label, predicate=True):
    assert predicate, label
    CHECKS.append(label)
    print(f'ok {len(CHECKS)} - {label}', flush=True)


class Fixture(http.server.ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self):
        super().__init__(('127.0.0.1', 0), Handler)
        self.paths, self.starts, self.closes, self.gates = [], collections.defaultdict(threading.Event), collections.defaultdict(threading.Event), collections.defaultdict(threading.Event)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *_): pass
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query, keep_blank_values=True).get('q', [''])[0]
        self.server.paths.append(self.path)
        if not q.startswith('slow'): self.server.starts[q].set()
        body = json.dumps(PAYLOAD).encode()
        status, mime = 200, 'application/json'
        if q.startswith('name:'):
            body = json.dumps(dict(accounts=[dict(ACCOUNT, display_name=q)], hashtags=[])).encode()
        if q=='slow-replacement':
            body=json.dumps(dict(accounts=[dict(ACCOUNT,display_name='New fetched row',acct='replacement',url='https://social.invalid/@replacement')],hashtags=[])).encode()
        if q.startswith('error'): status, body = 429, b'owned error'
        if q == 'bad-json': body = b'{bad'
        if q == 'bad-arrays': body = b'{"accounts":null,"hashtags":[]}'
        if q == 'bad-types': body = b'{"accounts":[],"hashtags":[{"name":2,"url":true}]}'
        if q == 'bad-mime': mime = 'text/plain'
        if q == 'suffix-json': mime = 'application/activity+json'
        if q == 'oversized': body = b' ' * (2*1024*1024+1)
        if q == 'too-many': body = json.dumps(dict(accounts=[], hashtags=[dict(name='x', url='https://x.invalid')]*513)).encode()
        if q == 'deep': body = ('['*70+'0'+']'*70).encode()
        if q == 'redirect':
            self.send_response(302); self.send_header('Location', '/api/v2/search?type=accounts&q=redirect');self.send_header('Content-Length','0');self.end_headers();return
        if q == 'cross-origin':
            self.send_response(302);self.send_header('Location','https://localhost:1/forbidden');self.send_header('Content-Length','0');self.end_headers();return
        try:
            self.send_response(status);self.send_header('Content-Type', mime);self.send_header('Content-Length', str(len(body)));self.end_headers()
            if q.startswith('slow'):
                self.wfile.write(body[:10]);self.wfile.flush()
                self.server.starts[q].set()  # a real partial body is on the socket
                end=time.monotonic()+3
                self.connection.settimeout(.05)
                while time.monotonic()<end and not self.server.gates[q].is_set():
                    try:
                        if not self.connection.recv(1): self.server.closes[q].set();break
                    except socket.timeout: continue  # timeout is NOT cancellation evidence
                    except (ConnectionError, ssl.SSLError, OSError): self.server.closes[q].set();break
                self.server.gates[q].wait(2)
                self.wfile.write(body[10:]);self.wfile.flush()
            else:
                self.wfile.write(body);self.wfile.flush()
        except (BrokenPipeError, ConnectionError, ssl.SSLError, OSError):
            self.server.closes[q].set()


class Pipe:
    def __init__(self, executable, ca=None):
        self.queue, self.backlog, self.effects = queue.Queue(), [], []
        env = dict(os.environ, HOME=str(WORK/'home'), XDG_CACHE_HOME=str(WORK/'home/cache'), XDG_CONFIG_HOME=str(WORK/'home/config'), TMPDIR=str(WORK))
        self.p = subprocess.Popen([str(executable)] + ([str(ca)] if ca else []), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        self.writer = threading.Lock()
        def read():
            for line in self.p.stdout:
                try: value=json.loads(line)
                except Exception as e: self.queue.put(e); return
                if value.get('type') == 'request': self.effects.append(value)
                self.queue.put(value)
            self.queue.put(EOFError())
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
        hello=self.wait(lambda v:v.get('type')=='hello')
        assert hello['id']=='com.tezbar.native.mastodon-search' and hello['sdkVersion']=='0.1.1'
        self.call('initialize',dict(protocol=1,extensionId=hello['id'],platform='macOS',packageDir=str(WORK),dataDir=str(WORK/'data'),tempDir=str(WORK/'temp'),grantedCapabilities=['shell.open','clipboard.write']))
    def send(self, value):
        with self.writer:
            self.p.stdin.write(json.dumps(value,separators=(',',':')).encode()+b'\n');self.p.stdin.flush()
    def request(self, method, params):
        id='h:'+str(uuid.uuid4());self.send(dict(type='request',id=id,method=method,params=params));return id
    def wait(self, test, timeout=8):
        for i,v in enumerate(self.backlog):
            if test(v):return self.backlog.pop(i)
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            v=self.queue.get(timeout=max(.001,end-time.monotonic()))
            if isinstance(v,BaseException):raise v
            if test(v):return v
            self.backlog.append(v)
        raise TimeoutError()
    def reply(self, id): return self.wait(lambda v:v.get('type')=='response' and v.get('id')==id)
    def call(self, method, params):
        r=self.reply(self.request(method,params));assert 'error' not in r,r;return r['result']
    def op(self, sid, operation, payload=None):return self.call('session.call',dict(sessionId=sid,operation='extension:'+operation,payload=payload or {}))
    def open(self, sid, instance, query=''):return self.call('session.open',dict(sessionId=sid,commandName='search',preferences=dict(instance=instance),searchText=query))
    def refresh(self,sid):return self.op(sid,'refresh-session')
    def complete(self,sid,condition=None):
        end=time.monotonic()+8
        while time.monotonic()<end:
            r=self.refresh(sid)
            if not r['root']['props']['isLoading'] and (condition is None or condition(r)):return r
            self.wait(lambda v:v.get('type')=='event' and v.get('sessionId')==sid)
        raise TimeoutError('completion')
    def invoke(self,sid,id,values=None):return self.op(sid,'invoke-action',dict(actionId=id,formValues=values or {}))
    def effect(self):return self.wait(lambda v:v.get('type')=='request')
    def ack(self,e,result):self.send(dict(type='response',id=e['id'],result=result))
    def finish_effect(self,sid,e,result):
        self.ack(e,result);return self.complete(sid,lambda r:r.get('message')!='Working…')
    def stop(self):
        if self.p.poll() is None:
            self.call('shutdown',{});self.p.wait(5)
        assert self.p.returncode==0,self.p.stderr.read().decode()
    def eof(self):
        self.p.stdin.close();self.p.wait(5);assert self.p.returncode==0


def action(r,title):return next(a['id'] for a in r['actions'] if a['title']==title)
def titles(r):return [x['props']['title'] for s in r['root']['children'] for x in s.get('children',[]) if x['type']=='List.Item']
def change(p,sid,q):return p.op(sid,'search-text-changed',dict(searchText=q))


def suite(prod, helper):
    ca=WORK/'ca.pem';key=WORK/'key.pem'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=Owned Mastodon QA','-addext','subjectAltName=IP:127.0.0.1,DNS:localhost','-keyout',str(key),'-out',str(ca)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    server=Fixture();tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(ca,key);server.socket=tls.wrap_socket(server.socket,server_side=True)
    threading.Thread(target=server.serve_forever,daemon=True).start();instance=f'127.0.0.1:{server.server_port}'
    p=Pipe(prod)
    p.open('reject',instance,'owned');r=p.complete('reject')
    check('genuine production TLS rejects untrusted owned CA', 'securely' in r.get('message','') and not titles(r));p.stop()
    p=Pipe(helper,ca)
    direct=subprocess.Popen([str(helper),str(ca),'--direct-preferences',instance],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,HOME=str(WORK/'home'),TMPDIR=str(WORK)))
    assert server.starts['slow-direct-preferences'].wait(4)
    out,err=direct.communicate(b'cancel\n',timeout=5)
    assert direct.returncode==0,err
    check('direct adapter invalid preference revokes actual TLS body read before validation',json.loads(out)['invalidPreferenceCancelled'] and server.closes['slow-direct-preferences'].wait(4));server.gates['slow-direct-preferences'].set()
    r=p.open('main',instance)
    check('SDK hello/initialize/default empty search and exact dropdown',not titles(r) and r['root']['props']['searchBarAccessory']['props']['value']=='accounts')
    change(p,'main','A');r=p.complete('main')
    check('trusted test-only transport gets exact source payload, duplicates/order/string IDs',titles(r)==['Owned A','Owned A','Owned A','z','z'] and r['root']['children'][0]['children'][0]['props']['sourceId']==ACCOUNT['id'])
    (ROOT/'qa/evidence/native-view.json').write_text(json.dumps(r,indent=2)+'\n')
    for title,method,params in [('Visit Profile','host.shell.open',dict(target=ACCOUNT['url'])),('Copy Profile URL','host.clipboard.write',dict(text=ACCOUNT['url'])),('Copy Handle','host.clipboard.write',dict(text=f'@local@{instance}')),('Visit Hashtag','host.shell.open',dict(target=PAYLOAD['hashtags'][0]['url']))]:
        id=action(r,title);a=p.request('session.call',dict(sessionId='main',operation='extension:invoke-action',payload=dict(actionId=id)));b=p.request('session.call',dict(sessionId='main',operation='extension:invoke-action',payload=dict(actionId=id)))
        replies=[p.reply(a)['result'],p.reply(b)['result']];e=p.effect()
        check(f'{title}: concurrent duplicate is one view / one unchanged / one frozen effect',sorted(x['mode'] for x in replies)==['unchanged','view'] and e['method']==method and e['params']==params)
        before=len(p.effects);r=p.finish_effect('main',e,dict(ok=True,message='Owned acknowledgement'));assert len(p.effects)==before
        check(f'{title}: explicit repeat receives fresh action ID',action(r,title)!=id)
    for ack in [None,True,'ok',{},dict(ok=False),dict(ok=True,message=None),dict(ok=True,extra=1)]:
        p.invoke('main',action(r,'Copy Handle'));e=p.effect();r=p.finish_effect('main',e,ack)
        check('malformed acknowledgement exposes manual-only retry',any(a['title']=='Retry Last Action' for a in r['actions']))
        before=len(server.paths);p.refresh('main');assert len(p.effects)>0
        p.invoke('main',action(r,'Retry Last Action'));retry=p.effect();assert retry['params']==e['params'];assert len(server.paths)==before
        r=p.finish_effect('main',retry,dict(ok=True));check('retry uses frozen text and no requery',retry['params']==e['params'])
    previous=action(r,'Copy Handle');parts=previous.split(':');p.invoke('main',previous);held=p.effect();before=len(p.effects)
    for guess in range(int(parts[-1])+1,int(parts[-1])+40):
        assert p.invoke('main',f'{parts[0]}:{parts[1]}:{guess}')['mode']=='unchanged'
    check('future/hidden effect tokens stay inert while an effect is pending',len(p.effects)==before)
    r=p.finish_effect('main',held,dict(ok=True))
    pending=change(p,'main','slow-replacement');assert server.starts['slow-replacement'].wait(3)
    p.invoke('main',action(pending,'Copy Handle'));held=p.effect();server.gates['slow-replacement'].set();r=p.complete('main')
    check('HTTP completion cannot restore effect IDs or erase pending effect ownership',titles(r)==['New fetched row'] and not any(a['title']=='Copy Handle' for a in r['actions']))
    r=p.finish_effect('main',held,{})
    n=len(server.paths);p.invoke('main',action(r,'Retry Last Action'));retry=p.effect()
    check('manual effect retry survives crossed payload replacement and keeps old displayed text',retry['params']==held['params']==dict(text=f'@local@{instance}') and len(server.paths)==n)
    r=p.finish_effect('main',retry,dict(ok=True))
    stale=action(r,'Copy Handle');check('foreign/unknown action IDs are inert',p.invoke('main','m:foreign:1')['mode']=='unchanged')
    for field in ['name:A','name:B','name:A']:
        change(p,'main',field);r=p.complete('main');assert titles(r)==[field]
    r=change(p,'main','name:B');check('A/B/A uses exact cached B while loading',titles(r)==['name:B']);r=p.complete('main')
    r=change(p,'main','error-refresh');r=p.complete('main');check('failed refresh keeps previous payload, manual search retry, no auto retry',titles(r)==['name:B'] and any(a['title']=='Retry Search' for a in r['actions']))
    (ROOT/'qa/evidence/failure-view.json').write_text(json.dumps(r,indent=2)+'\n')
    n=len(server.paths);p.refresh('main');p.refresh('main');check('refresh is effect-free and request-free',len(server.paths)==n)
    p.invoke('main',action(r,'Retry Search'));r=p.complete('main');check('manual search retry issues precisely one request',len(server.paths)==n+1)
    check('revoked old data action remains inert after query revisions',p.invoke('main',stale)['mode']=='unchanged')
    for k in ['hashtags','accounts','hashtags']:
        r=p.invoke('main',r['root']['props']['searchBarAccessory']['props']['actionId'],dict(value=k));r=p.complete('main');assert r['root']['props']['searchBarAccessory']['props']['value']==k
    check('kind A/B/A retains ownership through failed HTTP',r['root']['props']['searchBarAccessory']['props']['value']=='hashtags')
    r=p.invoke('main',r['root']['props']['searchBarAccessory']['props']['actionId'],dict(value=9));check('invalid dropdown revokes first and leaves a visible draft error','Choose' in r.get('message',''))
    r=p.invoke('main',r['root']['props']['searchBarAccessory']['props']['actionId'],dict(value='accounts'));r=p.complete('main')
    for q in ['bad-json','bad-arrays','bad-types','bad-mime','oversized','too-many','deep','redirect','cross-origin']:
        change(p,'main',q);r=p.complete('main');check(f'{q}: visible bounded failure and retained rows',bool(r.get('message')) and titles(r)==['name:B'])
    change(p,'main','suffix-json');r=p.complete('main');check('locked structured JSON MIME accepted',len(titles(r))==5)
    for q in ['a&b=2','a+b','#tag','%','a b','\t','Русский 😀',' leading ']:
        change(p,'main',q);p.complete('main');raw=f'https://{instance}/api/v2/search?type=accounts&q={q}'
        # WHATWG oracle covers all; literal network path checked for important separators.
        if q=='a&b=2':assert server.paths[-1].endswith('q=a&b=2')
        if q=='#tag':assert server.paths[-1].endswith('q=')
    check('real HTTP raw ampersand/plus/fragment/percent/space/tab/Unicode routes',True)
    for bad in [123,'x'*4097]:
        q=f'slow-invalid-{str(bad)[:3]}';change(p,'main',q);assert server.starts[q].wait(3)
        r=change(p,'main',bad);assert server.closes[q].wait(4)
        check('invalid input cancels actual active body read before validation','Search' in r.get('message','') and not r['root']['props']['isLoading']);server.gates[q].set()
        change(p,'main','name:valid');r=p.complete('main');assert titles(r)==['name:valid']
    q='slow-old';change(p,'main',q);assert server.starts[q].wait(3);change(p,'main','name:new');r=p.complete('main');server.gates[q].set()
    check('crossed old response cannot restore query/data',r['root']['props']['searchText']=='name:new' and titles(r)==['name:new'])
    r=change(p,'main','');n=len(server.paths);check('empty query retains previous payload and executes nothing',titles(r)==['name:new'] and not r['root']['props']['isLoading']);assert len(server.paths)==n
    change(p,'main','A');r=p.complete('main');p.invoke('main',action(r,'Copy Handle'));e=p.effect();change(p,'main','name:after-effect');p.ack(e,dict(ok=True));r=p.complete('main');check('late effect ACK cannot restore old query/surface',titles(r)==['name:after-effect'])
    q='slow-dispose';change(p,'main',q);assert server.starts[q].wait(3);p.call('session.dispose',dict(sessionId='main'));assert server.closes[q].wait(4);server.gates[q].set();check('dispose releases active socket',True)
    p.open('revision',instance)
    p.op('revision','search-text-changed',dict(searchText='slow-input-time',inputRevision=1));assert server.starts['slow-input-time'].wait(3)
    before=len(server.paths);r=p.op('revision','search-text-changed',dict(searchText='name:draft',inputRevision=2,draftOnly=True));assert server.closes['slow-input-time'].wait(4);server.gates['slow-input-time'].set()
    check('input-time draft revokes actual body read without starting replacement HTTP',len(server.paths)==before and r['root']['props']['__inputRevision']==2)
    r=p.op('revision','search-text-changed',dict(searchText='name:draft',inputRevision=2));r=p.complete('revision');check('debounced promotion of same client revision fetches once',titles(r)==['name:draft'] and len(server.paths)==before+1)
    control=r['root']['props']['searchBarAccessory']['props']['actionId']
    requests=[]
    for rev,k in [(3,'hashtags'),(4,'accounts'),(5,'hashtags')]:
        requests.append(p.request('session.call',dict(sessionId='revision',operation='extension:invoke-action',payload=dict(actionId=control,formValues=dict(value=k,inputRevision=rev)))))
    for id in requests:p.reply(id)
    r=p.complete('revision');check('rapid dropdown A/B/A from same displayed control preserves latest input revision',r['root']['props']['searchBarAccessory']['props']['value']=='hashtags' and r['root']['props']['__inputRevision']==5)
    check('stale dropdown input revision is inert unchanged',p.invoke('revision',control,dict(value='accounts',inputRevision=4))['mode']=='unchanged')
    check('native model revision and client input revision remain independent',r['root']['props']['__modelRevision']>r['root']['props']['__inputRevision'])
    p.call('session.dispose',dict(sessionId='revision'))
    p.open('stale-rpc',instance)
    p.op('stale-rpc','search-text-changed',dict(searchText='slow-stale-rpc',inputRevision=9));assert server.starts['slow-stale-rpc'].wait(3)
    old=p.op('stale-rpc','search-text-changed',dict(searchText='old input',inputRevision=8));assert old['mode']=='unchanged'
    server.gates['slow-stale-rpc'].set();r=p.complete('stale-rpc')
    check('stale SDK search RPC cannot cancel newer scope-owned HTTP work',r['root']['props']['searchText']=='slow-stale-rpc' and not r.get('message') and len(titles(r))==5)
    p.call('session.dispose',dict(sessionId='stale-rpc'))
    for i in range(140):
        sid=f'cancel-{i}';id='h:'+str(uuid.uuid4())
        # One write preserves reader-order cancellation before handler commit.
        first=dict(type='request',id=id,method='session.open',params=dict(sessionId=sid,commandName='search',preferences=dict(instance=instance)))
        second=dict(type='cancel',requestId=id)
        with p.writer:p.p.stdin.write((json.dumps(first)+'\n'+json.dumps(second)+'\n').encode());p.p.stdin.flush()
        reply=p.reply(id)
        if 'result' in reply: p.call('session.dispose',dict(sessionId=sid))
    check('140 real SDK cancel/open races recover capacity (completed opens explicitly disposed)',True)
    for i in range(128):p.open(f'capacity-{i}',instance)
    result=p.reply(p.request('session.open',dict(sessionId='overflow',commandName='search')))
    check('128 live sessions accepted, 129th rejected explicitly','error' in result)
    for op in ['load-more','made-up']:
        result=p.reply(p.request('session.call',dict(sessionId='capacity-0',operation='extension:'+op,payload={})))
        check(f'unknown/unsupported operation {op} rejects','error' in result)
    p.stop();check('shutdown with 128 sessions exits cleanly',True)
    p=Pipe(helper,ca);p.open('eof',instance,'slow-eof');assert server.starts['slow-eof'].wait(3);p.eof();assert server.closes['slow-eof'].wait(4);server.gates['slow-eof'].set();check('EOF aborts body read and scoped tasks',True)
    for frame in [b'{bad\n',b'[]\n',b'{}\r\n',b'{"x":"'+b'x'*(16*1024*1024)+b'"}\n',b'{']:
        x=subprocess.Popen([str(prod)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out,err=x.communicate(frame,timeout=8);check('malformed/oversized/truncated frame terminates boundedly',x.returncode!=0)
    server.shutdown();server.server_close()
    report=dict(checks=CHECKS,count=len(CHECKS),productionSha256=hashlib.sha256(Path(prod).read_bytes()).hexdigest(),trustedTransport='separate QA helper only; production CA rejection tested',nativeAcceptance='not-run')
    (ROOT/'qa/evidence/pipes.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':suite(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
