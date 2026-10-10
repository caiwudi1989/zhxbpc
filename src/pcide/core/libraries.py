"""Read-only command catalog and explicit imported-library records."""
from __future__ import annotations

import copy
import json
import keyword
import re
import shutil
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from .paths import atomic_write_json, read_json, sha256_file
from .modules import load_modules, validate_modules
from .plugins import PluginManifest, PluginRegistry
from .control_catalog import CONTROL_LABELS

TYPE_LABELS = ('字节型','整数型','长整数型','小数型','双精度小数型','数值型','逻辑型(布尔型)',
               '日期时间型','文本型','字节集','对象型','数组型')
CORE_CATEGORY_ORDER = ('流程控制','算术运算','逻辑比较','位运算','变量操作','数组操作',
                       '环境存取','文本操作','字节集操作','数值转换','时间操作','磁盘操作',
                       '文件读写','系统处理','程序调试','其他','数据库','网络通信','控制台操作',
                       '数据转换','线程与任务')
COMMAND_CONTRACTS = {
    '取绝对值': ('取绝对值(数值)', '数值型', '返回数值的绝对值。'),
    '取最大值': ('取最大值(数值1, 数值2, ...)', '数值型', '返回参数中的最大值。'),
    '取最小值': ('取最小值(数值1, 数值2, ...)', '数值型', '返回参数中的最小值。'),
    '求次方': ('求次方(底数, 指数)', '数值型', '计算底数的指定次方。'),
    '求平方根': ('求平方根(数值)', '小数型', '返回非负实数的平方根；负数报错。'),
    '取整': ('取整(数值)', '整数型', '向零截断小数部分。'),
    '四舍五入': ('四舍五入(数值)', '数值型', 'Python 的半值舍入与 JavaScript 不同，以实际运行语言规则为准。'),
    '取文本长度': ('取文本长度(文本)', '整数型', '按 Unicode 字符计数；不按易语言旧编码字节数计算。'),
    '寻找文本': ('寻找文本(原文本, 待寻找文本)', '整数型', '当前实现返回从 0 开始的位置；未找到返回 -1。'),
    '文本替换': ('文本替换(原文本, 被替换文本, 新文本)', '文本型', '替换文本中的匹配内容。'),
    '子文本替换': ('子文本替换(原文本, 被替换文本, 新文本)', '文本型', '替换文本中的匹配内容。'),
    '分割文本': ('分割文本(原文本, 分隔文本)', '数组型', '按指定分隔符分割为文本数组。'),
    '到整数': ('到整数(文本或数值)', '整数型', '按当前语言规则转换；非法内容可能报错。'),
    '到小数': ('到小数(文本或数值)', '小数型', '将文本或数值转换为浮点数。'),
    '到文本': ('到文本(值)', '文本型', '返回当前运行语言的文本表示。'),
    '到字节集': ('到字节集(文本)', '字节集', '示例按 UTF-8 编码文本。'),
    '取字节集长度': ('取字节集长度(字节集)', '整数型', '返回字节数量。'),
    '取数组成员数': ('取数组成员数(数组)', '整数型', '返回数组成员数量。'),
    '排序数组': ('排序数组(数组)', '数组型', 'Python 返回新数组；Node 示例按数值原地排序。'),
    '取运行目录': ('取运行目录()', '文本型', '脚本宿主启动时的工作目录为项目目录。'),
    '读取环境变量': ('读取环境变量(名称)', '文本型', '读取宿主环境变量，未设置时示例返回空文本。'),
    '取现行时间': ('取现行时间()', '日期时间型', '取得本机当前日期与时间。'),
    '读入文件': ('读入文件(文件路径)', '文本型', '当前示例读取 UTF-8 文本；文件缺失会报错。'),
    '写到文件': ('写到文件(文件路径, 内容)', '整数型', '当前示例写入 UTF-8 文本，覆盖现有文件。'),
    '文件是否存在': ('文件是否存在(路径)', '逻辑型', '检查路径是否存在。'),
    '数据库连接': ('数据库连接(项目内路径="database/app.sqlite")', 'SQLite 连接', '取得 SQLite 连接；使用完成后需关闭连接。'),
    '数据库执行': ('数据库执行(连接, SQL, 参数=())', '对象型', '使用现有数据库代理执行语句并提交；返回 rowcount 和 lastrowid。'),
    '网络请求': ('网络请求(URL, method="GET", body=None, timeout=30)', '对象型', 'HTTP/HTTPS 请求；响应最多 4MiB，超时上限 60 秒。'),
    '设置控件属性': ('设置控件属性(控件ID, 属性...)', '对象型', '发送 ui.set 消息，窗口线程更新控件；ID 必须对应运行表单中的控件。'),
    '打开窗口': ('打开窗口(窗口路径)', '对象型', '发送 ui.window.open 消息；窗口必须已包含在项目中。'),
    '关闭窗口': ('关闭窗口(窗口路径)', '对象型', '发送 ui.window.close 消息，关闭指定运行窗口。'),
}

