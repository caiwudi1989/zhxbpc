'use strict';
// Shared Node source preparation used by the source worker and bytecode build.
const fs = require('node:fs'), path = require('node:path');
const aliases = {'文本':'string','文本型':'string','字符串':'string','整数':'number','整数型':'number',
  '长整数型':'number','字节型':'number','小数':'number','小数型':'number','数值型':'number','双精度小数型':'number',
  '布尔':'boolean','逻辑型':'boolean','逻辑型(布尔型)':'boolean','对象':'object','对象型':'object',
  '数组':'array','数组型':'array','日期时间型':'string','字节集':'bytes'};
function literal(item) {
  const type = aliases[item.type] || item.type, raw = String(item.defaultValue ?? item.default ?? item.value ?? '');
  if (type === 'string') return JSON.stringify(raw);
  if (type === 'number') {
    const number = Number(raw || 0);
    if (!Number.isFinite(number) || (['整数','整数型','长整数型','字节型'].includes(item.type) && !Number.isSafeInteger(number))) throw Error('初始数值无效');
    return String(number);
  }
  if (type === 'boolean') {
    if (!raw || ['false','0','否','假'].includes(raw.toLowerCase())) return 'false';
    if (['true','1','是','真'].includes(raw.toLowerCase())) return 'true';
    throw Error('初始逻辑值无效');
  }
  if (type === 'object' || type === 'array') {
    const value = JSON.parse(raw || (type === 'object' ? '{}' : '[]'));
    if ((type === 'array') !== Array.isArray(value) || value === null || typeof value !== 'object') throw Error('初始集合类型无效');
    return JSON.stringify(value);
  }
  if (type === 'bytes') return `Buffer.from(${JSON.stringify(raw)},'utf8')`;
  if (!raw && /^[\p{L}_][\p{L}\p{N}_]*$/u.test(type)) return `new ${type}()`;
  throw Error('不支持的数据初始类型: ' + type);
}
function read(root, name, fallback) {
  const file = path.join(root, '.pcide', name+'.json');
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file,'utf8')) : fallback;
}
function contract(root) {
  return {metadata:read(root,'routines',{}), data:read(root,'data',{variables:[],constants:[],types:[],apis:[]})};
}
function dataSource(root) {
  const {data}=contract(root), lines=[];
  for(const type of data.types||[]) {
    if(!/^[\p{L}_][\p{L}\p{N}_]*$/u.test(type.id))throw Error('数据类型名称无效');
    lines.push(`globalThis[${JSON.stringify(type.id)}]=class {constructor(){${(type.members||[]).map(member=>`this[${JSON.stringify(member.id)}]=${literal(member)};`).join('')}}};`);
  }
  for(const item of [...(data.variables||[]),...(data.constants||[])]) {
    if(item.scope==='local')continue;
    let expression=literal(item);
    if(item.array)for(const dimension of item.array.split(',').reverse())expression=`Array.from({length:${Number(dimension)}},()=>${expression})`;
    const constant=(data.constants||[]).some(value=>value.id===item.id);
    if(item.scope==='global') lines.push(`Object.defineProperty(globalThis,${JSON.stringify(item.id)},{value:${expression},writable:${!constant},configurable:false});`);
    else {
      if(!item.owner)throw Error('窗口/模块变量必须声明所属名称');
      lines.push(`globalThis[${JSON.stringify(item.owner)}]??={};Object.defineProperty(globalThis[${JSON.stringify(item.owner)}],${JSON.stringify(item.id)},{value:${expression},writable:${!constant},configurable:false});`);
    }
  }
  for(const api of data.apis||[])lines.push(`globalThis[${JSON.stringify(api.id)}]=()=>{throw Error('Node DLL ABI 尚未开放，请使用 Python/中文源码独立宿主');};`);
  return lines.join('\n');
}
function prepare(ts, text, filename, root, language) {
  const {metadata, data} = contract(root), relative = path.relative(root, filename).replaceAll('\\','/');
  const edits = [], file = ts.createSourceFile(filename,text,ts.ScriptTarget.Latest,true,language==='typescript'?ts.ScriptKind.TS:ts.ScriptKind.JS);
  if(file.parseDiagnostics.length) throw Error(ts.flattenDiagnosticMessageText(file.parseDiagnostics[0].messageText,'\n'));
  const names = [];
  function visit(node) {
    if(ts.isFunctionDeclaration(node) && node.name && node.body) {
      const name = node.name.text;
      if(node.parent===file) names.push(name);
      const stored = Object.values(metadata).find(item=>item&&item.file===relative&&item.sourceName===name)||{};
      const locals = [...(stored.locals||[]), ...(data.variables||[]).filter(item=>item.scope==='local'&&[name,relative+':'+name].includes(item.owner)),
        ...(data.constants||[]).filter(item=>item.scope==='local'&&[name,relative+':'+name].includes(item.owner))];
      const used = new Set(node.parameters.map(parameter=>parameter.name.getText(file)));
      const prefix = locals.map(item=>{
        const identity=item.name||item.id;
        if(!/^[\p{L}_][\p{L}\p{N}_]*$/u.test(identity)||used.has(identity))throw Error('局部变量/参数重复或名称无效');
        used.add(identity);
        if(item.static)throw Error('Node 静态局部变量尚未开放');
        return `let ${identity}=${literal(item)};`;
      }).join('');
      // Inline declarations leave every existing source line in place.
      if(prefix)edits.push({position:node.body.getStart(file)+1,text:prefix});
    }
    ts.forEachChild(node,visit);
  }
  visit(file);
  edits.sort((a,b)=>b.position-a.position).forEach(edit=>{text=text.slice(0,edit.position)+edit.text+text.slice(edit.position);});
  if(language==='typescript')text=ts.transpileModule(text,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS},fileName:filename}).outputText;
  return {source:text,names};
}
module.exports={contract,prepare,literal,dataSource};
