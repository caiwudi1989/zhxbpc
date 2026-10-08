# zhxbpc 平台能力合同

`manifest.platform` 是项目能力的唯一声明入口，版本为 `1`。能力分为
`database`、`api`、`script`、`ai`、`game`、`compiler`、`agent` 和 `runtime`。
每项能力有 `enabled` 开关和 provider 列表；provider 通过项目下的
`providers/<id>/provider.json` 声明，IDE 只读取清单，不导入 provider 代码。

`core/product.py` 维护产品目录、合同版本和生命周期阶段。当前阶段用于让
设计器、编辑器、运行时和发布器共享同一份能力解析结果：

| 能力 | 合同 | 阶段 |
| --- | --- | --- |
| database | schema-v1 | schema / binding / crud |
| api | api-v1 | request / model / error |
| script | script-v1 | load / debug / reload |
| ai | ai-v1 | inference / vision / pipeline |
| game | game-v1 | scene / render / input / build |
| compiler | compiler-v1 | lex / parse / ir / emit |
| agent | agent-v1 | inspect / generate / verify |
| runtime | runtime-v1 | window / io / lifecycle |

第三方实现必须运行在现有插件/子进程边界内。硬件、GPU、Android 设备和生产级
模型质量仍需独立验收，能力开关本身不代表这些外部资源已经可用。

## 当前内置连接

- `database`: `core.database` + `runtime_api.db`，SQLite 可直接执行；其他数据库通过 provider。
- `api`: `core.api_center` + `runtime_api.network`，HTTP/HTTPS 可直接执行；WebSocket/TCP/UDP/MQTT 通过 provider。
- `ai`: `core.ai_runtime.VisionProvider` 复用现有 OCR/ONNX 工作台。
- `game`: `core.unity` 识别 Unity 工程并生成 `MonoBehaviour` 桥脚；Unity Editor 和平台构建保持外部进程边界。
- `compiler`: `core.compiler` 支持 `.版本 2`、程序集、子程序、输出/信息框基础语句并生成 Python Runtime 代码。