# System-library commands are shown with their Yi-style Chinese name, while
# the editor must also be searchable from an English keyboard.  Keep the
# English spellings in the library contract instead of deriving them from a
# translation at runtime: these names are part of the completion API and must
# stay stable when a code example changes.
COMMAND_ENGLISH_ALIASES = {
    '位与': ('bit_and',), '位异或': ('bit_xor',), '位或': ('bit_or',),
    '信息框': ('message_box',), '关闭任务池': ('close_task_pool',),
    '关闭窗口': ('close_window',), '写出文本文件': ('write_text_file',),
    '写到文件': ('write_file',), '分割文本': ('split_text',),
    '创建任务池': ('create_task_pool',), '创建字节集': ('create_bytes',),
    '创建目录': ('create_directory',), '删除数组成员': ('remove_array_item',),
    '删除文件': ('delete_file',), '到大写': ('to_upper',),
    '到字节集': ('to_bytes',), '到小写': ('to_lower',),
    '到小数': ('to_float',), '到整数': ('to_int',), '到文本': ('to_text',),
    '加入数组成员': ('append_array_item',), '取字节集长度': ('byte_length',),
    '取对象类型': ('object_type',), '取数组成员数': ('array_length',),
    '取整': ('truncate',), '取文本长度': ('text_length',),
    '取最大值': ('max_value',), '取最小值': ('min_value',),
    '取消友好延时': ('cancelable_sleep',), '取消后台任务': ('cancel_task',),
    '取现行时间': ('current_time',), '取系统名称': ('system_name',),
    '取绝对值': ('abs',), '取运行目录': ('current_directory',),
    '右移': ('bit_shift_right',), '后台更新窗口': ('update_window_async',),
    '四舍五入': ('round_value',), '如果': ('if',), '子文本替换': ('replace_subtext',),
    '寻找文本': ('find_text',), '左移': ('bit_shift_left',), '延时': ('delay',),
    '循环': ('while_loop',), '打开窗口': ('open_window',),
    '排序数组': ('sort_array',), '控制台输出': ('console_output',),
    '提交后台任务': ('submit_task',), '数值范围检查': ('clamp_number',),
    '数据库执行': ('execute_database',), '数据库连接': ('connect_database',),
    '文件是否存在': ('file_exists',), '文本替换': ('replace_text',),
    '查询任务完成': ('task_done',), '求平方根': ('sqrt',), '求次方': ('power',),
    '生成JSON': ('stringify_json',), '等待任务结果': ('wait_task',),
    '网络请求': ('http_request',), '置当前目录': ('change_directory',),
    '解析JSON': ('parse_json',), '设置控件属性': ('set_control_property',),
    '读入文件': ('read_file',), '读取文本文件': ('read_text_file',),
    '读取环境变量': ('get_environment_variable',), '调试输出': ('debug_print',),
    '赋值': ('assign',), '转大写': ('uppercase',), '转小写': ('lowercase',),
    '输出调试文本': ('debug_output',), '返回': ('return',), '逻辑非': ('logical_not',),
}


def _command_aliases(label):
    """Return stable English aliases for one system command."""
    values = COMMAND_ENGLISH_ALIASES.get(label, ())
    if isinstance(values, str):
        values = (values,)
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


FORMATS = {
    '.py': ('Python 源码模块','直接加入 src；按 模块名.公开函数 调用'),
    '.zhxb': ('中文源码模块','直接加入 src；公开子程序按 模块名.子程序 调用'),
    '.js': ('JavaScript 模块','加入 src；使用 require 加载，Python/中文项目不能直接调用'),
    '.ts': ('TypeScript 模块','加入 src；Node 项目运行和构建时编译'),
    '.ec': ('易模块','需用易语言引用并编译成 DLL 或协议桥接包；EC 不能作为 Python 源码执行'),
    '.fne': ('易语言支持库','需匹配易语言支持库 ABI 的独立桥接宿主；不能当普通 DLL 导出调用'),
    '.dll': ('DLL / .NET 程序集','普通 DLL 声明导出和参数类型；.NET 或插件 DLL 使用 plugin.json 封装'),
    '.pyd': ('Python 原生扩展','通过带 plugin.json 的 Python 插件包加入，ABI/位数必须匹配'),
    '.dex': ('Android DEX','由 Android ART 宿主加载；配置桥接地址、设备路径和类名后调用'),
    '.pcplugin': ('封装支持库包','包含 plugin.json、入口、依赖和公开能力，使用独立宿主调用'),
    '.zip': ('封装支持库包','包根必须有 plugin.json；导入时校验大小、路径及入口'),
    '.json': ('支持库清单','选择 plugin.json；将同目录入口和依赖一起加入项目'),
}


