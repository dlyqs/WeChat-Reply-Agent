# 个人微信 AI 回复 Agent 实施计划

创建日期：2026-10-21（Asia/Shanghai）  
计划版本：v2；按用户要求，在任何实现开始前细化为 18 个可直接实施和验收的阶段。  
交付工作区：`/Users/git_local/WeChat-Reply-Agent`  
流程依据：[dev-goal-workflow-meta-skill](/Users/git_local/dev-workflow-skill/SKILL.md)

```text
execution mode: auto_until
automatic start phase: 1
automatic stop phase: 3
conversation relay: off
plan review: accepted for Phase 1–3 by user instruction
execution authorization: 用户 2026-10-21「请自动完成 phase1-3」；保留 G1/G2 人工关口
```

本文件是后续“继续”“执行 Phase X”的唯一阶段状态来源；代码导航见 [overview.md](overview.md)。现已授权自动执行 Phase 1–3，按下方主表推进；G1/G2 人工验收不可跳过，没有真实微信验收结论。

**执行承诺：本计划覆盖最终答卷所需的全部开发、集成、测试、文档、启动打包与视频交付。每阶段按已列任务和用例直接实施；不得以“搭好框架”“仅完成 mock”“某个大模块后续另行规划”作为完成。全部 18 阶段的必需验收通过后，产物就是可提交答案。实施中只允许小范围技术修正和失败用例修复；若需要改变产品范围或已验收契约，明确报告阻塞，不静默重开大计划。**

## 1. 目标与范围

目标是在 macOS 上运行一个个人微信自动回复应用：白名单好友向当前个人号发送文本，应用识别会话和上下文，选择直接回答、检索内部知识或调用受限业务接口，再以该个人号回复。另提供简约的本地管理工作台、可复现测试、人工验收证据和演示视频。

语义已按前文归一：本题的核心是“替个人号回复好友”，不是“本人给微信 ClawBot 发消息”。单聊是必须交付范围；群聊不进入本期验收。语音、文件按原题交付应用设计和可测试处理边界，不预先承诺所有微信版本都能自动获取原始附件。

范围内：

- 白名单、垃圾/空消息/系统消息过滤、排除本人消息、去重、连续消息合并、按会话串行处理。
- LLM 多轮聊天、人格化但简洁的回复、知识问答和两个受限示例业务工具。
- 短期上下文、跨重启的长期偏好/事实、记忆隔离、更新和删除。
- 本地 Web 工作台、状态和日志可见、暂停与恢复、配置解耦。
- 明确的支持版本矩阵、故障处理、README、录像脚本、视频和代码交付。

本期不做：批量营销/加好友/朋友圈、支付等真实业务写入、群机器人、多账号并发、云托管、App Store 分发、读取既有全部聊天数据库或进程内存、Hook/协议逆向、为适配擅自降级微信或修改系统保护。ClawBot 只能作为将来另一种渠道，不得替换本题的好友回复验收。

## 2. 可行性、约束与待采集信息

### 2.1 可行性判断

Agent、知识检索、持久化和本地 UI 可采用成熟组件，工程可行性较高。最大不确定性是 Mac 微信的消息读取与发送：Accessibility 树、语言、窗口状态和发行渠道会变化；OCR 也可能误判方向或会话。先验证微信通道，再投入完整产品实现。

目标是“在明确测试过的多版本组合上稳定运行”，不能声称兼容所有微信版本。若用户无法提供第二个版本环境，兼容性要求保持未验收；架构可扩展、离线回归通过均不能替代实机证据。若通道原型在目标环境不可用，应停在原型阶段讨论范围或渠道调整，而不是把演示包装成完成。

### 2.2 必须遵守的协作边界

1. 助手不得自行拉起页面、启动浏览器做视觉检查，也不得使用 Playwright、浏览器自动验收 skill 或 CUA 绕过限制；前端仅做类型检查、构建、必要的组件逻辑验证和静态检查。
2. 2026-10-21 用户更新分工：安装和终端命令由助手执行，包括已授权范围的诊断/探针；用户负责打开微信、手机登录、界面操作、实际收发效果核对、多版本验证与录屏。真实发送仍须明确测试会话和发送授权，G1/G2 证据不可跳过。
3. 不使用 GitNexus；不创建额外会话、自动 relay 或子 agent。需要这些能力时另按用户明确指令处理。
4. 人工操作项要有命令/步骤、预期、结果记录和失败出口；缺少凭据、权限或环境时标记未验证，不反复尝试绕过。
5. 所有密钥、服务地址、模型、Token 预算与运行限制从后端 `.env`/环境变量加载；前端不得出现密钥、返回已有密钥或使用 `VITE_*` 承载敏感配置。
6. 默认 `dry-run`；默认白名单为空且停发。真实收发必须由用户在本机明确启动并配置测试白名单。
7. 工作台不冒充已经运行：离线样例、dry-run 和真实连接状态必须清楚可辨。

**2026-10-21 用户新增技术偏好**：最终实现不要使用 OCR，原因是效率和准确性。已停止待执行的视觉探针；已有 OCR 代码仅保留为诊断研究记录，不作为最终通道。当前转为核查无 OCR 的文本读取和窗口控制。Computer use 的截图推理不能被当作已解决结构化消息获取；切换 Windows worker 或采用本地数据库/进程访问属于原边界变更，仅比较和说明，不自行实施。G1/G2 及自动授权 1–3 保持。

### 2.3 Phase 1 采集，不阻塞本次计划的信息

用户提供或自行生成并审阅：macOS 版本、CPU 架构、微信准确版本/官网或 App Store/界面语言、是否有两位测试联系人、可用的第二版本环境。不要自动安装/切换微信版本。

LLM 默认采用可配置的兼容接口，模型和服务商由用户在本地填写；不需要向聊天粘贴 Key。知识和业务样例使用虚构数据，交付时明确其示例性质。时间预算尚未给定，阶段顺序按依赖确定，不承诺未知环境下的工期。

## 3. 技术路线与复用清单

正式实现默认选择：Python 3.12、FastAPI、LangGraph、SQLite（含 FTS5）、React + TypeScript + Vite + Tailwind CSS + shadcn/ui。以兼容依赖的锁文件为最终安装依据；Phase 1/3 验证支持架构。后端和微信 worker 运行于登录的 Mac 用户会话，前端为本地工作台；不把 GUI worker 放进 Docker、无桌面守护进程或云服务器。

应用链路：微信适配器 → 规范化事件 → 确定性过滤/去重 → 会话队列 → Agent → 知识/工具/记忆 → 发件箱 → 同一会话复核 → 发送 → 结果确认。

