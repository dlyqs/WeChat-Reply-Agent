# 个人微信 AI 回复 Agent 执行计划

更新日期：2026-10-21（Asia/Shanghai）。计划版本：v4。
本文件是阶段状态、实施顺序和完成条件的唯一来源；代码导航见 [overview.md](overview.md)。

~~~text
execution mode: auto_until
automatic start phase: 1
automatic stop phase: 2
execution state: completed
conversation relay: off
current change: phase 1-2 completed; G1/G2 passed; worker stopped
wechat foundation: wechatauto-replica 1.2.7.0
upstream commit: d322c4a9b1124228820bab363e5676016f188fc6
~~~

v4 完整替换 v3 和原 18 阶段规格。Phase 1–3 保留原有含义；后续合并为 Phase 4–7。2026-10-21 用户明确要求自动完成 Phase 1–2；现已完成 G1/G2 并停止。本次不继续 Phase 3，原计划修订时的暂停记录已由本次执行状态替代。

## 1. 交付目标与范围

交付一个在固定 Windows 桌面环境运行的个人微信回复应用：指定测试好友发来文本，应用按间隔读取、过滤、归入会话，调用 Agent 后通过当前微信账号回复。应用提供统一启动入口、本地工作台、可配置模型、上下文、知识与记忆、运行记录，以及真实演示视频和可复现源码包。