def command(label, category, python, node=None, zhxb=None, description='', aliases=None):
    signature, return_type, help_text = COMMAND_CONTRACTS.get(label, ('', '', '使用下方当前语言 API 示例；根据项目填写实际参数。'))
    details = description or help_text
    if signature:
        details = signature+'\n返回类型：'+return_type+'\n'+details
    aliases = _command_aliases(label) if aliases is None else list(dict.fromkeys(str(value).strip() for value in aliases if str(value).strip()))
    return {'label':label,'category':category,'description':details,
            'signature':signature,'return_type':return_type,
            'aliases': aliases,
            'code':{'python':python,'zhxb':zhxb or python,'javascript':node,'typescript':node}}


def yi_command(label, category, python, zhxb=None, description=''):
    """Create a catalogue entry shared by Python and Chinese-source views.

    The Chinese view keeps Yi-style command spelling where the compiler
    understands it.  Entries that need a runtime proxy use an explicit
    ``__import__`` expression so inserting them does not invent a hidden
    global import.
    """
    return command(label, category, python, None, zhxb or python, description)


# The core catalogue follows Yi-language command classes, with executable
# PCIDE implementations. Unimplemented Yi-language commands/types are not
# added as pretend callable entries.
YI_CORE_COMMANDS = [
    yi_command('如果', '流程控制', 'if True:\n    pass', '如果 真\n结束如果', '条件分支；中文源码使用“如果 … / 结束如果”。'),
    yi_command('循环', '流程控制', 'while False:\n    pass', '循环 假\n结束循环', '条件循环；请在循环体中检查取消条件。'),
    yi_command('返回', '流程控制', 'return 0', '返回(0)', '从当前子程序返回一个值。'),
    yi_command('求次方', '算术运算', 'pow(2, 3)'),
    yi_command('求平方根', '算术运算', '__import__("math").sqrt(9)'),
    yi_command('取整', '算术运算', 'int(1.9)'),
    yi_command('数值范围检查', '算术运算', 'value = max(0, min(100, 50))', 'value = max(0, min(100, 50))'),
    yi_command('逻辑非', '逻辑比较', 'value = not True', 'value = not 真'),
    yi_command('位与', '位运算', 'value = 5 & 3'),
    yi_command('位或', '位运算', 'value = 5 | 3'),
    yi_command('位异或', '位运算', 'value = 5 ^ 3'),
    yi_command('左移', '位运算', 'value = 5 << 1'),
    yi_command('右移', '位运算', 'value = 5 >> 1'),
    yi_command('赋值', '变量操作', 'value = 1', '赋值(变量, 1)', '把表达式结果写入变量。'),
    yi_command('加入数组成员', '数组操作', 'values = [1, 2]\nvalues.append(3)', '列表 = [1, 2]\n列表.append(3)'),
    yi_command('删除数组成员', '数组操作', 'values = [1, 2, 3]\nvalues.pop(0)', '列表 = [1, 2, 3]\n列表.pop(0)'),
    yi_command('置当前目录', '环境存取', '__import__("os").chdir(".")'),
    yi_command('寻找文本', '文本操作', '"文本".find("本")'),
    yi_command('子文本替换', '文本操作', '"文本".replace("文", "字")'),
    yi_command('到大写', '文本操作', '"abc".upper()'),
    yi_command('到小写', '文本操作', '"ABC".lower()'),
    yi_command('到字节集', '字节集操作', '"文本".encode("utf-8")'),
    yi_command('取字节集长度', '字节集操作', 'len("文本".encode("utf-8"))'),
    yi_command('取现行时间', '时间操作', '__import__("datetime").datetime.now().isoformat()'),
    yi_command('文件是否存在', '磁盘操作', '__import__("pathlib").Path("data.txt").exists()'),
    yi_command('创建目录', '磁盘操作', '__import__("pathlib").Path("data").mkdir(exist_ok=True)'),
    yi_command('删除文件', '磁盘操作', '__import__("pathlib").Path("data.txt").unlink(missing_ok=True)'),
    yi_command('读入文件', '文件读写', '__import__("pathlib").Path("data.txt").read_text(encoding="utf-8")'),
    yi_command('写到文件', '文件读写', '__import__("pathlib").Path("data.txt").write_text("内容", encoding="utf-8")'),
    yi_command('取系统名称', '系统处理', '__import__("platform").system()'),
    yi_command('输出调试文本', '程序调试', 'print("调试文本")', '调试输出("调试文本")'),
    yi_command('信息框', '程序调试', 'print("提示")', '信息框("提示")', '当前中文源码宿主将信息框映射为有界输出；原生窗口消息需要窗口支持库。'),
    yi_command('数据库连接', '数据库', '__import__("pcide.runtime_api", fromlist=["db"]).db.connect()'),
    yi_command('数据库执行', '数据库', '__import__("pcide.runtime_api", fromlist=["db"]).db.execute(connection, "select 1")'),
    yi_command('网络请求', '网络通信', '__import__("pcide.runtime_api", fromlist=["network"]).network.request("https://example.invalid")'),
    yi_command('控制台输出', '控制台操作', 'print("控制台")', '输出("控制台")'),
    yi_command('取对象类型', '其他', 'str(type(object()).__name__)'),
]


