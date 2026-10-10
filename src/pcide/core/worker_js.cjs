'use strict';
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const inspector = require('node:inspector');
function readLine(){let text='',b=Buffer.alloc(1);while(fs.readSync(0,b,0,1,null)){if(b[0]===10)return text;text+=b.toString();if(text.length>65536)throw Error('command too large');}return '';}
const request=JSON.parse(readLine()), project=request.project, session=request.session;
function send(kind,data={}){fs.writeSync(1,JSON.stringify({session,kind,...data})+'\n');}
const manifest=JSON.parse(fs.readFileSync(path.join(project,'.pcide/project.json'),'utf8'));
const api={
 ocrMock:(image,text='OK')=>({kind:'ocr',source:image,items:[{text,confidence:.99,box:[0,0,80,28]}],simulated:true}),
 yoloMock:(image,label='object')=>({kind:'yolo',source:image,detections:[{label,confidence:.95,box:[10,10,100,60]}],simulated:true}),
 screenshotMock:(name='screen')=>({kind:'screenshot',name,simulated:true}),
 ui:{set:(id,properties)=>send('ui.set',{id,properties}),open:(window)=>send('ui.window.open',{window}),close:(window)=>send('ui.window.close',{window})}
};
const filename=path.join(project,manifest.entry);
const scriptUrl=require('node:url').pathToFileURL(filename).href;
let source=fs.readFileSync(filename,'utf8');
const sdk=process.env.PCIDE_TYPESCRIPT||path.join(process.env.PCIDE_ROOT,'sdk/typescript/package/lib/typescript.js');
const published=process.env.PCIDE_PREPARED_NODE==='1';
const ts=published?null:require(sdk), sourceContract=published?null:require('./source_contract.cjs');
const preparedProject=published?JSON.parse(fs.readFileSync(path.join(project,'.pcide/prepared-node.json'),'utf8')):null;
if(published&&(preparedProject.version!==1||!preparedProject.exports||!preparedProject.metadata||typeof preparedProject.dataSource!=='string'))throw Error('invalid published Node contract');
if(!published&&manifest.language==='typescript'){
 const result=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS},fileName:filename,reportDiagnostics:true});
 const errors=(result.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error);
 if(errors.length)throw Error(ts.flattenDiagnosticMessageText(errors[0].messageText,'\n'));
 source=result.outputText;
}
source=published?source:sourceContract.prepare(ts,fs.readFileSync(filename,'utf8'),filename,project,manifest.language).source;
const context=vm.createContext({console:{log:(...args)=>send('stdout',{text:args.map(a=>typeof a==='string'?a:JSON.stringify(a)).join(' ')+'\n'}),
 error:(...args)=>send('stderr',{text:args.map(String).join(' ')+'\n'})},
 require:name=>name==='pcide'?api:require(require.resolve(name,{paths:[path.dirname(filename)]})),
 module:{exports:{}},exports:{},__filename:filename,__dirname:path.dirname(filename),setTimeout,clearTimeout,Buffer,process});
