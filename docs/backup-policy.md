# 源码备份规则

使用 `tools/backup_source.ps1` 执行备份。每次备份：

1. 提交当前源码变更到 `main`。
2. 创建或更新日期分支 `backup/YYYY-MM-DD`。
3. 将 `main` 和日期分支推送到 GitHub `origin` 与 Gitee `gitee`。

仓库只保存源码、文档、测试、示例和项目配置。以下目录及生成物禁止进入备份：

`cache/`、`build/`、`outputs/`、`runtime/`、`downloads/`、`sdk/`、`third_party/`、`assets/`、`projects/`、Python 缓存、日志和临时文件。

远程配置：

- GitHub：`https://github.com/caiwudi1989/zhxbpc.git`
- Gitee：`https://gitee.com/caiwudi1989/zhxbpc.git`

如只需本地检查或暂不推送，可运行：

```powershell
.\tools\backup_source.ps1 -SkipPush
```

4. 两个远程均推送成功后，删除本地专用备份目录 cache/backup/ 和 cache/backups/ 中的备份包与备份缓存；任一推送失败或使用 -SkipPush 时不清理。

清理范围仅限上述专用目录，不删除构建产物、运行环境或其他缓存。
