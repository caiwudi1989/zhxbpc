# PC Modules

## 最新交付：页面继续复核与遗漏补齐

| 模块 | 内容 | 验证 |
| --- | --- | --- |
| main / library_dialog | 14页与提示、命令/片段/组件说明、共享输出清空/导出、调用/断点回车与工程边界、预览当前未保存设计及事件隔离、设计动作适用性 | native/Monaco各15项通过；4种工程冻结UI与脚本smoke在两路径通过 |
| core/menus / control_catalog / builder | 明确menu/item/separator字段和层级；最多256项/8层、唯一ID/快捷键、状态/处理器验证；菜单模块纳入Runtime源码身份 | 非法合同拒绝；三套Runtime已重建且实际编译代码审计一致 |
| ui/menu_dialog / properties / form_runtime | 真实菜单树与编辑、快捷键/状态/勾选、源码事件创建/定位；属性统一入口；实际嵌套QMenu/QAction与更新、单次事件参数 | 真实保存/取消/源码/运行行为，菜单编辑和运行菜单截图 |
| ui/designer / main排列菜单 | 完整对齐/等大/等间距/容器居中/z顺序；右键共用动作；真实父级坐标、复制和脱离；显式QMenu生命周期 | 保存/撤销/坐标回归；最后修正后排列定向1项与5份Monaco截图通过 |
| docs/规范/pages.md / libraries.md | 页面清单、合并/删减、菜单/提示/排列/预览/输出/导航说明与实际边界 | 冻结资源逐项摘要一致，73编译模块/483资源/入口/Runtime审计ok:true |

- 当前完整交付 `build/PCIDE/PCIDE.exe`，SHA-256 `2cb2adfa016ae3bdd36d915b65853a47761c079f13de41b8160a73f9f4491c33`；旧目录 `build/pages-followup-previous-20261010`。证据 `cache/logs/pages-followup-{primary-artifact,primary-ui,promotion}-20261010.json`，实际截图 `pages-followup-captures-20261010`；测试范围详见verification最新节。未宣称EC/FNE/Timer/WebView或本轮未测设备/生产视觉/干净机器已完成。

## 此前交付：页面内容补齐与合并

| 模块 | 内容 | 验证 |
| --- | --- | --- |
| MainWindow / routine_ranges | 13 页面恢复/适用模式、入口/其他文件共用子程序扫描，补 Python async、JS/TS export/async、排除注释/字符串、真实行号导航和入口去重；断点/调用表、共享日志、设计器打开前保存 | 88 项较广 native；38 项最终 native（37通过/1环境跳过）、30 项 Monaco全通过；异步导航/范围 native定向4项；两路径三工程冻结启动 |
| resource_panel / configuration_dialogs | 真实资源表、预览/导入/复制路径/改名/删除；真实运行限制与平台声明/提供者清单 | 二进制不打开源码、字段实际保存、声明不执行的 UI 用例 |
| platform_dialogs / api_center | SQLite/API 全字段、JSON 同步、生成预览、保护用户代码、失败回滚；引号/名称/HTTP校验、JS/TS超时取消、共享导入 | SQLite 实执行、Python 生成客户端调用、Node 执行 JS/转译 TS 并取消、写入故障回滚；最后 API 5 项通过 |
| properties / designer / flow_canvas / vision_panel / editor | 组件选择、中文事件、窗口宽高；节点参数/方向/连线删除；标注表/逐条删除/反馈；原生断点显示 | 20 新页面用例、实际表单/流程保存与执行，30 份页面截图 |
| 页面帮助 / 打包审计 | `docs/规范/pages.md` 记录全部核对入口、合并和真实边界，并随 EXE 分发 | 71 编译模块、483 资源、三套既有 Runtime 和入口一致，原路径 `ok:true` |

- 当前 EXE SHA-256 `dacdc0f7a297896ed9700a0f0ff6ea06509de3f28cc640c2d5bca37d63448809`；完整交付 `build/PCIDE`，原版本保留 `build/pages-review-previous-20261010`，导航修复前版本保留 `build/pages-review-before-navigation-20261010`。证据 `cache/logs/pages-review-{primary-artifact,primary-ui,promotion}-20261010.json`。EC/FNE/Timer/WebView/调试写入/非 HTTP transport 等边界未伪称已实现；本轮范围不包含历史全量、硬件/Android/生产视觉/客户发布与干净机器验收。

## 上轮交付：支持库目录与非脚本源码显示

