# 源码备份规则

当聊天框提出“备份”时，固定执行 `tools/backup_source.ps1`，不得只备份单个平台：

1. 提交当前源码变更到 `main`。
2. 创建或更新日期分支 `backup/YYYY-MM-DD`。
3. 将当前 `main` 覆盖推送到 GitHub `origin` 与 Gitee `gitee`。
4. 将当天日期分支 `backup/YYYY-MM-DD` 覆盖推送到 GitHub 与 Gitee。

仓库只保存源码、文档、测试、示例和项目配置。以下目录及生成物禁止进入备份：

`cache/`、`build/`、`outputs/`、`runtime/`、`downloads/`、`sdk/`、`third_party/`、`assets/`、`projects/`、Python 缓存、日志和临时文件。

远程配置：

- GitHub：`https://github.com/caiwudi1989/zhxbpc.git`
- Gitee：`https://gitee.com/caiwudi1989/zhxbpc.git`

如只需本地检查或暂不推送，可运行：

```powershell
.\tools\backup_source.ps1 -SkipPush
```

5. 两个远程的 `main` 和日期分支全部推送成功后，删除本地专用备份目录 `cache/backup/` 和 `cache/backups/` 中的备份包与备份缓存；任一推送失败或使用 `-SkipPush` 时不清理。

6. 推送遇到网络或远程暂时失败时，每个远程自动重试最多 10 次；10 次仍失败才停止并报告具体远程，不能把本地提交当作备份完成。

6.1. 两个远程必须在同一次备份中都尝试；一个远程失败时继续推送另一个远程，最后统一报告失败远程。只有全部成功才清理缓存并报告完成。

7. 每次备份同时生成 `backup-archives/source-YYYY-MM-DD.zip` 日期源码压缩包并提交、推送到两个远程。压缩包只包含源码、文档、测试、示例和项目配置，排除缓存、环境、构建物、日志、临时文件及此前压缩包。

清理范围仅限上述专用目录，不删除构建产物、运行环境或其他缓存。

标准命令：

```powershell
.\tools\backup_source.ps1
```

脚本会先检查禁止目录是否被 Git 跟踪，再提交源码，覆盖推送两个远程，最后才清理备份缓存。

## GitHub 命令行推送代理规则

当浏览器可以访问 GitHub、而 Git 命令行直连 `github.com:443` 超时时，备份必须先检查本机代理端口 `127.0.0.1:10808`，端口可用后配置：

```powershell
git config --global http.proxy http://127.0.0.1:10808
git config --global https.proxy http://127.0.0.1:10808
```

代理配置后，必须按同一次备份完整执行并核验：

1. 提交源码和当天压缩包到 `main`。
2. 将当天日期分支强制同步到最新 `main`：`git branch -f backup/YYYY-MM-DD main`。
3. 同时推送 GitHub `origin` 和 Gitee `gitee` 的 `main`、`backup/YYYY-MM-DD` 四个远程分支。
4. 使用 `git ls-remote` 核对两个远程的两个分支都指向本次最新提交；日期分支未同步不得报告备份完成。
5. 四个分支全部成功后才清理专用备份缓存；任一失败则保留缓存并报告失败远程。
