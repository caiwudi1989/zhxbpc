# Verification Evidence

## 2026-10-11 子程序不能输入与 Ctrl 快捷键回归（最新交付）

- 直接证据：用户运行的旧 EXE/HelloAutomation 窗口出现 `Cannot edit in read-only editor`；对应用户截图为前三个子程序收缩、Button2 展开。根因是源码收缩把全编辑器设只读，旧验证要求全收缩时禁止输入；这不等于可用的正文编辑。另有正文隐藏 textarea 被误认 HTML 输入框的撤销路由、Qt/Monaco 焦点未同步。修复后收缩只影响显示，点击正文/恢复代码页同步焦点，完全收缩时输入先展开可见正文；native 使用同一合同并补真正查找替换。
- 环境：`runtime/dev/Scripts/python.exe -B`，`PYTHONUTF8=1`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONPATH=F:\PC端软件\src`；Monaco/冻结 UI 使用正常 Windows token，native 门禁用 `PCIDE_EDITOR_BACKEND=native` 和 `QT_QPA_PLATFORM=offscreen`。所有输入只在 cache 工程副本，验证前后比较用户 HelloAutomation 全部文件摘要。

| 命令/门禁 | 最终结果 | 证据（cache/logs） |
| --- | --- | --- |
| `-m unittest tests.test_editor_input` + 5项既有折叠/输入/布局/控件导航/快捷键，Monaco | exit0；7项全部通过；15.156秒 | `editor-input-monaco-final-20261011.txt` |
| 同组 native offscreen | exit0；7项为6通过/1 Monaco几何用例跳过；4.684秒 | `editor-input-native-final-20261011.txt` |
| `cache/verify_editor_input_delivery_20261011.py source` | exit0、ok:true；实际默认工程4子程序逐个展开/点入/输入；九组 Ctrl 操作、中文提交和磁盘保存/重开通过 | `editor-input-source-ui-20261011.json`、`editor-input-source-keyboard-20261011.json/png` |
| `tools/freeze_ide.py --output-directory build/editor-input-staging-20261011` | 最终 exit0；完整独立目录，包含最终输入探针与 main 入口 | `editor-input-freeze-ide-20261011.txt`、`cache/build/ide/freeze.log` |
| `tools/verify_development_artifacts.py <EXE> --report <报告>`，staging/原路径 | 均 exit0、ok:true；入口、训练worker、74编译模块/483资源及三套 Runtime 实际编译代码、指纹、启动器、EXE一致 | `editor-input-{staging,primary}-artifact-20261011.json` |
| `cache/verify_editor_input_delivery_20261011.py staging/primary --exe <EXE>` | 两路径均 exit0、ok:true；冻结 EXE 实际4子程序输入/九组 Ctrl 操作/保存重开；另3种工程 Monaco 启动通过，原文、共享输出、帮助、冻结资源路径正确 | `editor-input-{staging,primary}-ui-20261011.json` 与对应 keyboard/cpp/zhxb/python JSON/PNG/TXT |
| `cache/promote_editor_input_20261011.py` | exit0、ok:true；新 EXE 摘要绑定审计/输入门禁，检查 build 内绝对路径和旧 EXE 写权限，保留旧目录后提升；配置工作区 `..\..`，失败分支含回退 | `editor-input-promotion-20261011.json` |

- 5个既有 unittest 目标（`tests.test_ui.UiTests.` 前缀）：`test_startup_collapse_owns_file_initialization_and_separators`、`test_typing_and_newlines_preserve_routine_widgets`、`test_routine_layout_is_compact_resizes_and_preserves_edits`、`test_control_double_click_enters_expanded_routine_body`、`test_shortcuts_have_no_collisions_and_switch_view_without_closing_project`。新输入组确认 marker 属于当前子程序并实际验证 Ctrl+A/C/X/V/Z/Y/S/F/H；Ctrl+F 检查真实选中，Ctrl+H 点击全部替换并校验源码。Monaco 自然按单词/空格建立撤销组，逐组撤销/重做，不要求一键删除全部连续键入。剪贴板原 MIME 数据在测试结束恢复；空剪贴板恢复为空。
- 诊断与失败未冒充通过：隐藏代码页等待 WebEngine 初始化导致进程阻塞，测试改为先显示代码页；输入探针在 JavaScript 回调内请求下一结果会阻塞，改为回调返回后由 QTimer 执行。查找面板动画中的负坐标导致测试点击失败，等待250ms完成动画后实际点入；native查找关闭后恢复主窗口/正文焦点。native offscreen 恢复空 MIME 曾在解释器退出时崩溃，改为清空；正常 Windows Qt6Core 曾有一次0xc0000409退出，最终源码和两路径冻结门禁均完整 exit0，未把早期失败记录算作成功。
- 交付：`build/PCIDE/PCIDE.exe` + 同级 `_internal`，SHA-256 `43f8dd535c8c0865da193c41691f77f554a907ffdcb977017f99bd98c063934b`；旧版 `2cb2adfa016ae3bdd36d915b65853a47761c079f13de41b8160a73f9f4491c33` 保留在 `build/editor-input-previous-20261011`。本轮变更在 UI/main，Runtime 指纹清单内源码没有变化，三个既有 Runtime 沿用并实际审计一致。
- 桌面 Computer Use 因用户 Esc 停止后没有再次调用；之后使用被测程序内的 Qt 鼠标/键盘事件及 QInputMethodEvent 中文 commit 实测，截图实际显示字母/数字/中文，不代表 Windows 输入法候选窗口专项验收。本轮没有重跑历史全量、独立客户 EXE、硬件/Android/生产 OCR/YOLO、签名或干净机器；未修改用户工程、D盘，未创建子代理，未提交/推送。

## 2026-10-10 页面继续复核：提示、菜单、排列与预览（此前交付）

- 延续用户要求检查所有页面、加入遗漏并合并/删减；本轮增加操作提示页，主页面共14个，页面和配套对话框清单见 `docs/规范/pages.md`。新增真实菜单层级/事件编辑、完整排列、容器父级坐标、未保存预览、回车导航和输出清空/导出；MenuBar属性的普通items输入合并为专用菜单编辑器，菜单/控件事件共用源码定位与创建入口，排列右键共用主菜单动作。
- 环境：`runtime/dev/Scripts/python.exe -B`，`PYTHONUTF8=1`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONPATH=F:\PC端软件\src`。native 使用 `PCIDE_EDITOR_BACKEND=native`，Monaco与冻结UI使用正常Windows令牌。临时工程和截图在cache；构建、冻结启动和脚本检查由有界子进程管理。

| 命令/门禁 | 实际结果 | 证据（cache/logs） |
| --- | --- | --- |
| native：`-m unittest tests.test_page_followup tests.test_page_contents tests.test_contracts tests.test_development_ui -v` | exit0；57项，56通过/1符号链接环境跳过，26.611秒；该次有Qt槽旧选择ID异常打印，之后修复，未当作最终无异常证据 | `pages-followup-native-20261010.txt` |
| native：`tests.test_page_followup` + 6项既有窗口/编辑回归 | exit0；15项全部通过，10.033秒；旧选择异常修正后 | `pages-followup-native-final-20261010.txt` |
| 正常Windows Monaco：相同15项 | exit0；15项全部通过，19.496秒 | `pages-followup-monaco-20261010.txt` |
| 最后排列对象生命周期修正后：`tests.test_page_followup.PageFollowupUiTests.test_arrangement_spacing_order_undo_and_saved_geometry`，native | exit0；1项通过，1.497秒；实际访问排列QMenu动作并检查几何、顺序、撤销和保存 | `pages-followup-arrangement-final-20261010.txt` |
| `cache/capture_pages_followup_20261010.py`，正常Windows Monaco | exit0、ok:true、monaco:true；设计/提示、菜单编辑、运行窗口、运行菜单、排列菜单5份实际截图完成并目视检查；排列菜单无释放报错 | `pages-followup-capture-20261010.txt`、`pages-followup-captures-20261010/capture.json`及PNG |
| `tools/freeze_runtime.py --profile all` | exit0；basic/vision/node三套重建完成 | `pages-followup-freeze-runtime-20261010.txt` |
| `tools/freeze_ide.py --output-directory build/pages-followup-staging-20261010` | exit0；完整独立冻结目录 | `pages-followup-freeze-ide-20261010.txt` |
| `tools/verify_development_artifacts.py <EXE> --report <报告>`，staging和原路径 | 均exit0、ok:true；入口、训练worker、73编译模块、483资源、3套Runtime清单/实际编译模块/启动器/EXE一致 | `pages-followup-{staging,primary}-artifact-20261010.json` |
| `cache/verify_pages_followup_delivery_20261010.py <EXE> staging/primary` | 两路径均exit0、ok:true；各实际启动C++、中文窗口、Python脚本、菜单窗口4份MonacoUI和1份脚本smoke；14页模式/可见性、提示、共享日志、帮助、冻结资源路径、C++原文及工程源码不变通过 | `pages-followup-{staging,primary}-ui-20261010.json`、对应各工程JSON/PNG/TXT |
| `cache/promote_pages_followup_20261010.py` | exit0、ok:true；校验staging审计与4工程UI摘要、EXE写权限和build内绝对路径，保留旧目录后提升完整目录；配置工作区为`..\..`，失败分支有回退 | `pages-followup-promotion-20261010.json` |

