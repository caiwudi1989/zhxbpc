'use strict';
const fs = require('node:fs'), Module = require('node:module');
const [sourcePath, outputPath, tsPath, bytecodePath, language, handlersJson] = process.argv.slice(2);
const ts = require(tsPath), bytenode = require(bytecodePath);
const text = fs.readFileSync(sourcePath, 'utf8');
const file = ts.createSourceFile(sourcePath, text, ts.ScriptTarget.Latest, true,
    language === 'typescript' ? ts.ScriptKind.TS : ts.ScriptKind.JS);
if (file.parseDiagnostics.length) throw Error(ts.flattenDiagnosticMessageText(file.parseDiagnostics[0].messageText, '\n'));
const names = [];
for (const node of file.statements) {
  if (ts.isFunctionDeclaration(node) && node.name) names.push(node.name.text);
}
let source = text;
if (language === 'typescript') {
  const result = ts.transpileModule(text, {compilerOptions: {target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.CommonJS}, fileName: sourcePath, reportDiagnostics: true});
  const errors = (result.diagnostics || []).filter(d => d.category === ts.DiagnosticCategory.Error);
  if (errors.length) throw Error(ts.flattenDiagnosticMessageText(errors[0].messageText, '\n'));
  source = result.outputText;
}
for (const name of JSON.parse(handlersJson || '[]')) {
  if (/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(name) && !names.includes(name)) names.push(name);
}
source += '\n' + names.map(name => `if(typeof ${name}==='function')module.exports[${JSON.stringify(name)}]=${name};`).join('\n');
fs.writeFileSync(outputPath, bytenode.compileCode(Module.wrap(source)));
