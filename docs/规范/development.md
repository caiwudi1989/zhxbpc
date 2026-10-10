# 软件、游戏、编译与迭代

## 从欢迎页开始

启动 IDE 显示欢迎页；项目菜单也可重新打开。选择开发类型、语言/开发模式、编译方式与名称，然后创建。

| 开发类型 | 模板 | UI 与运行方式 |
| --- | --- | --- |
| 脚本与自动化 | Python、中文源码、JavaScript、TypeScript | 代码编辑、F5运行、脚本断点/单步、支持库、流程 |
| 窗口软件 | 上述四语言窗口模板 | PCIDE控件设计器、事件、预览、AI表单JSON写入 |
| 小型原生软件 | C、C++控制台、C++ Win32 | 系统编译器生成机器码；Win32直接使用Windows API |
| 多文件原生工程 | C++ CMake | 系统CMake、工程定义的依赖与增量构建；约定app目标和bin/app.exe |
| C#软件 | 控制台、Windows Forms | 系统.NET发布；控制台可选择Native AOT；WinForms使用框架依赖发布 |
| 网页与小游戏 | HTML/JavaScript | 系统浏览器、Canvas、静态资源发布 |
| 游戏引擎 | Unity 2D/3D、Godot 2D/3D | 编辑源码，打开外部引擎、运行/导出、日志、超时和停止 |

模板、构建方式与语言由同一个项目工厂管理；`.pcide/project.json`中的`development`声明模板、target、configuration、jobs、tools和engine_root。旧脚本工程自动补齐兼容配置。拒绝未知字段、错误语言组合、不支持的构建方式和非法工具路径。

## 编译与静态编译

Ctrl+B打开设置；Ctrl+Shift+B按当前设置增量编译。菜单支持重新构建、取消、查看产物。输出包含真实耗时、产物字节数、缓存命中、编译文件数与工具日志。

| 方式 | 交付物 | 目标机器需要什么 |
| --- | --- | --- |
| 脚本独立EXE | 单文件EXE及应用字节码 | 包含所需脚本/窗口运行时；文件体积包含这些依赖 |
| 脚本系统环境 | 源码payload、轻量PCIDE辅助字节码、launch.cmd | Python 3.12；Node工程另需Node；窗口工程另需PySide6；不附带解释器或Qt DLL |
| C/C++系统CRT | app.exe与项目resources | 编译器对应的系统/共享运行库；MinGW共享C++库需要目标机已有相应DLL |
| C/C++静态CRT | app.exe与项目resources | 可静态链接的CRT进入EXE；Windows系统DLL仍由操作系统提供 |
| CMake | app.exe、同输出目录运行文件与resources | 取决于CMake工程自己的链接与依赖选择 |
| .NET系统运行时 | app.exe、应用程序集/配置 | 匹配的系统.NET，不复制.NET环境 |
| .NET Native AOT | 本机机器码与发布资源 | 开发机需已有AOT原生工具/包；不启用远程包下载；不承诺任意反射/插件代码都能AOT |
| Unity/Godot | 引擎生成的Windows游戏 | 引擎负责自身数据文件、运行库与平台导出要求 |
| 网页 | HTML/JS/CSS与资源 | 系统浏览器 |

想要很小的独立Windows工具，可选择C或C++ Win32模板，按需链接、Release优化和静态CRT。脚本单文件打包与机器码静态链接是不同的构建方式。复杂UI、模型、媒体和游戏资源会增加体积，不能由一个打包开关消除。

C/C++按源文件和头文件内容、工具身份、配置缓存目标文件；头文件改变会使相关保守缓存失效。并行数限制为1..4。CMake保留自己的构建目录；脚本继续使用原有字节码缓存。缓存命中前检查交付文件摘要；源码在构建期间改变会拒绝提升，失败或取消保留此前成功产物。MinGW使用相对输出、临时文件和链接搜索路径处理中文工作目录，不需要创建系统盘符。

原生增量缓存按每个源文件实际解析到的项目 `#include` 依赖计算；修改未被该源文件引用的头文件不会触发无关翻译单元重编，新增或删除已引用头文件仍会使对应对象失效。CMake 首次配置后复用 `CMakeCache.txt`，仅在强制重建时重新配置；.NET 首次发布生成离线 assets 后的源码迭代使用 `--no-restore`，避免重复解析包图。编译对话框选择的目标、Release/Debug 和并行上限会保存到 `.pcide/project.json`，重开工程继续使用同一发布合同。