- 15项组的6个既有目标是 `tests.test_ui.UiTests` 下的 `test_designer_drop_move_resize_copy_undo_roundtrip`、`test_real_click_updates_runtime_control`、`test_runtime_window_constraints_and_lifecycle`、`test_runtime_form_window_resize_and_close_events`、`test_control_double_click_enters_expanded_routine_body`、`test_monaco_edit_save_models_navigation`；本轮新合同/页面共9项。整组通过后，实际截图仍发现排列子菜单包装已释放，最终使用显式 `QMenu("排列", edit_menu)` 并保存父对象；该最后UI改动通过定向测试、Monaco截图及最终编译审计，没有声称其后重跑全部15项。
- 菜单编辑保存真实树值，取消保留原定义；事件按钮写入真实源码并保存。运行菜单检查嵌套、分隔、勾选、处理器和动态替换，单纯预览验证不调用runner事件；F5/F4预览分发单次菜单事件。容器复制/脱离和排列保存回磁盘，断点/调用表通过真实Qt回车跳转，外部路径被拒绝；输出导出检查单条共享日志只出现一次。
- 三套Runtime在核心菜单和form_runtime稳定后重建，最后的排列QMenu修正只涉及main，不改变Runtime输入。审计逐项比较实际嵌入的编译代码，包含新增menus模块；没有用仅指纹相等代替实际代码核对。冻结UI probe保留实际源码语言，使用独立case字段区分普通Python脚本和Python菜单窗口。
- 原路径交付：`F:\PC端软件\build\PCIDE\PCIDE.exe`和完整同级`_internal`；最终SHA-256 `2cb2adfa016ae3bdd36d915b65853a47761c079f13de41b8160a73f9f4491c33`。原版本SHA-256 `dacdc0f7a297896ed9700a0f0ff6ea06509de3f28cc640c2d5bca37d63448809`保留在`build/pages-followup-previous-20261010`。staging与原路径最终报告均绑定该新摘要，提升未触发回退。
- 10月11日收尾检查：按Windows CRLF配置执行 `git diff --check`，exit0；新菜单/测试/帮助文件无行尾空白。最终EXE、旧目录摘要、相对工作区和两份内置帮助逐项复查一致；正常Windows只读进程检查中build与prebuilt路径进程数为0。证据 `pages-followup-diff-check-20261010.txt`、`pages-followup-process-state-20261010.json`与`pages-followup-final-state-20261010.json`。
- 未宣称完整易语言/EC/FNE二进制兼容、Timer/WebView实现、运行中调试写入/实时断点、非HTTP transport或生产设备能力。本轮未重跑历史全量、客户EXE发布、生产OCR/YOLO、Android/硬件/引擎/GPU/签名/干净机器部署；5份截图证明本轮界面与布局。未创建子代理、未修改D盘、未提交/推送。

## 2026-10-10 页面内容逐项补齐与合并（此前交付）

- 用户要求继续核对各页、补加入内容并合并/删减。按工程规则和易语言官方操作手册的工作夹/状态夹/设计编辑组织方式检查；完整清单、处理与边界见 `docs/规范/pages.md`，该文档随 EXE 分发。
- 环境：`runtime/dev/Scripts/python.exe -B`，`PYTHONUTF8=1`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONPATH=F:\PC端软件\src`；native 组设置 `PCIDE_EDITOR_BACKEND=native`，Monaco 与冻结 UI 在正常 Windows 桌面令牌运行。子工具统一 `run_bounded` 有超时、有限日志和进程树回收。

| 命令/门禁 | 实际结果 | 证据（cache/logs） |
| --- | --- | --- |
| `-m unittest tests.test_page_contents tests.test_development_ui tests.test_ui tests.test_editor tests.test_contracts -v`，较广 native | exit 0；88 项，83通过/5条件跳过；38.876秒。随后还修正入口导航/断点切文件，并补新用例 | `pages-review-native-20261010.txt` |
| `-m unittest tests.test_page_contents tests.test_page_generators tests.test_contracts -v`，最终 native | exit 0；38 项，37通过/1符号链接环境跳过；13.027秒 | `pages-review-final-native-20261010.txt` |
| native：新增 Python/Node 异步导航 + 既有四语言代码范围/启动收缩 | exit 0；4项全部通过；3.279秒；真实声明行号、跳转正文、自己的文件、关闭后恢复、入口去重和源码不变均检查 | `pages-review-navigation-native-20261010.txt` |
| Monaco：20 页面 + 3 生成合同 + C++ 编辑/中文库 + 控件双击/编辑保存/TS 诊断 + 四语言代码范围/启动收缩 | exit 0；30项全部通过；40.635秒，含异步/导出导航及注释/字符串排除 | `pages-review-final-monaco-20261010.txt` |
| 最终 API：生成合同3项 + 引号路径实际 Python 调用 + 源码保护/原生只保存定义 | exit 0；5项全部通过 | `pages-review-api-final-20261010.txt` |
| 真实 UI 页面截图：代码、设计/属性/事件/组件树、目录/帮助、流程、断点、数据、资源、视觉、欢迎、所有设计/配置/参数/示例对话框及 JSON/预览、C++ | 30份截图完成并目视检查，Monaco；入口源码未改变；最终 API 预览单个共享导入 | `pages-review-captures-20261010/capture.json`、对应PNG；`pages-review-capture-monaco-final-20261010.txt` |
| `tools/freeze_ide.py --output-directory build/pages-review-staging-20261010` | exit 0；独立完整目录，新页面说明打包 | `pages-review-freeze-final-20261010.txt` |
| `tools/verify_development_artifacts.py <EXE> --report <报告>`，staging/原路径 | 均exit 0、ok:true；入口、71编译模块、483资源、三个既有Runtime的指纹/实际编译代码/启动器及EXE一致 | `pages-review-{staging,primary}-artifact-20261010.json` |
| `cache/verify_pages_delivery_20261010.py <EXE> staging/primary` | 两路径均exit 0、ok:true；各实际启动C++、中文窗口、Python脚本三份Monaco和一份脚本smoke；页面适用性/可见性、共享输出、帮助资源、原文、退出/流程和源码不变均通过 | `pages-review-{staging,primary}-ui-20261010.json`、`pages-review-{staging,primary}-*-monaco-20261010.json/png` |

- Monaco 完整目标：`tests.test_page_contents`、`tests.test_page_generators`、`tests.test_development_ui.DevelopmentUiTests.test_cpp_view_edits_and_saves_original_language_without_keyword_projection`、`test_zhxb_project_shows_yi_style_library_categories_and_types`，以及 `tests.test_ui.UiTests.test_control_double_click_enters_expanded_routine_body`、`test_monaco_edit_save_models_navigation`、`test_monaco_typescript_worker_diagnostics`、`test_routine_code_ranges_in_all_editor_languages`、`test_startup_collapse_owns_file_initialization_and_separators`。native导航组为页面类的 `test_python_async_routines_are_complete_and_exclude_nested_or_literal_declarations`、`test_node_exported_and_async_routines_are_complete_in_entry_and_other_files` 加上述两个范围/启动收缩用例。最终 API 组为 `tests.test_page_generators` 和 `tests.test_page_contents.PageContentsUiTests` 的两个 API 保存/保护用例。
- 实执行证明：生成 CRUD 在 SQLite 内存库执行读写，默认值/索引保存；Python 客户端的真实调用参数经网络请求替身验证（不代表真实外部服务）；Node 执行实际生成 JS 与 TypeScript 转译产物，调用返回值/引号路径/配置超时取消均检查（fetch替身，不是生产网络）。第二个文件故障注入证明定义回滚。资源/标注/窗口宽高/流程保存后重新读取磁盘，流程由 FlowRunner 实际运行。
- 发现并修复：原生 `QPlainTextEdit.ExtraSelection` 不存在，改用真实 QTextEdit 类型；入口和其他文件导航恢复/去重；Monaco中文事件测试等待异步保存时使用缺省值，避免尚未写入的键产生测试误报；测试临时目录复用既有 WorkspaceCase，解决本机 restricted-token 的0700 DACL问题。截图 harness 先显示代码页再等 Monaco，冻结 ui-smoke 同步处理，避免隐藏 WebEngine 页初始化等待。首次失败/超时记录未冒充成功。
- 目录提升：先校验 staging 审计/启动证据和当前 EXE 摘要，再保存旧目录并提升完整 `_internal`，配置为 `..\..`，失败路径有回退。第一次提升后预览检查发现生成 API 重复导入，已合并并独立重建；最终两个路径门禁重新绑定最终 EXE。最初旧版 `5a59206eb6f09affda0b263035631f7b305a821f66a53180990cd3228d389d90` 保留在 `build/pages-review-previous-20261010`；第一次本轮构建的临时回退及空 staging 在最终门禁后已清理（pages-review-cleanup-20261010.json）；原版本回退保留，提升证据 `pages-review-promotion-initial-20261010.json` 与 `pages-review-promotion-20261010.json`。
- 最终检查另发现入口旧正则漏掉 Python async 和 JS/TS export/async，其他文件的 Runtime 扫描也漏 Node async；两处改用 `ui/routine_ranges.scan_editor`，UI 扫描补异步声明并屏蔽注释/字符串。入口独立列表/文件下节点的完整性、真实行号、正文跳转、代码页恢复、文件返回、去重和源码不变在 native/Monaco 实测。此项修改之后重新冻结、审计并复验两路径，原提升记录保留为 `pages-review-promotion-before-navigation-20261010.json`；修复前 EXE `1dc324396915cc6abfbff3bc04609f0e47353d7358ff3eff63193dd8a0177cb9` 保留于 `build/pages-review-before-navigation-20261010`。
- 当前交付：`build/PCIDE/PCIDE.exe` + 完整同级 `_internal`，SHA-256 `dacdc0f7a297896ed9700a0f0ff6ea06509de3f28cc640c2d5bca37d63448809`。本轮没有修改 Runtime 指纹清单成员的源码，三套 Runtime 沿用且通过实际代码一致性审计。
- 本轮不宣称全部易语言内容、EC/FNE ABI、时钟定时/WebView浏览、调试变量写入/实时断点、非HTTP transport、响应声明强制解析、其他数据库/完整ORM；页内/帮助明示。未重跑历史全量、独立客户EXE发布、真实OCR/YOLO生产效果、Android/硬件/GPU/外部引擎/签名/另一台干净Windows；未提交/备份/推送源码。人工截图的标注样图只证明界面和标签文件操作。

## 2026-10-10 支持库目录与非脚本源码显示修复（上轮交付）

- 截图根因：C++ 工厂模式项目的六个线程/资源管理/Win32 片段被列为支持库命令，Monaco 还把 `const/return` 错投影为中文。已分离支持库与代码片段，加入类别/类型/常量及组件属性/事件/方法，显示条目完整帮助；中文关键字投影仅对 Python 生效，非脚本源码原样显示和保存。
- 测试环境：`runtime/dev/Scripts/python.exe -B`，`PYTHONUTF8=1`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONPATH=F:\PC端软件\src`；native 组设置 `PCIDE_EDITOR_BACKEND=native`。Monaco 定向组和冻结 UI 在正常 Windows 令牌下运行。

