const {ocrMock, yoloMock, ui} = require('pcide');
function on_main_form_load(event) { console.log('主窗体已加载'); }
function on_Button1_click(event) {
  console.log(ocrMock('screen','Hello'));
  console.log(yoloMock('screen'));
  ui.set('Label1',{text:'事件已执行'});
}
console.log('脚本已就绪');
