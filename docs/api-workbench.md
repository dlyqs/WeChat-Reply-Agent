# 本地 API 与工作台

Phase 3–4 实现说明，2026-10-21。阶段状态以 [主计划](wechat-agent-plan.md) 为准。

运行 `uv run wechat-agent serve`，手动访问 `http://127.0.0.1:8765`。监听仅限 loopback，不打开浏览器、不初始化微信。前端构建产物在 Python 包中，无需 Node 开发服务器。服务启动时固定 stopped/dry-run；配置返回的 `session` 来源表示本次启动覆盖。

## 请求约定

所有路径与前端同源，Host 必须是当前端口的 `127.0.0.1`、`localhost` 或 `[::1]`。Origin 存在时也必须匹配上述源；写请求必须带同源 Origin、`X-WeChat-Agent: 1`、`Content-Type: application/json`，JSON 请求体不超过 64 KiB。无 CORS 放行，不支持反向代理或远程访问。命令行调用也需要这些头。

错误统一为 `{code, message, trace_id}`，不返回输入值、异常堆栈、完整模型 prompt、密钥、上游原始对象或隐藏思维链。会话正文和模型最终回复仅在专用记录接口中返回给本机工作台。

| 方法 / 路径 | 内容 |
| --- | --- |
| GET /api/health | 应用可用性、运行摘要；不检查/初始化原生微信 |
| GET /api/runtime | stopped/starting/running/paused/degraded/stopping、原因、连接、模式、代数与本轮计数 |
| POST /api/runtime/start | 请求显式初始化、建立基线并开始；异步返回 starting，失败转 degraded |
| POST /api/runtime/pause | 废弃迟到结果，等待当前调用结束并暂停 |
| POST /api/runtime/resume | 从 paused 重新连接与建立基线；不恢复旧队列 |
| POST /api/runtime/stop | 等待当前调用结束并停止 |
| GET /api/conversations | limit（1–100，默认50）、offset；返回 items/limit/offset |
| GET /api/conversations/{id}/messages | 必需 scope，按观察顺序倒序；limit/offset 同上 |
| GET /api/runs | 最近执行的分页摘要，含 trace_id、输入引用、最终回复、原因和耗时 |
| GET /api/runs/{trace_id} | 单次执行记录；不存在返回 404 |
| GET /api/outbox | 分页回复意图、结果和人工处理状态；不暴露完整基座回执 |
| POST /api/outbox/{id}/resolve | `{resolution: "sent"或"discarded"}`，仅停止/暂停/降级时记录人工结果，不重发 |
| GET /api/settings | values/sources/readonly；密钥仅 llm_api_key_configured |
| PATCH /api/settings | 变更字段；密钥空值保留，clear_llm_api_key=true 显式清除 |
| POST /api/diagnostics | 停止/暂停/降级时只读环境/能力检查，不取钥、不热激活 |

运行与诊断请求可以使用空对象 `{}`。工作台每 3 秒读取状态，消息/会话每页 30 条，概览展示最近 50 条发送与 Agent 记录；API 支持继续分页。会话 id 必须配合 scope 使用，scope 隔离账号代数和发送模式。

## 数据与运行控制

正式 Ledger 使用原来的 `DATA_DIR/prototype.sqlite3`，名称为兼容旧 CLI 保留。`storage/prototype.py` 仅导出同一个 Ledger 类。迁移保留 inbox、原生消息身份、outbox 输入唯一约束、游标、上下文和运行记录，并加入 contacts/conversations/messages、元数据绑定、状态索引与运行状态。messages 状态随 inbox 同事务更新。

服务与 connect/probe/prototype 共用跨平台 `probe.lock`。只有一个专用线程执行连接、读取、发送和显式诊断；模型结果先落账本，再经过运行代数与发送闸门。暂停/停止可能等待当前模型超时或原生发送返回，UI 显示“正在处理”。停止响应返回后不会继续操作微信，退出会 join 线程。

启动恢复将 pending 输入置 paused，将 pending outbox 置 paused，将 sending 置 unknown；未人工处理的 paused/unknown outbox 会阻止开始。标已发/作废不会自动重试，也不会把人工结果冒充本地数据库发送证据。自动每轮最多 3 条，发送至少间隔 30 秒、每分钟至多 2 次。

首次正式运行核对旧 inbox 的账号/代数，再固定 profile 的原生账号、self_username、数据根与现有数据库文件身份；后续变化被拒绝。新增/替换分片可能需要重新人工核实绑定；不宣称支持热换数据库。运行中及模型返回后发送前都检查应用账本与已绑定原生库文件身份。

配置以环境变量 > `.env` > 默认值读取。保存先校验，在 `.settings-private/` 中以当前用户权限暂存，fsync 后原子替换 `.env`；失败保留旧文件与内存配置。新配置仅在下次开始时用于 adapter/model。秘密不会进入 VITE_*、日志或 GET 响应。账号及数据库路径属于本机设置，可由设置页显示，不能作为公开报告内容。

`RETENTION_DAYS` 控制显式开始时清理 DATA_DIR/replica 下过期缓存文件，保留新文件，不跟随逃逸目录的链接；不删除账本、身份、去重、profile 和 G1/G2 报告。过期密钥/校准缓存删除后会在显式连接流程重建。数据库、上下文和验收报告的人工清理需先停止服务。

## 自动验证与人工验收

`uv run pytest -q` 包含配置优先级/原子失败/密钥、v1 迁移、账号变化、队列溢出、跨平台锁、暂停迟到结果、重启 unknown、API 来源与错误等离线用例。Fake adapter/model 仅用于这些测试；不会被 CLI 当成微信。前端运行 `npm ci && npm run build` 完成类型检查及构建。

`uv run python scripts/acceptance/phase34_install_check.py` 从 sdist 提取到私有干净目录，按锁安装 Windows extra，再用正式 CLI 启动停止状态的 HTTP 服务，验证页面、静态资源、API 和掩码；不打开浏览器、不连接/发送微信。结果写 `.local/acceptance/phase-3/install-check.json`。

以下需要用户人工验收，本次自动检查不能将其标 passed：

1. 在概览/会话/设置间切换，检查桌面布局、空态、错误与模式提示。
2. 保存配置、只读诊断，核对有效值与来源；空密钥应保留，清除行为明确。
3. 在绑定测试好友场景开始 dry-run，核对真实微信连接状态及来信记录；暂停/恢复/停止与界面同步。
4. 如需 live，显式保存 live、开始，再由测试好友发新消息并核对收件；unknown 时先核实再标已发/作废。

本次没有打开页面、执行 UI 自动化或重新发送微信消息。既有 G1/G2 仍是原 Phase 1–2 证据，不能替代正式工作台的人体验收。