SYSTEM_LIBRARIES = (
    {'id':'system.core','name':'系统核心支持库','commands':[
        command('调试输出','程序调试','print("内容")','console.log("内容")','输出("内容")'),
        command('取绝对值','算术运算','abs(-1)','Math.abs(-1)'),
        command('取最大值','算术运算','max(1, 2)','Math.max(1, 2)'),
        command('取最小值','算术运算','min(1, 2)','Math.min(1, 2)'),
        command('四舍五入','算术运算','round(1.5)','Math.round(1.5)',description='遵循当前语言的舍入规则'),
        command('取文本长度','文本操作','len("文本")','Array.from("文本").length'),
        command('文本替换','文本操作','"文本".replace("文", "字")','"文本".replaceAll("文", "字")'),
        command('分割文本','文本操作','"a,b".split(",")','"a,b".split(",")'),
        command('转大写','文本操作','"abc".upper()','"abc".toUpperCase()'),
        command('转小写','文本操作','"ABC".lower()','"ABC".toLowerCase()'),
        command('到整数','数值转换','int("123")','Number.parseInt("123", 10)'),
        command('到小数','数值转换','float("1.5")','Number("1.5")'),
        command('到文本','数值转换','str(123)','String(123)'),
        command('取数组成员数','数组操作','len([1, 2])','[1, 2].length'),
        command('排序数组','数组操作','sorted([2, 1])','[2, 1].sort((a,b)=>a-b)'),
        command('创建字节集','字节集操作','"文本".encode("utf-8")','Buffer.from("文本", "utf8")'),
        command('读取环境变量','环境存取','__import__("os").environ.get("TEMP", "")','process.env.TEMP || ""'),
        command('取运行目录','环境存取','str(__import__("pathlib").Path.cwd())','process.cwd()'),
        command('延时','时间操作','__import__("time").sleep(0.1)',None,description='单位秒；脚本宿主的超时/取消仍生效'),
        command('读取文本文件','文件读写','__import__("pathlib").Path("resources/data.txt").read_text(encoding="utf-8")','require("node:fs").readFileSync("resources/data.txt", "utf8")'),
        command('写出文本文件','文件读写','__import__("pathlib").Path("resources/data.txt").write_text("内容", encoding="utf-8")','require("node:fs").writeFileSync("resources/data.txt", "内容", "utf8")'),
        command('解析JSON','数据转换','__import__("json").loads("{}")','JSON.parse("{}")'),
        command('生成JSON','数据转换','__import__("json").dumps({"值": 1}, ensure_ascii=False)','JSON.stringify({"值":1})'),
        command('创建任务池','线程与任务','pool = tasks.pool(workers=2, capacity=16)',None,'pool = __import__("pcide.runtime_api", fromlist=["tasks"]).tasks.pool(workers=2, capacity=16)',description='每宿主最多4池，每池1..4线程、最多64任务；推荐使用 with tasks.pool() 自动关闭。回调首参数为取消事件。'),
        command('提交后台任务','线程与任务','job = pool.submit(lambda cancel: sum(range(100)))',None,'job = pool.submit(lambda cancel: sum(range(100)))',description='submit(function, *args, **kwargs)；回调接收cancel事件；容量满立即拒绝，完成后释放函数与参数引用。'),
        command('等待任务结果','线程与任务','result = job.result(timeout=10)',None,'result = job.result(timeout=10)',description='result(timeout) 返回结果或抛出任务异常；有限等待，不在界面事件回调中长时间阻塞。'),
        command('取消后台任务','线程与任务','job.cancel()',None,'job.cancel()',description='尚未开始的任务取消；运行中的任务通过cancel事件协作退出，非协作代码由独立宿主超时/停止回收。'),
        command('查询任务完成','线程与任务','job.done()',None,'job.done()',description='done() 返回逻辑值；不阻塞当前线程。'),
        command('取消友好延时','线程与任务','tasks.sleep(cancel, 0.1)',None,'__import__("pcide.runtime_api", fromlist=["tasks"]).tasks.sleep(cancel, 0.1)',description='用于任务回调内；取消时立即返回False，否则延时后返回True。'),
        command('关闭任务池','线程与任务','pool.close(timeout=3)',None,'pool.close(timeout=3)',description='取消排队任务并通知运行任务；有界等待、释放线程。推荐with上下文；超时将报告未响应取消。'),
        command('后台更新窗口','线程与任务','job = pool.submit(lambda cancel: ui.set("Label1", text="任务完成"))',None,'job = pool.submit(lambda cancel: __import__("pcide.runtime_api", fromlist=["ui"]).ui.set("Label1", text="任务完成"))',description='ui.set通过宿主协议和Qt队列回到UI线程，后台代码不直接访问Qt控件。'),
        *YI_CORE_COMMANDS,
    ],'types':TYPE_LABELS,'constants': [('圆周率','3.141592653589793'),('换行符','"\\r\\n"'),('空文本','""')]},
    {'id':'system.window','name':'窗口支持库','commands':[
        command('设置控件属性','窗口操作','ui.set("Label1", text="内容")','require("pcide").ui.set("Label1", {text:"内容"})','__import__("pcide.runtime_api", fromlist=["ui"]).ui.set("Label1", text="内容")'),
        command('打开窗口','窗口操作','ui.open("ui/main.form.json")','require("pcide").ui.open("ui/main.form.json")','__import__("pcide.runtime_api", fromlist=["ui"]).ui.open("ui/main.form.json")'),
        command('关闭窗口','窗口操作','ui.close("ui/main.form.json")','require("pcide").ui.close("ui/main.form.json")','__import__("pcide.runtime_api", fromlist=["ui"]).ui.close("ui/main.form.json")'),
    ],'types':('窗口', *CONTROL_LABELS.values()),'constants':[
        ('方向_水平','"horizontal"'),('方向_垂直','"vertical"'),
    ]},
)