| 命令/定向组 | 结果 | 证据（`cache/logs/`） |
| --- | --- | --- |
| `-m unittest tests.test_libraries -v` | exit 0；11 项通过，7.209 秒 | `support-catalog-core-20261010.txt` |
| `-m unittest tests.test_development_ui tests.test_ui.UiTests.test_support_catalog_configuration_search_and_source_admission tests.test_editor -v`，native | exit 0；18 项通过，9.065 秒 | `support-catalog-native-20261010.txt` |
| Monaco：C++ 显示/捕获/编辑/保存，中文支持库目录，欢迎页原生工程，支持库配置/搜索/加入 | exit 0；4 项通过，5.891 秒 | `support-catalog-monaco-20261010.txt` |
| `-m unittest tests.test_ui.UiTests.test_editor_python_projection_regex_is_unicode_safe tests.test_ui.UiTests.test_editor_routine_zone_is_after_declaration -v` | exit 0；2 项通过，1.164 秒 | `support-catalog-editor-contract-20261010.txt` |

- Monaco 四个完整 unittest 目标：`tests.test_development_ui.DevelopmentUiTests.test_cpp_view_edits_and_saves_original_language_without_keyword_projection`、`tests.test_development_ui.DevelopmentUiTests.test_zhxb_project_shows_yi_style_library_categories_and_types`、`tests.test_development_ui.DevelopmentUiTests.test_welcome_creates_native_project_and_switches_editor_mode`、`tests.test_ui.UiTests.test_support_catalog_configuration_search_and_source_admission`。使用上述 Python 与 `-m unittest ... -v` 运行。
- 核心目录测试实际编译全部可插入的中文源码示例，执行平方根、位运算、文件写读、SQLite 连接/执行/关闭、任务池结果 4950 与窗口代理；新增类型只包含现有窗口/控件，时钟/WebView 的实现限制在帮助中注明。既有模块、DLL、封装插件、权限、EC/FNE 登记和路径合同仍通过。
- 独立冻结：`tools/freeze_ide.py --output-directory build/support-catalog-staging-20261010`，exit 0，日志 `support-catalog-freeze-20261010.txt`。新增随 IDE 打包的 `docs/规范/libraries.md` 纳入资源一致性审计。
- staging 审计：`tools/verify_development_artifacts.py build/support-catalog-staging-20261010/PCIDE/PCIDE.exe --report cache/logs/support-catalog-staging-artifact-20261010.json`，exit 0、`ok:true`，69 编译模块/482 资源/三套 Runtime 一致。staging C++ native 与中文 Monaco UI smoke 均通过，报告和截图为 `support-catalog-staging-{cpp-native,zhxb-monaco}-20261010.*`。
- 交付提升：用户确认已保存并关闭占用 EXE 的旧窗口后，`cache/promote_support_catalog_20261010.py` exit 0；先校验 staging 审计和 EXE 摘要，再保留旧目录并提升完整新目录，失败路径包含回退。工作区配置改为 `..\..`。报告 `support-catalog-promotion-20261010.json` 为 `ok:true`；旧版保留在 `build/support-catalog-previous-20261010`，旧 EXE 摘要 `ba2e0c2e9979800da554f115b3eee32c5ea76662858a81d1643b0569bfe4ee94`。
- 当前交付：`build/PCIDE/PCIDE.exe`，SHA-256 `5a59206eb6f09affda0b263035631f7b305a821f66a53180990cd3228d389d90`，完整同级 `_internal`。原路径 `tools/verify_development_artifacts.py build/PCIDE/PCIDE.exe --report cache/logs/support-catalog-primary-artifact-20261010.json` exit 0、`ok:true`，入口/69 编译模块/482 资源/三套 Runtime 一致。本轮 Runtime 清单内核心代码未变化，无须重建 Runtime。
- 原路径 UI：`cache/verify_support_catalog_primary_20261010.py` 通过 `run_bounded` 启动两次 `PCIDE.exe --ui-smoke --editor monaco --project <工程> --report <报告> --screenshot <截图>`，单次超时 30 秒、有界日志和进程清理。C++ 工程为 `projects/Example_native_factory`，中文工程为 `cache/support-catalog-preview-20261010/projects/ChineseLibrary`；两次实际退出 0，`qt/frozen/monaco/editor_ready:true`，资源来自原路径 `_internal`。C++ 源码显示逐字一致、中文视图禁用、片段类别独立；中文工程显示核心/窗口库目录、无开发片段。报告与截图 `support-catalog-primary-{cpp,zhxb}-monaco-20261010.*` 已读取和目视检查，工程源码摘要均未变化，汇总 `support-catalog-primary-ui-20261010.json` 为 `ok:true`。
- 范围：这是 PCIDE 实现的易语言式目录和实际 API 子集。EC/FNE 专用 ABI/官方编译桥接未实现；此前全量、独立客户 EXE、生产视觉、Android、硬件和干净机器验收未在本轮重跑。以下记录保留各自原有范围。

## 2026-10-10 通用开发与游戏工程最终交付

- 交付：`build/PCIDE/PCIDE.exe`（当前 SHA-256 `ba2e0c2e9979800da554f115b3eee32c5ea76662858a81d1643b0569bfe4ee94`）与完整同级 `_internal`；迭代审计为 `cache/logs/development-iteration-artifact-20261010.json`，最终发布门禁为 `cache/logs/frozen-release.json`，上一版交付保留在 `build/development-previous-iteration-20261010`。
- 入口与工厂：`development.py` 19种模板覆盖四种脚本及窗口、C/C++/Win32/CMake、C#/WinForms、网页/Canvas、Unity/Godot 2D/3D；`BuildService` 提供10类发布目标、并行上限、取消、增量缓存、编译期间输入一致性和失败回滚。`toolchains.py` 的工作区默认工具路径可复用，未下载任何环境。
- 引擎：Unity/Godot已有工程绑定已接到统一工厂与外部 `ToolSession`；Unity命令包含项目路径、日志、批处理、构建方法和受控 Job worker 数量，Godot包含 headless Windows Desktop 导出。外部工程文件未被接入流程覆盖；本机未配置 Unity/Godot/CMake，因此没有伪称引擎运行成功。
- 交互：欢迎页、编译/静态编译页、工具/引擎页、100例中心、AI结构化 UI 写入、支持库右键说明/例子/双击/拖放、原生/C#控制台实时输出和输入栏均已接入。关闭项目后欢迎页仍可新建/打开；切换/退出会停止外部工具并清空输入引用。
- 线程与资源：`tasks.py` 每宿主最多4池、每池最多4线程/64任务；控制台输入每次最多4096字符、队列16条；ChildLog有界1MiB且按UTF-8增量解码；临时目录、SQLite游标、HTTP响应、任务函数引用和外部进程在出口清理。
- 系统环境：JavaScript/TypeScript发布在构建阶段完成转换及元数据/公开接口准备，交付不带 TypeScript SDK；Python/中文/Node 系统环境目录没有解释器、DLL或SDK。标准库动态导入清单位于 `builder.STANDARD_LIBRARY_IMPORTS`，参与 Runtime 指纹。
- 真实证据：`cache/logs/development-full-final-20261010.txt` 为 139 项通过、4 项环境跳过；`development-ui-monaco-final-20261010.txt` 为49项通过、1项跳过；`development-examples-frozen-20261010.json` 的100例 `ok:true`；`development-delivery-20261010.json` 的四语言 standalone/system 客户验证 `ok:true`；`development-promoted-artifact-20261010.json` 的入口/69核心模块/481资源/三套Runtime审计 `ok:true`；`frozen-release.json` 的最终发布门禁 `ok:true`，包含真实 OCR/CPU ONNX、Python/C/.NET 插件和 worker 超时/取消/断开/崩溃回收。
- 限制：脚本独立 EXE 携带运行时，不能等同 C/C++ 静态机器码；静态 CRT 仍依赖 Windows 系统 DLL；.NET AOT/Unity/Godot/CMake 仍要求目标工具已安装；Android ART/真机、串口/HID、GPU训练、代码签名、恶意代码 OS 沙箱和另一台干净 Windows 未验收。

## 2026-10-10 支持库、数据表、参数与快捷键最终交付

本节是当前交付记录，优先于下方历史冻结记录。本轮修正真实源码参数/中文默认值语义，增加支持库加入与调用、数据表操作和快捷键路由，保留此前代码体收缩、输入稳定、双击正文定位和单勾选修复。

### 实现与源码验证

- `core/libraries.py` / `ui/library_dialog.py`：系统核心23项真实表达式/命令及窗口API，按命令分类、库类型、库常量显示；项目数据独立在程序夹。加入/配置/搜索/帮助、四语言源码公开接口、DLL ABI参数表、封装包与权限、DEX配置和调用示例均有实际入口。EC/FNE保存后明确显示待桥接；裸PYD要求清单包装。插件/DLL代码由独立宿主执行，worker提供有界 `plugins.call` 并finally关闭宿主；不会在IDE中加载第三方代码。
- `data_panel.py`：按类别显示相关列、完整新增属性、中文类型/所属范围/数组/静态、类型成员数组、实际DLL参数表。删中间行后组合框绑定条目身份。`routine_signatures.py` / `parameter_dialog.py`：参数保存回真实源码，参数与局部初始化分离；保留Python参数形式，中文无默认值为必填，编译器版本4使旧缓存失效。F1提供快捷键，代码页/项目关闭分键，设计快捷键和撤销按焦点范围工作。
- `runtime/dev/Scripts/python.exe -B -m unittest tests.test_routine_signatures tests.test_libraries tests.test_contracts tests.test_closeout -v`：exit0，40项，39通过/1环境跳过，13.620秒；日志 `cache/logs/library-parameters-core-final-20261010.txt`。覆盖四语言源码导入/调用/编辑重载、真实DLL/封装插件执行、权限与回滚、必填/default/keyword/可变参数、中文显式局部重置、同名全局遮蔽及原有执行/生命周期合同。
- 正常Windows会话 `cache/release-probes/editor_interaction_gate_20261010.py monaco tests.test_ui`，标签 `library-parameters-monaco-final`：exit0，39项，38通过/1native专属跳过，65.208秒；日志 `editor-interaction-library-parameters-monaco-final-20261010.progress.txt`。65秒faulthandler输出诊断栈，随后完成OK，未误报失败或忽略未完成测试。新增支持库配置/加入/搜索、完整数据新增/成员数组、参数源码保存、真实Ctrl+E和快捷键无冲突/DLL参数表用例；原有真实键盘输入零表格替换、折叠/展开、双击正文位置和勾选保存继续通过。
- native同组在DLL表用例加入前为38项，34通过/4Monaco专属跳过，15.918秒；日志 `editor-interaction-library-parameters-native-final-20261010.progress.txt`。随后定向DLL参数表和参数源码保存2项均通过，1.279秒；日志 `editor-interaction-dll-parameter-table-20261010.progress.txt`。没有把两组重复签名用例相加为新的完整39项原生门禁。
- 真实源码Qt截图 `library-parameters-{editor,data,import,signature}-20261010.png` 已查看，参数/局部两区、一个勾、支持库完整命令名和中文按钮确认。门禁后仅修正模块导入保留引用表未保存编辑和帮助文字，最终重新冻结包含这两个UI改动；未改变最终核心/Runtime输入。