系统环境发布在编译阶段处理JavaScript/TypeScript的程序数据、公开调用、局部初始化和TS转换；交付物不带TypeScript SDK。保留原始模块文件名以兼容显式`require("./helper.ts")`和元数据，但交付`.ts`正文已转换为JavaScript；继续开发时编辑原工程，重新发布。

冻结IDE和脚本宿主显式包含常用Python标准库（配置INI、文本差异、压缩/归档、HTTP/XML、SQLite、统计、线程和unittest等），避免源码运行成功但冻结后动态导入缺失。清单位于`builder.STANDARD_LIBRARY_IMPORTS`并参与Runtime缓存身份；额外第三方包仍需明确的支持库/插件接入。

## 环境与引擎交互

“环境 → 系统工具与游戏引擎”发现已有PATH或系统安装目录；可以填入真实.exe。留空继续发现。勾选“保存为工作区默认”后，新工程和示例副本会复用`runtime/toolchains.json`中的工具路径；单个工程的配置优先。此设置页不安装或下载工具。MSVC需要已初始化的开发命令环境；CMake使用自己的已安装生成器/工具链。

Unity模板有C#脚本、包清单和`Assets/Editor/PCIDEBuild.cs`。打开Unity后，用`PCIDE/Create Demo Scene`创建示例场景，再按Play。IDE的F5打开Unity编辑器；Unity的Play/Profiler/断点由Unity管理。Windows构建调用批处理入口；已绑定外部Unity工程则使用其已有Build Settings场景。需要本机Unity编辑器、许可证和Windows Build Support。模板为Unity 6基础工程，版本升级由所选Unity编辑器处理。

“游戏引擎 → 接入已有 Unity/Godot 工程”统一创建可构建的IDE引用工程；在同种引擎模板内选择时直接更新绑定。“平台 → 接入 Unity 工程”也使用这一流程。原有外部资产不被导入流程改写；F5、打开编辑器、Ctrl+B和停止使用同一绑定。Unity 2D模板使用正交摄像机和Z轴旋转，并声明内置2D物理/输入模块；支持库根据Unity模板显示对象、协程、场景API。Unity导入/Job worker数量跟随1..4并行设置。

Godot模板包含project.godot、场景、脚本和Windows Desktop导出预设。F5运行游戏；游戏引擎菜单打开编辑器或导出Windows游戏。需要Godot 4编辑器及匹配导出模板。可在配置页填写`engine_root`绑定已有Unity/Godot工程；此时源码编辑仍使用PCIDE工程内文件，外部工程的场景/脚本在对应引擎编辑器中编辑。没有偷偷覆盖外部工程资产的同步行为。

外部引擎/游戏/应用始终由IDE拥有的子进程启动。停止、切换工程、退出IDE会终止进程树；单次构建有时间与1MB字符日志上限。IDE不会将引擎或客户DLL加载到自己的进程。脚本调试器支持四种脚本语言；C/C++/C#/引擎调试使用各自外部工具，当前没有声称实现通用原生调试协议。

原生/C#控制台工程F5编译后启动，底部输出区实时显示程序输出（包含没有换行的提示）；在“控制台输入”栏输入并回车/点发送。每次最多4096字符、队列最多16条，写入堵塞会回收子进程。程序退出后输入自动禁用；GUI和引擎通过自己的窗口交互。脚本使用其表单/事件协议交互。

重新运行或批处理编译前，先关闭当前外部程序/引擎，或按Shift+F5停止；避免运行中的交付文件被替换和Unity工程锁冲突。关闭工程后欢迎页继续可用，可直接创建/打开另一工程。

## 支持库与线程

支持库可搜索，选中项在下方显示说明与调用例子；每个命令可以右键帮助、插入或复制，也可双击或拖到编辑器。源码模块的帮助读取真实签名/文档字符串，不导入第三方代码。原生/引擎模板的线程、RAII、using、Win32、信号/节点释放与网页动画示例位于左侧独立“代码片段”页。中文源码支持库按命令、类型属性/事件/方法和常量组织，详细能力边界见 `libraries.md`。

Python/中文运行时提供`tasks`：

```python
from pcide.runtime_api import tasks, ui

def work(cancel, value):
    if not tasks.sleep(cancel, 0.01):
        return None
    ui.set("Label1", text=str(value))
    return value * value

with tasks.pool(workers=2, capacity=4) as pool:
    job = pool.submit(work, 42)
    result = job.result(timeout=3)
```