| 模块 | 实现与边界 | 验证 |
| --- | --- | --- |
| `core/libraries.py` / `main.py` / `ui/library_dialog.py` | 实际核心命令分类、库定义类型/常量、组件属性/事件/方法；选择条目显示完整说明/格式/返回值/代码。C/C++/.NET/引擎/网页代码片段位于独立页。27 控件与窗口按真实实现生成，时钟/WebView 限制明确；EC/FNE 专用 ABI 仍待桥接 | 核心 11/native 18/Monaco 4 项均通过，包含真实目录示例运行、拖放/帮助和导入配置 |
| `ui/editor.py` / `editor.html` | Python 才使用中文关键字投影；非脚本语言显示与保存原文，中文子程序视图按钮按文件语言启用 | C++ 两后端编辑/保存回归、2 项静态合同，以及原路径 C++ Monaco 逐字显示检查通过 |
| `tools/freeze_ide.py` / `verify_development_artifacts.py` | 支持库文档纳入冻结资源；完整目录提升到原启动路径，工作区 `..\..`，旧目录保留 | 原路径 69 编译模块/482 资源/三套现有 Runtime 审计 `ok:true`，C++/中文两工程冻结 Monaco UI 均退出 0 |

- 当前 `build/PCIDE/PCIDE.exe` SHA-256：`5a59206eb6f09affda0b263035631f7b305a821f66a53180990cd3228d389d90`；回退目录 `build/support-catalog-previous-20261010`。证据 `cache/logs/support-catalog-{promotion,primary-artifact,primary-ui}-20261010.json`，截图 `support-catalog-primary-{cpp,zhxb}-monaco-20261010.png`。本轮未重跑后文历史全量/客户发布/视觉/硬件门禁。

## 0.2 软件与游戏开发扩展

| 模块 | 入口 | 本轮交互与边界 |
| --- | --- | --- |
| 项目/构建工厂 | development.py / build_service.py | 19模板，系统环境、原生静态CRT、.NET系统/AOT、CMake、网页和Unity/Godot发布；当前外部工具已安装才执行 |
| 精确增量构建 | build_service.py / main.py | 编译设置保存到项目；原生按传递本地头文件失效，CMake复用配置缓存，.NET复用离线 assets |
| 已有引擎与工具默认 | engines.py / toolchains.py | Unity/Godot已有工程接入可运行/构建引用工程；工具路径复用于新工程/示例，项目配置优先 |
| 欢迎/编译/示例 | development_dialogs.py / main.py | 类型与模式选择、增量/重新构建/取消/产物、100完整例双击载入副本 |
| 外部进程与缓存 | tool_session.py / processes.py | 外部引擎/程序所有权、超时/有限日志/停止/切换/退出回收，编译失败保留旧产物 |
| 控制台交互 | MainWindow / ToolSession.send / ChildLog | 原生/C# F5启动，实时输出、输入队列、写入超时；程序退出后禁用输入 |
| 线程/资源 | tasks.py / runtime_api.py / editor.py | 有界任务与协作取消、游标/响应/临时文件清理、已保存编辑模型淘汰；未保存内容受保护 |
| 支持库/AI UI | libraries.py / catalog_tree.py / main.py / agent_tools.py | 命令分类/类型属性事件方法/常量、选择即显示说明；原生和引擎示例在独立代码片段页；已批准JSON表单刷新设计器 |
| 原生源码显示/保存 | editor.py / editor.html | 中文关键字投影仅用于Python；C++ const/return等保持原文；中文子程序视图按钮跟随当前文件语言 |

本轮使用方式和官方来源在`docs/规范/development.md`；具体测试、真实耗时/体积、冻结产物及未配置引擎边界在verification最新节。

最终交付为 `build/PCIDE/PCIDE.exe` + `_internal`；100 个离线例子在 `examples/catalog.json` / `examples/projects`，双击载入副本。工具与引擎不下载；Unity/Godot/CMake 只在检测到已有可执行文件后运行。

