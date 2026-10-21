# WeChat Reply Agent

基于 wechatauto-replica 的个人微信 AI 回复应用。目标是在固定 Windows 环境中完成“测试好友发消息 → Agent 处理 → 微信回复”，并提供本地工作台、知识检索、联系人记忆和真实演示视频。

当前已内置固定 Replica 基座，Windows 微信 4.1.15.56 已完成 G1 固定收发验收。最小 LangGraph、DeepSeek 兼容客户端和 SQLite 原型账本已实现，真实三轮 G2 已通过（含上下文追问）；测试 worker 已自动停止。Phase 3 正式迁移/运行控制与 Phase 4 API/工作台已完成自动验证和用户人工验收；知识/长期记忆和最终交付尚未完成。

执行顺序、阶段状态及完成条件见 [执行计划](docs/wechat-agent-plan.md)，当前代码事实见 [开发入口](docs/overview.md)。

Mac Phase 5: the user has explicitly selected a degraded flow mode using one bound independent AX window, one clipboard paste/send, and independent database confirmation. Visual draft/occlusion checks are skipped and reported as unverified. A natural-conversation fixed send was received once; two real Agent replies were DB-confirmed and accepted by the user. The degraded flow is marked passed and the worker is stopped. Strict Mac G1/G2 have not passed and Phase 6 has not started. See [Mac setup and limitations](docs/mac-probe.md).

## 技术路线与运行范围

