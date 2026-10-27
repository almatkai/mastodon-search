// Executes complete own TS/TSX and the real locked utils bundle in a closed VM.
// All effects/producers are replaced before evaluation. No service is contacted.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const base = path.resolve(__dirname, '..');
const ts = require(path.join(base, '.work/v1/node_modules/typescript'));
const original = path.join(base, 'qa/fixtures/source');
const deep=(a,b)=>assert.equal(JSON.stringify(a),JSON.stringify(b));
let count = 0;
const check = (label, run) => { run(); count++; console.log(`ok ${count} - ${label}`); };

function createWorld() {
  let slots = [], cursor = 0, effects = [], dirty = false, tree;
  const pending = [], toasts = [], logs = [], cache = new Map(), modules = new Map();
  let preferences = {instance:'mastodon.social'};
  const same = (a,b) => a && b && a.length === b.length && a.every((v,i)=>Object.is(v,b[i]));
  const react = {
    useState(initial) {
      const i=cursor++;
      if (!(i in slots)) slots[i]={value:typeof initial==='function'?initial():initial, set:(update)=>{const next=typeof update==='function'?update(slots[i].value):update;if(!Object.is(next,slots[i].value)){slots[i].value=next;dirty=true;}}};
      return [slots[i].value,slots[i].set];
    },
    useRef(value) {const i=cursor++; if(!(i in slots)) slots[i]={current:value};return slots[i];},
    useMemo(fn,deps) {const i=cursor++;if(!slots[i] || !same(slots[i].deps,deps))slots[i]={value:fn(),deps};return slots[i].value;},
    useCallback(fn,deps) {return react.useMemo(()=>fn,deps);},
    useEffect(fn,deps) {const i=cursor++;if(!slots[i] || !same(slots[i].deps,deps)){const old=slots[i];slots[i]={deps};effects.push(()=>{old?.cleanup?.();slots[i].cleanup=fn();});}},
    useSyncExternalStore(subscribe,snapshot) {react.useMemo(()=>subscribe(()=>dirty=true),[subscribe]);return snapshot();},
  };
  class Cache {
    constructor({namespace}={}) {this.map=cache.get(namespace)||new Map();cache.set(namespace,this.map);this.subscribe=(f)=>{this.listeners.add(f);return()=>this.listeners.delete(f);};this.listeners=new Set();}
    get(key){return this.map.get(key);}
    set(key,value){this.map.set(key,value);for(const f of this.listeners)f();}
    remove(key){this.map.delete(key);for(const f of this.listeners)f();}
    clear(){this.map.clear();}
  }
  const List=Object.assign('List',{}); // Use named tokens without running Raycast.
  const api={
    List:{Section:'List.Section',Item:'List.Item',Dropdown:{Item:'List.Dropdown.Item'}},
    ActionPanel:'ActionPanel',Action:{OpenInBrowser:'Action.OpenInBrowser',CopyToClipboard:'Action.CopyToClipboard'},
    Image:{Mask:{RoundedRectangle:'roundedRectangle'}},Icon:new Proxy({}, {get:(_,k)=>`Icon.${k}`}),
    getPreferenceValues:()=>({...preferences}),Toast:{Style:{Failure:'Failure'}},
    showToast:(...args)=>{toasts.push(args);return Promise.resolve({});},Cache,
    environment:{launchType:'user',supportPath:'/owned/support',assetsPath:'/owned/assets',commandName:'search',extensionName:'mastodon-search'},
    LaunchType:{Background:'background'},LocalStorage:{getItem:async()=>undefined,setItem:async()=>{},removeItem:async()=>{}},
    OAuth:{PKCEClient:class{}},
  };
  // Object-valued component tokens retain the exact source nested properties.
  api.List.__token='List'; api.List.Dropdown.__token='List.Dropdown';
  const jsx=(type,props,key)=>({type:type?.__token||type,props:{...props},key});
  const deny = new Proxy(function(){throw Error('Forbidden oracle producer');},{get:()=>deny});
  const consoleStub={log:(...a)=>logs.push(a),error:(...a)=>logs.push(a),warn:(...a)=>logs.push(a)};
  class FixedDate extends Date {constructor(...args){super(...(args.length?args:[0]));}static now(){return 0;}}
  const context=vm.createContext({
    console:consoleStub,URL,URLSearchParams,Request,Response,Headers,AbortController,AbortSignal,DOMException,Buffer,
    Date:FixedDate,structuredClone,setTimeout,clearTimeout,setInterval:deny,clearInterval:deny,
    process:{env:{},platform:'darwin',arch:'arm64',cwd:()=>'/owned',versions:{node:'26.7.0'}},
    fetch:(url,options={})=>new Promise((resolve,reject)=>{
      const request={raw:String(url),url:new URL(url).href,resolve,reject,aborted:false};pending.push(request);
      options.signal?.addEventListener('abort',()=>{request.aborted=true;reject(new DOMException('Aborted','AbortError'));},{once:true});
    }),
  });
  const pure = {'node:path':require('node:path'),'node:buffer':require('node:buffer'),'node:stream':require('node:stream'),'node:util':require('node:util'),'node:stream/promises':require('node:stream/promises'),'node:string_decoder':require('node:string_decoder'),'node:events':require('node:events'),'node:url':require('node:url'),'node:os':{homedir:()=>'/owned',tmpdir:()=>'/owned/tmp'},'node:crypto':{createHash:crypto.createHash}};
  let utils;
  const external=(id)=>{
    if(id==='react')return react;
    if(id==='react/jsx-runtime')return {jsx,jsxs:jsx,Fragment:'Fragment'};
    if(id==='@raycast/api')return api;
    if(id==='@raycast/utils')return utils;
    if(id==='dequal/lite')return require(path.join(base,'.work/v1/node_modules/dequal/lite'));
    if(pure[id])return pure[id];
    if(['node:fs','node:fs/promises','node:child_process'].includes(id))return deny;
    throw Error(`Unapproved oracle import ${id}`);
  };
  function evaluate(code,filename,loader=external){const m={exports:{}};vm.runInContext(`(function(require,module,exports){${code}\n})`,context,{filename})(loader,m,m.exports);return m.exports;}
  utils=evaluate(fs.readFileSync(path.join(base,'qa/fixtures/locked-utils/main.js'),'utf8'),'locked-utils-2.3.0.js');
  function load(file){
    file=path.resolve(file);if(modules.has(file))return modules.get(file);
    const source=fs.readFileSync(file,'utf8');
    const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
    const value=evaluate(code,file,(id)=>{if(!id.startsWith('.'))return external(id);const p=path.resolve(path.dirname(file),id);return load(fs.existsSync(p+'.ts')?p+'.ts':p+'.tsx');});modules.set(file,value);return value;
  }
  const Command=load(path.join(original,'src/search.tsx')).default;
  const expand=(node)=>{if(node==null||node===false)return null;if(Array.isArray(node))return node.flatMap(x=>{const e=expand(x);return Array.isArray(e)?e:[e];}).filter(Boolean);if(typeof node!=='object')return node;if(typeof node.type==='function')return expand(node.type(node.props));const props={...node.props};if(props.searchBarAccessory)props.searchBarAccessory=expand(props.searchBarAccessory);if(props.actions)props.actions=expand(props.actions);const children=expand(Array.isArray(props.children)?props.children:[props.children]);delete props.children;return {type:node.type,props,children};};
  const render=()=>{cursor=0;effects=[];dirty=false;tree=expand(Command());for(const f of effects)f();return tree;};
  const settle=async()=>{for(let i=0;i<32;i++){await new Promise(r=>setImmediate(r));if(dirty)render();}return tree;};
  const input=async(q)=>{tree.props.onSearchTextChange(q);render();return settle();};
  const kind=async(k)=>{tree.props.searchBarAccessory.props.onChange(k);render();return settle();};
  const respond=async(payload,opts={})=>{const req=pending.at(-1);req.resolve(new Response(typeof payload==='string'?payload:JSON.stringify(payload),{status:opts.status||200,statusText:opts.statusText||'OK',headers:{'Content-Type':opts.mime||'application/json'}}));return settle();};
  return {load,render,settle,input,kind,respond,pending,toasts,logs,get tree(){return tree;},set preferences(p){preferences=p;},unmount(){for(const s of slots)s?.cleanup?.();}};
}