| 部分 | 复用来源与具体位置 | 采用方式 | 必须自己补齐或核实 |
| --- | --- | --- | --- |
| Mac 视觉接入候选 A | [wechat-mac-rpa](https://github.com/wq19901103wq/wechat-mac-rpa)：`src/capture/`、`src/ocr/`、`src/layout/`、`src/action/` | 优先提取最小截图/OCR/发送能力；不整体搬入其 Agent、后台和历史数据功能 | 识别方向、会话匹配、窗口限制、延迟、发送确认、真实版本验收 |
| Mac AX 接入候选 B | [WeChat-MCP](https://github.com/BiboyQG/WeChat-MCP)：`src/wechat_mcp/wechat_accessibility.py`、`fetch_messages_by_chat_utils.py`、`reply_to_messages_by_chat_utils.py` | 在用户目标环境确实暴露 AX 控件时，复用其薄封装；可直接适配 Python 接口，不为使用 MCP 而引入额外服务 | 主动轮询、会话识别、幂等、后台生命周期；核对 [#8](https://github.com/BiboyQG/WeChat-MCP/issues/8)、[#17](https://github.com/BiboyQG/WeChat-MCP/issues/17) |
| Agent 状态机 | [LangGraph](https://github.com/langchain-ai/langgraph)、[Memory 文档](https://docs.langchain.com/oss/python/langgraph/add-memory) | 依赖库；使用 graph、工具节点和 SQLite checkpointer，避免自写 Agent 循环 | 本题路由、终止条件、会话隔离、超时和预算 |
| 配置与接口校验 | Pydantic Settings、Pydantic、FastAPI、HTTPX | 依赖库 | `.env` 加载优先级、校验、脱敏、受限工具契约 |
| 知识处理 | `langchain-text-splitters`、`jieba`、SQLite FTS5；文件解析库 | 复用分块与中文分词后建立小规模全文索引，检索返回来源 | 验证中文短语/订单术语召回、无命中、更新、隔离和引用；本期不强制新增向量服务 |
| 长期记忆 | SQLite + LangGraph store/持久化接口设计 | 复用存储机制，事实提取和更新策略保持小而可解释 | 按联系人隔离、冲突更新、TTL、删除、跨重启验证；checkpoint 不等于长期记忆 |
| UI | shadcn/ui、Radix、Lucide、Tailwind CSS | 复用表单、对话框、表格、图标；以统一 token 组合 | 页面信息结构、交互状态、无障碍、用户人工视觉验收 |
| 附件扩展 | `pypdf`、`python-docx` 等解析库；可替换 ASR 接口 | 使用合成样例验证内容处理；避免自写解析器 | 微信附件获取能力必须另验证；本期语音最低交付为完整设计与转写事件入口 |
| 稳定性与验证 | pytest、HTTPX 测试客户端、ruff、tsc、Vite | 离线回放、模拟接口、静态验证 | 人工实机结果和版本矩阵，不能由 mock 代替 |
| 其他成品参考 | [CowAgent](https://github.com/zhayujie/CowAgent) 的 channel/工具/记忆边界 | 架构参考，不默认导入整个运行框架 | 其当前 ClawBot 渠道不满足代回好友；避免第二套 Agent 基座 |

复用纪律：Phase 1 创建 `docs/reuse-register.md`，记录来源 URL、确切 commit SHA/包版本、许可证、采用的文件/符号、改动和验证范围。对复制/改编代码保留声明并写入 `THIRD_PARTY_NOTICES.md`，依赖按许可证要求处理。不得把上游历史或作者功能当成自己的贡献。

调研已查得两个文件的来源定位点：RPA `message_sender.py` 最近文件变更为 `0c129a5bb255a6640694c73fcdf178e7c3dda49b`；MCP `wechat_accessibility.py` 为 `5ffd0b4d80655bc5e284b3cea06a0a7b0278fa57`。它们仅用于追溯，不代表整仓最佳版本或已验证适配；真正采用前仍要审阅选定快照、所有相关文件和许可证。RPA 近期 Star 图表自动提交不能作为功能维护证据。

候选选择遵循证据：A 为首选验证对象，B 为备选；如果 B 在当前环境明显更准确且更快，可以选择 B。每个版本配置只启用一个明确适配器，识别不确定时停发，不让两个识别器各自发送。仅在验证需要时增加局部 fallback，避免同时维护两套完整接入。

## 4. 本轮冻结的交付规格

### 4.1 开发和完成口径

- 原型直接建立在最终 `src/wechat_reply_agent/` 包内，复用正式配置、事件、适配器与存储接口，不另建一套必然丢弃的系统。G1/G2 通过前仍不铺完整产品。
- 技术栈、运行形态、页面、业务示例和接口在本轮确定。后续直接实现与验收；`architecture.md`、`ui-design.md` 是同步实现的说明，不是需要再次审批的大模块计划。
- 原型事实只决定视觉/AX 适配器和版本 profile；模型由 `.env` 选择。这些在 Phase 2 落定，不改变后续模块边界。
- 本地导入 TXT、Markdown、文本型 PDF、DOCX 并处理其正文为必做；扫描/加密 PDF 返回明确不支持结果，不留“预算内再考虑”的必做功能。
- 原题仅要求语音/文件的应用思路。语音必做完整设计、类型契约、转写文本入口和失败测试；原生微信音频获取、真实 ASR 服务、视频理解不在本期必须范围。能力标签如实展示，这是范围定义，不是中途待规划模块。
- 群聊、多账号、全量历史、云托管、向量数据库、原生安装器不在本期；最终是 Mac 本地源码启动交付，不把这些作为最后欠缺的开发。
- 每阶段交付可验证增量：代码、必要测试、README 增量、复用登记和真实提交。内部模块用自动测试验收；明列的真实微信、模型效果和 UI 视觉由用户当阶段验收，不能全部后移。
- 下文 CLI/API/文件为冻结的实施目标，当前尚未创建；该阶段完成后必须真实存在。命令中 `<...>` 由用户在本机替换。

### 4.2 运行、配置和状态契约

最终唯一应用入口为 `uv run wechat-agent serve`，同源提供本地工作台与 API，worker 初始停止、模式默认 `dry-run`。Python 使用 `uv.lock`，前端使用 `ui/package-lock.json` 和兼容的 Node.js 22。按 2026-10-21 更新分工，终端命令由助手执行；用户负责微信界面、手机登录和真实效果核对。

| CLI 契约 | 固定行为 |
| --- | --- |
| `doctor --output <json>` | 只读诊断环境/权限/依赖，不发送、不修改系统设置 |
| `probe read --contact <alias> --limit 5 --output <json>` | 读取指定测试会话和方向，原文留本机，公开报告仅摘要 |
| `probe send --contact <alias> --text <text> --confirm-send` | 显式发送参数、非空白名单、复核会话；不确定则停发 |
| `prototype --mode <mode> --duration <seconds>` | mode 为 dry-run 或 live；Phase 2 最小循环，live 必须显式选择和本地配置 |
| `serve --host 127.0.0.1 --port <port>` | 唯一实例锁、同源静态 UI/API，不自动开浏览器 |
| `replay --suite <name> --output <json>` | 合成数据/假适配器，不需要微信或 Key，结果标 `offline` |
| `verify --output <json>`、`package --video <path>` | 就绪检查/打包，不启动微信或页面、不上传/推送 |

配置分组固定：

| 分组 | `.env` 字段 |
| --- | --- |
| 模型 | `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL/LLM_TIMEOUT_SECONDS/LLM_MAX_INPUT_TOKENS/LLM_MAX_OUTPUT_TOKENS/LLM_MAX_CALLS_PER_TURN` |
| 接入 | `WECHAT_ADAPTER/WECHAT_PROFILE/WECHAT_ACCOUNT_REF/WECHAT_ALLOWLIST/POLL_INTERVAL_SECONDS` |
| 运行 | `SEND_MODE/COALESCE_WINDOW_MS/QUEUE_MAX_SIZE/MAX_SENDS_PER_MINUTE/CONFIRMATION_TTL_SECONDS` |
| 存储 | `DATA_DIR/RETENTION_DAYS/MEMORY_CONTEXT_TOKENS/UPLOAD_MAX_BYTES/PARSE_TIMEOUT_SECONDS` |
| 服务 | `APP_HOST/APP_PORT/APP_ENV/LOCAL_DEV_ORIGIN` 与示例业务接口配置；启用远端能力才增加对应 Key/Token |

Settings 定义默认值并列入 `.env.example`，密钥仅空占位；GUI 接入不杜撰一个必填 IM Token。优先级为进程环境 > `.env` > 默认值；无 Key 仍可进入诊断/UI，使用真实模型时才校验。保存先校验再原子替换，环境覆盖项只读且显示来源，失败不损坏旧文件。API 只回掩码和 configured；密钥空输入表示保留、显式清除才删除，不把 `******` 当 Key 写回。

运行状态为 `stopped/starting/running/paused/degraded/stopping`，模式另为 `dry-run/live`。暂停增加运行代数，使旧队列和迟到模型结果失效；恢复不自动重发旧队列。切换到 live 要在停止状态、健康且白名单已解析后由用户重新开始。已发生的不可撤销按键可能完成，必须记录此边界。

### 4.3 跨模块数据和存储契约

| 对象 | 必需字段/行为 |
| --- | --- |
| `ConversationRef` | 本地 account_ref/conversation_id/contact_alias、profile、身份依据/可信度；昵称不能冒充原生 wxid |
| `InboundEvent` | event_id/conversation_id/source_message_id?/occurrence_ref/direction/type/text?/attachment_ref?/observed_at/trace_id/confidence；方向 incoming/outgoing/system/unknown，未知不可自动回复 |
| `AgentResult` | reply_text/intent/citations/tool_run_refs/memory_changes/confirmation_ref?/usage/outcome；区分回复、待确认、无须回复和错误 |
| `SendIntent` | outbox_id/conversation_id/input_event_refs/reply_text/run_generation/mode/status；一组输入唯一发送意图 |
| `SendResult` | verified_sent/not_sent/unknown、确认依据/错误；按回车不等于对端送达 |
| `AdapterCapabilities` | profile、消息类型、原始附件获取、身份/发送确认能力和窗口条件，供 doctor/UI/README 共用 |
| `WechatAdapter` | health()、poll_events(cursor)、resolve_conversation(alias)、send_text(intent)；Mac 原生依赖懒加载，离线使用 FakeAdapter |

SQLite 使用参数化 SQL、外键、事务、WAL 和 schema migration。LangGraph checkpoint 使用独立受控连接/库，不改第三方 schema。

| 创建阶段 | 表/数据 | 职责 |
| --- | --- | --- |
| Phase 1/2，Phase 3 收敛 | contacts/conversations/messages/message_occurrences/outbox/runtime_state/schema_versions | 本地身份、消息观察/去重、发送状态、运行代数；原型数据直接迁移 |
| Phase 6 | events/llm_runs | 脱敏执行轨迹、SSE 游标、实际 Token/耗时，不保存运维完整 prompt |
| Phase 7 | documents/chunks/chunks_fts | 原名、hash/版本、分块、来源与中文检索 |
| Phase 8 | tool_runs/confirmations；示例库 orders/tickets | 工具、会话级确认、幂等写入和虚构业务数据 |
| Phase 9 | memories/memory_sources/memory_tombstones、checkpoint | 长期事实/来源、更正/遗忘抑制、短期状态 |
| Phase 10 | analysis_jobs | 本地导入文件解析/分析状态和结果 |

去重基于会话、方向、跨帧序列对齐和气泡出现次数，不能只用正文 hash。无法确定是否新消息时记录 gap/uncertain 并停发。首次启动建立可见基线，默认不补回观察前历史；已处理消息重启不能再回复，离线未知消息不承诺无损补收，UI/README 明示。

### 4.4 API 和页面接线契约

列表具备固定排序/分页/空态；错误为 code/message/trace_id，不返回异常栈。仅 loopback，校验 Host/Origin；本地会话使用 HttpOnly、SameSite cookie，写操作校验同源/CSRF。同源静态 UI/API；开发模式只允许明确本地来源，禁止通配 CORS。

| API | 契约 | 阶段 |
| --- | --- | --- |
| `GET /api/session` | 建立本地会话与 CSRF nonce，不暴露后端凭据 | 6 |
| `GET /api/health`、`GET /api/runtime` | capabilities/权限/状态/模式/队列/失败/用量 | 6 |
| `POST /api/runtime/{start,pause,resume,stop}` | 严格状态迁移，非法 409，开始前检查健康/配置 | 6 |
| `GET /api/events` | SSE、递增 event_id、Last-Event-ID 回放，过期提示重取快照 | 6 |
| `GET /api/conversations`、`GET /api/conversations/{id}/messages` | 分页和明确方向/过滤/预览状态 | 6 |
| `GET /api/runs/{trace_id}` | 分支/来源/工具结果/耗时/错误，无隐藏推理 | 6/8 |
| `GET/PATCH /api/settings` | schema/掩码/来源/校验/原子保存 | 6，接线 14 |
| `POST /api/diagnostics` | 只读健康及用户显式请求的模型连通检查，不发微信 | 6，接线 14 |
| `POST/GET /api/knowledge/documents`、`GET/DELETE /api/knowledge/documents/{id}` | 导入、状态、来源/分块、删除同步索引 | 7 |
| `GET /api/memories`、`PATCH/DELETE /api/memories/{id}` | 会话范围、事实版本冲突检查、更正/遗忘 | 9 |
| `POST /api/analysis/files`、`GET /api/analysis/{id}` | 上传和分析任务，默认只分析、不发微信 | 10 |
| `POST /api/analysis/transcripts` | 人工转写文本复用 Agent，标清来源 | 10 |
| `POST /api/outbox/{id}/resolve` | 用户核实 unknown 后标已发/作废，不盲目重发 | 5/6 |

示例业务接口也在本轮固定：`GET /demo-api/orders/{order_id}` 返回 order_id/status/estimated_delivery，`POST /demo-api/tickets` 接收 summary/conversation_ref/idempotency_key，返回 ticket_id/status。工具客户端使用 `.env` 的 `DEMO_API_BASE_URL/DEMO_API_TOKEN`；示例路由用独立服务认证，不能由聊天提供认证头，联系人可访问范围由本地绑定决定。同一 FastAPI 进程提供这些路径，工具仍经 HTTPX 调用，不要求用户额外部署一个服务；超时与错误都进入正式工具结果。

四页固定为概览、会话、知识与记忆、设置；知识与记忆内为知识库/联系人记忆/文件分析三个页签。每个入口在所属阶段必须接真实后端。mock 仅用于测试和有明确标识的离线 demo。

### 4.5 全阶段统一完成标准

阶段完成须同时具备：任务实现、必要自动检查通过、该阶段必验人工结果、已有上下游接通、README/overview/复用记录同步、真实功能提交；不能有本阶段必做的 stub/TODO/假成功。未到开发阶段的入口可以不显示，但不能拿无动作按钮交验。

每阶段生成 `.local/acceptance/phase-N/report.json`，字段为 phase/commit/environment/mode/cases[id,executor,expected,actual,status,evidence_ref]/failures。用例状态 passed/failed/not_tested；脚本只填自己执行的项，人工由用户确认。必验缺失/失败时阶段不完成。公开仅脱敏摘要；阶段事实只写本文件对应详情和主表，不另建重复进度账本。

验收编号与测试入口在下文固定；执行时直接编写实现/测试和用户清单，不再先做一轮大模块规划。工具版本导致的小命令调整可以记录，验收目标不能静默变更。

### 4.6 原题到最终交付的完整映射

| 题目要求 | 必做实现阶段 | 最终可核对产物/证据 |
| --- | --- | --- |
| 实时监听、垃圾/白名单过滤 | 1–5 | 真实微信探针、会话路由、过滤原因、发送/去重记录；17 实机回归 |
| LLM 理解意图与拟人回复 | 2、8 | 真实模型闭环、图编排、知识来源、HTTP 工具和确认；真实视频 |
| 长短期记忆 | 9 | 持久 checkpoint、摘要、事实更正/遗忘、跨会话隔离和跨重启实测 |
| 语音/文件分析应用思路 | 10、13 | 四类文件处理、转写入口、完整语音方案和真实能力表，不以占位充正文 |
| 测试与使用视频 | 18 | 用户实际录制文件、场景覆盖与视频时间点；不能只有录屏脚本 |
| macOS/不同微信版本稳定 | 1、2、4、5、15–17 | 至少两微信版本矩阵、60 分钟样本、故障恢复与准确限制 |
| 代码和清晰 Commit 历史 | 每阶段、18 | 可运行源码、真实 Conventional Commits、history.bundle、来源许可证 |
| 敏感配置和 Token 限制解耦 | 1、3、6、14、18 | .env.example、后端校验/掩码、配置保存和包/历史敏感检查 |
| README 介绍/启动/使用指南 | 每阶段、15、18 | 干净目录启动验证、包内有效命令/链接、故障与能力边界 |

## 5. 单一主阶段表

用户要求在实施前细化，且旧阶段均未开始，因此此次统一重排：旧 1/2 保留；旧 3 对应新 3–6，旧 4 对应新 7–8，旧 5/6 对应新 9/10，旧 7 对应新 11–14，旧 8 对应新 16–17；启动集成独立为新 15，最终交付为新 18。以后使用新编号，不再使用旧编号 3–9 的含义。

| 阶段 | 主题 | 可验收增量 | 状态 | 实际产物 | 依赖/人工关口 |
| --- | --- | --- | --- | --- | --- |
| Phase 1 | 微信通道原型 | 诊断、读取、固定回复正确 | blocked | AX 候选/CLI/47 项离线测试；G1 实机待用户 | G1 用户实机必验 |
| Phase 2 | 最小 AI 闭环 | 白名单好友多轮真实回复与重启去重 | pending | 等待 G1，尚未实施 | Phase 1；G2 用户必验 |
| Phase 3 | 配置和持久化 | 配置、迁移、身份与状态仓储 | pending | 等待 G1/G2，尚未实施 | Phase 2 |
| Phase 4 | 可靠收消息 | 多会话、过滤、合并、排队与去重 | pending | — | Phase 3；用户实机必验 |
| Phase 5 | 可靠发送与启停 | 复核、发件箱、未知恢复、取消迟到结果 | pending | — | Phase 4；用户实机必验 |
| Phase 6 | 后端 API 和事件 | 控制/配置/会话 API、SSE、脱敏日志 | pending | — | Phase 5 |
| Phase 7 | 知识库闭环 | 导入、分块、中文检索、引用、更新删除 | pending | — | Phase 6 |
| Phase 8 | Agent 与业务工具 | 图编排、HTTP 查询、确认后写入 | pending | — | Phase 7；用户模型/微信必验 |
| Phase 9 | 完整记忆 | 摘要、长期事实、隔离、更正和忘记 | pending | — | Phase 8；用户跨重启必验 |
| Phase 10 | 文件和语音边界 | 四类文件、分析/转写入口、能力说明 | pending | — | Phase 9 |
| Phase 11 | UI 基础和概览 | 统一布局、真实状态与启停 | pending | — | Phase 10；用户视觉必验 |
| Phase 12 | 会话工作台 | 消息、执行轨迹、引用和未知处理 | pending | — | Phase 11；用户交互必验 |
| Phase 13 | 知识记忆工作台 | 导入删除、更正遗忘、文件分析全接线 | pending | — | Phase 12；用户交互必验 |
| Phase 14 | 设置诊断工作台 | 掩码、白名单、预算、保存与诊断 | pending | — | Phase 13；用户交互必验 |
| Phase 15 | 启动与产品集成 | 单命令、静态资源、干净环境安装 | pending | — | Phase 14；用户干净启动必验 |
| Phase 16 | 故障回归与就绪 | 离线回放、故障注入、交付检查 | pending | — | Phase 15 |
| Phase 17 | 实机稳定与兼容 | 两微信版本、长时运行和关键场景 | pending | — | Phase 16；用户实机硬关口 |
| Phase 18 | 视频与提交包 | 真实录像、README、源码/历史/报告归档 | pending | — | Phase 17；用户视频硬关口 |

## 6. 逐阶段可执行任务和验收用例

顺序输入为前阶段已通过的提交。每阶段完成记录填真实改动、文件、检查、人工证据、跳过/偏差和下一阶段；不要新建第二张进度表。

### Phase 1：微信通道原型与 G1

**目标/文件**：最终包与最小 CLI；`pyproject.toml/uv.lock/.env.example/.gitignore`、`config.py`、`domain/messages.py`、`adapters/wechat/base.py` 和选中的 `mac_vision.py` 或 `mac_ax.py`、`cli.py`、`tests/adapter/`；`docs/prototype-report.md`、`docs/reuse-register.md`、`THIRD_PARTY_NOTICES.md`、README 初版。

**任务**：

- [x] 审阅候选准确快照，登记具体文件/符号和许可证；不搬入整个上游 Agent/后台。
- [x] 实现事件/适配器契约和最小 Settings、dry-run、空白名单停发；Mac 依赖与离线依赖隔离。
- [x] 实现 doctor、probe read、probe send，报告环境/profile、方向、身份可信度和发送确认依据；不修改系统权限。
- [x] 唯一联系人别名映射；同名、未知身份/方向一律停发。
- [x] 编写 G1 步骤和报告输出，固定回复验证前不调用模型或做 UI。

**验收用例**：

| 编号 | 输入/操作与预期 | 执行者 |
| --- | --- | --- |
| P01-01 | 合成消息字段完整；未知身份无法生成可发送意图 | 助手 |
| P01-02 | 缺权限/微信未运行只返回诊断，不发送或更改权限 | 助手验证分支，用户实机诊断 |
| P01-03 | 两位联系人各发 5 条，含连续同文；读取会话和方向正确 | 用户 |
| P01-04 | 每位至少 1 条固定回复发对；切换/焦点不明则停发 | 用户 |

**验证分工**：助手 `uv run pytest tests/adapter -q` 和 lint；用户 doctor→read→带 `--confirm-send` 的 send，确认实际结果。G1 必须有环境和用户结果，调用成功不能替代送达确认。

**复用/日志/出口**：复用 RPA 或 AX 薄层，记录 `adapter.health/identity_uncertain/send.result`。缺权限/联系人或 G1 未通过则 `blocked`；同一问题最多两轮基于证据修正，仍失败报告备选，不自行操纵微信。通过后 Phase 2。

**完成记录（2026-10-21，部分交付，blocked）**：

- 已实现 `pyproject.toml/uv.lock/.env.example`、最终包内事件/适配器/最小配置/CLI、AX 候选/profile、合成 FakeAdapter、结构化边界日志、私有回执与单探针锁；新增 `tests/adapter/`、G1 报告初始化脚本、README、原型报告、复用登记、MIT 声明。已有 `.gitignore` 已覆盖私有证据/环境/产物，无需改写。
- 审阅 A 的发送/布局与 MIT；改编 B 的 AX 遍历/识别符/输入与截图方向采样。AX 仅作 G1 待验证候选，尚未证实优于 A，最终适配器/profile 不冻结；具体文件、SHA、许可和改动见 `docs/reuse-register.md`。
- 离线检查：Python 3.12.14；`uv sync --locked [--extra mac]`、47 项 pytest、ruff check/format、lock --check、CLI help、wheel/sdist 构建/隐私与 notice 清单检查均通过。Mac extra 仅 import/符号检查，没有执行原生 API、真实 doctor/probe、微信收发、浏览器或页面。
- P01-01 passed；P01-02 的离线缺权限分支 passed，用户实机部分 not_tested；P01-03/04 not_tested。统一私有证据 `.local/acceptance/phase-1/{report.json,pytest.xml}`；公开脱敏说明 `docs/prototype-report.md`。
- 安全/限制：仅用户当前前台测试单聊；标题绑定身份依赖用户核实账号/同名/单聊；方向是 0.7 置信截图启发式，unknown 停用自动回复；可见快照不声称跨帧去重。Return 尝试记 unknown 而非送达，无自动重试；失败可能留测试草稿，保留现场。完整 SQLite/outbox 恢复按后续阶段，不冒充本阶段已具备。
- **人工关口与解除条件**：用户按 README 填私有 profile，执行 doctor、两联系人各 5 条读取及各 1 条固定回复，核对方向/同文/收件对象，验证错会话和焦点不明时停发，提供脱敏 P01-02–04 结果。缺少上述环境和证据，G1 不能通过。
- 用户随后明确「需要安装或者终端执行的你都自己执行」，据此执行真实只读 doctor：macOS 27.0.1 / arm64，Accessibility 与屏幕录制权限均可用，桌面已解锁，微信进程未运行。修正 Quartz console key，新增合成原生桥回归；当前 48 项 pytest、ruff 均通过。修复提交 `dc60302`。真实报告 `.local/acceptance/phase-1/doctor.json`；无实际读取/发送，G1 等待用户打开登录微信并核对效果。
- 后续用户确认已登录并指定测试单聊，本地建立 `test-a` 绑定（真实名称仅存忽略的私有 profile）。实测 doctor 已可用，检测微信版本 4.1.5（31960），非 App Store 安装（原始渠道未核实）；P01-02 passed。读取尝试因微信不在前台被正确拒绝，未读取/发送消息，P01-03/04 仍未验收，等待用户保持测试会话前台。
- 用户保持测试会话前台后，读取实际触发，但 AX 返回 `ax_control_missing_or_ambiguous`。只读树诊断仅 5 个节点，无会话/消息/输入框；临时 AXEnhancedUserInterface 启用请求返回 -25208，前后 false。判定当前微信 4.1.5（31960）AX 候选不可用。按既定 A 备选审阅截图/OCR 源码与 MIT，新增本机 Vision 只读诊断（不发送、不将 OCR 行冒充消息），56 项离线测试及合成图片真实 OCR 通过。等待用户前台采样验证；G1 仍未通过，不进入 Phase 2/3。原始诊断仅存本地忽略目录，公开不含真实会话名或正文。
- 无 OCR 核查：主进程消息树不可见，13 个同应用包辅助进程未暴露 AX 窗口；未发现原生 AppleScript 脚本字典。菜单存在 Copy/Select All/Paste，但当前 disabled，复制原始消息的能力仍 not_tested。停止视觉等待，优先考虑剪贴板取文验证；Windows UIA、数据库读取仅对比，未改变平台/数据库边界。完整脱敏发现见 prototype-report 的无 OCR 小节，G1 仍 blocked。
- 按用户要求完成 GitHub 与全网无 OCR 读取调研，筛查十余个项目并核对关键源码/当前可用性，结果见 `docs/wechat-reading-research.md`。优先研究候选调整为可审计的只读 DB+WAL Reader（Gist / wx-cli-again），发现旧 Python new-messages 仅摘要、Rust 时间戳增量仍需补消息级游标；Chatlog 等旧依赖链已有移除/不可访问。此为选型建议，不执行真实取钥、重签/断点或数据库读取，不改变现有接入授权边界；G1 仍 blocked。
- 授权原话「请自动完成 phase1-3」已保存为 `auto_until` 1–3；因 G1 硬关口停止，Phase 2/3 依赖未满足，不实现、不标完成。收到 G1 证据后按原授权续做；G2 仍须真人实测。实现提交 `7a7425c`（`feat(adapter): add guarded AX channel prototype and offline G1 tests`）；授权和阻塞状态另作文档提交。

### Phase 2：最小 AI 闭环与 G2

**目标/文件**：`llm/{base,client}.py`、`runtime/prototype.py`、最小 `storage/`、`routing/`、`tests/prototype/`；直接扩展 Phase 1 最终包。

**任务**：

- [ ] 配置一种真实模型，实现请求/响应、超时、Token/调用预算；FakeModel 只用于自动测试。
- [ ] 白名单→本人/系统过滤→最小上下文→生成→复核发送；连续消息合并和最小 SQLite 已处理记录。
- [ ] 简短自然中文人设、输出长度受限；异常不把堆栈发给好友。
- [ ] `prototype --mode dry-run|live --duration ...` 真正可运行，live 不自动启用。
- [ ] 报告落定默认适配器/profile、窗口条件、模型契约，测量 30 条普通文本的耗时/Token。

**验收用例**：

| 编号 | 输入/操作与预期 | 执行者 |
| --- | --- | --- |
| P02-01 | 离线收→模型→发闭环、超时和预算分支正确 | 助手 |
| P02-02 | 微信“我叫小周→我刚才说叫什么”，追问正确 | 用户 |
| P02-03 | 本人/白名单外不回复，无自循环 | 用户 |
| P02-04 | 重启不重复回复已处理消息；同文新气泡仍可处理 | 助手与用户 |
| P02-05 | ≥30 条测量；空闲轮询目标 ≤2 秒，普通文本端到端 P95 ≤20 秒，不含等待用户确认 | 用户采样，助手汇总 |

**验证分工**：助手 `uv run pytest tests/prototype -q`；用户本地填 Key，验证真实模型与微信 G2。性能不达标先定位修正，改变目标须用户确认，不能挑样本。不能用 FakeModel 或控制台替代 G2。

**复用/日志/出口**：已有模型客户端、SQLite、适配器；同 trace 的 `route.decision/llm.result/send.result`。G1/G2 都通过才进入 Phase 3，缺证据则 `blocked`；后续按已冻结边界实现。

**完成记录**：未开始；执行后补充。

### Phase 3：配置、数据库与身份仓储

**目标/文件**：`config.py`、`storage/{database,migrations,repositories}.py`、`domain/`、`tests/config/`、`tests/storage/`；完整 `.env.example` 和 schema 说明。

**任务**：

- [ ] 完成第 4.2 节全部配置、数值/路径校验、覆盖来源、掩码、原子保存；不输出实际 `.env`。
- [ ] 把原型表迁到正式 schema，保留已处理消息；实现外键/唯一约束/事务/migration 和本地目录权限。
- [ ] 建立 contacts/conversations/messages/message_occurrences/outbox/runtime_state 仓储；不使用猜测的原生 wxid。
- [ ] 数据层备份/恢复和保留期清理，不能删除仍需恢复的 outbox；存储错误可读。
- [ ] 固定业务 repository 方法；后续 Agent/API 共用，不直写多套 JSON 文件。

**验收用例**：`P03-01` 配置优先级、非法限额、缺 Key 诊断、掩码不回写；`P03-02` 空库/原型库迁移、重复迁移、新连接恢复；`P03-03` 同名不混、账号/会话隔离；`P03-04` 保存失败旧配置完整，清理/备份保留未决状态。

**验证分工**：助手 `uv run pytest tests/config tests/storage -q`，使用临时目录和真实 SQLite；无需用户微信操作，交付离线验收报告。

**复用/日志/出口**：Pydantic Settings、SQLite/aiosqlite；`config.validation/storage.migrate/storage.error`。仓储必须实现并可使用，不能仅交 schema 文档。下一阶段 Phase 4。

**完成记录**：未开始；执行后补充。

### Phase 4：收消息、过滤、去重与会话队列

**目标/文件**：`routing/{filters,dedup,coalescer}.py`、`runtime/{poller,queues}.py`、`tests/routing/`；受控多会话轮询与持久化。

**任务**：

- [ ] 轮询白名单会话，明确当前/未读的检测边界；名字变化或无法唯一匹配转 degraded，不猜测发送。
- [ ] 模型前确定性过滤空/系统/本人/非白名单/垃圾规则/低可信消息；保留可解释原因。
- [ ] 跨帧对齐与 occurrence 去重，不只 hash 正文；启动基线、重启恢复、观察中断 gap 都落地。
- [ ] 每会话 FIFO、公平轮询、全局有界队列、连续文本合并；A/B 不串，队列满可见降级，不静默丢弃。
- [ ] 白名单移除立即使旧队列失效；合并事件可追溯到原 event_id。

**验收用例**：`P04-01` 旧帧重放 10 次只处理一次；`P04-02` 两个合法“你好”新气泡保留出现次数，合并不丢语义；`P04-03` A/B 交替各 3 轮、本人/垃圾/移出白名单；`P04-04` 队列满/身份不明/观察中断有明确状态；`P04-05` 用户真实微信验证同文新消息、交替会话及过滤，无误路由。

**验证分工**：助手 `uv run pytest tests/routing -q` 与合成回放；用户 P04-05 为本阶段必验，不能只靠离线结果完成。

**复用/日志/出口**：参考 RPA 去重，使用 asyncio 队列，不加消息中间件；`route.filtered/deduplicated/coalesced/queue_full`。下一阶段 Phase 5。

**完成记录**：未开始；执行后补充。

### Phase 5：可靠发送、发件箱恢复与启停

**目标/文件**：`runtime/{sender,controller,recovery}.py`、outbox repository、`tests/sending/`；统一启停和用户核实服务。

**任务**：

- [ ] 事务创建唯一 SendIntent，全局 GUI 锁；发送前复核白名单/代数/会话/窗口，发送后依据能力确认。
- [ ] 完整 pending/sending/verified_sent/failed/unknown/cancelled；发送后确认前崩溃置 unknown，不自动重发，不假称 exactly-once。
- [ ] 用户可“核实已发/作废”，无盲目重发；仅对明确未发出的可恢复错误进行有界重试。
- [ ] 完成运行状态、模式切换、取消队列、迟到结果作废、权限/锁屏降级和用户恢复；已发生按键的边界说清楚。
- [ ] 单工作目录实例锁，异常退出可恢复，第二 worker 不能同时发送。

**验收用例**：`P05-01` 同一意图重放无重复发；`P05-02` 模型处理中暂停，晚返回不发；`P05-03` 发送前/确认前/确认后崩溃各自正确恢复；`P05-04` 目标不符/权限失效/重复实例停发；`P05-05` 用户实测暂停恢复、会话切换、焦点丢失，不确定时待核实且不重发。

**验证分工**：助手 `uv run pytest tests/sending -q`、FakeAdapter 故障注入；用户只用测试白名单执行 P05-05，结果未确认则阶段不完成。

**复用/日志/出口**：参考上游必要的发送复核/剪贴板保护；`outbox.transition/send.verify/runtime.transition`。下一阶段 Phase 6。

**完成记录**：未开始；执行后补充。

### Phase 6：本地 API、SSE 与可观测性

**目标/文件**：`api/{app,runtime,conversations,settings,events,diagnostics}.py`、`observability/`、events/llm_runs migration、`tests/api/`、OpenAPI。

**任务**：

- [ ] 完成第 4.4 节本阶段路由和统一错误；CLI/API 共用领域服务，不另写消息循环。
- [ ] session cookie、CSRF、Host/Origin、loopback、配置掩码；诊断不附带发微信。
- [ ] SSE 持久游标、Last-Event-ID 回放和过期提示；客户端断线不影响 worker。
- [ ] trace 串起入站→分支→模型/知识/工具→发件箱；会话/用量/统计来自真实存储，不写死。
- [ ] 执行详情采用扩展载荷契约，后续模块写入同一事件体系；第 8 节日志底座本阶段全部落实。
- [ ] 提供阶段开发启动命令 `uv run uvicorn wechat_reply_agent.api.app:create_app --factory --host 127.0.0.1 --port 8765`；Phase 15 再收敛正式 serve，后续 UI 验收无需先完成打包。

**验收用例**：`P06-01` 启停合法/非法迁移、分页/空态；`P06-02` 非本地 Host/越源/缺 CSRF 拒绝、Key 不返回；`P06-03` SSE 重连回放、游标过期明确；`P06-04` CLI/API 状态一致、日志无凭据或原文。

**验证分工**：助手 `uv run pytest tests/api -q`，HTTPX/FastAPI 测试客户端；不打开文档页面/浏览器，内部阶段无需用户微信操作。

**复用/日志/出口**：FastAPI/Pydantic/标准 logging，复用已有运行服务。API 必须能真实调用；下一阶段 Phase 7。

**完成记录**：未开始；执行后补充。

### Phase 7：知识导入、检索与来源闭环

**目标/文件**：`knowledge/{ingest,splitter,index,retriever,service}.py`、知识路由/migration、`examples/knowledge/`、`tests/knowledge/`。

**任务**：

- [ ] TXT/Markdown 导入、hash 去重、版本与失败状态；文件只在受控目录，文档更新替换对应索引。
- [ ] 复用分块器/jieba，FTS5 存中文分词结果；参数化和转义查询，返回有界 top_k、文件/章节/段落定位及版本。
- [ ] 知识 API 全接通：列表、详情、分块预览、删除；删除后检索和后续引用均不能用旧数据。
- [ ] 虚构售后/退换货/产品知识、已知答案和无答案样例；资料文本不当作系统指令。
- [ ] 无命中返回结构化空结果，不编造知识。正式 Agent 在下一阶段接入这个实际服务。

**验收用例**：`P07-01` 导入/重复/更新/删除及来源一致；`P07-02` 中文短语、订单术语找到预期段落；`P07-03` 无命中、超长/特殊查询可控；`P07-04` 删除即索引失效，预览/引用版本相同。

**验证分工**：助手 `uv run pytest tests/knowledge -q`，真实 FTS5 和合成文件，不依赖外部向量服务/微信。内部验收结果可复现。

**复用/日志/出口**：langchain-text-splitters/jieba/FTS5；`kb.ingest/reindex/retrieve/delete`。本阶段交付本期完整文本知识库，不留“再建设知识库”。下一阶段 Phase 8。

**完成记录**：未开始；执行后补充。

### Phase 8：LangGraph Agent、HTTP 业务工具与确认

**目标/文件**：`agent/{graph,state,policy}.py`、`agent/prompts/`、`agent/tools/`、`demo_services/`、tool_runs/confirmations migration、`tests/agent/`、`tests/tools/`。

**任务**：

- [ ] 图包括载入上下文→意图/澄清→直接回答/知识/工具→结果校验→回复/待确认；复用 Phase 2 模型客户端、LangGraph 工具机制，有界循环。
- [ ] 知识回答带有效来源；普通聊天不强制检索，无知识依据如实说明。
- [ ] 真正由 HTTPX 调用的本地示例服务：订单查询、创建工单；虚构种子订单、权限/参数契约、持久工单。说明是示例系统，不假装连接真实企业业务。
- [ ] query_order 校验联系人访问范围；create_ticket 先显示具体内容，确认绑定会话/参数摘要/TTL/幂等键，拒绝或过期不写入。
- [ ] 工具/参数/HTTP 目标白名单、超时/预算生效；工具失败不能说成功，聊天/附件内容不能扩权。
- [ ] trace 和执行 API 返回工具结果、知识来源、用量/耗时，不输出隐藏推理。

**验收用例**：

| 编号 | 输入/操作与预期 | 执行者 |
| --- | --- | --- |
| P08-01 | 直接聊天、知识、无命中、澄清分别进入正确分支 | 助手控制模型分支 |
| P08-02 | 真实示例 HTTP 查询；A 不能查 B 的示例订单 | 助手 |
| P08-03 | 确认后仅一条工单；拒绝/过期/跨会话确认均不写 | 助手 |
| P08-04 | 超时/429/坏 JSON/注入/预算不产生误发或越权 | 助手 |
| P08-05 | 真实微信聊天、知识、查单、确认/取消工单，语气和工具选择可接受 | 用户 |

**验证分工**：助手 `uv run pytest tests/agent tests/tools -q`，假模型控制分支、真实示例 HTTP/存储；用户验证真实模型选择能力。不能只靠关键词路由或假工具结果完成。

**复用/日志/出口**：LangGraph/Pydantic/HTTPX；`agent.route/tool.request/result/confirmation.resolved`。下一阶段 Phase 9。

**完成记录**：未开始；执行后补充。

### Phase 9：短期压缩、长期事实与遗忘

**目标/文件**：`memory/{context,facts,retrieval,service}.py`、checkpoint/记忆 migration、记忆 API、`tests/memory/`。

**任务**：

- [ ] 持久 checkpoint、近期窗口和超预算滚动摘要；待确认/工具状态保持结构化，不依靠摘要记住状态。
- [ ] 事实包括账号/会话、键值、来源、版本、更新时间/TTL；有依据才写入，不把模型推断当确认事实。
- [ ] “叫我小周→改叫小李→忘记称呼”；更正替代旧值，遗忘清理检索/摘要影响并留不含原值的抑制标记，避免旧聊天自动再提取已忘事实。
- [ ] 按命名空间召回、预算内注入；A/B 隔离，公共知识与个人事实访问分开。
- [ ] 列表/更正/删除 API、版本冲突与真正删除生效；新进程可恢复正确事实。

**验收用例**：`P09-01` 多轮指代和超预算摘要；`P09-02` A/B 隔离、重启召回；`P09-03` 更名不再用旧值、遗忘后旧摘要不复活；`P09-04` TTL/来源/冲突/删除 API；`P09-05` 用户真实微信记住→重启→召回→更正→忘记。

**验证分工**：助手 `uv run pytest tests/memory -q`，检查新进程及真实 SQLite 状态；用户 P09-05 本阶段必验，不能写“最终再验”。

**复用/日志/出口**：LangGraph SQLite checkpointer、已有仓储；`memory.read/write/update/delete/context.compact`。下一阶段 Phase 10。

**完成记录**：未开始；执行后补充。

### Phase 10：文件处理和语音应用方案

**目标/文件**：`multimodal/{types,parsers,transcripts,analysis}.py`、analysis_jobs migration、analysis API、`tests/multimodal/`、`examples/files/`、`docs/multimodal-design.md`。

**任务**：

- [ ] TXT/MD、文本型 PDF、DOCX 四类必做解析；复用 pypdf/python-docx，可选择导入知识或一次分析，两者不能混淆。
- [ ] 校验大小/类型/长度/超时，禁止任意路径、执行、外部链接拉取；扫描/损坏/加密 PDF 给出明确结果。
- [ ] 文件分析/人工转写复用 Phase 8 Agent，标人工导入；默认只返回结果，绝不自动向某个好友发送。
- [ ] 交付 voice→获取→解码→ASR→文本事件→Agent 的完整设计、ASR Protocol、转写入口和成功/超时契约测试；不把假 ASR 测试说成真实原生支持。
- [ ] capabilities 使用 designed/fixture_verified/live_verified/unsupported；微信文件名或“语音”占位不能当正文。

**验收用例**：`P10-01` 四类文件抽出预期正文并分析；`P10-02` 知识导入可检索，一次分析不污染知识；`P10-03` 超大/损坏/加密/扫描/路径越界可解释失败；`P10-04` 转写入口共用 Agent、附件指令不扩权；`P10-05` 能力表与实际入口/证据一致。

**验证分工**：助手 `uv run pytest tests/multimodal -q`，合成文件。原生微信音频/附件获取不列必验；用户另测可按事实升级能力状态，不能据此留下本期必做欠项。

**复用/日志/出口**：pypdf/python-docx 和既有 Agent；`attachment.parsed/rejected/analysis.result`。下一阶段 Phase 11。

**完成记录**：未开始；执行后补充。

### Phase 11：UI 基础、布局和概览

**目标/文件**：`ui/package.json/package-lock.json`、`ui/src/app/`、`styles/tokens.css`、`components/`、`lib/{api,events}`、`pages/Overview/`、`docs/ui-design.md`。

**任务**：

- [ ] 直接按第 7 节做亮色 token、系统字体、统一控件、224px 侧栏、页头/状态条；只做四页既定结构，不再规划新产品。
- [ ] 同源 API/CSRF 客户端、typed DTO、SSE 重连/快照恢复；真实/离线/预览始终可辨。
- [ ] 概览接真实健康/队列/失败/用量及启停；开始按钮提示具体缺失项，暂停停止遵守 Phase 5。
- [ ] 加载/空/断连/失败/禁用齐全；响应式、长文本、焦点/标签/reduced motion；未实施页面不伪装成功。
- [ ] 复用 shadcn/Radix/Lucide，统一表单/按钮/对话框/表格，避免双视觉系统。
- [ ] 实现 `npm --prefix ui run dev -- --host 127.0.0.1` 与 `/api` 本地代理，开发来源显式配置；给用户完整后端/前端启动步骤，不能到 Phase 15 才可验收 UI。

**验收用例**：`P11-01` 类型/构建/客户端错误状态；`P11-02` 用户在 1280×800、1440×900 检查留白/层级/对齐/对比度；`P11-03` 概览状态和启停真实；`P11-04` 后端断开/恢复有提示，重连不留旧状态。

**验证分工**：助手 `npm --prefix ui run typecheck`、`npm --prefix ui run build`、必要客户端状态测试，不打开页面；用户 P11-02–04 为本阶段必验，视觉未确认不完成。

**复用/日志/出口**：组件库与 Phase 6 API；`ui.control/api.error/stream.state` 边界日志。下一阶段 Phase 12。

**完成记录**：未开始；执行后补充。

### Phase 12：会话列表、消息和执行时间线

**目标/文件**：`ui/src/pages/Conversations/`、`components/{ConversationList,MessageList,RunDrawer,OutboxResolution}`，必要 DTO 修正。

**任务**：

- [ ] 分页/选中会话与消息；清楚展示方向、时间、过滤/预览/待确认/失败/未知，dry-run 不显示已真实发送。
- [ ] 详情侧栏包含可读步骤、来源、工具输入摘要/结果、预算/耗时/trace，无思维链/凭据。
- [ ] unknown 可核实已发/作废并说明影响，无盲目重试或任意联系人发送入口。
- [ ] SSE 更新到正确会话，保持滚动/分页/选中；长中文/引用、无消息/已删会话/断连均处理。

**验收用例**：`P12-01` 用户切 A/B 无消息/trace 串线；`P12-02` 知识/工具/确认沿同 trace 可解释；`P12-03` 预览/真实、unknown/已发可辨，核实操作生效；`P12-04` 加载/空/长文/断连恢复布局正常。

**验证分工**：助手构建/类型检查、关键分页/事件 reducer 测试；用户逐项交互验收。仅修正所属实现，不把页面问题推到最终一轮大修。

**复用/日志/出口**：UI11 组件与既有 API；`outbox.resolved` 共用服务。下一阶段 Phase 13。

**完成记录**：未开始；执行后补充。

### Phase 13：知识、记忆与文件分析页面

**目标/文件**：`ui/src/pages/KnowledgeMemory/{KnowledgeTab,MemoryTab,AnalysisTab}`、上传/分块详情/记忆编辑等通用控件。

**任务**：

- [ ] 知识页签导入四类文件、展示解析/索引状态、查看来源/分块、删除后同步列表和检索。
- [ ] 记忆页签按联系人查看事实/来源/时间，更正/遗忘调用正式 API，版本冲突提示重载，删除确认。
- [ ] 分析页签接一次文件分析和人工转写，区别于知识导入；展示来源和能力，不误导可自动读所有微信语音。
- [ ] 上传/处理中/失败/超大/重复/空态都有文案，成功后能查到后端记录，不只显示 toast。

**验收用例**：`P13-01` 用户导入/预览/删除真实改变检索；`P13-02` 更正/忘记后 Agent 不再用旧事实；`P13-03` 四类分析及错误可见，转写来源清楚；`P13-04` 控件、密度、状态/焦点与概览一致。

**验证分工**：助手构建/类型检查和上传/轮询/版本冲突状态测试；用户页面/模型交互必验。按钮当阶段全接通，不留大模块后续实现。

**复用/日志/出口**：Phase 7/9/10 API 与 shadcn 控件，复用对应事件。下一阶段 Phase 14。

**完成记录**：未开始；执行后补充。

### Phase 14：设置、白名单和诊断页面

**目标/文件**：`ui/src/pages/Settings/`、配置表单/敏感字段/ProfileCapabilityPanel/诊断控件；配置 schema 同步。

**任务**：

- [ ] 模型、白名单/profile、预算/频率、存储保留分组；即时提示，以后端校验为准。
- [ ] Key 仅输入/替换/清除，已有值只显示已配置；空保留/掩码不提交，环境覆盖只读；保存后重载生效值。
- [ ] 白名单绑定唯一映射，需要重启项清楚提示；live 不能运行中静默启用，移除联系人立即失效。
- [ ] 诊断显示权限/微信/profile/存储/模型连通/支持能力；用户显式点模型检查才请求服务，诊断不发微信。
- [ ] 保存失败、重启要求、无 Key、非法限额/网络异常可操作，不回显 Key 或异常栈。

**验收用例**：`P14-01` 保存→刷新/重启仍生效；`P14-02` 保留/清除 Key 正确、非法值不破坏旧配置；`P14-03` 白名单移除/同名/模式规则真生效；`P14-04` 诊断真实且无凭据泄露、视觉一致。

**验证分工**：助手构建/类型检查和设置合约测试，使用假 Key；用户本机设置/诊断必验，无需向聊天提供密钥。

**复用/日志/出口**：已有 Settings/诊断服务与控件；`settings.saved/restart_required/diagnostics.result`。下一阶段 Phase 15。

**完成记录**：未开始；执行后补充。

### Phase 15：单命令启动、静态资源与干净安装

**目标/文件**：正式 `cli.py`、应用 lifespan、静态挂载、`scripts/bootstrap.sh`、依赖 extras/锁、README 启动章节、`tests/packaging/`。

**任务**：

- [ ] bootstrap 检查 Mac/Python/Node/uv、装锁定依赖/构建 UI/初始化目录；不自动装微信、授权、降级或开浏览器，不静默改 `.env`。
- [ ] serve 同源 UI/API、初始 stopped/dry-run；SPA 回退和 API 404 分开，不能把接口错误返回 HTML。
- [ ] SIGINT 取消新工作、保护未决 outbox、关库；端口占用、重复实例、缺 UI 构建错误清楚。
- [ ] README/CLI help 一致：安装→配置→doctor→启动→用户打开地址→启用；有停止/重启/恢复及桌面会话要求。
- [ ] 无开发机绝对路径，干净拷贝/新虚拟环境可启动，不依赖上游目录、既有 node_modules 或 `.local`。

**验收用例**：`P15-01` 构建、安装包/导入/静态资源；`P15-02` API404/SPA刷新/端口占用/退出；`P15-03` 用户新环境按 README 完成配置→doctor→启动→页面→真实回复；`P15-04` 无 Key 可诊断、无误发。

**验证分工**：助手非 GUI 安装/构建/API 测试；用户干净环境真实启动与刷新必验。缺启动脚本或仍需另部署后台不得完成。

**复用/日志/出口**：uv/npm/FastAPI，不做原生安装器；`app.startup/shutdown/instance_lock`。下一阶段 Phase 16。

**完成记录**：未开始；执行后补充。

### Phase 16：完整离线回归、故障与就绪检查

**目标/文件**：`tests/replay/`、`tests/faults/`、`scripts/acceptance/`、verify 命令、`docs/acceptance.md`、runbook 故障索引。

**任务**：

- [ ] 汇总 P01–P15，覆盖聊天、重复/连续消息、知识/工具/记忆、文件/设置；模块测试在各阶段已具备，不到此才首次补测。
- [ ] 注入模型/工具超时、429/5xx/坏响应、队列满、库不可写、崩溃、发送 unknown、暂停晚回/SSE 断线，验证既定恢复。
- [ ] verify 检查配置 schema、依赖锁、迁移、离线场景、前端构建/资源并出报告；人工项保持真实结果，不填虚假 pass。
- [ ] 日志和保留期有效，不刷敏感内容；缺陷按原 Phase 5/6/12/14 等归属修复，不新增大模块计划。
- [ ] 给 Phase 17 用户可直接执行的用例、采样/环境字段、失败报告出口和停止条件。

**验收用例**：`P16-01` 全量确定性测试通过；`P16-02` 故障无误发/错写/无限循环；`P16-03` trace 定位失败、离线/真实和自动/人工证据分明；`P16-04` 新临时目录 verify 不读私人数据/Key、不启动页面/微信。

**验证分工**：助手 pytest、ruff、UI typecheck/build、`uv run wechat-agent verify --output ...`。此前必验未过则回所属阶段修复；本阶段只回归/修缺陷，不负责尚未开发的主功能。

**复用/日志/出口**：pytest/HTTPX/FakeAdapter 与正式服务；下一阶段 Phase 17。

**完成记录**：未开始；执行后补充。

### Phase 17：真实多版本兼容与持续运行

**目标/文件**：用户运行既有验收入口；`docs/compatibility.md`、`docs/acceptance.md` 填脱敏结果和支持边界。

**任务**：

- [ ] 两个不同 Mac 微信版本跑同一关键集，记录 macOS/架构/版本/发行渠道/语言/profile/窗口与解锁条件/日期；不擅自重装降级。
- [ ] 每版本涵盖双联系人交替、连续同文、本人/非白名单/垃圾、知识、查单/工单确认、记忆更正忘记、重启/暂停恢复/网络异常。
- [ ] 主环境连续 ≥60 分钟、≥50 条正常文本及 20 条应过滤消息；错对象/白名单外自动回复/自循环均 0，正常文本成功率 ≥95%，所有失败保留。
- [ ] ≥30 条普通文本测 P95 ≤20 秒及轮询目标；包括排队/模型/发送、不含等待确认，不挑最佳样本。
- [ ] 用户验证锁屏/睡眠/最小化/焦点被抢，不能工作时显示 degraded 和恢复要求；四页视觉/真实状态最终一致。

**验收用例**：`P17-01` 两版本有可审阅证据；`P17-02` 长时间/样本/成功率/零错对象达到目标；`P17-03` 所有失败可定位、unknown 不偷重发；`P17-04` 矩阵仅标实测、最终 UI 通过。

**验证分工**：用户全部实机/模型/界面操作；助手分析脱敏结果并修正既有模块。缺第二版本、样本或关键安全失败则 blocked，mock/架构可扩展不能替代。兼容修正限定在 profile/适配器契约；若需新技术则报告原型假设失败，不隐瞒。

**复用/日志/出口**：复用验收脚本/trace，原始数据留本机；通过后 Phase 18 只录像归档，不补主功能。

**完成记录**：未开始；执行后补充。

### Phase 18：真实录像、README 与最终可提交包

**目标/文件**：README 终版、`docs/{demo-script,delivery-checklist,submission}.md`、package 命令、`dist/submission/` 和校验清单。

**任务**：

- [ ] README 含介绍、架构/复用、准确矩阵、权限配置、安装启动使用、测试、隐私边界、恢复、语音文件思路和视频；不再新开文档规划。
- [ ] 给可直接录制的脚本：启动/模式→好友聊天追问→过滤→知识→查询及确认/取消→记忆跨重启/更正/忘记→暂停恢复→工作台/能力边界。建议 5–8 分钟，剪辑标清重启，不伪造实测。
- [ ] 用户录真实视频并确认可交付；实际文件可用、覆盖场景、无 Key/无关私聊。只有脚本不算视频完成。
- [ ] 包含可运行源码/锁/合成样例/许可证来源/README/脱敏验收摘要/视频；排除 `.env`、真实数据/截图/依赖缓存；附 `commit-history.txt` 和通过敏感检查的 `history.bundle` 保留真实历史。
- [ ] `dist/submission/` 有完整可解压压缩包、校验和、提交说明；按包内布局核对文档/视频相对链接，不依赖开发机路径或不存在地址。
- [ ] 核查工作树/历史/包清单、Conventional Commits、依赖命令和必验结果；泄露必须清理并处理凭据，不能只加 gitignore。
- [ ] 默认本地压缩包满足“压缩包或仓库”；用户另选 GitHub/GitLab 时按明确仓库/可见性/发布授权推送，不擅自公开/上传。

**验收用例**：`P18-01` 用户新目录解压，按包内 README 启动并真实对话；`P18-02` 视频真实覆盖且可用；`P18-03` 包/历史无密钥私聊、许可证与真实提交完整；`P18-04` 原题每项映射到文件/测试/视频时间点，18 阶段无必做欠项。

**验证分工**：助手清单/链接/历史/离线检查，用户录像/播放/最终解压启动。缺视频或前阶段必需证据则 blocked，不报“代码完成，交付后补”。

**复用/日志/出口**：标准 zip/git bundle/hash。通过后用户可直接交包，无下一轮大模块开发；外部发布未授权不妨碍已完成本地包交付。

**完成记录**：未开始；执行后补充最终产物、校验和、用户验收和原题映射。

## 7. UI 设计约束（Phase 11–14 直接实施）

这是本地管理工作台，不制作营销首页。风格参考成熟协作软件的低噪声界面：排版优先、留白充分、信息可读、状态明确，避免大面积渐变、霓虹、玻璃卡片和无意义仪表盘。

- 导航固定为“概览 / 会话 / 知识与记忆 / 设置”，日志和具体工具结果用详情侧栏展开，主界面不堆实现术语。
- 亮色优先：背景 `#F7F8FA`、表面 `#FFFFFF`、主文本 `#17212B`、次文本 `#667085`、边线 `#E7EBF0`；强调色 `#167D64`。错误/警告独立语义色；实际对比度在实现时检查。
- 系统字体，中文跟随系统；正文 14–15px、标题 20–24px，数字等宽；8px 间距基准、8–12px 圆角、极轻阴影，减少无边界卡片嵌套。
- 桌面布局侧栏约 224px、内容最大宽约 1440px；以 1280×800 和 1440×900 作为人工检查尺寸，较窄时折叠导航、不隐藏核心操作。
- 主按钮有单一优先级：开始/暂停；“真实发送”和“仅预览”具有持久且清晰的模式提示。预算/凭据只放设置，日常会话不显示原始 JSON。
- 用会话和执行时间线解释“为什么回复/为什么过滤”，提供适量结果摘要与知识引用，不展示思维链。
- 轻量动效 120–180ms，尊重 reduced motion；使用 Lucide 统一图标，不用 emoji 代替主要图标体系。
- 如后续明确使用设计 skill，先确认其适合本地项目，告知用户并读取指令；不得因此自动打开页面、使用 Playwright、发布网站或扩大产品范围。本计划不要求创建 Figma 文件或托管站点。

## 8. 关键链路日志、隐私与测试分工

使用 Python `logging` 输出单行结构化 JSON，稳定字段为 `timestamp/level/event/trace_id/conversation_ref/message_ref/adapter/duration_ms/outcome/reason`。标识用本地不透明代号或稳定摘要；不是微信真实身份的 ID 必须明确命名。以下为长期诊断信息，不是临时调试打印：

| 链路 | 记录边界 | 避免噪声/泄露 |
| --- | --- | --- |
| 接入→路由 | 连接状态变化、新事件、方向不明、过滤/去重原因、排队 | 静止轮询只记采样健康指标，不输出每帧或原始消息 |
| Agent→知识/模型 | 分支、检索命中数、模型调用次数、Token 数、耗时、失败类别 | 不记录完整 prompt、回复、知识正文或模型隐藏推理 |
| 工具→系统接口 | 工具名、参数校验结果、确认状态、调用成败/幂等命中 | 不记录 Token、认证头、真实订单详情或任意响应大包 |
| 记忆→存储 | 读写数量、命名空间代号、更正/删除、数据库错误 | 不把用户偏好/隐私事实原文写入运维日志 |
| 发件箱→微信 | 发送状态迁移、会话复核结果、失败/未知和恢复 | 不凭“按下回车”记录为已确认送达，不自动重发未知结果 |
| UI→运行控制 | 启停、模式切换、配置字段名、SSE 连接变化 | 不输出配置值；高频状态推送不逐条刷日志 |

原始聊天、截图、数据库、报告及 Key 默认存放 Git 忽略的 `.local/` 或运行目录，带保留期限；公开 evidence 仅含人工确认脱敏内容。启用远程模型/OCR/ASR 时 UI 和 README 说明哪些必要内容会发给配置的服务商。不读取或打印现有 `.env` 内容以“检查配置”。

自动验证只覆盖纯逻辑、存储、接口和构建；关键真人验证由用户负责。每阶段明列的必验人工项不能等到 Phase 17 才首次做，Phase 17 是多版本与长时间回归。助手交付清单时写明前置条件、步骤/命令、预期、记录字段和失败出口。缺失结果为 `not_tested`、失败为 `failed`、环境缺失阶段为 `blocked`；无证据不得填 `passed`。

## 9. 后续执行契约

1. 首先读取本计划和 `docs/overview.md`，再核查当前工作树与适用用户约束。初始计划创建后停在评审，不开始 Phase 1；无需额外 executor skill。
2. 默认 `manual`。用户“执行 Phase X”仅执行该阶段；“继续”先复查相关 `blocked` 条件，再选择首个 `in_progress`，否则首个可执行 `pending`。被未完成依赖阻塞时报告依赖，不跳过 G1/G2。
3. 计划存在后，用户可明确授权“自动完成剩余阶段”切换 `auto`；或“自动执行 Phase 1 到 Phase 5 后停止”切换 `auto_until`。先校验并记录原话与范围，再实现。没有这类指令不得推断自动授权。
4. `auto` 的起止字段均为 `none`。`auto_until` 起止必须是表中存在的包含式范围；省略起点取当前 `in_progress`，否则首个 `pending`，按主表将“再做 N 阶段”等转换为具体终点。范围错误保留原模式并澄清。
5. 自动模式每阶段开始前重读状态、依赖和边界，将选中项置 `in_progress`；完成后更新该阶段完成记录、唯一主表和 overview，再选择下一个范围内阶段。已完成阶段不重跑。
6. 自动模式不因非阻塞的附加建议停止；但 G1、G2、各功能/UI 阶段的必验人工项、Phase 17 实机矩阵、Phase 18 录像缺失必须停止，将阶段置 `blocked` 并记录解除条件，保留自动模式和范围，用户取消自动才改模式。
7. 任一明确单阶段命令仅限本轮该阶段，即使当前持久模式为自动也不能连续执行；不擅自更改持久模式。后续“继续”再按保存模式执行。
8. `auto_until` 只选起止范围内的阶段；全部必需阶段及任何必需交付返回验证完成后，改回 `manual`，起止清为 `none`，在该终点完成记录中注明已达授权边界，不执行下一阶段。仅终点完成不代表中间阶段已完成。
9. 后续如目标阶段被拆分，原阶段终点映射到最后一个子阶段；只有用户明确点名子阶段时才能在该子阶段停下。已经全部完成的范围先审计交付，再结束授权，不重新实现。
10. 本轮已按用户要求完成评审前细化；实施中不因“大模块尚未规划”新建计划。仅真实证据证明阶段不能安全完成时，才在本文件最小拆为通常两个子阶段，先同步主表/详情/验收再实现；不静默扩范围、改验收或重编号无关阶段。
11. 有产品歧义、外部授权、真实环境缺失或验证失败且无安全修复时，记录阻塞与解除条件；不自行申请/购买服务、修改系统设置、发送消息、发布或扩大业务范围。
12. 每次阶段完成记录写入对应阶段：实际文件/改动、执行检查与结果、跳过项、偏差、证据路径、人工项和下一建议。不另建重复的全局完成记录。
13. 从实施开始按功能形成真实 Conventional Commits，如 `feat(adapter): ...`、`feat(agent): ...`、`fix(runtime): ...`；按授权和适用 git skill 提交，不擅自 push，不留到最后补造历史。本次只细化计划，不创建代码提交。
14. relay 默认 `off`，不自动新建会话、worktree 或交接。以后用户明确启用时，先读 skill 的 relay/worktree-return 参考、记录固定交付目标和批次，再执行其交接与返回核验要求。

## 10. 最终完成条件

全部 18 阶段任务和必需验收通过，原题每项映射到实际产物；G1/G2、功能/UI 人工验收、多版本和真实录像齐备；干净解压可启动、配置数据未泄露、真实提交和许可证可审查。交付包含代码/文档/脱敏摘要/历史/视频，用户无需再规划开发大模块即可提交。环境不足时保持缺口与 blocked，不能用“后续完善”替代完成。
