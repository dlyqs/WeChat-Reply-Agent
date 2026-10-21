# WeChat Reply Agent

基于 Windows wechatauto-replica 和 Mac 数据库/原生桥的个人微信 AI 回复应用。在固定桌面环境中完成“绑定好友发消息 → Agent 处理 → 微信回复”，提供本地工作台；知识检索、联系人记忆和最终演示交付尚待后续阶段。

当前已内置固定 Replica 基座，Windows 微信 4.1.15.56 已完成 G1 固定收发验收。最小 LangGraph、DeepSeek 兼容客户端和 SQLite 原型账本已实现，真实三轮 G2 已通过（含上下文追问）；测试 worker 已自动停止。Phase 3 正式迁移/运行控制与 Phase 4 API/工作台已完成自动验证和用户人工验收；知识/长期记忆和最终交付尚未完成。

执行顺序、阶段状态及完成条件见 [执行计划](docs/wechat-agent-plan.md)，当前代码事实见 [开发入口](docs/overview.md)。

Mac Phase 5–6 已在显式降级模式下通过：一个已绑定独立 AX 聊天窗、一次剪贴板粘贴/发送、独立数据库确认，共用正式服务、API、账本和工作台。用户确认独立窗自动切回、两轮正式回复、含换行/emoji/长段落的消息完整收件及保持登录均通过。截图、空草稿、粘贴全文和遮挡检查未验证，严格 Mac G1/G2 未通过。222 项测试及 Mac 干净安装通过；Windows 本次合成回归通过，真实回归按用户选择待验证。worker 已停止，不自动进入 Phase 7。见 [Mac 接入与限制](docs/mac-probe.md)。

## 技术路线与运行范围

