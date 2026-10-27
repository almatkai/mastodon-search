// Small deterministic React hook scheduler. Runs actual pinned component bodies;
// it does not model or reimplement their reconciliation decisions.
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const ts=require(path.join(root,'.work/v1/node_modules/typescript'));
exports.runtime=function(externals={},globals={}){
  let slots=[],cursor=0,effects=[],dirty=true,tree,component,props,now=0,next=1,timers=new Map();
  const same=(a,b)=>a&&b&&a.length===b.length&&a.every((v,i)=>Object.is(v,b[i]));
  const react={
    useState(initial){let i=cursor++;if(!(i in slots))slots[i]={value:typeof initial==='function'?initial():initial,set:u=>{let v=typeof u==='function'?u(slots[i].value):u;if(!Object.is(v,slots[i].value)){slots[i].value=v;dirty=true;}}};return[slots[i].value,slots[i].set];},
    useRef(value){let i=cursor++;if(!(i in slots))slots[i]={current:value};return slots[i];},
    useMemo(fn,deps){let i=cursor++;if(!slots[i]||!same(slots[i].deps,deps))slots[i]={value:fn(),deps};return slots[i].value;},
    useCallback(fn,deps){return react.useMemo(()=>fn,deps);},
    useEffect(fn,deps){let i=cursor++;if(!slots[i]||!same(slots[i].deps,deps)){let old=slots[i];slots[i]={deps};effects.push(()=>{old?.cleanup?.();slots[i].cleanup=fn();});}},
  };
  react.default=react;
  const jsx=(type,props,key)=>({type,props:props||{},key});
  const context=vm.createContext({console:{log(){},error(){},warn(){}},URL,Uint8Array,Blob,AbortController,
    setTimeout:(fn,ms=0)=>{let id=next++;timers.set(id,{fn,at:now+ms});return id;},clearTimeout:id=>timers.delete(id),...globals});
  const external=id=>{if(id==='react')return react;if(id==='react/jsx-runtime')return{jsx,jsxs:jsx,Fragment:'Fragment'};if(id in externals)return externals[id];throw Error('Unapproved renderer import '+id);};
  const load=(file,extra='')=>{
    let source=fs.readFileSync(file,'utf8')+'\n'+extra;
    let result=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}});
    const m={exports:{}};vm.runInContext('(function(require,module,exports){'+result.outputText+'\n})',context,{filename:file})(external,m,m.exports);return m.exports;
  };
  const render=(fn=component,value=props)=>{component=fn;props=value;let rounds=0;do{cursor=0;effects=[];dirty=false;tree=component(props);for(let f of effects)f();if(++rounds>20)throw Error('Renderer did not settle');}while(dirty);return tree;};
  const tick=ms=>{now+=ms;for(let[id,t]of [...timers])if(t.at<=now){timers.delete(id);t.fn();}if(dirty)render();};
  const flush=async()=>{for(let i=0;i<16;i++){await Promise.resolve();if(dirty)render();}return tree;};
  return{load,render,tick,flush,get tree(){return tree;},unmount(){for(let s of slots)s?.cleanup?.();},context};
};
exports.walk=function walk(node,predicate){if(!node)return[];if(Array.isArray(node))return node.flatMap(n=>walk(n,predicate));if(typeof node!=='object')return[];return[...(predicate(node)?[node]:[]),...walk(node.props?.children,predicate)];};