| 部分 | 方案 |
| --- | --- |
| 微信基座 | [wechatauto-replica 1.2.7.0](https://github.com/fanyuantaier/wechatauto-replica/tree/d322c4a9b1124228820bab363e5676016f188fc6)，固定源码快照，已作为 third_party 本地 path 依赖内置 |
| 消息读取 | 基座的本地数据库解密/WAL 读取，按其实现读取微信进程中的密钥材料并缓存 |
| 回复发送 | 基座 UIA 优先、坐标/OCR fallback、剪贴板粘贴与回车；允许其 UIA 热激活运行时标志写入 |
| Agent | LangGraph、可配置模型/人设、多轮上下文、知识检索与按联系人隔离的记忆 |
| 应用 | Python 3.12、FastAPI、SQLite、React/TypeScript/Vite；API/UI 不直接调用第三方 GUI 方法 |
| 环境 | 一台 Windows 10/11 x64 电脑、一个账号和测试好友单聊；固定微信版本、保持桌面解锁与窗口可见 |
| 节奏 | 默认 15 秒轮询，可配置；不要求实时、多系统、多版本或全天候运行 |

微信 4.1.15.53 为上游记录的测试组合，可优先验证；本项目本次实际验证的是 4.1.15.56，不要求为适配擅自覆盖当前客户端或聊天数据。OCR 已允许使用，不再强制关闭。详细初始化步骤和 G1 用例见 [Windows 接入](docs/windows-probe.md)。

## 集成与当前可用内容

已实现的原型链路为：ReplicaAdapter → 身份/白名单过滤 → SQLite inbox → 会话队列 → Agent → outbox → 基座发送 → 回读/人工核对。应用单独管理游标、状态和失败，不把模型与发送直接放进可自动重试的监听回调。

现有代码可运行离线检查：

~~~sh
uv sync --locked --extra windows
uv run pytest -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv build
~~~

这些离线检查不访问微信。当前可运行的 Windows 入口：

~~~sh
uv run wechat-agent doctor --output .local/acceptance/phase-1/doctor.json
uv run python scripts/acceptance/bind_replica.py --alias test-a --wechat-id <明确测试好友的微信号>
uv run wechat-agent connect --output .local/acceptance/phase-1/connect.json
uv run wechat-agent probe read --contact test-a --limit 5 --output .local/acceptance/phase-1/read.json
uv run wechat-agent probe send --contact test-a --text "测试回复" --confirm-send
uv run wechat-agent prototype --mode dry-run --duration 120 --max-replies 3
~~~

复制 `.env.example` 为本机 `.env`，设置 JSON 白名单及模型密钥。绑定脚本拒绝覆盖已有 profile，也拒绝多个候选账号/联系人；已有 profile 需人工核实后处理。doctor 只读；connect 和读取探针会显式初始化原生路径，允许取钥、校准与 UIA gate。probe send 默认 dry-run；真实固定发送还需 `SEND_MODE=live` 和 `--confirm-send`。prototype live 使用显式 `--mode live`，且必须先有 v4 Replica G1 passed 报告。

测试默认每 15 秒读取、至少 30 秒发送间隔、每分钟至多 2 次，单次最多 3 条后自动停止。先发一条，收到回复再进行下一轮。Ctrl+C 停止；不确定发送在 SQLite 里保留 unknown，重启拒绝继续，人工核实后用 `resolve --ledger --outbox-id <id> --resolution sent或discarded` 记录，不会重新发送。probe 的未知回执使用相同命令但不加 `--ledger`。

原型启动重新建基线，不补发旧历史；上下文按账号代数/会话/运行模式隔离。模型调用不执行工具，失败不自动发送替代话术。正式服务复用同一个 `prototype.sqlite3` 账本并自动迁移，不建立第二份历史。

旧 scripts/probes/windows_read.py 使用 wxauto4，旧 Mac doctor/probe 使用 AX；均保留作研究参考，不作为当前 Windows 路线的安装或验收入口。

## 本地工作台（Phase 3–4）

构建产物已随源码保存，安装 Python 依赖后无需 Node 服务即可运行：

~~~sh
uv sync --locked --extra windows
uv run wechat-agent serve
~~~

手动访问 `http://127.0.0.1:8765`。服务不打开浏览器，不连接微信，worker 初始 stopped，发送模式每次启动强制 dry-run；本次运行覆盖值的配置来源显示 session。设置页显式保存 live 后，再点击开始才会真实运行。`--host` 仅接受回环地址，`--port` 可更改端口。服务与探针共用 DATA_DIR 单实例锁。Ctrl+C 会停止并等待工作线程退出。

- **概览**：真实运行状态、连接状态、模式、开始/暂停/恢复/停止、Agent 时间线、发送记录与 unknown/paused 人工处理。每次开始/恢复最多回复 3 条，随后停止；开始前需本机已有 v4 Replica G1/G2 passed 报告、模型 Key、已绑定白名单与 10 秒以上轮询。
- **会话**：按账号代数和发送模式隔离的会话、分页消息、基线/过滤/处理状态。回复及其输入引用在概览时间线中查看。
- **设置**：校验后原子替换 `.env`，环境变量仍优先，密钥仅返回 configured 状态。空密钥保留，显式清除才删除；DATA_DIR、监听地址/端口与适配器需重启 CLI 修改。运行中不可保存设置，暂停后可保存并重新建立基线。
- **诊断**：显式只读环境/能力检查，不取钥、不热激活；点击开始才执行实际初始化。环境可用不等于已连接。

暂停/停止会废弃迟到模型结果，等待当前调用结束；已经进入发送动作的调用会先落下结果。恢复与重启均不消费旧队列。崩溃中 sending 转 unknown，pending 转 paused，人工核对并标已发/作废后才可再次运行；此操作不重发。账号、原生数据库文件身份或应用账本被替换时拒绝继续，需要人工核实并重新绑定，不能只改账号别名。

`RETENTION_DAYS` 仅控制显式开始时清理过期的 Replica 密钥/快照/校准缓存；账本身份与去重记录、上下文、绑定和验收报告不会自动删除。首次迁移会核对既有 inbox 的账号/代数，再固定当前账号/数据根及原生库文件身份。迁移不提供跨账号复用账本。备份或清理私有数据前须先停止服务。

前端开发与重建（Node 22）：

~~~sh
cd ui
npm ci
npm run typecheck
npm run build
~~~

构建输出到 `src/wechat_reply_agent/web`；提交 UI 改动时同时更新构建产物。Vite dev 用于开发预览；管理操作的 Host/Origin 校验以正式同源服务为准。API、错误格式与人工验收清单见 [API 与工作台说明](docs/api-workbench.md)。不自行打开浏览器做视觉验收。

## 使用与数据边界

默认 dry-run、空白名单和停止状态。只在明确绑定的测试账号/好友上开启 live；有既存草稿、焦点/会话无法确认或发送结果 unknown 时暂停，不自动重发。基座回读仅证明本地出现发出记录，对端收件仍需核对。

安装、依赖与终端操作由助手完成；用户负责微信客户端、手机登录、测试消息、收件确认、界面验收和录像。前端不自行打开页面做视觉检查。

模型 Key、微信密钥、明文快照、消息/截图/校准记录仅留私有 DATA_DIR，不进入 Git、日志或公开交付。远程模型仅接收配置场景需要的输入。低频和旧版本不构成免于账号限制的保证。

本期不提供群聊、多账号并发、朋友圈、批量营销、全量历史导入或长期无人值守承诺。可选业务工具、文件/语音入口按计划选择后实现，未实现时不显示入口。

## 许可证

原创应用代码采用 [PolyForm Noncommercial License 1.0.0](LICENSE)，属于公开源码、非商业许可项目。未授予商业部署、付费产品集成、收费服务或其他商业用途许可；免费提供的商业服务也不自动成为非商业用途。商业使用须另行取得相关权利人的书面许可，具体以许可证正文为准。

内置的 wechatauto-replica 保留 Apache-2.0，已有第三方改编代码与依赖保留原许可证；本项目不能收回第三方原有许可权利。来源、采用状态和补丁见 [复用登记](docs/reuse-register.md) 与 [第三方声明](THIRD_PARTY_NOTICES.md)。

本项目面向本人授权账号与测试对象的个人研究和辅助工作流，不提供诈骗、骚扰、垃圾营销或未经授权获取信息的支持。用途说明不修改标准 LICENSE 条款，公开源码不代表微信官方授权。
