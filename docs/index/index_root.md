# Project Index

## 最新交付：子程序输入与 Ctrl 快捷键

- 完整交付 `build/PCIDE/PCIDE.exe`，SHA-256 `43f8dd535c8c0865da193c41691f77f554a907ffdcb977017f99bd98c063934b`；旧目录 `build/editor-input-previous-20261011`。两路径实际逐个点入默认工程4个子程序，验证字母/数字/换行/中文提交、9组 Ctrl 操作和保存重开；入口、74编译模块/483资源/3套 Runtime 审计一致，C++/中文窗口/Python Monaco 启动通过。精确范围见 `archive/verification.md` 最新节。
- `ui/editor.html` / `editor.py`：收缩不再锁整个文档；全收缩输入先展开正文，正文点击与代码页恢复 Qt/Monaco 焦点，正文撤销/重做走 Monaco。
- `ui/native_edit.py`：同一可编辑合同、native 查找/替换与 Esc 返回正文、跨子程序定位。
- `ui/input_probe.py` / `main.py --ui-input-smoke`：只允许 cache 副本的真实鼠标/键盘/中文提交、Ctrl+A/C/X/V/Z/Y/S/F/H、实际查找替换、磁盘保存检查；60秒有界门禁，输入探针在 WebEngine 回调返回后执行。
- `tests/test_editor_input.py` / `test_ui.py`：用户4子程序操作回归、全收缩自动进入正文；Monaco7项通过，native6通过/1后端几何跳过。Qt 测试先显示代码页再等初始化，旧“收缩就必须只读”的要求已移除。

## 此前交付：页面继续复核与遗漏补齐

- 当前完整交付 `build/PCIDE/PCIDE.exe`，SHA-256 `2cb2adfa016ae3bdd36d915b65853a47761c079f13de41b8160a73f9f4491c33`；旧目录 `build/pages-followup-previous-20261010`。staging/原路径均通过入口、73编译模块、483资源和三套重建Runtime的实际代码审计；四种工程MonacoUI与脚本smoke成功。详细范围见 `archive/verification.md` 最新节。
- `main.py`：14页适用性/恢复与当前提示、清空/导出共享输出、调用表/断点回车及工程路径边界；窗口菜单/控件事件共用源码入口，未保存设计预览及事件隔离，设计动作限制工程模式；显式排列QMenu对象生命周期修正。
- `core/menus.py`：明确菜单层级/类型/状态/处理器合同，256项/8层、唯一ID/快捷键和字段校验；旧items兼容。`core/control_catalog.py`验证表单属性，`core/builder.py`将菜单模块纳入Runtime身份。
- `ui/menu_dialog.py` / `properties.py`：真实菜单树、添加/移动/分隔/删除、快捷键、状态、事件代码创建/定位；属性合并为专用菜单入口。`ui/form_runtime.py`创建实际QMenu/QAction、嵌套/checked/更新和单次事件参数。
- `ui/designer.py`：完整排列与z顺序、画布局部选择/复制/粘贴、真实父级场景坐标、容器复制和父项删除后孩子位置保持；右键与主菜单共享动作。
- `tests/test_page_followup.py`：9项菜单/页面合同；native及Monaco各15项功能/窗口回归全通过，最后排列对象修正后1项定向与5份实际Monaco截图通过。较广57项为56通过/1环境跳过，其旧选择Qt槽异常已修复。
- `docs/规范/pages.md` / `libraries.md`：14页清单、菜单/排列/提示/预览/输出/回车导航、合并记录与真实能力边界；随最终EXE分发。EC/FNE、Timer/WebView和设备/生产视觉/干净机器等边界仍保留。

## 此前交付：页面内容补齐与合并