# Native/engine snippets use the actual language API instead of script runtime aliases.
DEVELOPMENT_COMMANDS = {
    'c': [('输出文本','stdio.h','printf("%s\\n", "ready");','需要 #include <stdio.h>'),
          ('写出文件','stdio.h','FILE *f = fopen("data.txt", "w");\nif (f) { fputs("ready", f); fclose(f); }','必须关闭FILE；检查失败返回值。')],
    'cpp': [('后台线程','线程','std::thread worker([] { /* 工作 */ });\nworker.join();','需要 <thread>；必须join。窗口消息/更新应由窗口线程处理。'),
            ('互斥锁','线程','std::lock_guard<std::mutex> guard(mutex);','需要 <mutex> 和已声明的std::mutex，作用域退出自动解锁。'),
            ('异步任务','线程','auto future = std::async(std::launch::async, [] { return 42; });\nauto value = future.get();','需要 <future>；控制任务数量，不在界面线程无限等待。'),
            ('智能指针','资源管理','auto value = std::make_unique<int>(42);','需要 <memory>，RAII作用域退出回收。'),
            ('窗口消息','Win32','PostMessageW(window, WM_APP + 1, 0, 0);','需要 <windows.h> 和window句柄，UI线程处理WM_APP消息。'),
            ('提示框','Win32','MessageBoxW(nullptr, L"内容", L"提示", MB_OK);','链接user32；原生窗口接口。')],
    'csharp': [('异步后台任务','线程','using var cancellation = new CancellationTokenSource();\nvar result = await Task.Run(() => 42, cancellation.Token);','using System.Threading / System.Threading.Tasks；取消在任务内也需检查Token。'),
               ('取消任务','线程','cancellation.Cancel();','Cancel通知任务，回调需响应CancellationToken。'),
               ('自动释放资源','资源管理','using var stream = File.OpenRead("data.txt");','using作用域结束时Dispose，避免文件句柄泄漏。'),
               ('窗口线程更新','Windows Forms','form.BeginInvoke(new Action(() => form.Text = "任务完成"));','只能在WinForms项目使用；将更新回到UI线程。')],
    'gdscript': [('逐帧迭代','游戏生命周期','func _process(delta):\n    queue_redraw()','Godot逐帧回调，delta单位秒。'),
                 ('释放节点','资源管理','queue_free()','延迟释放节点，避免回调中立即销毁。'),
                 ('发送信号','游戏交互','signal completed(value)\n\nfunc finish():\n    completed.emit(42)','通过信号连接UI与游戏逻辑。')],
    'html': [('释放定时器','资源管理','const timer = setInterval(() => {}, 1000);\nwindow.addEventListener("pagehide", () => clearInterval(timer), {once:true});','页面退出时清理定时器。'),
             ('动画循环','游戏生命周期','let frame;\nfunction tick(time) { frame = requestAnimationFrame(tick); }\nframe = requestAnimationFrame(tick);\nwindow.addEventListener("pagehide", () => cancelAnimationFrame(frame), {once:true});','Canvas动画循环；需要清理requestAnimationFrame。')],
}

UNITY_COMMANDS = [
    ('逐帧更新','Unity生命周期','void Update() { transform.Rotate(0f, 60f * Time.deltaTime, 0f); }','在MonoBehaviour类内添加；deltaTime保证帧率变化时速度一致。'),
    ('键盘控制','Unity交互','var movement = new Vector3(Input.GetAxis("Horizontal"), 0f, Input.GetAxis("Vertical"));\ntransform.Translate(movement * Time.deltaTime);','旧Input Manager接口；可改用已配置的新Input System，项目需对应设置/包。'),
    ('创建游戏对象','Unity对象','var instance = Instantiate(prefab);','需要已赋值的prefab引用；不在每帧无界创建对象，适合对象池复用。'),
    ('释放游戏对象','Unity资源','Destroy(instance);','Unity主线程延迟销毁对象；不要用后台线程调用Unity对象API。'),
    ('协程与取消','Unity任务','System.Collections.IEnumerator Work() {\n    yield return new WaitForSeconds(0.1f);\n    Debug.Log("完成");\n}\nvoid Start() { StartCoroutine(Work()); }\nvoid OnDisable() { StopAllCoroutines(); }','在MonoBehaviour类内添加；协程在主线程执行，后台CPU任务需受控Task与取消Token。'),
    ('切换场景','Unity场景','UnityEngine.SceneManagement.SceneManager.LoadScene("Main");','目标场景需加入Unity Build Settings或Build Profiles；由Unity编辑器管理场景。'),
]