| Module | Entry / Direct Dependencies | State |
| --- | --- | --- |
| Project | `Project.create/open/load_form/save_form` -> JSON schema, atomic IO | Implemented and validated |
| Editor | `ui/editor.py` -> `pcide://editor` -> offline Monaco 0.52.2/WebChannel; restricted-host fallback -> native `QPlainTextEdit` | Monaco is used on supported desktops; Codex/restricted Windows tokens avoid the Chromium Mojo named-pipe popup through the native fallback; both source and frozen UI smoke pass |
| Designer | graphics scene -> form model -> property/events/tree | Drag, resize, copy, undo/redo, save/load and event preview validated |
| Script/debug | `core/runner.py` -> owned console child -> Python bdb or Node inspector | Python/JS/TS run, debug, stop, timeout, error and pipe lifecycle validated |
| Flow | node graph -> `FlowRunner` -> bounded operations | Dependency, timeout, cancellation and local operations validated |
| Plugins | manifest -> `PluginRegistry` -> isolated Python/C/.NET/DEX hosts | Permission, crash, timeout, reload and frozen Python/C/.NET paths validated; Android ART remains device-gated |
| Vision | dataset/labels -> `VisionWorkbench` -> RapidOCR/OpenCV/optional training | Real OCR and ONNX execution/export validated; accuracy remains outside synthetic gate |
| Build | runtime fingerprint -> `.pyc`/`.jsc` cache -> fixed runtime -> payload archive | Directory/standalone incremental builds, source scan and portable customer EXEs validated; binary payloads stream without wasteful zlib compression and packaging format is part of the cache fingerprint |
| Windows/data contracts | `Project.window_paths/load_window/rename_path/delete_path` -> form schema -> `RuntimeWindowManager`; window menu/context menu -> new/open/rename/delete form -> designer view; project-tree file/dir actions -> validated filesystem mutation; `runtime_api.ui.open/close/set` -> window/control routing; `.pcide/data.json` -> `core.data` -> language generators | Independent form files, discoverable new-window entry, safe project-tree file operations with protected required paths, designer switching without opening source code, size/layout constraints, runtime open/close/update/resize/close-event lifecycle, recursive project tree, four variable scopes, constants, DLL/API metadata, and Chinese label/English ID mapping are source/Qt-tested |

Final command evidence and limits are recorded in `docs/archive/verification.md` and the JSON reports under `cache/logs`.

- 2026-10-07：用户界面、提示、弹窗和模板示例已中文化；冻结构建已重新生成并通过发布验收。
| IDE layout/completion | `main.py` -> workspace tabs, project tree/routines, support-library/property tabs, environment dialog; `ui/editor.py` -> project symbols -> Monaco completion/signature/folding | Implemented; source and frozen smoke/UI smoke validated |
| IDE layout closeout | `main.py` -> left support/property/data tabs + project/routine navigation, center designer/code workspace, right toolbox, bottom output; `properties.py`/`designer.py`/`form_runtime.py` -> Frame/Tabs properties and runtime rendering; `editor.py`/`editor.html` -> completion/signature/folding | Layout aligned to the supplied Yi-language reference; 40 source tests and frozen/delivery smoke gates passed |
| IDE editor theme | `ui/editor.html` -> Monaco `pcide-light` theme and editor surface | Fixed invalid color literals that caused Monaco theme variables to fall back to pure red; verified white editor surface, Yi-style line numbers/highlight, and collapsible routine metadata in source capture and frozen/delivery smoke |
| Control catalog/property sync | `core/control_catalog.py` -> `project.py` schema validation -> `designer.py` toolbox -> `properties.py` -> `form_runtime.py` | 27 control types grouped into basic/data/container/advanced categories; selected-control properties, immediate commit on focus/Enter/combo changes, and runtime/design preview synchronization validated |

| Final editor/release closeout | `ui/editor.py` native fallback + `main.py` lifecycle/plugin menus -> `core/project.py` safe import -> `core/plugin_market.py` upgrade/rollback -> `core/archive_bundle.py` | Native fallback has highlight/completion/undo/find/format/breakpoint support; 56-test regression, frozen smoke/UI smoke, isolated customer release and worker cleanup all passed on the constrained Windows host |
| Yi-style routine metadata | `main.py` primary-window load event -> `ui/editor.py` -> Monaco zones / native `routine_panel.py` -> `.pcide/routines.json` | Primary software startup title stays editable without changing its handler; ordinary renames update source calls/events; metadata follows file/source identity across line insertions; locals participate in actual runtime/build |
| Source/data/modules | `source.py`, `project_sources.py`, `source_contract.cjs`, `modules.py` -> workers / builder | Shared source contract, lazy public calls, typed locals/shared data, explicit module exports/exact dependencies; current boundaries in `docs/规范/routine-runtime.md` |
| DLL host | `dll.py` -> `PluginSession` -> `plugin_host.py` -> `dll_host.py` | Real scalar call, timeout, crash, unloading and recovery verified; native DLL code never enters IDE; pointer/text returns and advanced ABI explicitly unavailable |
| 支持库与加入 | `libraries.py` -> `library_dialog.py` / 左侧支持库 -> modules/data/plugins | 系统库命令按真实语言API生成；源码、明确ABI DLL、JSON封装包实际调用；EC/FNE待桥接，DEX待Android部署/真机 |
| 参数与局部 | `routine_signatures.py` -> `parameter_dialog.py` -> 两编辑器 -> compiler/source/worker | 参数保存回真实源码；与普通/静态局部初始化分开；中文无默认值参数必填，复杂Node参数使用源码视图 |
| 数据表与快捷键 | `data_panel.py` / `main.py` -> 程序夹和F1说明 | 分类列、完整新增、成员数组/DLL参数表、作用域补全；当前文本/代码/设计撤销路由，设计快捷键不抢文本输入 |