### 冻结、一致性与独立客户EXE

- `tools/freeze_runtime.py --profile all`：最终三套完整刷新成功，日志 `freeze-runtime-libraries-parameters-final-20261010.txt`。`tools/freeze_ide.py --output-directory build/library-parameters-staging`：exit0，日志 `freeze-ide-libraries-parameters-final-20261010.txt`。staging script/native/受限auto/正常桌面Monaco smoke均exit0，UI为editor_ready:true。
- `cache/release-probes/library_parameters_artifact_gate_20261010.py audit`：核对HTML/main、8个UI模块、8个核心模块的实际编译代码；三个Runtime的源码/prebuilt/IDE内置指纹一致，并核对Runtime PYZ中6个实际核心模块，`runtime_compiled_matches:true`。staging报告 `libraries-parameters-staging-artifact-20261010.json`、原路径报告 `libraries-parameters-artifact-20261010.json` 均ok:true，防止只更新指纹但Runtime仍含旧代码。
- 正常Windows会话 `cache/release-probes/verify_libraries_20261010.py`：exit0，`library-customers-20261010.json` 为ok:true并绑定当前IDE的SHA-256。四语言先用冻结IDE实际构建，再运行真正单文件客户EXE；全部exit0并输出42。中文模块使用默认参数40和显式局部increment=2；Python另执行真实封装JSON宿主输出LIBRARY_HOST_OK、真实DLL导出pcide_init返回0及ui.set消息。封装宿主是测试库，不冒充生产视觉能力。
- 客户验证配置 `PCIDE_PYTHON` 为不存在路径、`PYTHONPATH` 为空，移除外部Node/TypeScript/.NET路径覆盖；IDE资源确认为其内置_internal。客户归档载荷文件数Python11、中文7、JS6、TS6，扫描无项目源码/SDK。工作区 `cache/library-release/20261010-150701` 保留。此前受限token `_MEI`父目录ACL失败不算通过；本轮最终在正常token完成，本机隔离验证不等同另一台干净Windows。

### 原路径提升与能力边界

- `cache/release-probes/promote_libraries_parameters_20261010.py`：exit0。核对staging审计/客户摘要/四种smoke，检查build内绝对目标和重解析点及两EXE写权限后，将完整旧目录移动到 `build/libraries-parameters-previous-20261010`，将完整新版提升 `build/PCIDE`，相对workspace恢复为 `..\\..`；失败可回退，不删除旧交付。记录 `libraries-parameters-promotion-20261010.json`。
- 原路径 `build/PCIDE/PCIDE.exe` 的script/native/受限auto/正常桌面Monaco smoke全部exit0；报告 `libraries-parameters-primary-{script,native,auto,monaco}-20261010.json`。正常桌面为monaco:true/editor_ready:true；冻结截图已查看。脚本smoke中的OCR/YOLO是模拟示例，本轮未把它作为生产识别验收。
- 最终完整交付 `F:\PC端软件\build\PCIDE\PCIDE.exe` 和同级完整 `_internal`。EXE SHA-256 `7cbf56abba6212e282be8c5e3cb90919469e99eac3a9249bec11c34889bfea74`；HTML SHA-256 `e0a9617a8dc008f467adc6274d2ea3b77a79fceec6d1ea093d871534dae91223`。
- `docs/规范/libraries.md`记录入口/格式/真实封装例子/参数与局部/快捷键及官方参考。EC尚无编译器，FNE尚无专用ABI宿主；需用官方工具编译或供应方协议桥接，登记不代表执行。DEX须部署到Android并提供ART宿主，真机未验收。Node插件/DLL代理、静态局部和精确版本模块表，以及高级DLL ABI仍未开放；参数改名须同步正文和调用处。
- 本轮未重跑此前84项全量、真实OCR/ONNX发布、硬件、GPU、签名或另一台干净机器；旧证据保持其原范围。未访问D盘，未提交/备份/推送；此前被自动审批拒绝删除的回退和探针缓存均保留。受限会话CIM读取失败后，在正常Windows token完成只读进程复查，项目相关进程清单为空；未把访问失败当作无进程。最终进程/保留状态记录 `libraries-parameters-final-state-20261010.json`，换行配置下 `git diff --check` 证据 `libraries-parameters-diff-check-20261010.txt`。

## 2026-10-10 公开列单个勾选

- 用户截图中的双勾来自复选框自带勾选与旁边额外span。`editor.html`删除`routine-public-mark/publicMark`，保留红色复选框及原保存回调；`routine_panel.py`把“公开 ✔”恢复为“公开”。
- 复用`test_routine_public_name_return_and_remark_are_editable`（Monaco，1项，1.714秒）和`test_native_routine_edit_save_local_scope_and_ordinary_rename`（native，1项，0.893秒），均通过；日志`editor-interaction-public-single-check-{monaco,native}-20261010.progress.txt`。未为这个低影响显示修改新增测试，也未冒称重跑此前整组32项门禁。
- 真实源码宿主截图`editor-public-single-check-collapsed-20261010.png`已目视核对四行公开列均只有一个勾；`editor-public-single-check-capture-20261010.json`同时确认完整源码与收缩视图保持一致。
- 独立冻结`build/editor-public-single-check-staging`成功；日志`freeze-ide-editor-public-single-check-20261010.txt`。staging脚本、native、受限auto、正常桌面Monaco smoke报告均成功。确认旧IDE已退出且EXE可写后提升`build/PCIDE`，保留上版`build/editor-public-single-check-previous-20261010`；记录`editor-public-single-check-promotion-20261010.json`。
- 原路径启动及编译代码核对证据`editor-public-single-check-primary-{script,native,auto,monaco}-20261010.json` / `editor-public-single-check-artifact-20261010.json`。源码/冻结HTML与main、四个UI模块一致，三个Runtime指纹一致。EXE SHA-256 `7af7a78c96c613211aacfb78b413c146b8a384d9376f4a80ff06c3aaaee0df1e`，HTML SHA-256 `cff31d86f97691b23085f9f0e61f7557227a0c5ff381543d282aa973f283e158`。本轮未重跑Runtime/客户EXE/生产视觉与硬件发布门禁。

## 2026-10-10 收缩后残留启动代码与空白

本节修正上一次“顶层启动输出保留”的视图行为：用户要求所有收缩后不再露出“脚本已就绪”。当前文件的初始化与空白随显式绑定的启动处理器收缩/展开；无启动处理器的普通文件仍保留独立顶层代码。真实源码与执行语义不变。

- Monaco 全模型隐藏会被拒绝。本轮保留末行作为不可见、不可编辑的显示锚点，名称表保持可操作；展开恢复正文，跳转到初始化行展开启动程序。原生同步启动初始化范围与隐藏正文的只读保护。零高度的离屏表格测量不再覆盖有效高度。
- 最终 Monaco 32项：31通过、1 native专属跳过，40.217秒；native 32项：28通过、4 Monaco专属跳过，12.210秒。命令 `cache/release-probes/editor_interaction_gate_20261010.py monaco|native`，标签 `startup-scope-monaco-final` / `startup-scope-native-final`；证据 `editor-interaction-startup-scope-{monaco,native}-final-20261010.progress.txt`。覆盖Python/JS/TS有/无末尾空行、实际键盘对隐藏正文的保护、保存源码完整、名称行连续、输入与回车零表格替换和控件双击正文定位。
- 未通过探针保留：早期新增范围覆盖整个模型导致代码重新露出；一轮桌面定向测试卡在WebEngine初始化，120秒有界超时后回收，日志 `editor-interaction-startup-scope-monaco-complete-20261010.progress.txt`。另一次测试重复使用已缓存文件路径导致无末尾空行fixture仍读取前一份文档，已改独立路径后在最终两后端门禁通过。这些失败未计入通过。
- `editor-startup-scope-expanded-20261010.png` / `editor-startup-scope-collapsed-20261010.png` 是真实源码宿主截图，已目视核对；`editor-startup-scope-capture-20261010.json` 的 `visible_code` 为空，四个名称行位置连续，完整模型与用户文件相同。截图未冒称独立冻结交互测试。
- `tools/freeze_ide.py --output-directory build/editor-startup-scope-staging` exit0，日志 `freeze-ide-editor-startup-scope-20261010.txt`。独立staging及原路径各自script/native/受限auto/正常桌面Monaco smoke均exit0；报告 `editor-startup-scope-staging-primary-{script,native,auto,monaco}-20261010.json` / `editor-startup-scope-primary-{script,native,auto,monaco}-20261010.json`。脚本输出的OCR/YOLO是模拟调用，未当作生产识别验收。
- 用户明确保存关闭旧IDE后提升原路径，`editor-startup-scope-promotion-20261010.json`记录路径及workspace配置；保留`build/editor-startup-scope-previous-20261010`，此前被自动审批拒绝清理的目录也保持保留。
- `editor-startup-scope-artifact-20261010.json`确认源码/交付HTML、冻结main入口与四个UI模块实际编译代码一致，三套Runtime的源码/prebuilt/IDE内置指纹一致。EXE SHA-256 `2c564f90b68ce6ecf082a4d915e0ff9206621779c21876ac55f2daf513ca5d81`；HTML SHA-256 `8fa0f807a597f5d35847810d0cedae0bf4d12a447ea6985bad156537552527cc`。
- 本轮未重跑此前84项全量、Runtime冻结、客户EXE、生产视觉或硬件/干净机器发布门禁；本轮覆盖编辑器修正与当前IDE交付。
- 最终项目相关进程清单 `editor-startup-scope-final-processes-20261010.json` 为空；src/tests旁没有`__pycache__`。未删除回退副本或已被自动审批拒绝清理的缓存。`git diff --check`使用仓库换行配置exit0，证据`editor-startup-scope-diff-check-20261010.txt`；临时关闭autocrlf的探针曾把已有CRLF识别为行尾空白，已恢复正常仓库配置核对，无需重写源码换行。