微信控制采用 [fanyuantaier/wechatauto-replica](https://github.com/fanyuantaier/wechatauto-replica/tree/d322c4a9b1124228820bab363e5676016f188fc6)，复用其数据库读取、密钥缓存、UIA、坐标/OCR、剪贴板输入和发送回读。OCR 允许使用并默认遵循基座的混合路线，不再维护独立的无 OCR 门槛，也不另写一套微信底层。

### 1.1 最终交付必需项

- 一台 Windows 10/11 x64 电脑、一种实际验证过的微信版本、一个明确绑定的账号和测试好友单聊；只承诺文字收发。
- 可配置的低频轮询，默认 15 秒，演示允许 10–30 秒；按本机实际耗时展示，不承诺实时、所有版本、全天候或后台无桌面运行。
- 白名单、本人/系统/未知方向过滤、连续消息合并、消息级去重、会话串行、持久化 inbox/outbox 与 unknown 停发。
- LangGraph 最小 Agent、多轮上下文、可配置模型与人设、超时/长度/调用预算；小规模本地知识检索和按联系人隔离的长期记忆。
- 简约本地工作台：状态与启停、会话/执行记录、配置与诊断，Phase 5 再接入知识/记忆管理。
- 原创代码的非商业许可、第三方来源与补丁记录、安装/启动/限制说明、真实录像和无私密数据的源码包。

### 1.2 可选增强与明确不做

Phase 6 的虚构业务工具、文件分析和语音转写入口为可选增强，初始未选择；未实现时不显示功能入口，也不作为最终交付缺口。需要采用时在主表明确选择，不以空实现通过验收。

不要求 macOS、多版本矩阵、群聊、多账号并发、全量历史导入、原始音视频获取、朋友圈、批量营销、云托管、原生安装器或长期稳定性认证。上游已有这些接口不代表应用要全部暴露。首次启动建立基线，默认不回复启动前历史；停机期间不承诺无损补收。

## 2. 基座版本、运行前提与权限边界

| 项目 | 固定选择与验证要求 |
| --- | --- |
| 基座 | wechatauto-replica 1.2.7.0；源码固定 d322c4a9b1124228820bab363e5676016f188fc6，不自动跟随 main |
| Python / 桌面 | Python 3.12 x64；登录用户的 Windows 交互桌面，保持解锁，微信窗口可见 |
| 微信 | 优先验证当前可正常登录的 4.1.15.53 或同基座可适配版本；这是上游记录，不是本项目兼容结论 |
| 读取 | 选定账号的本地加密数据库与 WAL；按基座流程读取进程中的密钥材料并缓存，实际新鲜度需核对 |
| 发送 | 基座 UIA 优先、坐标/OCR fallback；允许窗口激活、搜索/切换到已绑定目标、点击、粘贴、回车 |
| UIA 热激活 | 接受基座对微信进程内 Qt accessibility 标志位的运行时写入，按选定版本验证；不宣称纯 UIA 或零侵入 |
| 系统范围 | 不额外扩展为任意内存修改、DLL 注入、Hook、协议模拟、系统保护修改或登录限制绕过 |
| 安装 | 助手在 Windows 执行安装、终端诊断和已选路线；客户端来源与签名要核实，不擅自覆盖现有客户端或聊天数据 |
| 人工职责 | 打开微信、手机登录、核实账号/测试好友、发测试消息、确认对端收件、界面验收与录屏 |
| 操作范围 | 基座选型与上述技术路线已确定；真实发送仍限明确绑定测试会话、非空白名单和显式 live |

doctor 必须保持只读：不构造会取钥或热激活的对象，不调用完整 WeChat() 充当纯环境检查。初始化、取钥、OCR 校准和热激活由显式 connect/开始操作触发，并展示实际执行步骤。初始化成功不等于消息读取/发送验收通过。

不以随机延迟、旧版或只读数据库承诺不会发生账号限制。检测到客户端退出、账号变化、无法识别会话或基座异常时进入 degraded，停止自动发送。

## 3. 基座内化与应用边界

### 3.1 内化方式

在 Phase 1 把固定源码快照作为本地第三方依赖纳入 third_party/wechatauto_replica/，保留上游 wechatauto 包名、Apache-2.0 LICENSE、必要版权/NOTICE、包元数据、README_pypi.md 和运行资源。保留依赖所需模块，避免因顶层导入链裁剪造成运行时缺失；不复制 .git、账号数据、开发者代理指令或无关开发缓存。

主项目通过 uv 的本地 path source 和仅 Windows 生效的 extra 接入。上游仍是独立 Python 包，应用只通过适配器调用，不将上游各模块散拷进 Agent 或 UI。提交包必须包含该本地依赖目录，不能依赖另一台电脑的绝对路径或临时 pip 安装。

third_party/wechatauto_replica/UPSTREAM.md 记录来源、精确 SHA、导入文件、上游版本、资源、依赖和每个本地补丁；原依赖范围经 Windows 锁解析收敛到 uv.lock。升级是明确的补丁/版本变更，不在应用启动时自动拉取。

仅对影响本期收发、身份、隐私或运行的具体问题做最小补丁；不重写 SQLCipher、OCR 引擎或整套 UI 自动化。固定源码已在 Phase 1 导入，实际补丁和限制见 third_party/wechatauto_replica/UPSTREAM.md。

### 3.2 模块职责

除 third_party/、ui/、scripts/ 和 tests/ 外，下表应用模块均位于 src/wechat_reply_agent/ 内。

| 位置 | 职责 |
| --- | --- |
| third_party/wechatauto_replica/ | 上游读取、解密、WAL、UIA/OCR/键鼠能力与最小修复 |
| adapters/wechat/replica.py、replica_bridge.py | 懒加载、账号绑定、字段规范化、原生调用、发送结果映射与能力报告 |
| domain/ | 与第三方对象解耦的会话、消息、Agent、发送和运行契约 |
| storage/ | 应用 SQLite、inbox/outbox、游标、上下文、记忆、知识与运行记录 |
| runtime/ | 轮询、基线、事务入库、合并/队列、暂停代数、单实例与唯一 GUI 执行通道 |
| agent/、llm/ | LangGraph 路由、模型、人设、上下文/预算、检索和记忆 |
| api/、ui/ | 本地管理应用；UI 仅调用本项目 API，不直接操作基座 |
| scripts/acceptance/、tests/ | 脱敏实机报告、合成回放与必要故障测试 |

最终链路：

~~~mermaid
flowchart LR
  W[微信客户端] --> B[Replica 数据库读取]
  B --> A[适配器与身份过滤]
  A --> I[SQLite inbox 与游标]
  I --> Q[会话队列]
  Q --> G[LangGraph Agent]
  K[知识与记忆] --> G
  G --> O[SQLite outbox]
  O --> S[Replica UIA 与 OCR 发送]
  S --> W
  U[本地工作台] --> R[应用运行服务]
  R --> Q
  R --> O
~~~

### 3.3 复用与许可证

原创 Agent、适配器、工作台等继续采用根 LICENSE 的 PolyForm Noncommercial 1.0.0。基座保留 Apache-2.0 和适用的修改声明，已有 MIT 改编代码保留原声明；不把上游原有代码的权利改成禁止商业使用。所有依赖/资源按各自许可列入复用登记和 THIRD_PARTY_NOTICES.md。

应用的价值与改动要标清：微信读写来自基座，Agent 编排、应用状态、业务设计和集成为本项目实现。计划、文档和提交仅记录客观技术方案、变更与验证结果。

## 4. 集成时的必要封装与已知限制

以下来自固定快照的静态审阅，不是本机故障复现。Phase 1/2 优先处理会造成身份错误、重复发送或阻断当前演示的问题；不把完整底层审计升级为重建基座的前置任务。

| 发现 | 应用采用的处理 |
| --- | --- |
| get_new_messages 只用 sort_seq > since_seq；基座说明同一会话可有并列 sort_seq | 读取边界包含并列记录，以账号/会话/分片/local_id 标识去重；验证跨批/跨分片同序号，不只保存秒级时间或正文 hash |
| Listener 会重试整个回调，耗尽后仍推进水位 | 默认由应用调度 WeChatDB 轮询，消息和应用游标事务落库；不把模型或 GUI 发送放入基座回调，不以其 JSON 水位作为唯一账本 |
| 发送回读仍有 sender_id == 2 判断，分片编号未必代表本人 | 按当前分片解析 sender_username，与已绑定账号比较；解析不到为 unknown，不以数字常量判方向 |
| verify=False 有省略会话复核的快捷发送；部分失败会触发内部重试 | 适配器禁用不复核的快速路径；补充单次发送边界和执行回执，回车可能发生后不得自动改走第二条发送路径 |
| 回读水位获取失败可能退回匹配旧记录 | 无有效发送前水位不能自动判成功；按目标会话、新消息身份和完整文本核对，超时映射 unknown |
| WAL 有 salt 过滤，但缺完整提交帧/累计 checksum 校验；失败可回退旧快照 | 复用现有解密与校验，验证坏库/旧快照错误可暴露并降级；目标环境发现一致性缺陷时做必要补丁。通用 WAL 恢复与完整校验不是本期重建任务，未覆盖的边界写入限制，不承诺无损 |
| 默认账号选择/取钥存在自动回退，密钥与明文副本分散在临时目录 | 显式绑定账号与数据路径；禁止静默切到其他账号，缓存/备份/校准资料归入受控 DATA_DIR，按 Windows 当前用户 ACL 核查 |
| 基座日志/返回值可能包含正文、昵称或密钥相关数据 | 统一拦截第三方日志，保留稳定错误码和脱敏摘要；原始证据仅留私有目录，不直接将上游结果回传给浏览器或终端 |
| 现有主 CLI 无条件导入 fcntl/Mac 依赖 | Phase 1 改为平台隔离与懒加载，Windows 锁使用可用的跨平台实现，不要求 Windows 安装 PyObjC |

这些修复是接入适配工作，不扩展为全版本兼容研究。修复后仍无法在固定环境完成 G1 时，记录具体失败和支持范围，不继续铺应用，也不静默换控制基座。

## 5. 应用运行与数据契约

### 5.1 启动与配置

目标唯一入口为 uv run wechat-agent serve；FastAPI 同源提供构建后的 React/TypeScript/Vite 页面，不自动打开浏览器。worker 初始 stopped、模式 dry-run、白名单为空。开发时可用单独 UI dev 命令，前端仅作类型/构建/必要逻辑验证，界面由用户验收。

| CLI 目标 | 行为 |
| --- | --- |
| `doctor --output <json>` | 只读检查平台、依赖、客户端版本和可用权限；不取钥、不热激活 |
| `connect --output <json>` | 按已绑定配置初始化基座、取钥/缓存/校准/热激活，输出脱敏步骤结果 |
| `probe read --contact <alias> --limit 5 --output <json>` | 通过 Replica 读取测试单聊，原文仅写私有报告 |
| `probe send --contact <alias> --text <text> --confirm-send` | 一次显式固定回复；默认 dry-run，不确定时暂停 |
| `prototype --mode dry-run或live --duration <seconds>` | Phase 2 最小 Agent 循环，复用正式包和账本 |
| `serve --host 127.0.0.1 --port <port>` | 本地应用与 worker 管理，用户明确开始后才连接/运行 |
| `replay --suite <name> --output <json>` | 合成输入回放，结果标为 offline，不接触微信 |
| `verify` / `package --video <path>` | 检查/打包已存在的真实产物，不启动客户端、不上传或推送 |

当前已实现 doctor/connect/probe/resolve/prototype；serve/replay/verify/package 仍是后续目标，不能将其标为已可执行。

| 配置组 | 目标字段 |
| --- | --- |
| 微信 | WECHAT_ADAPTER=replica、WECHAT_PROFILE、WECHAT_ACCOUNT_REF、WECHAT_DB_ROOT、WECHAT_ALLOWLIST |
| 基座 | WECHAT_OCR_ENABLED=true、WECHAT_UIA_GATE_ENABLED=true、私有缓存/校准目录；变更需停止后重连 |
| 模型 | LLM_BASE_URL、LLM_API_KEY、LLM_MODEL、LLM_TIMEOUT_SECONDS、LLM_MAX_INPUT_TOKENS、LLM_MAX_OUTPUT_TOKENS、LLM_MAX_CALLS_PER_TURN |
| 运行 | POLL_INTERVAL_SECONDS=15、SEND_MODE=dry-run、COALESCE_WINDOW_MS、QUEUE_MAX_SIZE、MAX_SENDS_PER_MINUTE |
| 存储/服务 | DATA_DIR、RETENTION_DAYS、APP_HOST=127.0.0.1、APP_PORT、必要的知识/文件大小限制 |

配置优先级为环境变量 > .env > 默认值。API 仅返回 configured/掩码，空密钥表示保留，显式清除才删除；前端不使用 VITE_* 保存秘密。保存需先校验、原子替换，Windows/非 Windows 的设置读取与离线测试均可执行。

### 5.2 身份、消息与消费

- ConversationRef 包含本地别名、account_ref、原生会话 username 和身份依据；昵称只用于显示和绑定复核。
- InboundEvent 记录原生来源的 account/session/shard/local_id、sort_seq、发送者、方向、类型和 observed_at；source_message_id 不冒充服务端 ID。
- 消息唯一键包含账号代数、会话、分片和 local_id。sort_seq 仅作排序/扫描边界，不能独自保证唯一；库替换、账号切换或无法对齐边界时重新绑定并暂停。
- 启动先记录基线，已持久化的未完成发送保持暂停，默认不补发停机期间历史。同文新消息独立处理；来源身份不足时不自动回复。
- 读取事件、inbox 与应用游标在同一事务提交。模型只消费已入库事件，不直接驱动 GUI；同一会话串行，连续短消息可合并为一个输入批次。

### 5.3 Agent 与发送

Phase 2 即使用最小 LangGraph：输入过滤 → 上下文 → 模型 → 输出校验 → 待发送结果；Phase 5 扩展检索/记忆节点，Phase 6 按选项接工具。聊天文本、知识和模型输出都是数据，不得变成任意终端命令或基座方法调用。

outbox 由一组 inbox 输入唯一生成，记录运行代数、目标、草稿和状态。发送前验证账号/白名单/会话/草稿策略/焦点；按基座 UIA/OCR 复核，不因允许 OCR 而省略目标检查。初始只接受空白草稿，不覆盖既有用户内容。

SendResult 保留 verified_sent / not_sent / unknown：

- verified_sent 必须带目标会话中新的本人发出记录及完整文本匹配证据，依据标为 local_db_confirmed；对端是否收到由 G1/G2 人工核对，不声称服务器送达回执。
- not_sent 仅用于证实尚未发生发送动作的拒绝；超时、异常或缺少水位而可能已发送时为 unknown。
- unknown 停止该会话自动发送，提供人工核实后标已发/作废的入口，不一键盲目重发。

运行状态为 stopped/starting/running/paused/degraded/stopping。暂停或停止递增运行代数，废弃迟到模型结果；恢复不自动发送旧队列。单实例、单 GUI 执行通道，模型调用不能绕过 outbox 直接 SendMsg。

## 6. 单一主阶段表

| 阶段 | 主题 | 交付等级 | 状态 | 当前事实与依赖 |
| --- | --- | --- | --- | --- |
| Phase 1 | 基座内化、适配与固定收发 | 必需 | completed | 固定基座已内化；Windows 4.1.15.56 G1 通过，私有报告已记录 |
| Phase 2 | 最小 Agent 闭环 | 必需 | completed | LangGraph/SQLite 原型与 DeepSeek 三轮 G2 通过；达到 3 条上限后已停发 |
| Phase 3 | 配置、持久化与运行控制 | 必需 | pending | G2 已通过；本次范围止于 Phase 2，正式仓储/服务待后续授权 |
| Phase 4 | 本地 API 与工作台 | 必需 | pending | Phase 3；前端仅静态验证，用户验收界面 |
| Phase 5 | 知识检索与长期记忆 | 必需 | pending | Phase 4；复用 Phase 2 Agent 扩展 |
| Phase 6 | 业务工具、文件与语音入口 | 可选，未选择 | pending | Phase 5；未选择则记录不纳入并转 Phase 7 |
| Phase 7 | 集成回归、录像与交付 | 必需 | pending | Phase 5，以及已选择的 Phase 6 项 |

Phase 4–7 已有具体实施与验收定义，但不因本次计划修订而扩大现有自动执行范围。达到 Phase 3 后停止自动推进，汇报结果；不能将 Phase 3 完成称为整个应用交付完成。

### Phase 1：内化微信控制基座并通过 G1

目标文件：third_party/wechatauto_replica/、adapters/wechat/replica*.py、平台隔离的 cli.py、配置/profile、tests/adapter/、原型报告、复用登记和第三方声明。

任务：

- [x] 固定 SHA 导入源码与资源，记录许可、来源和本地补丁；本地 path 依赖在 Windows 锁定，Mac 不安装 Windows 原生包。
- [x] 实现 ReplicaAdapter/Bridge、明确账号与测试会话映射，归一化消息类型、发送者与方向；不启用上游全会话/媒体/朋友圈功能。
- [x] 处理第 4 节中影响当前通道的并列游标、方向、发送水位/重试、新鲜度与缓存/日志问题，保留可追溯补丁和必要合成回归，不扩展为通用底层重写。
- [x] Windows doctor/connect/probe read/send 可用，OCR/热激活按配置执行；移除 Windows 对 fcntl/Mac CLI 的运行依赖。
- [x] 先只读验证，再 dry-run，最后一次显式固定回复；每一步都有稳定错误、私有报告和停发出口。
- [x] 报告生成器补充 plan_version/foundation，旧案例和数据不自动填成新基座 passed。

验收：

- P01-01：无 Windows 原生库时仍可导入契约/配置并运行离线测试；doctor 不取钥、不写进程。
- P01-02：Windows 版本、账号绑定、数据路径、缓存、基座能力记录准确，初始化失败不伪装 healthy。
- P01-03：一个测试好友的 5 条文本含连续同文、本人消息，逐条内容/顺序/方向正确；未知方向、错目标和群聊被过滤。
- P01-04：dry-run 不按键；显式固定回复由对端确认；草稿/焦点/目标不符拒绝，可能发送后的失败保持 unknown。
- P01-05：合成同 sort_seq 跨批/跨分片、新旧同文发送回读和坏库/旧快照错误，验证应用能去重、拒绝错误确认并暴露降级；未覆盖的 WAL 边界明确披露。

完成记录（2026-10-21）：固定 SHA 内化、Windows extra/锁、懒加载适配、doctor/connect/probe、并列游标、发送证据及隐私限制已实现。92 项离线测试通过。Windows 微信 4.1.15.56 签名有效；进程账号与原生测试单聊绑定，5 条来信含连续同文和 1 条本人发出记录逐条核对，dry-run 无按键，一次固定回复经本地新记录和用户对端确认。反例/损坏快照为合成验证，不冒充实机故障。G1 passed；证据 `.local/acceptance/phase-1/report.json`。完整 WAL 提交/累计 checksum 边界仍未覆盖，见 UPSTREAM.md。

### Phase 2：最小 LangGraph Agent 与 G2

目标文件：agent/graph.py、llm/、runtime/prototype.py、最小 storage/、tests/prototype/；直接扩展正式应用包。

任务：

- [x] 可配置真实模型、简短人设、结构化 AgentResult、输入/输出限制、超时和调用预算；FakeModel 仅用于离线测试。
- [x] 应用低频轮询、基线、inbox/游标事务、本人/系统过滤、连续消息合并与单会话串行接通 Agent。
- [x] 先持久化模型结果和 outbox，再由唯一 GUI 通道调用基座；回调/模型重试不重试已不确定的发送。
- [x] prototype 支持 dry-run/live、停止与错误报告；公开日志不含私聊或凭据。

验收：

- P02-01：离线跑通收→入库→模型→outbox→假发送，并验证模型超时、重复输入和发送未知分支。
- P02-02：真实微信完成至少 3 轮问答，含“我叫小周→我刚才说叫什么”的上下文追问。
- P02-03：本人、非白名单、系统和未知方向不触发模型/发送，无自循环。
- P02-04：重复回调/轮询只生成一个 outbox；连续同文新消息可分别处理；重启重新建基线，不回复旧历史。
- P02-05：记录真实轮询、模型和发送耗时，不以旧实时指标拒绝固定环境演示，也不隐瞒实际延迟。

完成记录（2026-10-21）：最小 LangGraph、限时单次 DeepSeek 兼容调用、输入/输出预算、SQLite inbox/游标事务、合并/串行/outbox、跨重启基线和 unknown 停发已实现。121 项离线测试、Ruff 和构建通过；源码归档在新目录完成 Windows 锁安装及 CLI 导入。真实模型使用 deepseek-flash，已完成 3 轮微信问答，用户确认全部收件且上下文追问记得测试姓名；G2 passed。真实 poll 约 0.34–0.38 秒，模型约 1.2–1.5 秒，发送/回读约 3.4 秒；轮询配置 15 秒，发送间隔约 51 秒。原始证据 `.local/acceptance/phase-2/report.json`，不把离线反例当实机故障。worker 达到 3 条上限后已停止。Phase 3 未实施。

### Phase 3：配置、仓储与运行控制收敛

目标文件：config.py、storage/database.py/migrations.py/repositories.py、runtime/service.py/worker.py、domain/ 与对应 tests/config、tests/storage、tests/runtime。

任务：

- [ ] 收敛所有设置、来源、校验、掩码、原子保存；上游缓存/校准与应用 DATA_DIR 一起管理。
- [ ] 原型数据迁移为正式 contacts/conversations/inbox/messages/outbox/cursors/runtime_state/agent_runs，保留既有身份与去重记录。
- [ ] 实现 SQLite 事务/约束、单实例、跨平台文件锁、队列上限、运行代数、启停与 degraded 恢复。
- [ ] 崩溃后未确认 outbox 暂停待人工处理；退出不遗留工作线程或继续操作微信。
- [ ] 同步 README、接口、Windows 证据与许可证；到此达到现有自动范围终点。

验收：

- P03-01：配置优先级、非法配置与保存失败不损坏旧值，秘密不经 API/日志返回。
- P03-02：迁移/重启保留 inbox/outbox/身份，无重复消息/意图；数据库替换和账号变化有明确拒绝。
- P03-03：暂停后迟到模型结果不可发送，恢复不发旧队列；单实例、队列满与异常退出可恢复。
- P03-04：Windows 干净工作目录可按锁安装和运行既有 CLI/prototype；离线与真实结论分别记录。

完成记录：未开始；完成后自动范围停止于 Phase 3，不自动实施工作台。

### Phase 4：最终应用 API、工作台与统一启动

目标文件：api/、ui/、runtime/services、cli serve、tests/api/ 与必要前端逻辑测试。

API 至少包括 GET /api/health、GET /api/runtime、POST /api/runtime/{start,pause,resume,stop}、GET /api/conversations、GET /api/conversations/{id}/messages、GET /api/runs/{trace_id}、GET/PATCH /api/settings、POST /api/diagnostics、POST /api/outbox/{id}/resolve。Phase 5 增加 /api/knowledge/documents 和 /api/memories 的必要增删改查，不新增第二套运行服务。

任务：

- [ ] FastAPI 仅监听 loopback，同源服务静态页/API，校验 Host/Origin 和写操作来源；错误只返回稳定 code/message/trace_id。
- [ ] 接通健康/能力、启停、会话/消息/Agent 记录、outbox 人工处理、配置掩码与保存、显式诊断 API。
- [ ] React/TypeScript/Vite 工作台采用概览、会话、设置三个入口；空态、未连接、dry-run/live、unknown 与真实连接状态清楚。
- [ ] 使用现有组件库构建简洁桌面布局；状态和时间线解释输入、回复结果与过滤原因，不展示隐藏思维链或基座原始对象。
- [ ] serve 使用正式运行服务，初始停止，不自动打开网页；源码安装与构建后同源启动均可操作。

验收：

- P04-01：API 状态迁移/分页/错误/来源校验通过，无秘密字段或原始异常。
- P04-02：启停、保存、诊断、会话记录和 unknown 处理均调用真实后端，无占位按钮。
- P04-03：前端类型检查与构建通过；用户验证界面、交互和微信状态同步。
- P04-04：uv run wechat-agent serve 可从构建产物启动；没有 Node 开发服务器时仍能管理运行。

完成记录：未开始。

### Phase 5：知识检索与按联系人隔离的长期记忆

目标文件：knowledge/、memory/、agent/ 检索/记忆节点、相应仓储/API、工作台知识与记忆入口。

任务：

- [ ] 先支持本地 TXT/Markdown 知识导入、分块、jieba 中文切词与 FTS5 检索、来源引用、删除后不再召回；不增加向量服务。
- [ ] 在既有 LangGraph 中加入确定边界的检索和记忆读取/更新；无知识命中时明确说明，不编造来源。
- [ ] 区分短期上下文与长期事实；按账号/联系人隔离，支持偏好更正、查看/删除与跨重启保留。
- [ ] 工作台可导入/删除知识、查看/更正/忘记记忆，并展示真实处理结果。
- [ ] 聊天和文档不能修改系统设置、调用任意命令或读取其他联系人资料。

验收：

- P05-01：虚构知识问答可定位来源，无命中和删除后结果正确。
- P05-02：记住测试偏好，重启后仍可使用；更正与忘记生效，其他联系人不可见。
- P05-03：知识/记忆入口接真实 API，失败有明确状态；用户在微信核对回复。
- P05-04：模型输入受上下文预算限制，知识与记忆不会无界增长或直接进入运维日志。

完成记录：未开始。

### Phase 6：可选业务工具、文件与语音入口

选择状态：未选择。Phase 5 后可直接进入 Phase 7；不为可选项预留无动作入口。

可选任务：

- [ ] 业务工具：虚构订单查询和工单创建，Pydantic 参数校验/联系人范围约束；写入工具有会话级确认、过期与幂等。
- [ ] 文件：按需扩展文本 PDF/DOCX 解析，复用成熟库；文件导入/分析明确标注人工来源。
- [ ] 语音：复用基座可获取的本地素材或人工转写入口；ASR 为独立可替换配置，不承诺未下载音频可读。
- [ ] 只对选中项接工作台、Agent 和测试；未选择项在 README 写明不纳入。

验收：

- P06-01：选中工具参数、权限、取消/确认/幂等和超时分支正确，无真实业务写入。
- P06-02：选中文件/语音能力使用合成样例和真实可得输入验证，不把占位符当正文。
- P06-03：选中功能在最终应用与演示中可操作，其余入口隐藏。

完成记录：未开始；未选择不标 passed，交付清单注明不纳入。

### Phase 7：集成回归、真实录像与源码交付

目标文件：scripts/acceptance/、docs/demo-script.md、docs/delivery-checklist.md、package/verify 命令与 dist/submission/。

任务：

- [ ] 以正式服务回放同文/重复事件、本人/未知过滤、模型失败、发送未知、暂停/重启和知识/记忆更新，必要自动检查通过。
- [ ] 在唯一支持组合完成代表性微信对话及工作台操作；记录版本、窗口条件、延迟和已知限制，不要求第二版本或 24 小时运行。
- [ ] 给出 3–5 分钟真实录像脚本：启动→好友提问与追问→知识问答→记忆→暂停恢复→工作台记录；选中 Phase 6 时再加入相应场景。
- [ ] 用户录制并核对视频；真实读写、人工操作和实际等待如实呈现，剪辑标明，未实现能力不展示为已实现。
- [ ] 交付包含应用源码、内置基座、锁文件、合成样例、许可/NOTICE、启动说明、脱敏验收摘要和视频；排除 .env、密钥、解密库、校准截图、私聊与运行缓存。
- [ ] 从干净目录核对包内相对路径、uv 本地 path 依赖和启动；只打本地包，不默认推送、发布或上传。

验收：

- P07-01：必要 Python/前端检查通过，关键故障回放与运行状态一致。
- P07-02：Windows 干净目录可安装并启动完整应用，third_party 不依赖开发机绝对路径。
- P07-03：视频文件实际存在、可播放、展示真实闭环和支持限制，经用户确认。
- P07-04：源码包/历史/录像不含秘密或无关私聊，许可与上游补丁记录齐备。

完成记录：未开始。缺真实录像、G1/G2 或必需功能时不得标整个应用完成。

## 7. 验证、日志与协作纪律

- 自动验证针对契约、身份/去重、事务/崩溃、Agent/接口和构建。微信、模型效果、界面和视频由用户核对，mock 不替代真人结果。
- 助手不自行打开页面、Playwright、CUA 或 GitNexus；不创建子 agent、新会话、worktree 或自动 relay。前端只做静态/构建和必要逻辑测试。
- 原生微信依赖懒加载，Mac 可运行应用纯逻辑测试；Windows 完成原生初始化、取钥、UIA/OCR、键鼠和真实收发。
- 报告位于 .local/acceptance/phase-N/report.json，字段含阶段、commit、环境、模式、case/expected/actual/status/evidence_ref；人工项未核实为 not_tested，失败为 failed，无证据不填 passed。
- 日志保留时间、事件、trace、脱敏会话/消息引用、耗时、状态和原因；不打印正文、昵称、完整 prompt、模型密钥、数据库密钥或隐藏思维链。
- 第三方生成的密钥/备份/明文库/图片/校准资源同样纳入私有目录、保留期、删除与 ACL 检查，不能只忽略应用自己的文件。
- 代码/文档/验证按功能形成真实英文 Conventional Commits，不默认 push；公开材料不包含聊天原话、非技术讨论或私有环境信息。

## 8. 续做与旧版本衔接

1. 下一次先读本计划、overview 和 Windows 接入说明，核对当前工作区、提交、已有 Windows 证据及适用约束。
2. 不再安装旧 wxauto4 探针依赖，不按旧 Mac AX/OCR 选型继续试错；旧文件只作历史，必要契约和测试可复用。
3. 本次明确执行 Phase 1–2，已完成并停止；原 1–3 自动范围不覆盖本次收窄指令。G1/G2 缺失或环境未就绪时记录 blocked 和解除条件，不能跳关。
4. Phase 1–3 编号保持，旧 Phase 4–6/11–15 相关应用集成合并到新 Phase 4；旧 7/9/13 的知识记忆归新 Phase 5；旧 8/10 的工具与附件归新 Phase 6；旧 15–18 的打包/验证/录像归新 Phase 7。
5. 旧用例编号和报告保留其日期与方案，不改写旧测试结果，不将其映射成新基座已通过；新记录注明 plan_version=v4 和 foundation=replica。
6. Phase 3 后仍保留当前授权终点；后续实施按明确阶段/范围指令推进，不因已写出计划而自行执行。
7. 运行时遇到上游缺陷只做必要且可追溯的补丁；改变产品范围、控制路线或支持声明须明确更新本计划。

## 9. 最终完成条件

Phase 1–5 与 Phase 7 的必需任务、G1/G2、工作台人工验收和真实视频齐备；Phase 6 仅对明确选择的项目验收。应用可从干净 Windows 源码包启动，复用基座作为内置依赖，Agent/知识/记忆/状态/API/UI 接通，发送不确定时停止，许可证和来源清楚，交付无秘密与私聊。仅通道库、离线截图、模型控制台或阶段文档不能作为最终完成。

本次执行范围由用户明确收窄为 Phase 1–2；完成 Phase 2 后停止，不自动实施 Phase 3。测试采用单好友低频、至少 30 秒发送间隔、单次最多 3 条回复；不承诺避免账号限制。
