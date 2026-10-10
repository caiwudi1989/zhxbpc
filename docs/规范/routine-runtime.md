# 子程序、程序数据与 DLL 执行合同

日期：2026-10-10。这是 PCIDE 当前实现合同，不是完整易语言或 Visual Basic 的兼容声明。

## 源码与编辑视图

- 子程序三角实际隐藏/恢复所属代码体与设置区，保留名称行；Monaco 按缩进或成对括号判断范围，不收回后续独立子程序与顶层启动代码。模型、保存内容不删减。
- 正文输入和换行按文件/源码名称复用现有 view zones，位置变化只更新锚点，隐藏范围未改变时不重复设置；原生面板也保留未改变的字段，只有实际可见性变化才更新文档布局。
- 控件双击与子程序导航调用 `goto_routine()`，定位首个代码位置而非隐藏的声明行；子程序已收缩时先展开。普通调试/行号跳转进入折叠体也会展开。新建 Node 事件处理器生成多行代码体。
- 真实源码保存在编辑器文档模型中。隐藏声明/导入、选择子程序、收缩信息区都不删除源码；保存、运行与构建使用完整文档。
- 原生 Qt 提供可编辑名称、返回类型、公开复选框、备注和局部变量表；按所选子程序显示代码体，并使用真实源码行号。关闭中文视图可以查看整个文件。
- Monaco 使用 view zones 和隐藏行；单行 JavaScript/TypeScript 函数含有实际语句时保留该行，防止连同函数体一起隐藏。
- 中文视图中，文件顶层初始化及分隔空白随显式绑定的启动处理器收缩/展开；无启动处理器的普通文件保留独立顶层代码。仅改变可见范围，不移动源码或改变执行语义。Monaco 全收缩需要一个末行显示锚点，该行源码、光标和高亮均不可见且正文只读；展开或跳转到所属代码恢复显示和编辑。原生收缩时同样保护隐藏正文。
- Monaco 名称只出现在可编辑声明行，三角紧邻名称；声明源码号放在实际左侧 gutter。设置/参数/局部表宽度统一，空局部表仅显示添加条；ResizeObserver 按实际内容同时增减高度，删除局部和收缩后不会残留预留空白。原生表也按实际内容限制高度，隐藏空局部表。
- `_启动程序` 是主窗口 load 处理器的默认显示标题。改标题不会改真实处理器或事件绑定。次级窗口 load 不成为全局软件入口。中文源码只有 `主程序` 或 `_启动程序` 会自动调用；普通首个函数不会自动启动。
- `.pcide/routines.json` 记录 `id/file/sourceName/line`、返回类型、公开、备注、局部变量。匹配使用文件与源码名称，行号仅用于定位；插入行后重新对齐，删除声明后清除旧元数据。
- 普通子程序改名同步项目源码中的标识符和所有窗口事件绑定；字符串、注释保持原文。其他文件存在同名声明时拒绝改名，避免错误地改到另一条调用链。

## 运行与作用域

- `core/source.py` 是 Python/中文源码运行和构建共用的 AST 入口。元数据局部变量在所属函数内初始化，原语句行号不变；不会加入全项目补全。
- 全局数据由 worker 内共享对象承载；全局常量不可赋值。参数、显式局部声明和局部元数据优先于同名全局数据。
- 窗口/模块数据使用显式的 `所属名称.代码名称`。局部数据必须填写所属子程序；Python/中文源码支持静态局部数据，Node 静态局部数据明确报错。
- 自定义类型生成真实类和成员初始化；拒绝未知类型、非法初值和递归初始化。整数型/长整数型/字节型具有声明范围校验。Python/中文源码的已声明返回类型和显式参数类型在 worker 校验。
- 公开函数通过 worker 内延迟模块加载器实际调用；重复的全局公开名称报错。普通 Python import 和 CommonJS require 仍遵循对应语言的模块规则；IDE 的公开表不是恶意代码沙箱。
- JavaScript/TypeScript 共用 `source_contract.cjs`，在所属函数中注入元数据局部变量；程序数据在 worker 初始化，公开调用在源代码和 Bytenode 交付中均走真实模块函数。
- 备注保存为声明注释元数据，不参与表达式求值。

## 中文源码语法边界

支持 `.版本 2`、`.程序集`、`.子程序`、`.参数`、`.局部变量`、`导入/.导入`、赋值、普通函数调用、`调用`、`返回`、`输出/调试输出/信息框`、`如果/否则如果/否则/结束如果`、`循环/结束循环` 和 `遍历 变量, 可迭代对象`。