## 2026-10-10 三项编辑器修复与原路径交付

本节覆盖用户最新三个问题：代码体收缩/展开、输入与换行闪烁、控件双击落到表格上一行。优先于下方此前“仅元数据折叠”的记录。本次未改 Runtime 核心，也未重跑此前 84 项全量或客户发布门禁。

- `editor.html` 折叠按真实代码范围设置 hidden areas，保留名称行与完整源码；Python 多行字符串和嵌套代码、JS/TS 字符串/模板/注释/正则括号、中文源码实际折叠均覆盖。两个子程序可独立收缩，顶层启动输出保留，折叠后保存内容完整。
- 原先每次 onDidChangeModelContent 都删除/重建全部 view zones，重新测量高度；现在按文件和源码身份复用节点，正文输入/回车的真实 Qt 键盘用例检查 DOM 节点不替换、MutationObserver 替换计数 0、焦点保留。相同隐藏范围不反复更新；原生同样保留未变字段/可见性。
- `goto_event` / 子程序导航调用 `goto_routine`，定位代码体首个有效位置并展开目标；真实 Qt 设计器按钮双击用例检查光标位于正文且源码不变。Node 新事件处理器采用多行模板。
- 最终源 Monaco：31 项，30 通过、1 native 专属跳过，38.767 秒；命令为 `cache/release-probes/editor_interaction_gate_20261010.py monaco`（日志标签 source-monaco-final），证据 `cache/logs/editor-interaction-source-monaco-final-20261010.progress.txt`。原生：31 项，27 通过、4 Monaco 专属跳过，11.978 秒，证据 `editor-interaction-native-20261010.progress.txt`。
- 探针实验未计入通过：processEvents 初始化轮询/冻结 HTML 外部宿主探针曾超时；另一次将 unittest 包装进 app.exec 的实验触发已删除 LocalPage 的生命周期错误并异常退出，该包装已撤回。最终回归按原有 unittest 方式通过；独立截图采用正常 app.exec 循环通过。有限子进程已回收。
- `tools/freeze_ide.py --output-directory build/editor-interaction-staging` exit 0，日志 `freeze-ide-editor-interaction-20261010.txt`。staging 冻结 Monaco smoke exit 0。确认无 PCIDE 进程且原 EXE 可写后才移动原目录并提升新版；`editor-interaction-promotion-20261010.json` 记录路径、哈希及 workspace 配置。
- 原路径 `build/PCIDE/PCIDE.exe` 的 script、native、受限 auto、正常桌面 Monaco smoke 均 exit 0，报告 `editor-interaction-primary-{script,native,auto,monaco}-20261010.json`。脚本 smoke 的 OCR/YOLO 输出明确为模拟调用，本轮没有把它当作生产识别验收。
- `editor-interaction-expanded-20261010.png` / `editor-interaction-collapsed-20261010.png` 是实际源码宿主编辑区截图，已目视复核；`editor-interaction-capture-20261010.json` 确认收缩后只显示独立顶层启动输出，完整源文仍保留。截图 HTML 与交付 HTML 哈希一致；并非声称外部源码宿主等于独立冻结交互测试。
- `editor-interaction-artifact-20261010.json`：源码/交付 HTML SHA-256 `5dabc760869150254c93fc30e122ac5363904dcca5b804a1ff516764a2c40c7d`；冻结入口与四个 UI 模块的实际编译代码与源码核对一致；三个 Runtime 的源码/prebuilt/IDE 内置指纹一致。最终 EXE SHA-256 `c3ed7af5dde3d19413e782962f5118df224f8e89bdabd4c41ce5079f716af6ec`。
- 自动审批拒绝递归清理旧交付副本和探针目录，理由为未明确授权删除可回退旧版的代价较高；保留 `build/editor-interaction-previous-20261010` 和缓存探针，不改新版。`editor-interaction-cleanup-20261010.json` 记录保留状态，`editor-interaction-final-processes-20261010.json` 是最终业务进程清单。源码旁没有新增字节码缓存；`editor-interaction-diff-check-20261010.txt` exit 0。


## 2026-10-10 用户截图后的编辑器修正与新交付

本节覆盖最新代码区修正，优先于下方同日的此前冻结记录。此次没有改 Runtime 执行核心，没有重跑此前 84 项全量或五项目发布门禁；当前证据为两个后端完整 UI 回归、冻结脚本/UI smoke 和 Runtime/客户载荷指纹审计。

- 根因：旧子程序标题与输入名称重复；几张表宽度不同；view zone 固定预留 `220+...` 像素，测量仅增高，删除/折叠后不缩回。修正为一条可编辑名称行、左侧三角、统一表宽、空局部添加条与双向真实尺寸测量。声明号使用 marginDomNode，对应源码真实行号。
- 临时元数据先前可能在重绘时匹配到旧记录；现在发布同一源码身份时去除旧记录，并支持绝对/相对文件匹配。折叠、插入行、切文件后仍保留名称/备注和局部。保留 HTML 原生鼠标焦点和文本选择。
- 正常桌面 Monaco：`python -B -m unittest tests.test_ui -v` exit `0`，28 项，27 通过、1 native 专属跳过，33.530 秒；`cache/logs/editor-layout-monaco-final-20261010.txt`。新用例实际发送 Qt 鼠标/键盘事件编辑名称，检查落盘、事件绑定、三次添加/删除后的高度增长与回收、折叠、插行、切文件及完整源码保存。
- 原生 Qt：同一 UI 组 exit `0`，28 项，24 通过、4 Monaco 专属跳过，11.505 秒；`cache/logs/editor-layout-native-final-20261010.txt`。空局部表隐藏，面板采用实际内容高度。
- 输入探针早期失败定位为 Qt WebEngine 渲染控件的坐标被测试框架偏移，日志保留在 `editor-layout-input-r*-20261010.txt`；修正为视口坐标后新用例及整组均通过。没有把 JavaScript 直接改 value 当成实际鼠标/键盘操作。
- 原路径首次打包失败：用户旧 IDE 正在运行，PyInstaller 清理目录时遇到占用的 `qgif.dll`。日志 `freeze-ide-editor-layout-20261010.txt`；随后从独立新版恢复缺失的 116 个资产，记录 `editor-layout-locked-runtime-repair-20261010.json`。冻结工具现支持 build 内独立输出、基于输出位置生成 workspace 配置，并在清理旧目录前检查 EXE 写权限。
- 独立冻结 `tools/freeze_ide.py --output-directory build/editor-layout-staging` exit `0`；`freeze-ide-editor-layout-staging-20261010.txt`。该 EXE 正常桌面 Monaco smoke 通过。用户随后明确“已保存并关闭旧 IDE”，确认进程退出后将新版移动到原交付目录并恢复 `workspace:../..`；记录 `editor-layout-promotion-20261010.json`。
- 原路径最终 `build/PCIDE/PCIDE.exe --ui-smoke --editor monaco` exit `0`，`frozen:true/monaco:true/editor_ready:true`；报告/截图 `editor-layout-frozen-20261010.json/png`。脚本 `--smoke`、native、默认受限 auto smoke 均 exit `0`；本次重新生成的 `frozen-script-release-20261010.json`、`frozen-native-release-20261010.json`、`frozen-auto-release-20261010.json` 均通过。截图已实际查看。
- `editor-layout-code-area-20261010.png` 是源码编辑控件直接截图；源码与冻结 `editor.html` SHA-256 同为 `53706e017c4d716883e1c2f510c309b4aa0c338e696355c60abb598b2c8e85f6`，记录 `editor-layout-artifact-20261010.json`。
- 最终完整交付为 `F:\PC端软件\build\PCIDE\PCIDE.exe` 和同级完整 `_internal`。当前 EXE SHA-256 为 `f4d5e131dea32aa2dd4a2bad913077c61b1fc02b65a51473274fd247c428ae91`；此前 EXE 哈希仅为历史版本。再次审计三套 Runtime 与源码/冻结内置指纹一致，四语言客户载荷仍通过，日志 `editor-layout-final-audit-20261010.txt`。
- 最终原路径验证后，本次生成的旧交付临时快照与空 staging 目录已校验绝对路径后清理；`editor-layout-cleanup-20261010.json` 记录源码旁字节码目录为空，`editor-layout-final-processes-20261010.json` 为 `[]`；最终 `git diff --check` exit 0，日志 `editor-layout-diff-check-20261010.txt`。未提交或推送本轮修改。

## 2026-10-10 中文 IDE 最终开发与交付门禁

本节是本轮最终证据。下方历史记录保留原结果，不代表当前版本。没有以受限 token 的截图/单文件 ACL 失败或静态合同代替正常桌面和实际 EXE 验证。

### 源码、执行与 UI

- 在正常 Windows 会话运行 `run_tests.ps1 -q`，原生编辑器后端：exit `0`，共 `84` 项，`81` 项通过、`3` 项跳过，`189.493` 秒。日志：`cache/logs/full-tests-release-20261010.txt`。跳过的是 Monaco 专属的收缩/展开、元数据 DOM 编辑和 TypeScript worker 诊断。
- 正常桌面 `python -B -m unittest tests.test_ui -v`，Monaco 后端：exit `0`，共 `27` 项，`26` 项通过、`1` 项跳过，`46.659` 秒。日志：`cache/logs/monaco-desktop-release-20261010.txt`。仅跳过原生子程序表专属用例；覆盖上面的三项 Monaco 用例及最新成员编辑对话框。
- 全量包含真实 DLL 标量调用、独立宿主 PID、sleep 超时、崩溃、失效句柄、卸载和恢复；四语言跨文件公开调用、局部变量与数据执行；模块精确依赖/版本/接口；静态局部与常量保护；堵塞输入管道回收、工具输出上限；四语言冻结目录版及元数据变化缓存失效。
- 源码 UI smoke `src/pcide/main.py --ui-smoke --editor native`：exit `0`，`editor_ready:true`；报告/截图 `cache/logs/source-native-release-20261010.json/png`。
- 冻结 IDE 的 `--smoke`、`--ui-smoke --editor native`、默认 `--ui-smoke`、正常桌面 `--ui-smoke --editor monaco` 均 exit `0`。报告分别为 `frozen-script-release-20261010.json`、`frozen-native-release-20261010.json`、`frozen-auto-release-20261010.json`、`frozen-monaco-release-20261010.json`。三份 UI 报告均 `editor_ready:true`；正常桌面强制 Monaco 为 `monaco:true`，受限环境默认 auto 为 native。对应 PNG 已实际查看，编辑区与子程序表可见且不重叠。

