# PC Script IDE Engineering Rules

- Source root is `F:\PC端软件`. This project has no game or cloud business dependency.
- Entry: `start_ide.ps1` / `src/pcide/main.py`. Read `docs/PROJECT_MEMORY.md` and `docs/index/index_root.md` first.
- Keep source in `src`, tests in `tests`, documentation in `docs`, examples in `examples`.
- Third party editor assets belong to `third_party`; downloads to `downloads`; SDKs to `sdk`; environments to `runtime`; all disposable output to `cache`; EXE delivery to `build`.
- Never modify `D:\zhxbapp`. Extract only directly reviewed generic code and record provenance.
- Script, native plugin, training, and Android hosts are owned child processes with bounded output, timeout, cancellation, and shutdown cleanup. DLL code never enters the IDE process.
- Keep project manifests and form/flow schemas explicit. Reject malformed paths, duplicate IDs, and unsupported execution modes.
- After changes update memory, module index, and verification evidence. Do not claim simulated tests prove hardware, Android, production OCR/YOLO, or clean-machine deployment.
- Do not create or delegate to subagents.

## 备份触发规则

- 用户说“备份”时，固定执行 `tools/backup_source.ps1` 的标准流程，不得只做本地备份或只提交不推送。
- 标准流程必须提交当前源码变更到 `main`，创建或更新当天的 `backup/YYYY-MM-DD` 分支，并将 `main` 与当天日期分支同时推送到 GitHub `origin` 和 Gitee `gitee`。
- 只有 GitHub 和 Gitee 两个远程都成功接收后，才清理 `cache/backup/` 与 `cache/backups/` 专用备份缓存；推送失败时保留缓存并报告失败原因。
- 用户不需要重复提醒“推送”：执行备份时必须主动完成双远程推送；每个远程最多自动重试 10 次，10 次仍失败才明确说明外部网络阻断。
- 备份禁止纳入 `cache/`、`build/`、`outputs/`、`runtime/`、`downloads/`、`sdk/`、`third_party/`、`assets/`、`projects/` 及 Python 缓存、日志和临时文件。
- 每次备份必须生成 `backup-archives/source-YYYY-MM-DD.zip` 日期源码压缩包，并随 `main` 和日期分支推送到 GitHub、Gitee；压缩包不得包含缓存、环境、构建物、日志、临时文件或其他压缩包。
- 详细规则与远程地址以 `docs/backup-policy.md` 为准；`-SkipPush` 仅用于用户明确要求本地检查时，不是“备份”的默认行为。
