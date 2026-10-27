// Type-check the complete pinned/proposed renderer functions against real React
// 19 types and pinned protocol types, with typed generic host/UI seams. This
// deliberately does not install or build the host and is not its full typecheck.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),ts=require(path.join(root,'.work/v1/node_modules/typescript'));
const work=path.join(root,'.work/host-types');fs.mkdirSync(work,{recursive:true});
const react=path.join(root,'.work/v1/node_modules/@types/react');
const misc=path.join(work,'misc.d.ts');fs.writeFileSync(misc,`
import type {ExtensionRefreshSessionResult} from '${path.join(root,'qa/fixtures/host/src/shared/extensionRuntime')}';
export const Hint:any,HintBar:any,Kbd:any,ViewHeader:any,Markdown:any,MetadataItem:any,MetadataSidebar:any,Button:any,Message:any,Action:any,ActionPanel:any,ActionRegistryContext:any,DetailRuntime:any,GridRuntime:any,Clipboard:any,environment:any,getPreferenceValues:any,NavigationContext:any,open:any,setRuntimeContext:any,showHUD:any,showToast:any,useCachedPromise:any,useFetch:any,useNavigation:any,usePromise:any;
export const FormRuntime:import('react').ComponentType<{ref?:any,root:any,title:string,onBack:()=>void,onSubmitForm:(values:Record<string,unknown>)=>void,onChangeField:(actionId:string,value:unknown)=>void,onInvokeAction:(id:string,values?:Record<string,unknown>)=>Promise<void>|void,onOpenActions:(ids?:string[])=>void,actionNotice?:any}>;
export const ActionPanelOverlay:import('react').ComponentType<{actions:Array<import('${path.join(root,'qa/fixtures/host/src/shared/extensionRuntime')}').ExtensionRuntimeAction>,onClose:()=>void,onExecute:(action:import('${path.join(root,'qa/fixtures/host/src/shared/extensionRuntime')}').ExtensionRuntimeAction)=>void}>;
export type FormRuntimeHandle={getValues:()=>Record<string,unknown>};
export function cx(...values:unknown[]):string;
export function buildColorConversionResults(query:string):Array<{id:string,title:string,subtitle:string,action:{type:string,text:string}}>;
export function startSessionRefresh(options:{sessionId:string,generation?:string,refreshMs?:number|null,subscribe?:any,subscribeVisibility?:any,refresh:()=>Promise<void>}):()=>void;
export type ExtensionRuntimeSurfaceProps={sessionId:string,title:string,extensionId:string,commandName:string,root:any,actions:any[],actionNotice?:any,onBack:()=>void,onSearchTextChanged:(s:string,r?:number)=>Promise<void>,onSearchInput?:(s:string,r:number)=>void,onLoadMore:()=>Promise<void>,onInvokeAction:(id:string,formValues?:Record<string,unknown>)=>Promise<void>};
export const ExtensionRuntimeSurface:import('react').ComponentType<ExtensionRuntimeSurfaceProps>;
export type ExtensionManifest=any;export type ExtensionPlatform=any;export type ExtensionRuntimeKind=any;export type NativeV2Info=any;export type LauncherCommandMetadata=any;
`);
const globalFile=path.join(work,'global.d.ts');fs.writeFileSync(globalFile,`
import type * as R from '${react}';
import type * as P from '${path.join(root,'qa/fixtures/host/src/shared/extensionRuntime')}';
declare global {
 namespace JSX {type Element=R.ReactElement;}
 interface Window {tezbar:{saveExtensionPreferences:(payload:any)=>Promise<void>;extensionLoadMore:(payload:any)=>Promise<P.ExtensionRefreshSessionResult>;getAssetIconDataUrl:(kind:string,path:string)=>Promise<string|null>;getAppIconDataUrl:(path:string)=>Promise<string|null>;clipboardWriteText:(text:string)=>Promise<void>;extensionDisposeSession:(payload:any)=>Promise<unknown>;extensionSearchTextChanged:(payload:{sessionId:string,searchText:string,inputRevision?:number,draftOnly?:boolean})=>Promise<P.ExtensionSearchTextChangedResult>;extensionInvokeAction:(payload:P.ExtensionInvokeActionRequest)=>Promise<P.ExtensionInvokeActionResult>;extensionRefreshSession:(payload:P.ExtensionRefreshSessionRequest)=>Promise<P.ExtensionRefreshSessionResult>;onExtensionSessionInvalidated?:any;onWindowVisibility?:any;extensionGetPreferences:(payload:any)=>Promise<any>;extensionSetPreferences:(payload:any)=>Promise<any>;extensionRunCommand:(payload:any)=>Promise<any>};}
}
`);
let result={};
for(const patched of [false,true]){
 const prefix=path.join(root,patched?'.work/host-patched':'qa/fixtures/host');
 const names=['src/renderer/src/raycast-api/list-runtime.tsx','src/renderer/ExtensionRuntimeView.tsx','src/renderer/src/raycast-api/index.tsx'].map(n=>path.join(prefix,n));
 const options={strict:true,noEmit:true,skipLibCheck:true,jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,moduleResolution:ts.ModuleResolutionKind.Bundler,target:ts.ScriptTarget.ES2022,esModuleInterop:true,types:[],lib:['lib.es2022.d.ts','lib.dom.d.ts','lib.dom.iterable.d.ts']};
 const host=ts.createCompilerHost(options);
 host.resolveModuleNames=(imports,from)=>imports.map(id=>{
  if(id==='react')return{resolvedFileName:path.join(react,'index.d.ts'),extension:ts.Extension.Dts};
  if(id==='react/jsx-runtime')return{resolvedFileName:path.join(react,'jsx-runtime.d.ts'),extension:ts.Extension.Dts};
  if(id.endsWith('shared/extensionRuntime'))return{resolvedFileName:path.join(root,'qa/fixtures/host/src/shared/extensionRuntime.ts'),extension:ts.Extension.Ts};
  if(id==='./list-runtime')return{resolvedFileName:path.join(prefix,'src/renderer/src/raycast-api/list-runtime.tsx'),extension:ts.Extension.Tsx};
  if(id.startsWith('.')&&!from.startsWith(react))return{resolvedFileName:misc,extension:ts.Extension.Dts};
  return ts.resolveModuleName(id,from,options,host).resolvedModule;
 });
 const program=ts.createProgram([...names,globalFile],options,host);
 const diagnostics=ts.getPreEmitDiagnostics(program).filter(d=>d.file&&names.includes(d.file.fileName));
 result[patched?'proposed':'baseline']=diagnostics.map(d=>({code:d.code,message:ts.flattenDiagnosticMessageText(d.messageText,' '),file:path.relative(prefix,d.file.fileName)}));
}
const key=d=>JSON.stringify(d);
const additional=result.proposed.filter(d=>!result.baseline.some(b=>key(b)===key(d)));
result.newDiagnostics=additional;result.scope='complete actual renderer bodies, typed host seams; not a full host build';
fs.writeFileSync(path.join(root,'qa/evidence/host-types.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result,null,2));assert.equal(additional.length,0,'Proposed patch introduces new type diagnostics');