| 方法 | 行为 |
| --- | --- |
| tasks.pool(workers, capacity) | 每宿主最多4个池，每池最多4线程和64个未完成任务 |
| pool.submit(function, *args, **kwargs) | 函数首参数为取消事件；队列容量满立即拒绝 |
| job.result(timeout) | 有限等待，返回结果或原任务异常 |
| job.cancel() / job.done() | 取消排队任务/通知运行任务；查询完成不阻塞 |
| tasks.sleep(cancel, seconds) | 可被取消打断的延时，取消时返回False |
| pool.close(timeout) / with | 取消、有限等待和线程清理；完成任务不留在池的结果列表 |

后台`ui.set`通过协议与Qt事件队列回到UI线程。取消是协作的：回调需检查事件或使用tasks.sleep；不可中断的客户代码由独立脚本宿主停止/超时回收。返回值仍由用户持有的job/result负责生命周期，池不会强行删除用户正在使用的对象。SQLite游标、HTTP响应及原生编译临时文件在对应出口关闭/清理。

## AI从后台写UI

AI助手可将当前窗口与入口加入批准路径。模型使用`inspect_ui`读取完整窗口合同，再用`write_ui`写完整模型：校验尺寸、控件类型、属性、唯一ID/name和事件名称；已有文件必须先读取，读取后内容被其他工具修改会拒绝覆盖。

`write_ui`允许已批准路径，写后设计器通过Qt信号刷新。事件处理代码由read_file/write_file工具写入入口源码。关闭助手后重新载入工程，预览按钮检查实际界面。新建窗口需显式批准其精确路径和create=true。原生WinForms、网页及引擎UI由AI编辑相应源码/场景文件；PCIDE JSON设计器不会伪装成Unity场景或WinForms设计器。

## 示例与迭代

“欢迎 → 100个完整示例”或“帮助 → 完整示例中心”可按类别/关键词搜索、阅读完整说明。双击载入工程副本，同名副本自动编号；原例不会被编辑覆盖。

100例包括60个Python基础/PC/数据/算法/工厂/线程/资源/回归工程、8个窗口例、4个多语言例、10个C/C++工程、6个C#工程、6个网页/Canvas例、3个Unity和3个Godot工程。每个例子有真实入口、明确所需工具、运行步骤和预期结果。未安装引擎或AOT工具时，界面会报告缺少的环境，而不会返回假构建成功。

迭代流程：修改 → 保存 → 运行/预览 → 查看日志/错误 → 再修改 → 增量构建。外部编辑器改动可通过“项目 → 重新载入磁盘内容”同步；IDE有未保存内容时先保存，避免覆盖。源文件、资源与配置都参与构建身份；当前输入扫描上限为10000文件/512MB，生成目录不会参与扫描。

## 官方参考与本轮验证范围

- [Unity命令行与构建](https://docs.unity3d.com/Manual/EditorCommandLineArguments.html)：工程路径、批处理、静态执行入口与Windows构建参数。
- [Godot命令行](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)：编辑器、运行、headless导出和预设/模板要求。
- [CMake命令行](https://cmake.org/cmake/help/latest/manual/cmake.1.html)：配置、保留构建目录、并行与clean-first。
- [Microsoft CRT选项](https://learn.microsoft.com/en-us/cpp/build/reference/md-mt-ld-use-run-time-library?view=msvc-170)：/MD与/MT的运行库区别。
- [.NET Native AOT](https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/)与[体积优化](https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/optimizing)：本机代码发布、限制和OptimizationPreference。
- [PyInstaller动态导入](https://pyinstaller.org/en/stable/when-things-go-wrong.html#listing-hidden-imports)：显式收集由客户脚本动态调用的标准库，并用冻结程序实际运行验证。
- [Windows 桌面应用开发](https://learn.microsoft.com/en-us/windows/apps/desktop/)：Win32、Windows App SDK 与桌面部署的官方入口；PCIDE 只配置已有 SDK/工具，不在 IDE 进程内加载第三方 DLL。
- [CMake 构建命令](https://cmake.org/cmake/help/latest/manual/cmake.1.html)：`--build --parallel`、`--clean-first` 和保留构建目录的命令合同。

实际测试和交付摘要在`docs/archive/verification.md`。引擎命令合同测试只证明参数/工程文件正确，不代表Unity/Godot已安装或游戏已在引擎中成功导出；另一台干净Windows机器、硬件/Android/GPU、任意第三方CMake/SDK工程也需各自实机验收。