### Runtime、冻结交付和独立 EXE

- `tools/freeze_runtime.py --profile all`：最终三套 profile 全部 exit `0`；本轮以 `cache/logs/freeze-runtime-release-20261010.txt` 为准。`tools/freeze_ide.py` exit `0`，以 `cache/logs/freeze-ide-release-20261010.txt` 为准。
- 完整 IDE 交付：`F:\PC端软件\build\PCIDE\PCIDE.exe` 和同级 `F:\PC端软件\build\PCIDE\_internal`；不可只复制 EXE。EXE SHA-256：`bb16970aa63b7bb769554ca5c5bf0fb1472708c952ee69056756fb2bcb46b110`。
- basic/vision/node 当前源码、prebuilt manifest 与 IDE 内置 manifest 指纹全部相同；`cache/logs/closeout-final-audit-20261010.json` 为 `ok:true`。四个客户 EXE 的实际归档载荷只有编译后的 `.pyc/.jsc`、显式 JSON/表单/流程等，无项目源码/SDK/`__pycache__`。
- `tools/measure_closeout.py` exit `0`，`cache/logs/closeout-build-timings-20261010.json` 为 `ok:true`。四种语言真实单文件客户 EXE 在无开发 Python、空 PYTHONPATH 的工作区退出 `0`，输出跨文件公开函数结果 `9`；交付位于 `build/closeout-projects/closeout-{python,zhxb,javascript,typescript}/`。

| 普通客户项目 | 首次（秒） | 修改后增量（秒） | 无变化（秒） |
| --- | ---: | ---: | ---: |
| Python | 1.797 | 1.391 | 1.015 |
| 中文源码 | 1.500 | 1.766 | 1.015 |
| JavaScript | 3.281 | 3.344 | 1.422 |
| TypeScript | 2.672 | 2.359 | 1.406 |

首次和增量均非整项目缓存命中，无变化均命中；修改后 changed_files 为 1。该项目包含公开库函数、元数据局部、全局数据、表单和流程，在本机满足 10 秒目标；没有承诺大型项目、首次依赖安装或 IDE/Runtime 完整冻结均在 10 秒内。

### 最终发布与清理

- 最终 `tools/verify_release.py` exit `0`，`76.202` 秒，日志 `cache/logs/verify-release-20261010-bounded-final.txt`，时间证据 `verify-release-20261010-timing.json`。`frozen-release.json` 为 `ok:true`、`temporary_workspace_removed:true`，覆盖五个隔离项目、客户 EXE-only 目录、源/SDK 泄漏扫描、真实 OCR/CPU ONNX、Python/C/.NET 插件。
- 六类 worker（native_event、cancel、disconnect、invalid、timeout、crash）全部 `ok:true/reaped:true`。发布工具现使用 `run_bounded` 的 Job/超时/日志上限；生命周期探针有独立记录数量与字节上限。
- 所有发布任务结束后的只读进程复查 `cache/logs/closeout-process-inventory-20261010.json` 为 `[]`。已确认绝对目标位于项目内、且不是重解析点后，删除五处 src/tests `__pycache__`、`cache/tmp-debug` 和 `cache/native-debug`；`closeout-cleanup-20261010.json` 记录剩余源码字节码目录为空。
- 本轮最终 `git diff --check` 无空白错误。未提交、备份或推送；未修改 `D:\zhxbapp`，没有进行该目录独立完整性审计。

### 本轮曾发现的失败与修复

- 早期受限会话的 `_MEI` ACL/屏幕抓取失败与启动树行号偏移属于旧门禁；树行号正则吞换行已修复，最终全量在正常会话重跑成功。
- 首轮正常 Monaco 回归发现 JS/TS 中文关键字投影干扰 TypeScript 诊断；已让 JS/TS 保留真实关键字，最终正常 Monaco 回归成功。
- 最终客户载荷附加审计首次失败是发布工具仍把中文语言归类为 `.jsc`，实际 EXE 已执行成功；已修正 `.pyc` 判断和未知语言拒绝，四语言归档审计成功，并重新运行最终有界发布门禁。没有把该失败忽略或称为客户 EXE 运行失败。

### 已知能力边界

- 中文编译器为明确子集，不是完整易语言/VB；普通 Python/JS/TS 类与继承走其原生运行时。详见 `docs/规范/routine-runtime.md` 的语法和官方参考。
- DLL 裸指针/文本指针返回、结构体、输出参数、跨位数、fastcall/thiscall 尚未开放；Node DLL、Node 静态局部、Node 版本模块表尚未开放；均有明确错误，未伪装成功。模块更新在下次运行创建 worker 时加载，不做运行中热替换。
- 公开表和子进程隔离不是恶意代码 OS 沙箱；字节码/Bytenode 不是加密。
- 真实 OCR/CPU ONNX 证明本机执行；模拟视觉/合成检测不证明生产识别质量。Android 真机、HID/串口硬件、GPU、代码签名和另一台干净 Windows 未验收。

## Final local Windows gate — 2026-10-07

All commands below ran from `F:\PC端软件` with the project development environment under `runtime/dev`; disposable workspaces were kept under `cache` and removed by the release gate.

- `& .\run_tests.ps1`: exit `0`; 29 tests passed in 83.304 seconds. This covers project/form/flow validation, Python/JS/TS run/debug and events, bounded output, timeouts/cancellation, plugin hosts, automation APIs, DEX fixtures, real Qt/Monaco UI operations, TypeScript worker diagnostic `2322`, and frozen build tests.
- `runtime/dev/Scripts/python.exe -B tools/freeze_runtime.py --profile all`: exit `0`; refreshed `runtime/prebuilt/project-runtime`, `project-runtime-vision`, and `project-runtime-node`. Evidence: `cache/logs/freeze-runtime-final2.log`.
- `runtime/dev/Scripts/python.exe -B tools/freeze_ide.py`: exit `0`; produced `build/PCIDE/PCIDE.exe`. Evidence: `cache/logs/freeze-ide-final2.log`.
- `runtime/dev/Scripts/python.exe -B tools/deliver_examples.py`: exit `0`; `HelloAutomation`, `JavaScriptDemo`, and `TypeScriptDemo` standalone EXEs ran with exit `0`; build and cached-build timings are in `cache/logs/delivery.json`.
- `runtime/dev/Scripts/python.exe -B tools/verify_release.py`: exit `0`; `cache/logs/frozen-release.json` has `ok: true`, `temporary_workspace_removed: true`, and an isolated workspace with no development Python, SDK, or source tree. The gate built and ran three language examples, a real RapidOCR/OpenCV ONNX project, and Python/C/.NET plugin project; checked payload members for source/SDK leakage; ran a frozen Monaco UI smoke with screenshot `cache/logs/frozen-ide.png`; and verified the customer EXE in an EXE-only directory.
- The same report records frozen worker lifecycle cases: native event with delayed NumPy import, cancellation, stdin disconnect, invalid command, partial-command forced termination (`alive_before_termination: true`), and an explicit crash. Each child was reaped; normal cancellation/disconnect returned `130`, invalid command returned `1`, timeout termination was forced by the owned Windows job, and crash returned `23`.
- `cache/logs/vision-verification.json`: real RapidOCR recognized `PCIDE 2026 TEST` at approximately `0.982` confidence; synthetic CPU YOLO training/export produced a real ONNX tensor `[1, 5, 8400]`. The record explicitly limits this to execution/export evidence, not recognition accuracy.

## Initial Bootstrap

- 2026-10-07: `compileall` returned 0; it created source-adjacent bytecode, which will be removed and all subsequent compilation redirected into `cache/bytecode`.
- `python -B -m unittest discover -s tests -v`: 7 cases; 6 passed/1 plugin ID validation error. Repaired legal underscore IDs and system DLL references.
- A .NET Framework launcher compilation probe ran with exit 0. This did not establish standalone runtime delivery and is not a release artifact.

## Unverified boundaries

- No Android device/ADB endpoint was available, so Android ART/DexClassLoader execution remains unverified; PC WebSocket fixture tests cover request ownership and disconnect errors only.
- Serial/HID tests cover loopback and device inventory, not hardware transmit/receive acceptance. GPU training, code signing, malicious-code OS sandboxing, and another clean Windows machine were not tested.

## 2026-10-09 最终收口验证

- `& .\run_tests.ps1 -q`: exit `0`; 56 tests passed, 1 environment-dependent test skipped, total `97.211` seconds (`cache/logs/full-tests-20261009-final.txt`). This includes editor fallback operations, project lifecycle/menu contracts, plugin install/repeat-install/uninstall/upgrade/rollback, Python/JavaScript/TypeScript/中文源码, build cache, UI, flow, vision and child-host lifecycle gates.
- `runtime\dev\Scripts\python.exe -B tools\freeze_runtime.py --profile node`: exit `0`, `60.093` seconds. The basic/vision/node manifests were compared against the current source fingerprints and all matched.
- `runtime\dev\Scripts\python.exe -B tools\freeze_ide.py`: exit `0`, `62.047` seconds; final delivery is `build\PCIDE\PCIDE.exe` with the complete sibling `build\PCIDE\_internal` directory.
- Final frozen smoke commands all exit `0`: `--smoke`, `--ui-smoke --editor native`, and default `--ui-smoke`. Reports are `cache/logs/frozen-ide-smoke-r2.json`, `cache/logs/frozen-ui-native-r2.json`, and `cache/logs/frozen-ui-auto-r2.json`; the default restricted-token backend is `native` with `editor_ready: true`, avoiding Chromium/Mojo popups. Screenshots are `cache/logs/frozen-ui-native-r2.png` and `cache/logs/frozen-ui-auto-r2.png`.
- `runtime\dev\Scripts\python.exe -B tools\deliver_examples.py`: exit `0`; standalone customer EXEs for HelloAutomation, JavaScriptDemo, and TypeScriptDemo ran without the development Python. Latest first/cached timings are respectively `3.231/1.133`, `1.689/1.390`, and `1.587/1.393` seconds. An isolated measurement after the packaging optimization recorded first/incremental/unchanged as `2.398/2.226/1.114` seconds.
- `runtime\dev\Scripts\python.exe -B tools\verify_release.py`: exit `0` in `72.685` seconds; `cache/logs/frozen-release.json` reports `ok: true`, `temporary_workspace_removed: true`, five isolated language/vision/plugin projects, source/SDK-free customer payloads, and reaped native/cancel/disconnect/invalid/timeout/crash workers. The UI evidence records `ui_editor: native`, `ui_monaco: false` for this restricted host; supported desktops may use Monaco.
- Source entry smoke (`src/pcide/main.py --smoke` and `--ui-smoke --editor native`) exited `0`; an isolated `.zhxb` source run and standalone customer EXE also exited `0` (`cache/logs/zhxb-source-smoke-final.txt`, `cache/logs/zhxb-exe-smoke-final-r2.txt`).
- The final native UI smoke was additionally attempted through the Computer Use bridge, but this session exposed browser controls only and returned no native-app inventory. Therefore the verifiable UI evidence is the executable's own screenshot-backed Qt smoke, not a claim of external accessibility automation.

