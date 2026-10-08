'use strict';
const fs = require('node:fs'), path = require('node:path'), Module = require('node:module');
function readLine() {
  const bytes = [], buffer = Buffer.alloc(1);
  while (fs.readSync(0, buffer, 0, 1, null)) {
    if (buffer[0] === 10) return Buffer.from(bytes).toString('utf8');
    if (bytes.length >= 65536) throw Error('command exceeds limit');
    bytes.push(buffer[0]);
  }
  return '';
}
const request = JSON.parse(readLine()), session = request.session;
const manifest = JSON.parse(fs.readFileSync(path.join(request.project, '.pcide/project.json'), 'utf8'));
function send(kind, values = {}) {
  const record = JSON.stringify({session, kind, ...values});
  if (record.length > 65536) throw Error('output record exceeds limit');
  fs.writeSync(1, record + '\n');
}
const api = {ui: {set: (id, properties) => send('ui.set', {id, properties}), open: window => send('ui.window.open', {window}), close: window => send('ui.window.close', {window})},
  ocrMock: (image, text='OK') => ({kind:'ocr',source:image,items:[{text,confidence:.99,box:[0,0,80,28]}],simulated:true}),
  yoloMock: (image, label='object') => ({kind:'yolo',source:image,detections:[{label,confidence:.95,box:[10,10,100,60]}],simulated:true}),
  screenshotMock: (name='screen') => ({kind:'screenshot',name,simulated:true})};
const originalLoad = Module._load;
Module._load = function(name, parent, isMain) {
  if (name === 'pcide') return api;
  if (parent && name.startsWith('.')) {
    const absolute = path.resolve(path.dirname(parent.filename), name);
    for (const candidate of [absolute, absolute.replace(/\.(js|ts)$/,'.jsc'), absolute+'.jsc', path.join(absolute,'index.jsc')]) {
      if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return originalLoad(candidate,parent,isMain);
    }
  }
  return originalLoad(name, parent, isMain);
};
console.log = (...args) => send('stdout',{text:args.map(x=>typeof x==='string'?x:JSON.stringify(x)).join(' ')+'\n'});
console.error = (...args) => send('stderr',{text:args.map(String).join(' ')+'\n'});
require(path.join(__dirname, 'bytenode.cjs'));
function invoke(handler, payload={}) {
  if (!/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(handler) || typeof entry[handler] !== 'function') throw Error('event handler not found');
  return entry[handler](payload);
}
let entry;
try {
  entry = require(path.join(request.project, manifest.entry));
  send('ready');
  for (const handler of request.events || []) invoke(handler);
  if (request.keep_alive) {
    require('node:readline').createInterface({input:process.stdin}).on('line', line => {
      let command;
      try {
        if (line.length > 65536) throw Error('command exceeds limit');
        command = JSON.parse(line);
        if (command.session !== session) return;
        if (command.command === 'stop') process.exit(130);
        if (command.command === 'event') { invoke(command.handler, command.payload); send('event.done',{request_id:command.request_id}); }
      } catch (error) { send('error',{message:error.message,traceback:error.stack,request_id:command?.request_id}); }
    }).on('close',()=>process.exit(0));
  } else send('done',{ok:true});
} catch (error) { send('error',{message:error.message,traceback:error.stack}); send('done',{ok:false}); process.exit(1); }
