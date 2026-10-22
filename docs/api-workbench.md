# 本地 API 与工作台

Phase 3–4、6–7 实现说明，2026-10-22。阶段状态以 [主计划](wechat-agent-plan.md) 为准。

运行 `uv run wechat-agent serve`，手动访问 `http://127.0.0.1:8765`。监听仅限 loopback，不打开浏览器、不初始化微信。前端构建产物在 Python 包中，无需 Node 开发服务器。服务启动时固定 stopped/dry-run；配置返回的 `session` 来源表示本次启动覆盖。

## 请求约定

所有路径与前端同源，Host 必须是当前端口的 `127.0.0.1`、`localhost` 或 `[::1]`。Origin 存在时也必须匹配上述源；写请求必须带同源 Origin、`X-WeChat-Agent: 1`、`Content-Type: application/json`，JSON 请求体不超过 64 KiB。无 CORS 放行，不支持反向代理或远程访问。命令行调用也需要这些头。

错误统一为 `{code, message, trace_id}`，不返回输入值、异常堆栈、完整模型 prompt、密钥、上游原始对象或隐藏思维链。会话正文和模型最终回复仅在专用记录接口中返回给本机工作台。

| 方法 / 路径 | 内容 |
| --- | --- |
| GET /api/health | 应用可用性、实际基座及运行摘要；不检查/初始化原生微信 |
| GET /api/runtime | stopped/starting/running/paused/degraded/stopping、原因、连接、模式、代数、本轮计数与平台能力 |
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
| GET /api/settings | values/sources/readonly/inactive/platform；密钥仅 llm_api_key_configured |
| PATCH /api/settings | 变更字段；密钥空值保留，clear_llm_api_key=true 显式清除 |
| POST /api/diagnostics | 停止/暂停/降级时只读平台/环境/能力与权限检查，不取钥、不热激活 |
| GET /api/knowledge/documents | 知识文件元数据，limit/offset 分页；不返回磁盘路径 |
| POST /api/knowledge/documents | `{name, content}`，UTF-8 TXT/Markdown；相同内容返回 duplicate；每份最多 48,000 字节 |
| DELETE /api/knowledge/documents/{id} | 删除文件及 FTS5 片段，事务清除旧会话上下文，历史执行记录保留 |
| GET /api/knowledge/search?q=... | 最多 3 个真实来源片段，最多 2,000 字查询；未命中返回空 items |
| GET /api/memories/contacts | 已持久化绑定的联系人及范围，首次开始后出现；不连接微信 |
| GET /api/memories?scope=...&contact=... | 限指定已绑定联系人，最多 20 条长期偏好 |
| PUT /api/memories | `{scope, contact, key, value}` 新增/更正偏好；key 最多40字，value最多200字 |
| DELETE /api/memories?scope=...&contact=...&key=... | 忘记偏好并清除该会话旧上下文；不删除历史收发证据 |

运行与诊断请求可以使用空对象 `{}`。工作台每 3 秒读取状态，消息/会话每页 30 条，概览展示最近 50 条发送与 Agent 记录；API 支持继续分页。会话 id 必须配合 scope 使用，scope 隔离账号代数和发送模式。

## 数据与运行控制

正式 Ledger 使用原来的 `DATA_DIR/prototype.sqlite3`，名称为兼容旧 CLI 保留。`storage/prototype.py` 仅导出同一个 Ledger 类。迁移保留 inbox、原生消息身份、outbox 输入唯一约束、游标、上下文和运行记录，并加入 contacts/conversations/messages、元数据绑定、状态索引与运行状态。messages 状态随 inbox 同事务更新。

服务与 connect/probe/prototype 共用跨平台 `probe.lock`。只有一个专用线程执行连接、读取、发送和显式诊断；模型结果先落账本，再经过运行代数与发送闸门。暂停/停止可能等待当前模型超时或原生发送返回，UI 显示“正在处理”。停止响应返回后不会继续操作微信，退出会 join 线程。

启动恢复将 pending 输入置 paused，将 pending outbox 置 paused，将 sending 置 unknown；未人工处理的 paused/unknown outbox 会阻止开始。标已发/作废不会自动重试，也不会把人工结果冒充本地数据库发送证据。自动每轮最多 3 条，发送至少间隔 30 秒、每分钟至多 2 次。

正式服务通过适配器 RuntimeBinding 核对账号/代数、原生库文件身份与平台，保留 Windows Phase 3 原指纹和旧账本。运行中及模型返回后发送前检查应用账本与源文件/盐变化；新增/替换分片可能需要重新核实绑定，不宣称热换库。睡眠/时钟异常间隔停止并要求重连。