def module_documentation(project, module, name):
    """Read a signature/docstring without importing third-party source."""
    path=project.root/module['file']
    if not path.resolve().is_relative_to(project.root) or path.stat().st_size>2*1024*1024:
        raise ValueError('模块说明文件越界或过大')
    source=path.read_text(encoding='utf-8')
    try:
        from .routine_signatures import parameter_details
        details=parameter_details(source,path.suffix,name)
        signature=name+'('+', '.join(p['name']+('='+str(p.get('default','')) if p.get('default') else '') for p in details)+')'
        description='公开接口 · '+signature
        if path.suffix=='.py':
            import ast
            node=next(n for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
            description+='\n'+(ast.get_docstring(node) or '此函数尚未提供文档字符串；参数说明以源码签名为准。')[:4000]
        code=module['id']+'.'+name+'('+', '.join((p['name']+'='+p['name']) if p.get('kind')=='keyword' else p['name'] for p in details if not p.get('optional') and p.get('kind') not in {'rest','kwargs'})+')'
        return description,code
    except (ValueError,SyntaxError,StopIteration):
        return '公开接口 · 请查看源码中的参数与返回值',module['id']+'.'+name+'()'


def validate_libraries(project, raw):
    if not isinstance(raw,dict) or type(raw.get('version',1)) is not int or raw.get('version',1)!=1:
        raise ValueError('支持库清单版本不支持')
    enabled = raw.get('system',[item['id'] for item in SYSTEM_LIBRARIES])
    if not isinstance(enabled,list) or any(not isinstance(value,str) for value in enabled) or len(enabled)!=len(set(enabled)) or set(enabled)-{item['id'] for item in SYSTEM_LIBRARIES}:
        raise ValueError('系统支持库配置无效')
    records = raw.get('imports',[])
    if not isinstance(records,list) or len(records)>128:
        raise ValueError('最多加入128个外部文件')
    used = set()
    for item in records:
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not item['id'].isidentifier() or keyword.iskeyword(item['id']) or item['id'] in used:
            raise ValueError('外部支持库身份无效或重复')
        used.add(item['id'])
        file = item.get('file','')
        if not isinstance(file,str) or not file or '\x00' in file:
            raise ValueError('外部支持库路径无效')
        path = project.root / file
        if '\\' in file or ':' in file or not file.startswith(('src/','resources/')) or '..' in Path(file).parts or path.is_symlink() or not path.resolve().is_relative_to(project.root.resolve()) or not path.is_file():
            raise ValueError('外部支持库文件缺失或越界')
        if item.get('kind') not in {'py','zhxb','js','ts','dll','ec','fne','dex'} or not re.fullmatch(r'\d+\.\d+\.\d+',str(item.get('version',''))) or not re.fullmatch(r'[0-9a-f]{64}',str(item.get('sha256',''))):
            raise ValueError('外部支持库格式、版本或摘要无效')
        if item['kind'] in {'py','zhxb','js','ts'}:
            exports=item.get('exports',[])
            if not isinstance(exports,list) or len(exports)>256 or any(not isinstance(name,str) or not name.isidentifier() for name in exports) or len(exports)!=len(set(exports)):
                raise ValueError('模块公开接口清单无效')
        # Source modules can be edited in the IDE. The hash records admission,
        # while the source/module contracts validate the next execution.
        if item['kind']=='dex':
            validate_dex_config(item.get('endpoint'),item.get('android_path'),item.get('class_name'))
    return {'version':1,'system':enabled,'imports':copy.deepcopy(records)}


def load_libraries(project):
    return validate_libraries(project,read_json(project.ide_dir / 'libraries.json', {}))


def save_libraries(project, model):
    atomic_write_json(project.ide_dir / 'libraries.json',validate_libraries(project,model))


def validate_dex_config(endpoint, android_path, class_name):
    if not all(isinstance(value,str) for value in (endpoint,android_path,class_name)):
        raise ValueError('DEX连接配置必须是文本')
    url=urlsplit(endpoint)
    if url.scheme not in {'ws','wss'} or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError('DEX桥接地址必须是有效的 ws/wss 地址')
    if not android_path or '\\' in android_path or android_path.startswith('/') or '..' in Path(android_path).parts or ':' in android_path or '\x00' in android_path:
        raise ValueError('Android路径必须是宿主内相对路径')
    if not re.fullmatch(r'[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+',class_name):
        raise ValueError('Android类名必须包含包名')


def validate_plugin_admission(project, manifest):
    existing={item.id:item for item in plugin_catalog(project)}
    if manifest.id in existing:
        raise ValueError('支持库ID已经存在')
    if manifest.abi!='json-v1' or manifest.python_abi!='cp312' and manifest.kind=='python':
        raise ValueError('支持库 ABI 不匹配；封装包要求 json-v1 / Python cp312')
    for identity,version in manifest.dependencies.items():
        if identity not in existing or existing[identity].version!=version:
            raise ValueError('请先加入依赖支持库：'+identity+'@'+version)
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,127}',manifest.id):
        raise ValueError('支持库ID必须以字母开头')
    root=(project.root/'plugins').resolve()
    if not root.is_relative_to(project.root.resolve()) or (project.root/'plugins').is_symlink():
        raise ValueError('支持库目录越界')