- 当前 `build/PCIDE/PCIDE.exe` SHA-256 `dacdc0f7a297896ed9700a0f0ff6ea06509de3f28cc640c2d5bca37d63448809`；原版本保留在 `build/pages-review-previous-20261010`，导航修复前版本保留在 `build/pages-review-before-navigation-20261010`。71 编译模块/483 资源/三套既有 Runtime 与源码一致，三个工程的原路径冻结 Monaco 和脚本启动通过。范围与证据见 `archive/verification.md` 最新节。
- `main.py` / `ui/routine_ranges.py`：13 页面适用性和视图恢复、断点/调用表状态、入口和其他文件共用子程序扫描（Python async、JS/TS export/async、排除注释/字符串）、真实行号导航与入口去重、资源导入、输出共享、数据库/API 打开前保存和冻结页面状态报告。
- `ui/resource_panel.py`：实际 resources 列表、搜索、预览、导入、相对路径复制、重命名/删除及显示上限。
- `ui/configuration_dialogs.py`：真实运行入口/限制、八项平台声明/配置与只读提供者清单。
- `ui/platform_dialogs.py` / `core/api_center.py`：数据库/API 结构化编辑、JSON 同步、生成预览、原子保存/源码保护；引号安全、名称/方法校验、JS/TS 超时取消和共享导入。
- `ui/properties.py` / `designer.py` / `flow_canvas.py` / `vision_panel.py`：组件选择/真实事件/窗口宽高、节点参数和连接方向、实际标注表/删除与空操作提示。`editor.py` 修正原生断点显示。
- `ui/module_dialog.py` / `library_dialog.py` / `development_dialogs.py` / `agent_dialog.py`：表格/项目名列宽及中文关闭按钮等页面整理。
- `tests/test_page_contents.py` / `test_page_generators.py`：20 页面用例和 3 生成/回滚合同；Monaco 30 项全通过，最终 native 38 项为37通过/1环境跳过，API 5 项通过。异步导航/收缩范围 native 定向4项通过。30 份实际截图在 `cache/logs/pages-review-captures-20261010`。
- `docs/规范/pages.md`：主页面、配套入口、补齐/合并/删减和能力边界；由 `freeze_ide.py` 打包，`verify_development_artifacts.py` 审计。EC/FNE、时钟/WebView 与非 HTTP transport 等边界仍保留。

- 上轮交付：支持库目录与非脚本源码显示修正，原路径 `build/PCIDE/PCIDE.exe` SHA-256 `5a59206eb6f09affda0b263035631f7b305a821f66a53180990cd3228d389d90`；旧目录 `build/support-catalog-previous-20261010`。核心 11/native 18/Monaco 4/编辑器合同 2 项均通过；原路径两工程 Monaco smoke 与 69 编译模块/482 资源/三套 Runtime 审计成功。证据 `cache/logs/support-catalog-{promotion,primary-artifact,primary-ui}-20261010.json`，详细范围见 `archive/verification.md` 最新节；EC/FNE 仍待桥接。
- `src/pcide/core/development.py`: 19个软件/脚本/网页/Unity/Godot模板，共用项目工厂与严格开发/构建方式合同。
- `src/pcide/core/build_service.py`, `toolchains.py`, `engines.py`, `tool_session.py`: 系统工具发现、10类发布目标、按文件原生缓存、静态CRT/.NET AOT入口、外部引擎与进程树生命周期；不安装环境。
- `core/build_service.py` 的原生对象缓存按传递本地 `#include` 依赖精确失效，CMake 复用 `CMakeCache.txt`，.NET 发布复用离线 assets；编译设置由 `main.py` 保存回 `.pcide/project.json`。
- `toolchains.py` 保存可复用工作区工具配置；`engines.bind_engine_project` 将旧Unity入口与Unity/Godot已有工程接入统一为可运行/构建引用工程，外部资产保留。
- `processes.ChildLog` 实时、有界UTF-8输出；`ToolSession.send` 和底部输入栏提供原生/C#控制台交互，16条队列/4096字符/写入超时回收。
- `builder.STANDARD_LIBRARY_IMPORTS` 显式收集常用标准库并参与Runtime身份；Node系统发布在构建时处理TS/程序数据/局部/公开模块，不交付TypeScript SDK。
- `src/pcide/ui/development_dialogs.py`: 欢迎页开发类型/模式、新建工程、编译设置、系统工具/引擎绑定、可搜索且双击载入的完整示例中心。
- `src/pcide/core/examples.py`, `examples/catalog.json`, `examples/projects`: 100个不同完整工程、介绍/依赖/预期结果；加载副本且不覆盖原例。
- `src/pcide/core/tasks.py`: 每宿主4池，每池4线程/64容量、协作取消、有限等待、结果/参数引用释放与worker退出清理。
- `src/pcide/ui/catalog_tree.py`, `core/libraries.py`, `main.py`: 支持库按命令分类、数据类型和常量组织；组件类型展开属性/事件/方法，选择即显示详细说明。C/C++/.NET/引擎/网页示例位于独立“代码片段”页。
- `ui/editor.py`, `editor.html`: 中文关键字投影限于 Python；C/C++/C#/HTML 等源码显示与保存原文，中文子程序视图按钮跟随当前文件语言。
- `core/agent_tools.py`, `ui/agent_dialog.py`: inspect_ui/write_ui结构化窗口读写、批准路径/并发改动/合同门禁、Qt信号刷新设计器；通用文本源码可编辑。
- `ui/editor.py`, `editor.html`: C/C++/C#/HTML/CSS/XML/GDScript语言识别；编辑文档64个/16MiB缓存上限，保存文档模型淘汰与未保存内容保护。
- `tests/test_development.py`, `tests/test_development_ui.py`, `tools/verify_development.py`: 工厂/模式/生命周期/AI表单/真实原生缓存回滚、窗口交互及100例实际执行/条件边界报告。
- `tools/verify_development_artifacts.py`, `tools/verify_development_delivery.py`: 实际PYZ/入口编译代码、三个Runtime、全体示例数据一致性；冻结IDE四语言独立EXE/系统环境发布、公开模块/局部/线程实执行。
- 最终交付证据：`cache/logs/development-full-final-20261010.txt`（139通过/4跳过）、`development-examples-frozen-20261010.json`（100例）、`development-delivery-20261010.json`（四语言 standalone/system）、`development-promoted-artifact-20261010.json`（ok:true）和 `frozen-release.json`（ok:true）。
- `docs/规范/development.md`: 开发方式、静态CRT与系统环境发布、Unity/Godot交互、线程/AIUI、迭代流程与本轮官方参考。