## 2026-10-07 中文化收口
- 修改范围：主界面、运行窗口、视觉面板、编辑器提示、模板与示例项目。
- 验证：run_tests.ps1 29 项通过；verify_release.py 输出 ok=true。

## 2026-10-08 窗口与程序数据收口

- `& .\run_tests.ps1`: exit `0`; 32 tests passed in 84.850 seconds. The added `tests/test_contracts.py` covers independent window files, bounded layout metadata, all variable scopes/constants, DLL/API metadata and code generation, and Chinese label/English ID round trips. Existing Qt/Monaco, runtime, plugin, DEX and build gates also passed.
- `runtime/dev/Scripts/python.exe -B tools/freeze_runtime.py --profile all`: exit `0`; the three prebuilt runtime profiles were refreshed after the final source changes. IDE EXE was not rebuilt in this closeout.
- Source-only boundaries: no physical Android device, HID hardware, GPU training, signing, or clean-machine deployment was claimed by these tests.

## 2026-10-08 二轮收口复核

- `& .\run_tests.ps1`: exit `0`; 34 tests passed in 85.402 seconds. This includes typed Python/JavaScript/TypeScript literal generation, fixed-width-only and fixed-height-only Qt constraints, runtime window aliases and multi-window open/close lifecycle, plus the existing build, worker, plugin, DEX, vision and Monaco gates.
- `runtime\dev\Scripts\python.exe -B tools\freeze_runtime.py --profile all`: exit `0`; refreshed `runtime/prebuilt/project-runtime`, `project-runtime-vision`, and `project-runtime-node` after the runtime window API and generator fixes.
- `runtime\node\node.exe --check src\pcide\core\worker_js.cjs` and `worker_bytecode.cjs`: exit `0`; Python sources and tests passed `compileall` before disposable `__pycache__` cleanup.
- The source closeout itself did not rebuild the IDE EXE; it was rebuilt and checked in the following packaging step. Android ART/device, HID hardware, GPU training, code signing, and another clean Windows machine remain unverified boundaries.

## 2026-10-08 IDE EXE 重打包

- `runtime\dev\Scripts\python.exe -B tools\freeze_ide.py`: exit `0`; rebuilt `build/PCIDE/PCIDE.exe` with the refreshed runtime profiles and current source.
- `build\PCIDE\PCIDE.exe --smoke --report cache\logs\ide-repack-smoke.json`: report confirms `frozen: true`, `script_exit: 0`, `flow: true`, `monaco_assets: true`, and the expected UI update.
- `build\PCIDE\PCIDE.exe --ui-smoke --screenshot cache\logs\ide-repack-ui.png --report cache\logs\ide-repack-ui-smoke.json`: exit `0`; report confirms `qt: true`, `monaco: true`, and `frozen: true`.

## 2026-10-08 窗口双击设计视图修复

- `& .\run_tests.ps1`: exit `0`; 35 tests passed in 96.884 seconds. The added Qt regression covers project-tree double-click of `main.form.json`, confirms the design view is selected, and confirms the source editor is not the active pane.
- `runtime\dev\Scripts\python.exe -B tools\freeze_ide.py`: exit `0`; rebuilt `build/PCIDE/PCIDE.exe` with the fix.
- `build\PCIDE\PCIDE.exe --smoke --report cache\logs\ide-window-fix-smoke.json`: exit `0`; frozen script, flow, UI update, and Monaco asset checks passed.
- `build\PCIDE\PCIDE.exe --ui-smoke --screenshot cache\logs\ide-window-fix-ui.png --report cache\logs\ide-window-fix-ui.json`: exit `0`; report confirms `qt: true`, `monaco: true`, and `frozen: true`.

## 2026-10-08 新建窗口入口修复

- `& .\run_tests.ps1`: exit `0`; 36 tests passed in 90.535 seconds. The added Qt coverage verifies the window menu/context flow creates or selects a form and leaves the designer view active.
- `runtime\dev\Scripts\python.exe -B tools\freeze_ide.py`: exit `0`; rebuilt `build/PCIDE/PCIDE.exe` with the discoverable new-window actions.
- `build\PCIDE\PCIDE.exe --smoke --report cache\logs\ide-new-window-smoke.json`: exit `0`; frozen script, flow, UI update, and Monaco asset checks passed.
- `build\PCIDE\PCIDE.exe --ui-smoke --screenshot cache\logs\ide-new-window-ui.png --report cache\logs\ide-new-window-ui.json`: exit `0`; report confirms `qt: true`, `monaco: true`, and `frozen: true`.

## 2026-10-08 全面项目管理与窗口事件收口