def import_library(project, source, identity, *, version='1.0.0', dll_entry='', dll_return='int32',
                   parameters=(), calling_convention='cdecl', exports=None,
                   endpoint='ws://127.0.0.1:8765', android_path='', class_name='', grant=False):
    original = Path(source)
    if original.is_symlink() or not original.is_file() or original.stat().st_size>128*1024*1024:
        raise ValueError('加入文件不存在、为符号链接或超过128MB')
    source = original.resolve()
    if not isinstance(identity,str) or len(identity)>64 or not identity.isidentifier() or keyword.iskeyword(identity) or identity.upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        raise ValueError('库/模块代码名称必须是合法标识符')
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):
        raise ValueError('版本必须是 major.minor.patch')
    suffix = source.suffix.lower()
    if suffix not in FORMATS:
        raise ValueError('不支持这个文件格式；请使用支持库封装包')
    model = load_libraries(project)
    if any(item['id']==identity for item in model['imports']) or identity in {item['id'] for item in load_modules(project)['modules']}:
        raise ValueError('库/模块名称已经存在')
    if suffix in {'.zip','.pcplugin','.json'}:
        from .plugin_market import install_archive
        if suffix=='.json':
            if source.name!='plugin.json':
                raise ValueError('请选择 plugin.json')
            manifest = PluginManifest.from_dict(read_json(source))
            validate_plugin_admission(project,manifest)
            files = list(source.parent.rglob('*'))
            if len(files)>2000 or any(p.is_symlink() for p in files) or sum(p.stat().st_size for p in files if p.is_file())>128*1024*1024:
                raise ValueError('支持库目录文件过多、过大或含符号链接')
            entry = source.parent / manifest.entry
            if ':' in manifest.entry or '\\' in manifest.entry or not entry.resolve().is_relative_to(source.parent) or not entry.is_file():
                raise ValueError('支持库入口缺失或越界')
            target = project.root / 'plugins' / manifest.id
            if target.resolve().is_relative_to(source.parent):
                raise ValueError('目标支持库目录不能位于待导入目录内')
            if target.exists():
                raise ValueError('该支持库已加入')
            shutil.copytree(source.parent,target)
        else:
            with zipfile.ZipFile(source) as archive:
                info=archive.getinfo('plugin.json')
                if info.file_size>65536:
                    raise ValueError('支持库清单过大')
                manifest=PluginManifest.from_dict(json.loads(archive.read(info)))
                validate_plugin_admission(project,manifest)
                if ':' in manifest.entry or '\\' in manifest.entry or manifest.entry not in archive.namelist():
                    raise ValueError('支持库包入口缺失')
            target=install_archive({'id':manifest.id,'version':manifest.version,'sha256':sha256_file(source)},source,project.root/'plugins')
        if grant:
            project.manifest['permissions']=list(dict.fromkeys(project.manifest.get('permissions',[])+manifest.permissions))
            atomic_write_json(project.ide_dir/'project.json',project.manifest)
        return {'id':manifest.id,'kind':manifest.kind,'file':str(target),'status':'已加入独立宿主支持库'}
    if suffix=='.pyd':
        raise ValueError('PYD 需要 plugin.json 声明 plugin_entry、Python ABI 和能力；请按引导封装后加入')
    if suffix=='.dex':
        from .dex_bridge import browse_dex
        index=browse_dex(source)
        validate_dex_config(endpoint,android_path,class_name)
        if 'L'+class_name.replace('.','/')+';' not in index['classes']:
            raise ValueError('DEX索引中未找到这个类名')
    target = project.root / ('src' if suffix in {'.py','.zhxb','.js','.ts'} else 'resources/libraries') / (identity+suffix)
    if not target.resolve().is_relative_to(project.root.resolve()) or any(path.is_symlink() for path in [target,*target.parents] if path.is_relative_to(project.root)):
        raise ValueError('目标目录越界或包含符号链接')
    if target.exists():
        raise ValueError('目标文件已存在，不覆盖现有文件')
    record={'id':identity,'file':target.relative_to(project.root).as_posix(),'kind':suffix[1:],
            'sha256':sha256_file(source),'version':version,'status':'待桥接封装' if suffix in {'.ec','.fne'} else '已加入'}
    modules=load_modules(project)
    if suffix in {'.py','.zhxb','.js','.ts'}:
        from .routines import scan
        text=source.read_text(encoding='utf-8')
        if len(text)>5*1024*1024:
            raise ValueError('源码模块超过5MB')
        if suffix=='.py':
            import ast
            ast.parse(text)
        if suffix=='.zhxb':
            from .compiler import parse
            parse(text)
        available=[routine['sourceName'] for routine in scan(text,suffix)]
        if exports is None:
            exports=available
        if not exports or not isinstance(exports,list) or any(name not in available for name in exports) or len(exports)!=len(set(exports)):
            raise ValueError('模块需要唯一的公开子程序')
        record['exports']=exports
        if suffix in {'.js','.ts'}:
            from .paths import Paths, node_runtime
            from .processes import run_bounded
            paths=Paths().ensure()
            checker='const fs=require("node:fs"),ts=require(process.argv[2]),p=process.argv[1];const f=ts.createSourceFile(p,fs.readFileSync(p,"utf8"),ts.ScriptTarget.Latest,true,p.endsWith(".ts")?ts.ScriptKind.TS:ts.ScriptKind.JS);if(f.parseDiagnostics.length)throw Error(ts.flattenDiagnosticMessageText(f.parseDiagnostics[0].messageText,"\\n"));'
            run_bounded([node_runtime(),'-e',checker,str(source),str(paths.resources/'sdk/typescript/package/lib/typescript.js')],
                        cwd=project.root,timeout=10,log_path=paths.logs/'module-syntax.log')
    if suffix=='.dll':
        from .dll import validate_signature
        validate_signature(dll_entry,[p['type'] for p in parameters],dll_return)
        if calling_convention not in {'cdecl','stdcall','winapi'}:
            raise ValueError('不支持的DLL调用约定')
        data=project.load_data()
        if identity in {item['id'] for key in ('variables','constants','types','apis') for item in data[key]}:
            raise ValueError('DLL命令代码名称重复')
        data['apis'].append({'id':identity,'label':identity,'library':record['file'],'entry':dll_entry,
                            'parameters':list(parameters),'return_type':dll_return,'calling_convention':calling_convention})
        from .data import validate_data
        data=validate_data(data)
        record['parameters']=list(parameters)
    if suffix=='.dex':
        record.update(endpoint=endpoint,android_path=android_path,class_name=class_name,classes=index['classes'],status='待Android部署/连接')
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
    previous={name:(project.ide_dir/name).read_bytes() if (project.ide_dir/name).is_file() else None for name in ('modules.json','data.json','libraries.json')}
    try:
        if suffix in {'.py','.zhxb'}:
            modules['modules'].append({'id':identity,'file':record['file'],'version':version,'exports':record['exports'],'dependencies':{}})
            modules=validate_modules(modules,project.root)
            atomic_write_json(project.ide_dir/'modules.json',modules)
        if suffix=='.dll':
            project.save_data(data)
        model['imports'].append(record)
        save_libraries(project,model)
    except Exception:
        for name,content in previous.items():
            path=project.ide_dir/name
            if content is not None:
                path.write_bytes(content)
            elif path.exists():
                path.unlink()
        # Retain the admitted file for diagnosis, restoring all reference tables.
        raise
    return record