## 2026-10-10 当前交付证据

- 最新支持库/数据表/参数/快捷键交付：原路径 `build/PCIDE/PCIDE.exe`，完整 `_internal` 同级；EXE SHA-256 `7cbf56abba6212e282be8c5e3cb90919469e99eac3a9249bec11c34889bfea74`。三个Runtime已重建且实际嵌入核心代码与源码一致；staging和原路径四种smoke均成功；保留 `build/libraries-parameters-previous-20261010`。证据 `libraries-parameters-{artifact,promotion}-20261010.json`。
- 核心40项为39通过/1环境跳过；Monaco39项为38通过/1原生专属跳过；native38项为34通过/4Monaco专属跳过，加DLL参数/签名定向2项通过。四语言实际构建/运行单文件客户EXE输出42，Python另验证封装插件和DLL；`library-customers-20261010.json`绑定最终IDE摘要。下方此前全量/视觉/硬件证据未冒充本轮重跑。
- 使用说明 `docs/规范/libraries.md` 覆盖加入位置、插件包、官方资料、参数/局部和快捷键；EC/FNE仍需官方编译或ABI桥接，DEX须Android宿主；Node插件代理与高级DLL ABI尚未开放。

- 最新显示修正：公开列只保留一个复选框勾选，Monaco删除额外span，原生公开标签去掉额外符号；既有勾选/保存用例和真实截图核对通过。交付`build/PCIDE`已更新，证据`editor-public-single-check-{capture,artifact,promotion}-20261010.json`。

- 最新残留内容修正：顶层初始化和空白随显式启动处理器收缩/展开，全收缩只剩连续名称行；完整源码不变，隐藏正文不可误输入。Monaco 32项为31通过/1专属跳过，native 32项为28通过/4专属跳过；原路径EXE已替换并通过脚本、native、auto和正常桌面Monaco smoke，源码/编译代码一致。证据 `editor-startup-scope-{capture,artifact,promotion}-20261010.json`。

- 最新三项修复：收缩/展开实际隐藏/恢复所属代码体；正文输入和换行保留表格及焦点；控件双击进入对应子程序代码体并自动展开。`ui/routine_ranges.py` 提供原生编辑范围，Monaco 复用 view zone；独立冻结后已替换 `build/PCIDE`，源码/打包 HTML 与四个编译 UI 模块一致。此前“元数据折叠”证据不等同于本次代码体折叠证据。

- 用户截图后的最新修正：子程序名称/三角合并到同一行、各表统一宽度、空局部表折为添加条、view zone 高度可增可减；真实鼠标键盘编辑、折叠、插行和切文件保存验证通过。Monaco 28 项为 27 通过/1 native 跳过，native 28 项为 24 通过/4 Monaco 跳过；最终 IDE 已独立重建后替换原路径，冻结截图 `editor-layout-frozen-20261010.png`。下列全量和发布数据属于此前 Runtime 收口，未冒充本次重跑。

- 全量 84 项：81 通过、3 Monaco 专属跳过；正常桌面 Monaco 27 项：26 通过、1 native 专属跳过。源代码及冻结版 native/受限 auto/正常桌面 Monaco UI smoke 均通过，截图已检查。
- 三套 Runtime 已刷新，与源码及 IDE 内置指纹一致；IDE 交付为 `build/PCIDE/PCIDE.exe` 和同级完整 `_internal`。
- 四语言独立客户 EXE 实际输出公开跨文件调用结果 `9`，载荷扫描无项目源码/SDK。增量构建 `1.391–3.344` 秒；首次和缓存数据见 `cache/logs/closeout-build-timings-20261010.json`。
- 作用域、模块、DLL、中文语法的明确限制见 `docs/规范/routine-runtime.md`；发布/生命周期最终证据见 `docs/archive/verification.md`。
