const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {runtime,walk}=require('./hook-vm.cjs');
const root=path.resolve(__dirname,'..');
let checks=[];
const check=(label,value)=>{assert.ok(value,label);checks.push(label);console.log(`ok ${checks.length} - ${label}`);};
const files=patched=>path.join(root,patched?'.work/host-patched':'qa/fixtures/host');
const clone=x=>JSON.parse(JSON.stringify(x));
const view=JSON.parse(fs.readFileSync(path.join(root,'qa/evidence/native-view.json'),'utf8'));view.root.props.__clientOwnedInput=true;
const baseProps={title:'Search Mastodon',commandName:'search',actions:view.actions,onBack(){},onRunPrimaryAction(){},onOpenActions(){},onSearchTextChanged(){},onLoadMore(){}};
const stubs={'../../ui/primitives':{Hint:'Hint',HintBar:'HintBar',Kbd:'Kbd',ViewHeader:'ViewHeader',cx:(...a)=>a.filter(Boolean).join(' ')},'../../ui/Markdown':{Markdown:'Markdown'},'./detail-runtime':{MetadataItem:'MetadataItem',MetadataSidebar:'MetadataSidebar'},'../../colorConverter':{buildColorConversionResults:()=>[]}};
function list(patched,globals={}){
  const r=runtime(stubs,globals);const m=r.load(files(patched)+'/src/renderer/src/raycast-api/list-runtime.tsx','exports.test={parseListAccessory,parseListRows,parseRowIcon,RowIcon,Accessory,SymbolIcon'+(patched?',listImageDimensions,SafeListImage':'')+'};');
  return{r,m};
}
const input=r=>walk(r.tree,n=>n.type==='input')[0];
const text=n=>typeof n==='string'?n:Array.isArray(n)?n.map(text).join(''):n?.props?text(n.props.children):'';
(async()=>{
  for(let patched of [false,true]){
    let {r,m}=list(patched);let p={...baseProps,root:clone(view.root)};p.root.props.searchText='';p.root.props.__inputRevision=null;let calls=[];p.onSearchInput=(q,rev)=>calls.push([q,rev]);r.render(m.ListRuntime,p);
    input(r).props.onChange({target:{value:'A'}});r.render();r.tick(200);input(r).props.onChange({target:{value:'B'}});r.render();
    p={...p,root:clone(p.root)};p.root.props.searchText='A';p.root.props.__inputRevision=1;r.render(m.ListRuntime,p);
    check(`${patched?'corrected':'baseline'} actual List input reconciliation`,input(r).props.value===(patched?'B':'A'));
    if(patched)check('input ownership fences at DOM input time before debounce',calls.length===2&&calls[1][0]==='B'&&calls[1][1]===2);
    if(patched){input(r).props.onChange({target:{value:'x'.repeat(4097)}});r.render();p={...p,root:clone(p.root)};p.root.props.searchText='';p.root.props.__inputRevision=3;r.render(m.ListRuntime,p);check('invalid draft stays visible in client input while native work is revoked',input(r).props.value.length===4097);}
    r.unmount();
    ({r,m}=list(patched));p={...baseProps,root:clone(view.root)};p.root.props.searchBarAccessory.props.value='hashtags';r.render(m.ListRuntime,p);
    const buttons=walk(r.tree,n=>n.type==='button'&&text(n)==='Hashtags');check(`${patched?'corrected':'baseline'} actual controlled dropdown selection`,buttons[0].props.className.includes('bg-white/[0.14]')===patched);
    const parsed=m.test.parseListRows(p.root);check(`${patched?'corrected':'baseline'} parser preserves order/string titles`,parsed.length===5&&parsed[3].title==='z'&&parsed[4].title==='z');
    check(`${patched?'corrected':'baseline'} icon mask preservation`,(parsed[0].icon.mask==='roundedRectangle')===patched);
    check(`${patched?'corrected':'baseline'} accessory tooltip preservation`,(parsed[0].accessories[0].tooltip==='Account is a bot')===patched);
    const icon=m.test.RowIcon({row:parsed[0]});check(`${patched?'corrected':'baseline'} actual avatar rendering path`,patched?icon.type===m.test.SafeListImage:icon.type==='img');
    const accessory=m.test.Accessory({accessory:parsed[0].accessories[0]});check(`${patched?'corrected':'baseline'} actual accessory render tooltip`,(accessory.props.title==='Account is a bot')===patched);
    p={...p,root:clone(p.root)};p.root.children=[{type:'List.EmptyView',props:{title:'No results',description:'Owned empty'}}];p.root.props.searchText='query';r.render(m.ListRuntime,p);check(`${patched?'corrected':'baseline'} actual empty-state rendering`,text(r.tree).includes(patched?'No results':'No matching applications'));
    r.unmount();
  }
  // Real parent functions, with their own async callbacks and state. Services are
  // replaced before module evaluation; test promises complete in controlled order.
  for(let patched of [false,true]){
    let refresh,searchResolve,actionResolve;
    const win={setTimeout:()=>1,clearTimeout(){},tezbar:{onExtensionSessionInvalidated(){},onWindowVisibility(){},extensionDisposeSession:async()=>({}),extensionSearchTextChanged:request=>request.draftOnly?Promise.resolve({ok:true,mode:'unchanged'}):new Promise(r=>searchResolve=r),extensionInvokeAction:()=>new Promise(r=>actionResolve=r),extensionRefreshSession:async()=>({...view,sessionId:'s',generation:'g'})}};
    const r=runtime({'./extensionSessionRefresh':{startSessionRefresh:opts=>{refresh=opts.refresh;return()=>{};}},'./ui/primitives':{Button:'Button',Message:'Message'},'./src/raycast-api':{ExtensionRuntimeSurface:'Surface'}},{window:win});
    const m=r.load(files(patched)+'/src/renderer/ExtensionRuntimeView.tsx');
    const initial={...clone(view),sessionId:'s',generation:'g',extensionId:'com.tezbar.native.mastodon-search',commandName:'search'};initial.root.props.searchText='';
    r.render(m.default,{initial,onBack(){}});let surface=walk(r.tree,n=>n.type==='Surface')[0];
    surface.props.onSearchInput?.('A',1);let promise=surface.props.onSearchTextChanged('A',patched?1:undefined);surface.props.onSearchInput?.('B',2);
    const result={...clone(initial)};result.root.props.searchText='A';result.root.props.__inputRevision=1;searchResolve(result);await promise;await r.flush();surface=walk(r.tree,n=>n.type==='Surface')[0];
    check(`${patched?'corrected':'baseline'} actual parent rejects A response after B input`,surface.props.root.props.searchText===(patched?'':'A'));
    promise=surface.props.onInvokeAction('owned-action');surface.props.onSearchInput?.('C',3);actionResolve(result);await promise;await r.flush();surface=walk(r.tree,n=>n.type==='Surface')[0];
    check(`${patched?'corrected':'baseline'} actual parent fences late effect view`,surface.props.root.props.searchText===(patched?'':'A'));
    await refresh();await r.flush();surface=walk(r.tree,n=>n.type==='Surface')[0];check(`${patched?'corrected':'baseline'} actual parent fences old refresh revision`,surface.props.root.props.searchText===(patched?'':'A'));
    promise=surface.props.onSearchTextChanged('C',patched?3:undefined);const newer=clone(result);newer.root.props.searchText='C';newer.root.props.__inputRevision=3;newer.root.props.__modelRevision=100;searchResolve(newer);await promise;await r.flush();
    win.tezbar.extensionRefreshSession=async()=>{const old=clone(newer);old.root.props.searchText='old-model';old.root.props.__modelRevision=99;return old;};
    await refresh();await r.flush();surface=walk(r.tree,n=>n.type==='Surface')[0];check(`${patched?'corrected':'baseline'} actual parent keeps native model revisions independent from client input`,surface.props.root.props.searchText===(patched?'C':'old-model'));
    r.unmount();
  }
  const {r,m}=list(true);
  const hooks={NavigationContext:{Provider:'Navigation'},setRuntimeContext(){}};
  const surfaceVm=runtime({'./action-runtime':{Action:'Action',ActionPanel:'ActionPanel',ActionPanelOverlay:'Overlay'},'./action-runtime-registry':{ActionRegistryContext:{Provider:'Registry'}},'./detail-runtime':{DetailRuntime:'Detail'},'./form-runtime':{FormRuntime:'Form'},'./grid-runtime':{GridRuntime:'Grid'},'./list-runtime':{ListRuntime:'NativeList'},'./hooks':hooks},{window:{addEventListener(){},removeEventListener(){}}});
  const surfaceModule=surfaceVm.load(files(true)+'/src/renderer/src/raycast-api/index.tsx');const controlId=view.root.props.searchBarAccessory.props.actionId;let controls=[];
  surfaceVm.render(surfaceModule.ExtensionRuntimeSurface,{sessionId:'owned',title:'Search Mastodon',extensionId:'owned',commandName:'search',root:view.root,actions:[{id:controlId,title:'Search for…'},{id:'retry-owned',title:'Retry Search'}],onBack(){},onSearchTextChanged(){},onLoadMore(){},onInvokeAction:(id,values)=>controls.push({id,values})});
  walk(surfaceVm.tree,n=>n.type==='NativeList')[0].props.onOpenActions();surfaceVm.render();check('actual parent surface hides dropdown plumbing from source action menu',walk(surfaceVm.tree,n=>n.type==='Overlay')[0].props.actions.every(a=>a.id!==controlId));
  walk(surfaceVm.tree,n=>n.type==='NativeList')[0].props.onRunPrimaryAction(controlId,{value:'hashtags'});check('actual parent surface still routes dropdown value changes',controls.length===1&&controls[0].id===controlId&&controls[0].values.value==='hashtags');surfaceVm.unmount();
  let debounced=[];const timed=list(true);let timedProps={...baseProps,root:clone(view.root),onSearchInput(){},onSearchTextChanged:(q,rev)=>debounced.push([q,rev])};timedProps.root.props.searchText='';
  timed.r.render(timed.m.ListRuntime,timedProps);input(timed.r).props.onChange({target:{value:'A'}});timed.r.render();input(timed.r).props.onChange({target:{value:'B'}});timed.r.tick(200);
  check('old debounce cannot borrow a newly typed client revision before effect cleanup',debounced.length===0);timed.r.tick(200);check('current debounce freezes its own input/revision pair',debounced.length===1&&debounced[0][0]==='B'&&debounced[0][1]===2);timed.r.unmount();
  const failure=JSON.parse(fs.readFileSync(path.join(root,'qa/evidence/failure-view.json'),'utf8'));let opened;
  r.render(m.ListRuntime,{...baseProps,root:failure.root,actions:failure.actions,onOpenActions:ids=>opened=ids});
  walk(r.tree,n=>n.type==='button'&&n.props['aria-label']==='Actions')[0].props.onClick();
  check('actual selected-row Actions control exposes manual retry with retained rows',opened.includes(failure.actions.find(a=>a.title==='Retry Search').id));r.unmount();
  for(const platform of ['MacIntel','Win32']){
    let invoked=[];const k=list(true,{navigator:{platform}});
    k.r.render(k.m.ListRuntime,{...baseProps,root:clone(view.root),onRunPrimaryAction:id=>invoked.push(id)});
    const event={key:'c',metaKey:platform==='MacIntel',ctrlKey:platform==='Win32',altKey:false,shiftKey:true,repeat:false,preventDefault(){},stopPropagation(){}};
    k.r.tree.props.onKeyDown(event);check(`actual selected-row Copy Profile URL shortcut on ${platform}`,invoked[0]===view.actions.find(a=>a.title==='Copy Profile URL').id);
    k.r.tree.props.onKeyDown({...event,altKey:true});check(`actual selected-row Copy Handle shortcut on ${platform}`,invoked[1]===view.actions.find(a=>a.title==='Copy Handle').id);
    k.r.tree.props.onKeyDown({...event,repeat:true});check(`actual shortcut repeat is inert on ${platform}`,invoked.length===2);k.r.unmount();
  }
  let stored=new Map([['tezbar-list-dropdown:owned:search','hashtags']]),restores=[];
  const restored=list(true,{window:{localStorage:{getItem:k=>stored.get(k)||null,setItem:(k,v)=>stored.set(k,v)}}});
  let restoredRoot=clone(view.root);restoredRoot.props.searchText='';restoredRoot.props.__inputRevision=null;restoredRoot.props.__draftOnly=false;
  restored.r.render(restored.m.ListRuntime,{...baseProps,root:restoredRoot,storageKey:'owned:search',onSearchInput(){},onRunPrimaryAction:(id,values)=>restores.push(values)});
  check('actual generic storeValue restores saved valid dropdown via read-only change control',restores.length===1&&restores[0].value==='hashtags'&&restores[0].inputRevision===1);
  walk(restored.r.tree,n=>n.type==='button'&&text(n)==='Hashtags')[0].props.onClick();check('clicking selected dropdown value emits no redundant change',restores.length===1);
  walk(restored.r.tree,n=>n.type==='button'&&text(n)==='People')[0].props.onClick();restored.r.render();check('actual generic storeValue writes only selected kind',stored.get('tezbar-list-dropdown:owned:search')==='accounts');restored.r.unmount();
  const png=new Uint8Array(fs.readFileSync(path.join(root,'assets/command-icon.png')));
  check('actual generic image preflight reads original PNG dimensions',String(m.test.listImageDimensions(png))==='512,512');
  check('actual image preflight rejects unknown/truncated bytes',m.test.listImageDimensions(new Uint8Array([1,2,3]))===null);
  let revoked=[],requested=[];let imageURL=class extends URL{};imageURL.createObjectURL=()=> 'blob:owned';imageURL.revokeObjectURL=u=>revoked.push(u);
  const a=list(true,{URL:imageURL,fetch:async(url,options)=>{requested.push({url:String(url),options});return new Response(png,{headers:{'content-type':'image/png'}});}});
  a.r.render(a.m.test.SafeListImage,{source:'https://avatar.invalid/a.png',mask:'roundedRectangle'});await a.r.flush();check('actual bounded image loader accepts owned raster via replaced producer',a.r.tree.type==='img'&&a.r.tree.props.style.borderRadius===4);a.r.unmount();
  check('actual image loader omits credentials/referrer/cache/redirects and releases URL',requested[0].options.credentials==='omit'&&requested[0].options.redirect==='error'&&requested[0].options.cache==='no-store'&&revoked[0]==='blob:owned');
  for(const mode of ['http','declared-oversized','stream-oversized','huge-dimensions']){
    let objects=0;const image=class extends URL{};image.createObjectURL=()=>{objects++;return'blob:unexpected';};image.revokeObjectURL=()=>{};
    let data=png,headers={};if(mode==='declared-oversized')headers['content-length']=String(2*1024*1024+1);if(mode==='stream-oversized')data=new Uint8Array(2*1024*1024+1);if(mode==='huge-dimensions'){data=png.slice();data[16]=127;data[17]=255;data[18]=255;data[19]=255;}
    const blocked=list(true,{URL:image,fetch:async()=>new Response(data,{headers})});blocked.r.render(blocked.m.test.SafeListImage,{source:mode==='http'?'http://avatar.invalid/a.png':'https://avatar.invalid/a.png'});await blocked.r.flush();check(`actual bounded avatar loader rejects ${mode} before creating image URL`,objects===0&&blocked.r.tree.type==='span');blocked.r.unmount();
  }
  const output={hostPin:'ea100cee3f69711de12485ba061950c5fc65258f',checks,count:checks.length,kind:'actual pinned/patched function execution in deterministic React hook VM; no installed GUI acceptance'};
  fs.writeFileSync(path.join(root,'qa/evidence/renderer.json'),JSON.stringify(output,null,2)+'\n');
})().catch(e=>{console.error(e);process.exitCode=1;});