def plugin_catalog(project):
    registry=PluginRegistry(project.root,project.manifest.get('permissions',[]))
    # Discovery reads manifests; it never loads library code into the IDE.
    return registry.discover()


def calling_example(record, language):
    identity=record['id']
    kind=record['kind']
    if kind in {'py','zhxb'} and language in {'python','zhxb'}:
        return identity+'.'+record['exports'][0]+'()'
    if kind in {'js','ts'} and language in {'javascript','typescript'}:
        return 'require('+json.dumps('./'+Path(record['file']).stem)+').'+record['exports'][0]+'()'
    if kind=='dll' and language in {'python','zhxb'}:
        return identity+'('+', '.join('""' if p['type'] in {'utf8','utf16','文本','文本型'} else '0' for p in record.get('parameters',[]))+')'
    if kind in {'python','native','dotnet','dex-remote'} and language in {'python','zhxb'}:
        capability=(record.get('capabilities') or [''])[0]
        return 'plugins.call('+json.dumps(identity)+', '+json.dumps(capability)+', {})'
    if kind=='dex' and language in {'python','zhxb'}:
        return ('__import__("pcide.core.dex_bridge", fromlist=["DexBridge"]).DexBridge('+json.dumps(record['endpoint'])+').request("dex.call", '+
                repr({'dex':record['android_path'],'class':record['class_name'],'argument':'{}'})+')')
    return ''