- `& .\run_tests.ps1 -q`: exit `0`; 39 tests passed in `cache/logs/tests-full-closeout.log`. Added coverage for safe project file/ directory rename/delete, protected project paths, window menu rename/delete entries, and runtime `resize`/`close` events.
- `runtime\dev\Scripts\python.exe -B tools\freeze_runtime.py --profile all`: exit `0`; refreshed all three prebuilt runtime profiles after the project-management and event-contract changes.
- `runtime\dev\Scripts\python.exe -B tools\freeze_ide.py`: exit `0`; rebuilt `build/PCIDE/PCIDE.exe` at 2026-10-08 02:03.
- `build\PCIDE\PCIDE.exe --smoke --report cache\logs\ide-closeout-smoke2.json`: exit `0`; report confirms `frozen: true`, `script_exit: 0`, `flow: true`, `monaco_assets: true`, and UI event update.
- `build\PCIDE\PCIDE.exe --ui-smoke --report cache\logs\ide-closeout-ui2.json`: exit `0`; report confirms `qt: true`, `monaco: true`, and `frozen: true`.
- Reviewed [Qt Widgets menus](https://doc.qt.io/qt-6/qtwidgets-mainwindows-menus-example.html), [Qt QFile](https://doc.qt.io/qt-6/qfile.html), and the public [精易 eIDE repository](https://github.com/kuodafu/eide); only interaction patterns were used, with no source copied.

## 2026-10-08 交付目录运行时修复

- Root cause: the first `outputs\PCIDE.exe` copy did not include its sibling `_internal` directory, so PyInstaller could not load `python312.dll`.
- Copied the complete `build\PCIDE\_internal` tree beside `outputs\PCIDE.exe`.
- From the actual outputs directory, `PCIDE.exe --smoke` exited `0`; `PCIDE.exe --ui-smoke` exited `0`; both reports resolve resources from `outputs\_internal`.
## 2026-10-08 易语言布局与补全收口

- 修改：中央工作区切换为“界面设计/代码工作区”；左侧项目树下增加子程序导航；右侧增加“支持库/属性”页；“环境 -> 项目环境”保存语言、Python 和 Node.js 路径到项目清单；支持库双击插入命令。
- 编辑器：Monaco 使用项目变量、常量、API、窗口控件与事件生成补全；支持 Ctrl+Space、`.`/`:`/中文句号触发、参数签名提示、代码片段、折叠和格式化入口；数据来源为当前项目 `.pcide/data.json` 与窗口表单。
- 验证：`& .\run_tests.ps1 -q` 退出 `0`，40 项通过；定向窗口/Monaco 测试 3 项退出 `0`；三个 runtime profile 指纹有效；`tools/freeze_ide.py` 退出 `0`；冻结版 smoke/UI smoke 报告 `cache/logs/ide-layout-smoke.json`、`cache/logs/ide-layout-ui.json` 均确认 `frozen: true`、Monaco/脚本/流程通过；交付目录 `outputs` 中 EXE-only smoke/UI smoke 均退出 `0`。
- 限制：未宣称 Android 真机、HID 硬件、GPU、代码签名或另一台干净 Windows 机器验证；vision 预编译曾出现超时，随后单独重跑已成功刷新。
## 2026-10-08 易语言布局最终复核

- 布局：左侧支持库、属性/窗口设置、变量常量分组夹，下面是项目和子程序导航；中间是界面设计与代码工作区；右侧是控件箱；底部是输出/调试信息；设计器支持双击进入代码工作区，代码工作区标签在下方显示并可关闭或右键关闭。
- 控件：分组框和标签页已加入控件箱；属性面板支持分组页名称、当前页、边框样式；设计器和运行时均绘制对应外观。
- 验证：`& .\run_tests.ps1 -q` 退出 `0`，40 项通过；`tools/freeze_ide.py` 退出 `0`；冻结版 `--smoke`、`--ui-smoke` 退出 `0`；交付目录 `outputs` 中 `PCIDE.exe` 与同级 `_internal` 的 EXE-only smoke/UI smoke 均退出 `0`。截图：`outputs\PCIDE-layout.png`。
- 边界：未宣称 Android 真机、HID 硬件、GPU、代码签名或另一台干净 Windows 机器验证。
## 2026-10-08 代码编辑区红底修复

- 根因：Monaco 主题的颜色值缺少 `#` 前缀，主题变量被解析为无效值并回退为 `#ff0000`，导致当前行、边距和概览区域出现红色。
- 修复：`src/pcide/ui/editor.html` 为语法色、编辑区、当前行、行号、边距、概览尺和滚动条全部使用合法颜色值，并增加宿主层白底保护样式。
- 验证：源代码编辑器截图 `cache/logs/ide-editor-theme-code.png` 已恢复白底和正常配色；`test_monaco_edit_save_models_navigation` 退出 `0`；`& .\run_tests.ps1 -q` 退出 `0`，40 项通过；`tools/freeze_ide.py` 退出 `0`；冻结版 smoke/UI smoke 与 `outputs` 目录 EXE-only smoke/UI smoke 均退出 `0`。交付新增截图 `outputs\PCIDE-code-layout.png`。
## 2026-10-08 控件分类与属性实时回写

- `& .\run_tests.ps1 -q`: exit `0`; 40 tests passed in 96.277 seconds after wiring the shared control catalog and runtime property application.
- `runtime\dev\Scripts\python.exe -B tools\freeze_runtime.py --profile all`: exit `0`; refreshed `project-runtime`, `project-runtime-vision`, and `project-runtime-node` after the control/property contract changes.
- `runtime\dev\Scripts\python.exe -B tools\freeze_ide.py`: exit `0`; rebuilt `build\PCIDE\PCIDE.exe` with the categorized toolbox, left docking tabs, and reactive property panel.
- Frozen reports: `cache\logs\ide-window-chrome-smoke.json` has `frozen: true`, `script_exit: 0`, `flow: true`, `monaco_assets: true`; `cache\logs\ide-window-chrome-ui.json` has `qt: true`, `monaco: true`, `frozen: true`.
- Delivery reports: `outputs\smoke-final.json` has `script_exit: 0`, `flow: true`, `monaco_assets: true`; `outputs\ui-smoke-final.json` has `qt: true`, `monaco: true`, `frozen: true`; `outputs\PCIDE.exe` is delivered beside `outputs\_internal`.
- Boundaries unchanged: Android ART/device, HID hardware, GPU training, code signing, and another clean Windows machine remain unverified.
- 最终回归补充：`& .\run_tests.ps1 -q` exit `0`，41 tests passed in 90.636 seconds；新增用例覆盖控件箱四组、设计区选中后属性页切换、宽度与文本焦点提交。
- 交付目录复核：从 `outputs` 启动 `PCIDE.exe`，`--smoke` 和 `--ui-smoke` 均由 `Start-Process -Wait` 返回 exit `0`，报告资源路径均为 `outputs\\_internal`。

## 2026-10-08 Qt WebEngine 弹窗收口

- 根因：在当前受限 Windows token 中，Qt WebEngine/Chromium 创建 Mojo 命名管道返回 `拒绝访问 (0x5)`，进程在页面初始化前触发 `FATAL:named-platform-channel-pipe` 弹窗。
- 修复：`src/pcide/ui/editor.py` 在构造 `QWebEngineProfile` 之前识别受限宿主并切换到原生 `QPlainTextEdit`；`--editor native` 可显式选择回退，`--editor monaco` 仅在确认宿主支持 WebEngine 时启用 Monaco。
- 源码验证：`src/pcide/main.py --ui-smoke --editor native` 退出 `0`，报告 `editor_ready: true`；`tests.test_contracts` 与 `tests.test_ui` 共 23 项定向测试退出 `0`。
- 冻结验证：`build\\PCIDE\\PCIDE.exe --smoke`、`--ui-smoke --editor native` 和默认 `--ui-smoke` 均退出 `0`；冻结报告分别为 `cache/logs/frozen-closeout-smoke.json`、`cache/logs/frozen-closeout-ui.json` 和 `cache/logs/frozen-closeout-ui-auto.json`。
- 当前环境的完整门禁仍受屏幕抓取失败与 PyInstaller 单文件 `_MEI` 目录 ACL 限制；这些是测试宿主限制，不是源码启动错误。

## 2026-10-09 Monaco 空白回归修复

- 用户截图中的实际错误为 `Uncaught SyntaxError: Invalid regular expression`：`src/pcide/ui/editor.html` Python 投影正则使用 `\#`，在带 `u` 标志的 JavaScript 正则中属于非法 identity escape，页面脚本因此在创建 Monaco 模型前终止。
- 修复为未转义的 `#`，并加入 `tests.test_ui.UiTests.test_editor_python_projection_regex_is_unicode_safe`，防止该错误回归。
- `runtime/node/node.exe` 对源码和冻结版内联脚本均返回语法检查成功；源码 `--smoke`、冻结版 `--smoke`、源码/冻结版 `--ui-smoke --editor native` 均返回 exit `0`，报告中的 `editor_ready` 为 `true`。
- 已重建交付文件：`build\PCIDE\PCIDE.exe` 与同级完整 `build\PCIDE\_internal`。在当前受限 token 中强制 `--editor monaco` 仍会触发 Qt Chromium Mojo 权限错误，因此默认后端继续自动回退原生编辑器；这与本次 JavaScript 正则修复是两个独立问题。

## 2026-10-09 子程序信息区重叠修复

- 根因：`renderRoutines()` 用零基源码数组索引作为 Monaco 一基 `afterLineNumber`，元数据 view zone 被放在子程序声明前；固定高度又偏小，表格可能继续压到代码行。
- 修复：`src/pcide/ui/editor.html` 使用 `afterLineNumber:index+1`，并为表格边框、内边距和参数行预留高度；`tests.test_ui.UiTests.test_editor_routine_zone_is_after_declaration` 固定该布局契约。
- `runtime/node/node.exe` 源码内联脚本语法检查成功；冻结版 `--smoke` 与 `--ui-smoke --editor native` 均 exit `0`，`editor_ready: true`。当前受限 token 仍不能用真实 Chromium 做视觉截图，故 Monaco 视觉位置以代码契约和可用桌面环境验收为准。

## 2026-10-09 子程序信息区收缩/展开收口

- `src/pcide/ui/editor.html` 为每个子程序元数据区增加 `−/＋` 按钮和标题栏；折叠保留标题，展开显示返回值与参数表；view zone 初始高度按 Windows 字体指标预留，并在首帧后按 DOM 实际高度校正。
- `tests.test_ui.UiTests.test_visible_code_pane_has_source_and_fitting_routine_tables` 与 `test_routine_metadata_can_collapse_and_expand` 在真实 Monaco/WebEngine 中通过，确认代码可见、表格没有穿透代码行，按钮可往返收缩/展开。
- `run_tests.ps1 -q`：exit `0`，60 tests passed, 2 environment-dependent tests skipped, 87.888 seconds；日志为 `cache/logs/full-tests-20261009-collapse.txt`。
- `tools/freeze_ide.py`：exit `0`，最终交付为 `build\PCIDE\PCIDE.exe` 和同级 `_internal`；冻结版 `--ui-smoke --editor monaco` exit `0`，`editor_ready: true`，截图为 `cache/logs/frozen-ui-monaco-collapse-20261009.png`。当前受限默认模式仍自动使用 native，显式 Monaco 在本次正常 WebEngine 上可见并显示两个带 `−` 按钮的子程序信息区。
- 追加元数据验收：`run_tests.ps1 -q` exit `0`，62 tests passed、3 environment-dependent tests skipped（76.264 秒，`cache/logs/full-tests-20261009-routine-metadata.txt`）；公开勾选、名称/返回值/备注字段及跨文件公开补全测试通过。最终冻结 UI smoke 为 `cache/logs/frozen-ui-routine-meta-20261009.json`，exit `0`，`monaco: true`。

## 2026-10-09 源码隐藏视图收口

- `src/pcide/ui/editor.html` 使用 Monaco `setHiddenAreas()` 只隐藏导入行和 `def/function/子程序`（包括 `.子程序`）声明行；模型快照、保存、运行和构建仍读取完整真实源码。
- 自定义 `▸/▾` 三角继续位于子程序信息区左侧，默认 Monaco 折叠三角保持隐藏；信息区输入框、公开红色 `✔`、备注和跨文件补全不受影响。
- 本轮冻结版原生 UI smoke `cache/logs/frozen-ui-hidden-native.json` exit 0；定向 `tests.test_ui` 为 15 项通过、3 项环境跳过。全量 62 项中 5 个构建 EXE 失败与 1 个屏幕抓取错误属于当前受限宿主的 PyInstaller ACL/屏幕捕获限制；显式 Monaco 在受限 token 中仍会触发 Chromium Mojo 权限错误，默认后端自动回退 native。

## 2026-10-10 启动子程序、行号和局部变量

- `_启动程序` 由当前窗口 `form.events.load` 唯一确定；它只是界面中的可编辑启动标题，真实加载处理器仍保持可运行绑定。其他子程序不会被批量改名。
- 子程序信息区增加自定义源码行号、完整中文返回类型下拉框、公开复选框、备注输入和局部变量（名称/类型/默认值/备注/删除）表；数据通过 `.pcide/routines.json` 保存。
- `runtime\dev\Scripts\python.exe -B -m unittest tests.test_ui -v`：20 项通过、3 项环境跳过，日志 `cache/logs/test-ui-startup-entry-final.txt`；内联 Monaco 脚本 `runtime\node\node.exe --check` exit 0；冻结 EXE `build\PCIDE\PCIDE.exe --smoke` 与 `--ui-smoke --editor native` 均 exit 0，报告 `cache/logs/frozen-startup-entry-smoke-final.json`、`cache/logs/frozen-startup-entry-ui-native-final.json`。
# 2026-10-10 迭代编译补强

- `src/pcide/main.py`：编译对话框确认后保存 target/configuration/jobs，关闭并重新打开工程仍沿用选择的发布合同。
- `src/pcide/core/build_service.py`：C/C++ 对象身份仅包含该源文件递归解析到的项目头文件摘要；无关头文件改动不会重编其他翻译单元。CMake 已有 `CMakeCache.txt` 时跳过重复配置，.NET 发布已有离线 assets 时使用 `--no-restore`。
- 验证：`tests.test_development.DevelopmentTests.test_native_real_static_build_incremental_headers_and_rollback`、模板工厂和工具复用三项通过（4.558 秒）；Python 语法编译通过。完整门禁中 PyInstaller 单文件和屏幕抓取的失败来自当前受限令牌/无桌面屏幕，使用正常 Windows 令牌复跑最小 onefile 解压成功，产品源代码未触发该权限错误。