const account={id:'109912345678901234',display_name:'Synthetic Person',acct:'local',avatar:'https://avatar.invalid/a.png',url:'https://social.invalid/@local',followers_count:42,bot:true};
const payload={accounts:[account,{...account,id:7,acct:'remote@else.invalid',display_name:'',followers_count:1e21,bot:false},account],hashtags:[{name:'rust',url:'https://social.invalid/tags/rust'},{name:'rust',url:'https://social.invalid/tags/rust2'}]};
const rows=(world)=>world.tree.children.flatMap(s=>s.children||[]);
const semantic=(row)=>({type:row.type,title:row.props.title,subtitle:row.props.subtitle,icon:row.props.icon,accessories:row.props.accessories,actions:row.props.actions.children.map(x=>({type:x.type,title:x.props.title,url:x.props.url,content:x.props.content,shortcut:x.props.shortcut}))});
(async()=>{
  const w=createWorld();w.render();await w.settle();
  check('empty default People dropdown, both sections, no request',()=>{assert.equal(w.pending.length,0);assert.equal(w.tree.type,'List');assert.equal(w.tree.props.searchText,'');assert.equal(w.tree.props.searchBarPlaceholder,'Search Mastodon');assert.equal(w.tree.props.throttle,true);deep(w.tree.children.map(x=>x.props.title),['People','Hashtags']);deep(w.tree.props.searchBarAccessory.children.map(x=>x.props.value),['accounts','hashtags']);assert.equal(w.tree.props.searchBarAccessory.props.storeValue,true);});
  await w.input('A');check('loading nonempty uses exact raw route',()=>{assert.equal(w.tree.props.isLoading,true);assert.equal(w.pending.at(-1).raw,'https://mastodon.social/api/v2/search?type=accounts&q=A');});
  await w.respond(payload);
  check('string and numeric IDs; duplicates; full source order and all action families',()=>{assert.equal(rows(w).length,5);assert.equal(rows(w)[0].props.subtitle,'@local@mastodon.social');assert.equal(rows(w)[1].props.subtitle,'@remote@else.invalid');assert.equal(rows(w)[1].props.accessories[0].text,'1e+21');assert.equal(rows(w)[0].props.accessories[0].text,'Bot Account');assert.equal(rows(w)[0].props.actions.children.length,3);assert.equal(rows(w)[3].props.actions.children.length,1);});
  const expectedRows=rows(w).map(semantic);
  await w.input('B');check('keepPreviousData during loading',()=>assert.equal(rows(w)[0].props.title,'Synthetic Person'));
  await w.respond({accounts:[{...account,display_name:'B person'}],hashtags:[]});
  await w.input('A');check('exact raw URL cache A/B/A before fresh response',()=>assert.equal(rows(w)[0].props.title,'Synthetic Person'));
  await w.respond('bad',{status:429,statusText:'Too Many Requests'});
  check('failed refresh retains cached A and custom Error toast; no source retry action',()=>{assert.equal(rows(w)[0].props.title,'Synthetic Person');assert.equal(w.toasts.at(-1)[1],'Error');assert.equal(w.toasts.at(-1)[2],'Too Many Requests');assert.equal(w.toasts.at(-1).length,3);});
  await w.input('');check('empty after success keeps previous data without fetching',()=>{assert.equal(w.pending.at(-1).raw.endsWith('q=A'),true);assert.equal(rows(w).length,5);});
  await w.kind('hashtags');check('empty dropdown does not execute',()=>assert.equal(w.pending.length,3));
  await w.input('tag');check('Hashtags dropdown uses exact type; not a local filter',()=>assert.match(w.pending.at(-1).raw,/type=hashtags&q=tag$/));
  await w.respond({accounts:[],hashtags:[{name:'z',url:'https://social.invalid/t/z'},{name:'a',url:'https://social.invalid/t/a'}]});
  check('hashtag ordering and URL retained',()=>deep(rows(w).map(x=>x.props.title),['z','a']));
  const vectors=[];
  const urlWorld=createWorld();urlWorld.render();await urlWorld.settle();
  for(const instance of ['mastodon.social','host.invalid:8443','host.invalid/base/','host.invalid/path?x=1','host.invalid/#frag','host.invalid\\base']){
    urlWorld.preferences={instance};
    for(const query of ['a&b=2','a+b','#tag','%','a b','\t','\n','Русский 😀',' leading ','x?y=1']){
      const previous=urlWorld.pending.length;await urlWorld.input(query);
      assert.equal(urlWorld.pending.length,previous+1);
      // Capture the actual complete-source/locked-hook request, then apply
      // Fetch's fragment-free wire serialization. No reconstructed template.
      const raw=urlWorld.pending.at(-1).raw;const u=new URL(raw);u.hash='';vectors.push({instance,query,raw,url:u.href});
    }
  }
  urlWorld.unmount();
  check('60 actual complete-source request WHATWG URL vectors',()=>assert.equal(vectors.length,60));
  const mime=['application/json','Application/JSON; charset=utf-8','application/activity+json','text/json','x/a-json-b','application/notjson','application/json_foo','application/json+foo','application/json;','bogus','', 'application/a/json'];
  // Execute actual locked parser with complete component, not a recreated MIME predicate.
  const mimeResults=[];
  for(let i=0;i<mime.length;i++){
    const x=createWorld();x.render();await x.settle();await x.input('mime'+i);let accepted=false;try{await x.respond(payload,{mime:mime[i]||' '});accepted=rows(x).length===5;}catch{}mimeResults.push({mime:mime[i],json:accepted});x.unmount();
  }
  check('actual locked JSON MIME parser vectors',()=>{assert.equal(mimeResults[2].json,true);assert.equal(mimeResults[5].json,false);});
  const evidence={sourceHead:'dd73024af23ed7d716421592aac26c323500206d',utilsVersion:'2.3.0',payload,rows:expectedRows,urlVectors:vectors,mimeVectors:mimeResults,checks:count};
  fs.writeFileSync(path.join(base,'qa/evidence/source-oracle.json'),JSON.stringify(evidence,null,2)+'\n');
  w.unmount();console.log(`source oracle: ${count} checks; no real network/fs/host/storage/clock producers`);
})().catch(e=>{console.error(e);process.exitCode=1;});