Windows v5 报告核验基座 revision/版本/绑定；原 v4 报告只能结合已有匹配的 Phase 3 本机账本识别，原报告不改写。Mac 默认视觉通道要求严格 G1/G2；显式降级通道核对本机版本、来源、绑定、用户已接受的 Phase 5 降级报告和原生固定发送回执。未决原生操作会在模型调用前阻止开始。人工处理先同步 Mac 原生 journal，再记录应用 outbox，仅记结论，不重发。

配置以环境变量 > `.env` > 默认值读取。保存先校验，在 `.settings-private/` 中以当前用户权限暂存，fsync 后原子替换 `.env`；失败保留旧文件与内存配置。新配置仅在下次开始时用于 adapter/model。秘密不会进入 VITE_*、日志或 GET 响应。账号及数据库路径属于本机设置，可由设置页显示，不能作为公开报告内容。

`RETENTION_DAYS` 控制显式开始时清理平台缓存，不跟随逃逸目录链接：Windows 清理 `DATA_DIR/replica` 的过期缓存；Mac 仅清理 `DATA_DIR/macos/diagnostics`，保留密钥、bootstrap 状态和发送 journal。不删除账本、身份、去重、profile 或验收报告。数据库、上下文和报告的人工清理需先停止服务。

## 自动验证与人工验收

`uv run pytest -q` 包含配置优先级/原子失败/密钥、v1 迁移、账号变化、队列溢出、跨平台锁、暂停迟到结果、重启 unknown、API 来源与错误等离线用例。Fake adapter/model 仅用于这些测试；不会被 CLI 当成微信。前端运行 `npm ci && npm run build` 完成类型检查及构建。

`uv run python scripts/acceptance/phase34_install_check.py` 从 sdist 提取到私有干净目录，按锁安装 Windows extra，再用正式 CLI 启动停止状态的 HTTP 服务，验证页面、静态资源、API 和掩码；不打开浏览器、不连接/发送微信。结果写 `.local/acceptance/phase-3/install-check.json`。

以下为人工验收清单；2026-10-21 用户已确认全部通过，结果依据用户人工操作与对端核对，自动检查不替代这些证据：

1. 在概览/会话/设置间切换，检查桌面布局、空态、错误与模式提示。
2. 保存配置、只读诊断，核对有效值与来源；空密钥应保留，清除行为明确。
3. 在绑定测试好友场景开始 dry-run，核对真实微信连接状态及来信记录；暂停/恢复/停止与界面同步。
4. 如需 live，显式保存 live、开始，再由测试好友发新消息并核对收件；unknown 时先核实再标已发/作废。

本次没有打开页面、执行 UI 自动化或重新发送微信消息。既有 G1/G2 仍是原 Phase 1–2 证据，不能替代正式工作台的人体验收。

人工验收完成记录（2026-10-21）：用户确认启动页面、配置/诊断、dry-run 完整流程、暂停/恢复/停止、一次 live 实际回复与对端收件，以及退出重启后 stopped/dry-run 和历史保留均通过。Phase 4 已完成。未要求刻意制造 unknown；unknown 人工处理与停发边界继续以既有离线用例为验证依据。本次授权范围止于 Phase 4。

## Mac Phase 6 验收

设置 `WECHAT_ADAPTER=mac_db` 后使用同一 `serve` 入口。概览显示 macOS/mac_db、文本能力及 `ui_checks_degraded` 提示；Mac 不适用的 Windows UIA/OCR 开关禁用，设置 API 也拒绝修改。诊断展示实际辅助功能/屏幕录制/锁屏状态，环境可用与已经连接分别展示。

2026-10-22 用户确认 Mac/降级提示、配置/诊断、会话/历史、dry-run/live、暂停/恢复/停止全部通过；从其他会话切回已打开的绑定独立窗、两轮正式回复、两条含 LF/emoji/长段落的固定消息完整收件及保持登录也确认通过。自动检查包括 222 项 Python 测试、前端类型/构建、Swift 自检与 Mac 干净源码安装；未自行打开页面或执行 UI 自动化。

`scripts/acceptance/phase6_install_check.py --output <全新私有目录>` 按本机平台安装对应 extra，验证 CLI、Swift（仅 Mac）、stopped/dry-run HTTP 与静态资源，不连接或发送微信。Mac 已通过；Windows 本次原生安装/收发按用户选择待验证，合成兼容回归通过。严格 Mac 视觉 G1/G2 未通过。worker 已停止，服务每次重启强制 dry-run；后续阶段未启动。见 [Mac 接入](mac-probe.md)。

## Phase 7 知识与记忆

最初的“知识与记忆”入口现拆分为知识库和联系人记忆。导入/删除知识、保存/忘记偏好只允许 stopped/paused/degraded，
运行时返回 `stop_before_content_change`；读接口可在运行中查看。DELETE 写请求同样需要来源头及 JSON `{}`。
文件只读取用户选择的 UTF-8 内容，通过 JSON 传入；不接受任意服务端文件路径。总量最多 200 份/8 MB，
单份 600 字分块并重叠 80 字，jieba 中文检索，Agent 每轮最多取 3 个来源、每个最多 300 字的相关摘录，
再按总输入预算丢弃旧历史/知识/偏好；预算不足为 `budget_omitted`，无命中为 `no_hits`。
实际加入模型的来源写入 AgentResult 与执行记录；默认不附文件名到微信正文，可配置 `reply_show_sources`。不接受模型伪造的来源标记。
无命中提示由模型系统约束明确要求，实际回复效果保留用户验证。