函数实参从第一个声明参数开始传递，事件数据通过关键字参数 `event` 独立传递。真/假/空只转换 NAME token，不改字符串或注释。中文源码尚无完整易语言控制流、参考参数、所有系统命令及中文类/继承语法；普通 Python/JS/TS 类和继承仍由相应语言运行时执行。

## 可迭代的源码模块

`.pcide/modules.json` 使用 `version:1`，每项包含 `id/version/file/exports/dependencies`。源码必须在项目 `src` 内；版本为三段精确版本；拒绝重复接口、缺失接口、路径越界、缺失依赖和依赖循环。

左侧“程序数据 → 模块引用表”可编辑模块引用。使用 `模块名.公开函数(...)` 或中文源码 `导入 模块名` 后调用。修改源码或版本后，下次运行重新创建 worker 并加载新代码；运行中的模块不做不安全热替换。当前版本化模块表开放 Python/中文源码；Node 使用公开表和 CommonJS/TypeScript 模块。

## DLL ABI

- `runtime_api.dll` 是客户端，不加载客户 DLL。`PluginSession → plugin_host → dll_host.DllLibrary` 独立承载 DLL，复用 Windows ProcessJob、ChildLog、协议记录限制、调用超时和崩溃检测。
- DLL 必须是项目内相对 `.dll` 路径，不接受符号链接、越界和系统搜索路径。宿主拒绝不同位数的 PE。API 库应明确放入项目中；系统 DLL 隐式搜索尚未开放。
- 调用约定：cdecl、stdcall、winapi。参数必须提供 `argument_types`，不根据实参猜 ABI。支持 int32/uint32/int64/uint64/uint8/float32/float64/bool32、UTF-8/UTF-16 输入。整数校验范围、文本不超过 16KB 且不含 NUL。
- 返回只开放标量和 void。文本指针返回、裸指针、结构体、输出参数、fastcall/thiscall、跨位数 ABI 尚未开放，明确报错。不存在固定长度 `ctypes.string_at` 读取或跨进程传递地址整数。
- load 返回不透明 UUID；每调用默认 5 秒、允许 0.05–60 秒；同时最多 4 个宿主。unload/worker 退出终止宿主，操作系统释放 DLL；调用超时或崩溃后旧句柄不可继续调用。
- Node DLL ABI 暂未开放，生成和运行入口显示明确错误。DLL 子进程隔离不能限制 DLL 自身访问系统资源，不宣称恶意代码 OS 沙箱。

## 构建输入与缓存

`.pcide/data.json`、`routines.json`、`modules.json` 与项目源码/表单/资源共同参与 SHA-256 输入指纹。Python/中文源码字节码缓存包含当前 Runtime/编译器指纹及数据/子程序元数据；Node 缓存同样包含源转换器与元数据。删除输入、产物校验失败或生成器变化都会触发重建。

用户项目构建复用预编译 Runtime；Node 编译器与基础设施冻结使用有日志上限、超时、取消和进程树清理的 `run_bounded`。普通项目的首次/增量/无变化耗时单独实测，不把 Runtime/IDE 完整冻结承诺为 10 秒。

## 已审阅官方资料

- [易语言资料手册](https://www.eyuyan.com/help/zlsc/lang.htm)：子程序参数/返回、全局/程序集/局部变量、类型成员、启动窗口与启动子程序分别处理。
- [易语言帮助](https://www.dywt.com.cn/help/lang.htm)：对应语言要素对照。
- [VB Module](https://learn.microsoft.com/en-us/dotnet/visual-basic/language-reference/statements/module-statement)：模块包含过程/数据，同名外部引用要限定模块；模块本身不继承。
- [VB 变量作用域](https://learn.microsoft.com/en-us/dotnet/visual-basic/programming-guide/language-features/declared-elements/how-to-control-the-scope-of-a-variable)：局部声明仅在所属过程或块中可见。
- [VB 声明引用](https://learn.microsoft.com/en-us/dotnet/visual-basic/programming-guide/language-features/declared-elements/references-to-declared-elements)：限定名称与引用范围。
- [VB 创建过程](https://learn.microsoft.com/en-us/dotnet/visual-basic/programming-guide/language-features/procedures/how-to-create-a-procedure)：有返回和无返回过程的声明及调用。
- [MSBuild 增量构建](https://learn.microsoft.com/en-us/visualstudio/msbuild/incremental-builds?view=visualstudio)：输入/输出变化与部分增量构建。PCIDE 使用哈希与完整输入清单，保留删除记录。

参考的是语言与工程合同，没有复制上述产品源码。