- `src/pcide/main.py`: launch, `--smoke`, `--ui-smoke`, Qt IDE entry, and project build smoke.
- `src/pcide/core`: project/form/flow schemas, bounded child process runner, Windows pipe protocol, plugin registry, vision adapters, and incremental builder.
- `src/pcide/core/platform.py`: versioned capability contract for database/API/script/AI/game/compiler/runtime/agent providers.
- `src/pcide/core/product.py`: product subsystem catalog and capability resolution shared by IDE panels and child hosts.
- `src/pcide/core/agent.py`: provider-neutral AI coding-agent session, tool contract, approval gate, bounded plan and workspace guard.
- `src/pcide/core/agent_client.py`: OpenAI-compatible/DeepSeek tool-calls HTTP client with bounded payloads and responses.
- `src/pcide/core/agent_tools.py`: bounded project listing, search, read, write, patch and verification tools.
- `src/pcide/ui/agent_dialog.py`: project-scoped AI programming assistant UI with one-session credentials and explicit write approval.
- `src/pcide/core/compiler.py`: Chinese source lexer/parser/IR and Python runtime emitter.
- `src/pcide/core/database.py`: versioned database schema validation, SQLite creation and CRUD generation.
- `src/pcide/core/api_center.py`: HTTP API endpoint contract and client code generation.
- `src/pcide/core/ai_runtime.py`: model/provider/session contract for ONNX/OCR/detection pipelines.
- `src/pcide/core/game_sdk.py`: renderer-neutral scene/camera/entity contract.
- `src/pcide/core/unity.py`: Unity project detection, scene inspection, MonoBehaviour bridge generation, and explicit Assets sync.
- `src/pcide/core/agent_roles.py`: architect/code/UI/database/model/test Agent role catalog.
- `src/pcide/core/plugin_market.py`: offline plugin catalog validation and package hash gate.
- `src/pcide/ui/editor.py`: Monaco editor with a native Qt fallback for Windows environments where Chromium Mojo IPC cannot create its named pipe; routine metadata view zones are positioned after declarations with Yi-style visible collapse/expand controls, editable name/return/remark fields, public red check marks, and measured heights.
- `src/pcide/ui/editor.html`: Monaco 视图通过 `setHiddenAreas()` 隐藏导入与子程序声明行，仅保留子程序信息区和代码体；`.zhxb` 保持原文，不做错误的关键字投影。
- `src/pcide/ui/editor.html`: 主窗口加载处理器显示为可编辑的 `_启动程序` 标题，次级窗口保持自己的加载名称；普通子程序改名同步调用与事件，返回值为中文类型下拉框，公开为复选框，备注和局部变量表可编辑。
- `src/pcide/ui/editor.html`: 紧凑统一宽度的子程序声明行，三角置于名称左侧；真实声明号使用 marginDomNode；ResizeObserver 同时扩高/收高，临时元数据跟随源码身份；实际 Qt 鼠标键盘输入、增删、折叠、插行和切文件回归见 `editor-layout-monaco-final-20261010.txt`。
- `src/pcide/ui/routine_panel.py`, `native_edit.py`: 原生 Qt 子程序元数据表、当前子程序代码体、真实行号与保留模型的隐藏视图。
- `src/pcide/ui/routine_ranges.py`: 编辑时的子程序代码范围与首个代码位置，Python 使用 AST/未完成源码回退，Node 忽略字面量和注释中的括号；不改变 Runtime 扫描合同。
- `editor.html` / `editor.py` / `main.py`: 子程序收缩包含代码体，表格按源码身份复用，正文输入/换行不重建表格；控件双击和子程序导航进入代码体并自动展开。最新交付与证据见 verification 的“三项编辑器修复”。
- `editor.html` / `editor.py`: 显式启动处理器收缩时包含文件初始化及分隔空白；Monaco 全收缩保留不可见末行锚点，文档保持可编辑；输入先展开当前正文，点击同步 Qt/Monaco 焦点。实际截图仅剩连续名称行，32项双后端门禁及最新原路径冻结证据见 verification 的“收缩后残留启动代码”。
- `editor.html` / `routine_panel.py`: 公开列只保留复选框本身的一个勾选，去掉旁边重复`✔`；既有保存用例与实际截图通过，最新交付见verification“公开列单个勾选”。
- `src/pcide/core/routines.py`: 按文件/源码名称匹配稳定元数据身份、重新对齐源码位置、保留字符串与注释的标识符改名。
- `src/pcide/core/source.py`, `project_sources.py`: Python/中文源码共享 AST 编译入口、实际局部变量、返回/参数类型校验、共享数据与延迟公开调用。
- `src/pcide/core/source_contract.cjs`: Node 源码/Bytenode 共用的程序数据与函数局部变量生成合同。
- `src/pcide/core/modules.py`, `ui/module_dialog.py`: 模块精确版本、路径、公开接口、依赖校验和可编辑引用表。
- `src/pcide/core/libraries.py`, `ui/library_dialog.py`: PCIDE 核心/窗口支持库目录、调用格式/返回说明、实际语言示例，项目配置、四语言源码/DLL/封装包加入、权限授权、DEX配置；EC/FNE登记后待桥接。时钟/网页类型的当前实现限制在目录中列明。
- `src/pcide/core/routine_signatures.py`, `ui/parameter_dialog.py`: 真实源码参数的读取与改写，Python位置/关键字/可变参数，中文必填/默认值语义；与内部初始化的局部变量分区显示。
- `src/pcide/ui/data_panel.py`: 类别相关列、完整新增属性、所属范围与数组/静态设置、类型成员数组和实际DLL参数ABI表；中间删行后下拉框绑定正确条目。
- `src/pcide/main.py`: F1快捷键说明、Ctrl+Alt+P/V参数/局部入口、代码页关闭与项目关闭分键、当前文本/代码/设计撤销路由和设计局部快捷键。
- `src/pcide/core/dll.py`, `dll_host.py`: DLL 客户端与独立插件宿主，明确宽度 ABI、每调用超时、崩溃隔离和进程退出卸载；指针/文本返回/结构体/输出参数未开放。
- `src/pcide/core/processes.py`: Windows Job、有限日志、有限输入管道写入与工具进程超时/取消。
- `src/pcide/ui/control_icons.py`: 27 类控件专用代码绘制图标，分类菜单点击添加与文字/图标列表。
- `docs/规范/routine-runtime.md`: 当前子程序、作用域、模块、DLL、中文源码语法与参考官方资料。
- `docs/规范/libraries.md`: 加入入口、封装格式/示例、系统库/程序数据区别、参数与局部语义、快捷键表、易语言/.NET/Android官方参考和真实能力边界。
- `tests/test_libraries.py`, `tests/test_routine_signatures.py`: 四语言源码实际导入/调用/重载、独立插件/DLL执行、参考表回滚、参数必填/默认值/形式、中文局部重置和同名全局遮蔽。
- `tests/test_closeout.py`, `tools/measure_closeout.py`: 实际跨文件/模块/DLL/数据执行回归和四语言客户构建耗时测量。
- `docs/规范/platform.md`: platform capability/provider contract and lifecycle stages.
- `src/hosts`: isolated native/.NET/Android host sources; contracts are in `docs/规范`.
- `third_party/monaco`: reviewed Microsoft editor distribution used by the Qt WebEngine editor.
- `tests`: core, automation, DEX, Qt/Monaco, and frozen build gates; previous full run is `cache/logs/full-tests-release-20261010.txt` (84 total, 81 passed, 3 skipped). Latest library/parameter core gate has 40 total/39 passed/1 skip; Monaco UI has 39 total/38 passed/1 skip; native has 38 total/34 passed/4 skips plus 2 targeted cases passed. Exact commands and scope are in verification.
- `tools/freeze_runtime.py`, `tools/freeze_ide.py`: reproducible local runtime and IDE freezes; final logs are in `cache/logs`.
- `tools/freeze_ide.py --output-directory`: permits an independent staging location under build and checks write access to an existing EXE before cleaning runtime assets; workspace config is relative to the selected delivery directory.
- `tools/verify_release.py`: isolated final frozen IDE/customer/worker lifecycle gate; report is `cache/logs/frozen-release.json` and accepts the bounded native editor fallback when WebEngine cannot initialize.
- `tools/deliver_examples.py`: example customer EXEs and cache/build timing report in `cache/logs/delivery.json`.
- `src/pcide/core/archive_bundle.py`: standalone payload archive; high-density binary files stream without zlib compression and packaging policy is fingerprinted by `core/builder.py`.
- `cache/logs/closeout-build-timings-20261010.json`, `closeout-final-audit-20261010.json`: four-language first/incremental/unchanged timings, real standalone public calls, source-free customer payloads and current/prebuilt/bundled Runtime fingerprint agreement.
- `cache/logs/freeze-runtime-release-20261010.txt`, `freeze-ide-release-20261010.txt`: current freezes; delivery is `build/PCIDE/PCIDE.exe` with complete sibling `_internal`.
- Latest library/parameter delivery supersedes earlier editor freezes: `freeze-runtime-libraries-parameters-final-20261010.txt`, `freeze-ide-libraries-parameters-final-20261010.txt`, `libraries-parameters-promotion-20261010.json`. `libraries-parameters-artifact-20261010.json` compares actual embedded UI/core code and three Runtime profiles to source; `library-customers-20261010.json` binds four successful standalone customer probes to the delivered EXE SHA-256. Primary script/native/auto/Monaco reports use `libraries-parameters-primary-*`.
- `tools/verify_release.py`: release child tools use bounded output/Job/deadline; payload entry checking accepts Chinese `.pyc` as well as Python `.pyc` and Node `.jsc`.
- `cache/logs/verify-release-20261010-bounded-final.txt`, `frozen-release.json`: latest release gate exit 0 in 76.202 seconds, real OCR/CPU ONNX and frozen Python/C/.NET plugins, six reaped worker cases and removed isolated workspace. Process inventory `closeout-process-inventory-20261010.json` is empty; cleanup is recorded in `closeout-cleanup-20261010.json`.
- `architecture.md`: directory/data/entry chains and delivery boundaries.
- `archive/verification.md`: commands, exit status, artifact evidence and limitations.
- [PC Module Index](平台/pc.md)

- `tools/backup_source.ps1`: 源码备份脚本，提交 main、日期分支并推送 GitHub/Gitee；双端成功后清理专用备份包和缓存。
- docs/backup-policy.md: GitHub/Gitee 源码备份规则。