记忆保存在同一个私有 SQLite v3，范围包括账号代数、账号引用、发送模式及联系人。
普通聊天不自动抽取；整条明确指令为“记住我的偏好：饮品=乌龙茶”“更正我的偏好：饮品=白茶”
或“忘记我的偏好：饮品”。每轮最多 4 个变更，仅对合法输入、有效回复及当前运行代数提交；
暂停后的迟到模型、失败、重复输入不写入。偏好与 AgentRun/outbox 同事务落库；发送 unknown 不回滚已明确保存的偏好。
图只暂存变更，不直接写入或执行任意工具。更正/忘记清除该联系人短期上下文，删除知识清除全部短期上下文，
避免旧答案重新影响模型；历史收发/执行证据仍保留在本机管理界面。

前端静态类型/构建、真实 API CRUD 和模型输入/预算/来源/隔离测试通过；两平台用户界面与微信回复尚未验收。
Phase 9 的离线回放、打包及最终人工步骤见 [交付清单](delivery-checklist.md)。

## Reply Studio 体验优化与扩展 API

工作台分为工作概览、会话与记录、知识库、联系人记忆和设置；详见 [用户指南](workbench-guide.md)。
新增接口沿用同源/写请求头/JSON限制，不暴露密钥，也不因页面加载而连接微信或请求模型。

| 方法 / 路径 | 行为 |
| --- | --- |
| GET /api/setup | 只读已有本机绑定文件，返回是否就绪及已确认好友别名；不取钥/激活/连接 |
| GET /api/dashboard | 当前可见消息/回复/执行数、偏好数、未决发送及平均模型耗时 |
| GET /api/agent/presets | 完整日常/跨境产品客服提示词及推荐预算，不含本机密钥 |
| POST /api/model/test | 使用当前或草稿地址/模型/密钥发送一次限时连接测试；不保存配置、不操作微信 |
| GET/POST /api/knowledge/bases | 列表/新建知识库，含真实文档数、容量、启用状态及示例测试问题 |
| PATCH/DELETE /api/knowledge/bases/{id} | 改名称/描述/启用状态或删除；默认 personal 库保留，停用/删除清空旧上下文 |
| POST /api/knowledge/demo | 显式恢复并启用北线咖啡内置资料；不会改写密钥/提示词或开启真实发送 |
| GET /api/knowledge/documents/{id} | 返回按原始重叠边界还原的文档正文 |
| POST /api/knowledge/documents | 原 `{name,content}` 增加可选 `base_id`，默认 personal；按库关联，同一内容可被多库共用 |
| DELETE /api/knowledge/documents/{id}?base_id=... | 只移除此知识库的关联；无其他库使用时才删除原文及FTS片段；省略base_id沿用旧全局删除语义 |
| GET /api/knowledge/documents 或 /search | 支持可选 base_id；检索只采用已启用库，价钱/price 补充价格同义词，摘录定位最相关窗口 |
| POST /api/agent/preview | `{question,base_id,history?}` 使用同一个 LangGraph 和真实配置模型试答；历史最多12条仅允许user/assistant；不读取联系人记忆、不落真实inbox/outbox/run、不发送微信 |
| POST /api/history/clear | `{confirmation:"清除",scope?,conversation?,forget_memories:false}` 清全部或指定范围，必须scope/conversation同时提供 |
| GET /api/outbox | 新增可选scope/conversation过滤，供会话页独立分页 |

SQLite v4 增量新增知识库、文档关联及历史清除标识表；旧文档归入个人库，不改原生ID。
首次准备5份默认停用的虚构示例，删除后不因重启自动恢复；明确恢复才重新添加。
演示资料和完整提示词随 wheel/sdist/源码包内置。新默认输入预算为8192；既有 `.env` 的显式值保持优先，选择客服预设时会把推荐预算放进待保存草稿。

清除只允许工作线程已结束的 stopped/paused/degraded 状态，原子清除正文/来源/短期上下文并隐藏旧行；可选忘记长期偏好。
保留来源事件ID、outbox/input唯一关系、游标、账号绑定、尝试时间与人工处理结论，重复读取旧事件不会补发。
有 pending/sending/unknown/paused 且未人工处理的意图时拒绝清除；不改原生操作journal/探针回执。
此管理操作只校验应用账本文件身份，不依赖微信源库仍然存在，因此微信清空聊天或断开后仍可管理本地记录。