const modules=new Map(), timeout=Math.max(1,Math.round((manifest.execution?.timeout_seconds||60)*1000));
const projectRequire=(name,parent=filename)=>{
 if(name==='pcide')return api;
 const candidate=path.resolve(path.dirname(parent),name);
 if(name.startsWith('.')&&candidate.startsWith(path.join(project,'src')+path.sep)) {
  const target=[candidate,candidate+'.js',candidate+'.ts',path.join(candidate,'index.js'),path.join(candidate,'index.ts')].find(file=>fs.existsSync(file)&&fs.statSync(file).isFile());
  if(target) {
   if(modules.has(target))return modules.get(target).exports;
   const relative=path.relative(project,target).replaceAll('\\','/');
   const prepared=published?{source:fs.readFileSync(target,'utf8'),names:preparedProject.exports[relative]||[]}:
       sourceContract.prepare(ts,fs.readFileSync(target,'utf8'),target,project,target.endsWith('.ts')?'typescript':'javascript');
   const module={exports:{}};modules.set(target,module);
   const previous=[context.__module,context.__require,context.__filename,context.__dirname];
   context.__module=module;context.__require=name=>projectRequire(name,target);context.__filename=target;context.__dirname=path.dirname(target);
   try {new vm.Script(`(function(require,module,exports,__filename,__dirname){${prepared.source}\n${prepared.names.map(name=>`module.exports[${JSON.stringify(name)}]=${name};`).join('\n')}})(__require,__module,__module.exports,__filename,__dirname);`,{filename:target}).runInContext(context,{timeout});}
   finally {[context.__module,context.__require,context.__filename,context.__dirname]=previous;}
   return module.exports;
  }
 }
 return require(require.resolve(name,{paths:[path.dirname(parent)]}));
};
context.require=name=>projectRequire(name);
for(const value of Object.values(published?preparedProject.metadata:sourceContract.contract(project).metadata)) {
 if(!value?.public||!value.file||!value.sourceName)continue;
 const target=path.resolve(project,value.file);
 if(!target.startsWith(path.join(project,'src')+path.sep))throw Error('公开子程序文件越界');
 if(target===filename)continue;
 if(context[value.sourceName])throw Error('公开子程序名称重复');
 context[value.sourceName]=(...args)=>{const exports=projectRequire('./'+path.relative(path.dirname(filename),target));if(typeof exports[value.sourceName]!=='function')throw Error('公开接口不存在');return exports[value.sourceName](...args);};
}
const debug=new inspector.Session();
let debugRun = null;
if(request.debug){
 debug.connect();
 debug.on('Debugger.scriptParsed',event=>{
  const parsed=event.params.url;
  if(parsed!==scriptUrl) return;
  for(const [file,lines] of Object.entries(request.breakpoints||{})){
   if(path.resolve(file)!==path.resolve(filename)) continue;
   for(const line of lines) debug.post('Debugger.setBreakpointByUrl',{url:parsed,lineNumber:Number(line)-1});
  }
 });
 debug.on('Debugger.paused',event=>{
  const frames=event.params.callFrames, current=frames.find(f=>f.url===scriptUrl)||frames[0], variables={};
  const scopes=current.scopeChain.slice(0,2).filter(scope=>scope.object?.objectId);
  let pending=scopes.length;
  const finish=()=>{
   if(pending>0) return;
   send('paused',{file:filename,line:current.location.lineNumber+1,variables,stack:frames.slice(0,32).map(f=>({file:f.url===scriptUrl?filename:f.url,line:f.location.lineNumber+1,function:f.functionName}))});
   for(;;){const line=readLine();if(!line){process.exit(130);}const command=JSON.parse(line);if(command.session!==session)continue;
    const action={continue:'Debugger.resume',step:'Debugger.stepInto',next:'Debugger.stepOver',out:'Debugger.stepOut'}[command.command];
    if(command.command==='stop')process.exit(130);if(action){send('resumed');debug.post(action);break;}
   }
  };
  if(!pending) finish();
  for(const scope of scopes) debug.post('Runtime.getProperties',{objectId:scope.object.objectId,ownProperties:true},(error,result)=>{
   if(!error) for(const property of (result.result||[]).slice(0,100)) variables[property.name]=String(property.value?.value??property.value?.description??'');
   pending--; finish();
  });
 });
 debugRun=run=>debug.post('Debugger.enable',()=>run());
}
function invoke(handler,payload={}){context.__pcidePayload=payload;
 new vm.Script(`if(typeof ${handler} !== 'function')throw Error('event handler not found'); ${handler}(__pcidePayload);`,{filename:scriptUrl}).runInContext(context,{timeout:Math.max(1,Math.round((manifest.execution?.timeout_seconds||60)*1000))});}
function run(){
 try{
  new vm.Script(published?preparedProject.dataSource:sourceContract.dataSource(project),{filename:'pcide-program-data'}).runInContext(context,{timeout});
  new vm.Script(source,{filename:scriptUrl}).runInContext(context,{timeout:Math.max(1,Math.round((manifest.execution?.timeout_seconds||60)*1000))});
  send('ready');for(const handler of request.events||[])invoke(handler);
  if(request.keep_alive){
   require('node:readline').createInterface({input:process.stdin}).on('line',line=>{
    let command;
    try{command=JSON.parse(line);if(command.session!==session)return;
     if(command.command==='stop'){send('done',{ok:false,cancelled:true});process.exit(130);}
     if(command.command==='event'){if(!/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(command.handler))throw Error('invalid handler');
       invoke(command.handler,command.payload);send('event.done',{request_id:command.request_id});}
    }catch(error){send('error',{message:error.message,traceback:error.stack,request_id:command?.request_id});}
   }).on('close',()=>process.exit(0));
  }else{send('done',{ok:true});if(request.debug)debug.disconnect();}
 }catch(error){send('error',{message:error.message,traceback:error.stack});send('done',{ok:false});process.exit(1);}
}
if(debugRun) debugRun(run); else run();