| 部分 | 方案 |
| --- | --- |
| 微信基座 | [wechatauto-replica 1.2.7.0](https://github.com/fanyuantaier/wechatauto-replica/tree/d322c4a9b1124228820bab363e5676016f188fc6)，固定源码快照，已作为 third_party 本地 path 依赖内置 |
| Mac 基座 | 固定 Gist revision 的 Reader/SQLCipher 与本地 Swift 桥，MIT 来源和补丁见 third_party/wechat_mac_toolkit |
| 消息读取 | Windows 为 Replica DB/WAL；Mac 为 SQLCipher 只读 DB/WAL、校验已有逐库密钥，首次取钥独立初始化 |
| 回复发送 | Windows UIA/坐标/OCR 与剪贴板，允许 UIA 热激活；Mac 原生独立窗、剪贴板/按键及精确 DB 回读 |
| Agent | LangGraph、可配置模型/人设、多轮上下文；知识检索与联系人记忆留待 Phase 7 |
| 应用 | Python 3.12、FastAPI、SQLite、React/TypeScript/Vite；API/UI 不直接调用第三方 GUI 方法 |
| 环境 | 固定 Windows x64 或 macOS Apple Silicon；每台本机一个账号/好友单聊、独立 DATA_DIR，桌面解锁且绑定窗口可用 |
| 节奏 | 默认 15 秒轮询，可配置；不要求实时、多版本矩阵或全天候运行 |

微信 4.1.15.53 为上游记录的测试组合，可优先验证；本项目本次实际验证的是 4.1.15.56，不要求为适配擅自覆盖当前客户端或聊天数据。OCR 已允许使用，不再强制关闭。详细初始化步骤和 G1 用例见 [Windows 接入](docs/windows-probe.md)。

## 集成与当前可用内容

已实现的链路为：ReplicaAdapter/MacAdapter → 身份/白名单过滤 → SQLite inbox → 会话队列 → Agent → outbox → 原生发送 → 回读/人工核对。应用单独管理游标、状态和失败，不把模型与发送直接放进可自动重试的监听回调。

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
uv run wechat-agent probe send --contact test-a --text "今天过得怎么样？晚上想吃点什么？" --confirm-send
uv run wechat-agent prototype --mode dry-run --duration 120 --max-replies 3
~~~

复制 `.env.example` 为本机 `.env`，设置 JSON 白名单及模型密钥。绑定脚本拒绝覆盖已有 profile，也拒绝多个候选账号/联系人；已有 profile 需人工核实后处理。doctor 只读；Windows connect 和读取探针显式初始化原生路径，允许取钥、校准与 UIA gate。probe send 默认 dry-run；真实固定发送还需 `SEND_MODE=live` 和 `--confirm-send`。prototype live 使用显式 `--mode live`；Windows 要求本机匹配的 G1 报告，旧 v4 报告另需已有匹配账本，Mac 原型门禁见接入说明。

测试默认每 15 秒读取、至少 30 秒发送间隔、每分钟至多 2 次，单次最多 3 条后自动停止。先发一条，收到回复再进行下一轮。Ctrl+C 停止；不确定发送在 SQLite 里保留 unknown，重启拒绝继续，人工核实后用 `resolve --ledger --outbox-id <id> --resolution sent或discarded` 记录，不会重新发送。probe 的未知回执使用相同命令但不加 `--ledger`。

原型启动重新建基线，不补发旧历史；上下文按账号代数/会话/运行模式隔离。模型调用不执行工具，失败不自动发送替代话术。正式服务复用同一个 `prototype.sqlite3` 账本并自动迁移，不建立第二份历史。

旧 scripts/probes/windows_read.py 使用 wxauto4，旧 Mac doctor/probe 使用 AX；均保留作研究参考，不作为当前 Windows 路线的安装或验收入口。

## 本地工作台（Phase 3–4、6）

构建产物已随源码保存，安装 Python 依赖后无需 Node 服务即可运行：

~~~sh
uv sync --locked --extra windows
uv run wechat-agent serve
~~~

手动访问 `http://127.0.0.1:8765`。服务不打开浏览器，不连接微信，worker 初始 stopped，发送模式每次启动强制 dry-run；本次运行覆盖值的配置来源显示 session。设置页显式保存 live 后，再点击开始才会真实运行。`--host` 仅接受回环地址，`--port` 可更改端口。服务与探针共用 DATA_DIR 单实例锁。Ctrl+C 会停止并等待工作线程退出。

Mac 改用 `uv sync --locked --extra mac`，独立安装 SQLCipher、构建 Swift 桥，并配置 `WECHAT_ADAPTER=mac_db`；详见 [Mac 初始化](docs/mac-probe.md)。安装后使用相同 `serve`，平台原生依赖不混装。

- **概览**：实际平台/基座、降级能力、运行/连接状态、模式、启停、Agent 时间线及发送/人工处理。每次开始/恢复最多 3 条；需要模型 Key、绑定白名单与 10 秒以上轮询。Windows 要求本机匹配 G1/G2（v4 另需既有匹配账本）；Mac 视觉模式要求严格 G1/G2，显式降级模式要求本机匹配且用户接受的 Phase 5 降级报告及原生回执。
- **会话**：按账号代数和发送模式隔离的会话、分页消息、基线/过滤/处理状态。回复及其输入引用在概览时间线中查看。
- **设置**：校验后原子替换 `.env`，环境变量仍优先，密钥仅返回 configured 状态。空密钥保留，显式清除才删除；DATA_DIR、监听地址/端口与适配器需重启 CLI 修改。运行中不可保存设置，暂停后可保存并重新建立基线。
- **诊断**：显式只读环境/能力检查，不取钥、不热激活；点击开始才执行实际初始化。环境可用不等于已连接。

暂停/停止会废弃迟到模型结果，等待当前调用结束；已经进入发送动作的调用会先落下结果。恢复与重启均不消费旧队列。崩溃中 sending 转 unknown，pending 转 paused，人工核对并标已发/作废后才可再次运行；此操作不重发。账号、原生数据库文件身份或应用账本被替换时拒绝继续，需要人工核实并重新绑定，不能只改账号别名。

`RETENTION_DAYS` 在显式开始时清理过期平台缓存：Windows 为 Replica 密钥/快照/校准缓存，Mac 仅诊断缓存。Mac 密钥/原生回执、账本身份、去重、上下文、绑定和验收报告不会自动删除。首次迁移核对既有账号/代数，固定当前绑定和原生源库；保留 Windows 原指纹，不跨账号复用账本。清理或备份私有数据前须停止服务。

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

Mac 显式降级模式无法自动检查既存草稿、粘贴全文和遮挡，运行前人工清空绑定独立窗输入框并保持窗口可用；工作台持续显示降级提示。支持 1000 Unicode 标量、LF/emoji/空格，默认模型回复上限 500。自动切回仅针对已经打开的绑定独立窗，不搜索或新建聊天窗。

安装、依赖与终端操作由助手完成；用户负责微信客户端、手机登录、测试消息、收件确认、界面验收和录像。前端不自行打开页面做视觉检查。

模型 Key、微信密钥、明文快照、消息/截图/校准记录仅留私有 DATA_DIR，不进入 Git、日志或公开交付。远程模型仅接收配置场景需要的输入。低频和旧版本不构成免于账号限制的保证。

本期不提供群聊、多账号并发、朋友圈、批量营销、全量历史导入或长期无人值守承诺。可选业务工具、文件/语音入口按计划选择后实现，未实现时不显示入口。

## 许可证

原创应用代码采用 [PolyForm Noncommercial License 1.0.0](LICENSE)，属于公开源码、非商业许可项目。未授予商业部署、付费产品集成、收费服务或其他商业用途许可；免费提供的商业服务也不自动成为非商业用途。商业使用须另行取得相关权利人的书面许可，具体以许可证正文为准。

内置的 wechatauto-replica 保留 Apache-2.0，已有第三方改编代码与依赖保留原许可证；本项目不能收回第三方原有许可权利。来源、采用状态和补丁见 [复用登记](docs/reuse-register.md) 与 [第三方声明](THIRD_PARTY_NOTICES.md)。

本项目面向本人授权账号与测试对象的个人研究和辅助工作流，不提供诈骗、骚扰、垃圾营销或未经授权获取信息的支持。用途说明不修改标准 LICENSE 条款，公开源码不代表微信官方授权。
