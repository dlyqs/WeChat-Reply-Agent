# 个人微信 AI 回复 Agent 执行计划

更新日期：2026-10-21（Asia/Shanghai）。计划版本：v5。
本文件是阶段状态、实施顺序和完成条件的唯一来源；代码导航见 [overview.md](overview.md)。

~~~text
execution mode: execute_phases_5_6
automatic start phase: 5
automatic stop phase: 6 (requires phase 5 G1/G2)
execution state: blocked_phase_5_native_bootstrap
conversation relay: off
current change: implement mac_db prototype; bootstrap blocked by Apple LLDB SIGBUS
last completed implementation scope: phase 1-4 on Windows
next implementation phase: 5 (resume after Apple LLDB repair; no live sends yet)
windows foundation: wechatauto-replica 1.2.7.0
windows upstream commit: d322c4a9b1124228820bab363e5676016f188fc6
macOS reference: acmerfight/0a01249ef72970d07a2603dbb629e80f
macOS reference revision: c98dbb10cf23c30e83d5d744905101b0880887a0
~~~

v5 在 v4 的 Phase 4 后插入 Phase 5「macOS 原型验证」和 Phase 6「macOS 与 Windows 已有功能对齐」；原 Phase 5/6/7 分别顺延为 Phase 7/8/9。Windows Phase 1–4 的完成事实、用例和私有报告保持原样。本次用户已明确授权 Phase 5–6，Phase 5 软件和合成验证已实施；首次取钥被 Apple LLDB 崩溃阻塞，尚未真实发送，Phase 6 未进入。具体完成事实见各阶段记录。

## 1. 交付目标与范围

交付一个分别在固定 Windows 和 macOS 桌面环境运行的个人微信回复应用：指定测试好友发来文本，应用按间隔读取、过滤、归入会话，调用 Agent 后通过当前微信账号回复。两平台共用 Agent、应用账本、运行控制、API 和工作台，原生接入按平台隔离；每次运行只控制本机一个账号和测试好友单聊。应用后续接入知识与记忆，并提供真实演示视频和可复现源码包。

Windows 微信控制继续采用 [fanyuantaier/wechatauto-replica](https://github.com/fanyuantaier/wechatauto-replica/tree/d322c4a9b1124228820bab363e5676016f188fc6)。Mac 参考 [acmerfight 的 Mac 工具](https://gist.github.com/acmerfight/0a01249ef72970d07a2603dbb629e80f)，采用「数据库/WAL 结构化读取 + 原生界面发送 + 数据库回读」路线。发送沿用本项目 Windows 已实现的目标/草稿/焦点/全文检查、单次发送和三态结果；OCR 允许用于界面核验，消息事件仍来自数据库。复用成熟 SQLCipher 和系统原生能力，不重写解密引擎或微信协议。

### 1.1 最终交付必需项

- Windows 10/11 x64 与 macOS Apple Silicon 各一个实际验证过的系统/微信版本组合；每个平台明确绑定本机账号和测试好友，只承诺文字收发。Mac 支持须通过 Phase 5/6 才成立，不能借用 Windows 或上游证据。
- 可配置的低频轮询，默认 15 秒，演示允许 10–30 秒；按本机实际耗时展示，不承诺实时、所有版本、全天候或后台无桌面运行。
- 白名单、本人/系统/未知方向过滤、连续消息合并、消息级去重、会话串行、持久化 inbox/outbox 与 unknown 停发。
- LangGraph 最小 Agent、多轮上下文、可配置模型与人设、超时/长度/调用预算；小规模本地知识检索和按联系人隔离的长期记忆。
- 简约本地工作台：状态与启停、会话/执行记录、配置与诊断，Phase 6 完成 Mac 对齐，Phase 7 再接入知识/记忆管理。
- 原创代码的非商业许可、第三方来源与补丁记录、安装/启动/限制说明、真实录像和无私密数据的源码包。

### 1.2 可选增强与明确不做

Phase 8 的虚构业务工具、文件分析和语音转写入口为可选增强，初始未选择；未实现时不显示功能入口，也不作为最终交付缺口。需要采用时在主表明确选择，不以空实现通过验收。

不要求 Mac Intel/Rosetta、多版本矩阵、群聊、多账号并发、跨设备同步账本、全量历史导入、原始音视频获取、朋友圈、批量营销、云托管、原生安装器或长期稳定性认证。Gist 的媒体/群聊能力不自动纳入范围。首次启动建立基线，默认不回复启动前历史；停机期间不承诺无损补收。

## 2. 基座版本、运行前提与权限边界

### 2.1 Windows：保留已验证路线

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

### 2.2 macOS：原型路线与支持前提

参考版本固定为 Gist revision `c98dbb10cf23c30e83d5d744905101b0880887a0`（2026-10-20，MIT）；实施前核对文件哈希和完整许可。重点参考读取/取钥代码、Swift 界面桥和 `send_verified.py`；上游自测与本项目验收分开记录。

上游记录为 macOS 15.6.1 / Apple Silicon / 微信 4.1.15；本机现状为 macOS 27.0.1 / arm64 / 微信 4.1.5（31960），尚无新路线实机通过证据。旧 AX 探针在此组合找不到消息列表与输入框，保留作历史；新通道不以这些 AX 子控件可见为前提。

| 项目 | Mac 方案与边界 |
| --- | --- |
| 读取 | 显式绑定本机账号、数据库根目录、本人/好友 username；验证逐库密钥后，以 SQLCipher 只读 DB+WAL 输出结构化事件，禁止修改聊天数据库来发送 |
| 首次取钥 | 优先复验已有密钥；缺失或失效时采用受控临时应用副本和 LLDB 捕获路径，限选定账号，设置超时、退出与恢复步骤。此流程会中断微信，并可能影响登录/缓存/原账号数据，不视为独立沙箱 |
| 原版与系统 | 保留原版路径、签名和聊天数据，不重签原版、不关闭 SIP、不安装全局 Hook；临时副本的创建、签名、启动和清理由独立显式初始化承担，不放进 doctor 或普通开始/恢复 |
| 原生发送 | ScreenCaptureKit/Apple Vision、系统剪贴板与键鼠事件；核对实际进程、目标主窗、会话、草稿、焦点和输入全文，单次发送后独立查库。AX 窗口信息可作辅助，不依赖旧消息控件标识 |
| 环境 | 原生 arm64、交互桌面解锁、微信已登录且主窗可见；记录准确版本、发行渠道、语言、主题、窗口/屏幕缩放与实际权限，窗口遮挡或身份不明时拒绝操作 |
| 依赖 | 主应用保持 Python 3.12/3.13；上游 Reader 的 Python 3.14 `compression.zstd` 改用兼容依赖。SQLCipher 动态库、Swift 编译产物和 Apple LLDB 运行环境分别声明，验证 ABI/架构；不直接混用 Python/LLDB |
| 初始化 | doctor 只读检查依赖/权限/版本；已有密钥的 connect 校验账号和缓存。缺密钥返回明确状态，进入独立 bootstrap；开始/恢复不自动重签、退出微信、重新登录或再次取钥 |
| 人工职责 | 用户处理系统授权、正常退出/登录、账号与测试好友核对、测试消息及对端收件、工作台验收和录像；自动终端/原生验证限后续阶段执行范围 |

Phase 5 可先限制为人工预选单聊和短单行文本，必须显式报告能力限制；Phase 6 要验证目标导航与应用配置范围内的回复处理，不能把短文本、人工切换或上游局部成功直接记为功能对齐。权限/签名/密钥失败时记录具体阻塞，不自动换微信版本或改系统保护。

## 3. 基座内化与应用边界

### 3.1 内化方式

在 Phase 1 把固定源码快照作为本地第三方依赖纳入 third_party/wechatauto_replica/，保留上游 wechatauto 包名、Apache-2.0 LICENSE、必要版权/NOTICE、包元数据、README_pypi.md 和运行资源。保留依赖所需模块，避免因顶层导入链裁剪造成运行时缺失；不复制 .git、账号数据、开发者代理指令或无关开发缓存。

主项目通过 uv 的本地 path source 和仅 Windows 生效的 extra 接入。上游仍是独立 Python 包，应用只通过适配器调用，不将上游各模块散拷进 Agent 或 UI。提交包必须包含该本地依赖目录，不能依赖另一台电脑的绝对路径或临时 pip 安装。

third_party/wechatauto_replica/UPSTREAM.md 记录来源、精确 SHA、导入文件、上游版本、资源、依赖和每个本地补丁；原依赖范围经 Windows 锁解析收敛到 uv.lock。升级是明确的补丁/版本变更，不在应用启动时自动拉取。

仅对影响本期收发、身份、隐私或运行的具体问题做最小补丁；不重写 SQLCipher、OCR 引擎或整套 UI 自动化。固定源码已在 Phase 1 导入，实际补丁和限制见 third_party/wechatauto_replica/UPSTREAM.md。

Mac 在 Phase 5 按上述固定 revision 选择内化必要源码到 `third_party/wechat_mac_toolkit/`（计划路径），保留 MIT、逐文件来源/哈希与补丁记录；不下载上游私有数据，也不执行其代理指令。保留可审计的 Reader/Swift 桥，通过本项目适配器和结构化进程接口调用。SQLCipher/Zstandard 等依赖单列来源与安装步骤；Phase 6 完成 Mac extra、锁文件、桥构建和干净安装，不让 Windows 安装 Mac 原生包。

### 3.2 模块职责

除 third_party/、ui/、scripts/ 和 tests/ 外，下表应用模块均位于 src/wechat_reply_agent/ 内。

| 位置 | 职责 |
| --- | --- |
| third_party/wechatauto_replica/ | 上游读取、解密、WAL、UIA/OCR/键鼠能力与最小修复 |
| adapters/wechat/replica.py、replica_bridge.py | 懒加载、账号绑定、字段规范化、原生调用、发送结果映射与能力报告 |
| third_party/wechat_mac_toolkit/、adapters/wechat/mac_db*.py（待新增） | Mac 只读数据库/取钥辅助与原生界面桥、MacAdapter/profile/能力和三态发送；与 Windows 原生包隔离 |
| adapters/wechat/base.py、domain/ 平台契约（待扩展） | 统一连接/关闭、绑定身份、源库文件身份、能力与报告依据；运行服务不直接理解第三方 profile 或目录 |
| domain/ | 与第三方对象解耦的会话、消息、Agent、发送和运行契约 |
| storage/ | 应用 SQLite、inbox/outbox、游标、上下文、记忆、知识与运行记录 |
| runtime/ | 轮询、基线、事务入库、合并/队列、暂停代数、单实例与唯一 GUI 执行通道 |
| agent/、llm/ | LangGraph 路由、模型、人设、上下文/预算、检索和记忆 |
| api/、ui/ | 本地管理应用；UI 仅调用本项目 API，不直接操作基座 |
| scripts/acceptance/、tests/ | 脱敏实机报告、合成回放与必要故障测试 |

最终链路：

~~~mermaid
flowchart LR
  W[微信客户端] --> B[Windows Replica / Mac SQLCipher 读取]
  B --> A[适配器与身份过滤]
  A --> I[SQLite inbox 与游标]
  I --> Q[会话队列]
  Q --> G[LangGraph Agent]
  K[知识与记忆] --> G
  G --> O[SQLite outbox]
  O --> S[Windows UIA / Mac 原生界面发送]
  S --> W
  U[本地工作台] --> R[应用运行服务]
  R --> Q
  R --> O
~~~

### 3.3 复用与许可证

原创 Agent、适配器、工作台等继续采用根 LICENSE 的 PolyForm Noncommercial 1.0.0。Windows 基座保留 Apache-2.0；Mac 参考源码及已有 MIT 改编代码保留 MIT、版权与适用修改声明，不把上游原有代码的权利改成禁止商业使用。所有依赖/资源按各自许可列入复用登记和 THIRD_PARTY_NOTICES.md。

应用的价值与改动要标清：微信读写来自基座，Agent 编排、应用状态、业务设计和集成为本项目实现。计划、文档和提交仅记录客观技术方案、变更与验证结果。

## 4. 集成时的必要封装与已知限制

下表来自 Windows 基座固定快照的静态审阅，不是本机故障复现。Phase 1/2 优先处理会造成身份错误、重复发送或阻断当前演示的问题；不把完整底层审计升级为重建基座的前置任务。Mac 后续复用这些发送/身份约束，具体新增项见表后。

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

Mac 新增集成约束：

- Gist 的增量批次和 ack 不替代应用 inbox/事务游标；分页满批必须继续读取或明确报告积压，不能跳到最新位置。以账号/源库代数、会话、分库和 local_id 标识事件，覆盖同秒/同文与多会话，不直接照搬单个时间戳或全局 local_id。
- 优先让 SQLCipher 处理有效 WAL；验证并发写入、未提交记录、checkpoint/reset、库替换、错误密钥和源库新鲜度。快照失败不能回退旧数据后继续发送，未覆盖边界写入限制。
- Gist 的 UI 核验和服务器 ID 可作辅助证据；应用成功依据与 Windows 一致，必须有发送前水位、同会话新增本人记录和全文匹配。只出现绿色气泡、非零 ID 或旧同文记录都不足以单独确认；多条候选无法归因时保持 unknown。
- 将原生桥操作 ID 固定映射到 outbox_id；共享同一私有状态目录和互斥锁。已有 prepared/dispatching/unknown 不换 ID、不换发送快捷键重试，人工 resolve 只记结论。
- 进程/窗口/账号必须一致；应用前台或背景截图成功不能证明目标主窗可接收输入。遮挡、布局变化、同名联系人或登录窗不能确认时停发，数据库回读不能替代发送前目标核验。
- 当前 Prototype 读取 Replica profile 字段，RuntimeService 直接拼库路径并限定 v4 Replica 报告。Phase 5 只提取原型必需契约，Phase 6 再完成正式运行服务解耦；不伪造 Replica profile、报告或降低 confidence/身份要求来接入 Mac。

## 5. 应用运行与数据契约

### 5.1 启动与配置

目标唯一入口为 uv run wechat-agent serve；FastAPI 同源提供构建后的 React/TypeScript/Vite 页面，不自动打开浏览器。worker 初始 stopped、模式 dry-run、白名单为空。开发时可用单独 UI dev 命令，前端仅作类型/构建/必要逻辑验证，界面由用户验收。

| CLI 目标 | 行为 |
| --- | --- |
| `doctor --output <json>` | 只读检查平台、依赖、客户端版本和可用权限；不取钥、不热激活 |
| `connect --output <json>` | Windows 按原路线初始化；Mac 校验已有密钥/账号/原生桥，首次 bootstrap 独立执行；输出脱敏步骤结果 |
| `probe read --contact <alias> --limit 5 --output <json>` | 通过选定平台适配器读取测试单聊，原文仅写私有报告 |
| `probe send --contact <alias> --text <text> --confirm-send` | 一次显式固定回复；默认 dry-run，不确定时暂停 |
| `prototype --mode dry-run或live --duration <seconds>` | Windows Phase 2 已实现；Mac 在 Phase 5 复用最小 Agent 和账本，要求对应平台 G1 |
| `serve --host 127.0.0.1 --port <port>` | 本地应用与 worker 管理，用户明确开始后才连接/运行 |
| `replay --suite <name> --output <json>` | 合成输入回放，结果标为 offline，不接触微信 |
| `verify` / `package --video <path>` | 检查/打包已存在的真实产物，不启动客户端、不上传或推送 |

Windows 已实现 doctor/connect/probe/resolve/prototype/serve。Mac 已实现 mac_db doctor/connect/probe/resolve/prototype、独立 mac-bootstrap 和 G1 报告识别，但真实取钥/收发未过；Mac serve 属于尚未进入的 Phase 6，当前明确拒绝。旧 mac_ax 只有历史探针。replay/verify/package 仍是后续目标，不能标为已可执行。Phase 3–4 干净安装验证脚本不是 Phase 9 的 verify/package 命令。

| 配置组 | 目标字段 |
| --- | --- |
| 微信 | Windows WECHAT_ADAPTER=replica；Mac 目标值 mac_db（待新增）；WECHAT_PROFILE、WECHAT_ACCOUNT_REF、WECHAT_DB_ROOT、WECHAT_ALLOWLIST |
| 基座 | WECHAT_OCR_ENABLED=true；WECHAT_UIA_GATE_ENABLED 仅 Windows；Mac 的密钥/桥路径、布局和发送快捷键在 Phase 5 确定并校验，不支持项明确显示；变更需停止后重连 |
| 模型 | LLM_BASE_URL、LLM_API_KEY、LLM_MODEL、LLM_TIMEOUT_SECONDS、LLM_MAX_INPUT_TOKENS、LLM_MAX_OUTPUT_TOKENS、LLM_MAX_CALLS_PER_TURN |
| 运行 | POLL_INTERVAL_SECONDS=15、SEND_MODE=dry-run、COALESCE_WINDOW_MS、QUEUE_MAX_SIZE、MAX_SENDS_PER_MINUTE |
| 存储/服务 | DATA_DIR、RETENTION_DAYS、APP_HOST=127.0.0.1、APP_PORT、必要的知识/文件大小限制 |

配置优先级为环境变量 > .env > 默认值。API 仅返回 configured/掩码，空密钥表示保留，显式清除才删除；前端不使用 VITE_* 保存秘密。保存需先校验、原子替换，Windows/非 Windows 的设置读取与离线测试均可执行。

平台选择与实际 OS 必须匹配，不静默 fallback；每个平台使用独立的 DATA_DIR/原生绑定，不直接复制 Windows 账本到 Mac 作为已绑定状态。Phase 6 新契约保留 Windows 既有消息 ID、游标、outbox 和上下文，不通过重算历史 ID 实现迁移。

### 5.2 身份、消息与消费

- ConversationRef 包含本地别名、account_ref、原生会话 username 和身份依据；昵称只用于显示和绑定复核。
- InboundEvent 记录原生来源的 account/session/shard/local_id、sort_seq、发送者、方向、类型和 observed_at；source_message_id 不冒充服务端 ID。
- 消息唯一键包含账号代数、会话、分片和 local_id。sort_seq 仅作排序/扫描边界，不能独自保证唯一；库替换、账号切换或无法对齐边界时重新绑定并暂停。
- 启动先记录基线，已持久化的未完成发送保持暂停，默认不补发停机期间历史。同文新消息独立处理；来源身份不足时不自动回复。
- 读取事件、inbox 与应用游标在同一事务提交。模型只消费已入库事件，不直接驱动 GUI；同一会话串行，连续短消息可合并为一个输入批次。

### 5.3 Agent 与发送

Phase 2 即使用最小 LangGraph：输入过滤 → 上下文 → 模型 → 输出校验 → 待发送结果；Mac 在 Phase 5/6 复用，Phase 7 扩展检索/记忆节点，Phase 8 按选项接工具。聊天文本、知识和模型输出都是数据，不得变成任意终端命令或基座方法调用。

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
| Phase 3 | 配置、持久化与运行控制 | 必需 | completed | 配置/迁移/单线程运行控制、故障回放及 Windows 干净目录锁安装通过 |
| Phase 4 | 本地 API 与工作台 | 必需 | completed | API/React 工作台/serve、自动检查及用户确认的界面/真实微信状态同步验收通过 |
| Phase 5 | macOS 固定收发与最小 Agent 原型 | 必需，新增 | blocked | 原型实现与 166 项测试通过；首次取钥在 LLDB CreateTarget 时 SIGBUS，G1/G2 未过 |
| Phase 6 | macOS 与 Windows 已有应用功能对齐 | 必需，新增 | pending | Phase 5 Mac G1/G2；完成正式服务/发送/工作台接入及 Windows 回归 |
| Phase 7 | 知识检索与长期记忆 | 必需，原 Phase 5 | pending | Phase 6；在两平台共用的 Agent/API 上扩展 |
| Phase 8 | 业务工具、文件与语音入口 | 可选，未选择，原 Phase 6 | pending | Phase 7；未选择则记录不纳入并转 Phase 9 |
| Phase 9 | 双平台集成回归、录像与交付 | 必需，原 Phase 7 | pending | Phase 6/7，以及已选择的 Phase 8 项 |

本次已授权 Phase 5–6，Phase 5 已开始；Phase 7–9 未授权实施。Mac G1 未通过不得运行 live Agent，G2 未通过不得进入 Phase 6。Mac 原型被阻塞时记录原因和证据，保留 Windows completed 状态，不把未完成 Mac 支持默认为可选或已通过。

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

完成记录（2026-10-21）：最小 LangGraph、限时单次 DeepSeek 兼容调用、输入/输出预算、SQLite inbox/游标事务、合并/串行/outbox、跨重启基线和 unknown 停发已实现。121 项离线测试、Ruff 和构建通过；源码归档在新目录完成 Windows 锁安装及 CLI 导入。真实模型使用 deepseek-flash，已完成 3 轮微信问答，用户确认全部收件且上下文追问记得测试姓名；G2 passed。真实 poll 约 0.34–0.38 秒，模型约 1.2–1.5 秒，发送/回读约 3.4 秒；轮询配置 15 秒，发送间隔约 51 秒。原始证据 `.local/acceptance/phase-2/report.json`，不把离线反例当实机故障。worker 达到 3 条上限后已停止。该完成记录形成时 Phase 3 尚未实施；本次续做见后续阶段记录。

### Phase 3：配置、仓储与运行控制收敛

目标文件：config.py、storage/database.py/migrations.py/repositories.py、runtime/service.py/worker.py、domain/ 与对应 tests/config、tests/storage、tests/runtime。

任务：

- [x] 收敛所有设置、来源、校验、掩码、原子保存；上游缓存/校准与应用 DATA_DIR 一起管理。
- [x] 原型数据迁移为正式 contacts/conversations/inbox/messages/outbox/cursors/runtime_state/agent_runs，保留既有身份与去重记录。
- [x] 实现 SQLite 事务/约束、单实例、跨平台文件锁、队列上限、运行代数、启停与 degraded 恢复。
- [x] 崩溃后未确认 outbox 暂停待人工处理；退出不遗留工作线程或继续操作微信。
- [x] 同步 README、接口、Windows 证据与许可证；继续实施本次已授权的 Phase 4。

验收：

- P03-01：配置优先级、非法配置与保存失败不损坏旧值，秘密不经 API/日志返回。
- P03-02：迁移/重启保留 inbox/outbox/身份，无重复消息/意图；数据库替换和账号变化有明确拒绝。
- P03-03：暂停后迟到模型结果不可发送，恢复不发旧队列；单实例、队列满与异常退出可恢复。
- P03-04：Windows 干净工作目录可按锁安装和运行既有 CLI/prototype；离线与真实结论分别记录。

完成记录（2026-10-21）：设置来源/校验/掩码、私有暂存与原子保存、v1 原位迁移、正式仓储、文件锁、队列上限、持久化运行代数/状态及唯一原生线程已实现。暂停丢弃迟到结果，恢复重建基线，未确认 outbox 人工处理，账号/库替换拒绝与缓存保留期均有离线验证。Windows 从无私有数据的 sdist 干净目录按锁安装 extra windows，既有 CLI 导入和 serve HTTP 检查通过；本次未重新执行原生微信收发。证据 `.local/acceptance/phase-3/report.json`、`install-check.json`。

### Phase 4：最终应用 API、工作台与统一启动

目标文件：api/、ui/、runtime/services、cli serve、tests/api/ 与必要前端逻辑测试。

API 至少包括 GET /api/health、GET /api/runtime、POST /api/runtime/{start,pause,resume,stop}、GET /api/conversations、GET /api/conversations/{id}/messages、GET /api/runs/{trace_id}、GET/PATCH /api/settings、POST /api/diagnostics、POST /api/outbox/{id}/resolve。Phase 6 为 Mac 复用这些接口，Phase 7 增加 /api/knowledge/documents 和 /api/memories 的必要增删改查，不新增第二套运行服务。

任务：

- [x] FastAPI 仅监听 loopback，同源服务静态页/API，校验 Host/Origin 和写操作来源；错误只返回稳定 code/message/trace_id。
- [x] 接通健康/能力、启停、会话/消息/Agent 记录、outbox 人工处理、配置掩码与保存、显式诊断 API。
- [x] React/TypeScript/Vite 工作台采用概览、会话、设置三个入口；空态、未连接、dry-run/live、unknown 与真实连接状态清楚。
- [x] 使用现有组件库构建简洁桌面布局；状态和时间线解释输入、回复结果与过滤原因，不展示隐藏思维链或基座原始对象。
- [x] serve 使用正式运行服务，初始停止，不自动打开网页；源码安装与构建后同源启动均可操作。

验收：

- P04-01：API 状态迁移/分页/错误/来源校验通过，无秘密字段或原始异常。
- P04-02：启停、保存、诊断、会话记录和 unknown 处理均调用真实后端，无占位按钮。
- P04-03：前端类型检查与构建通过；用户验证界面、交互和微信状态同步。
- P04-04：uv run wechat-agent serve 可从构建产物启动；没有 Node 开发服务器时仍能管理运行。

完成记录（2026-10-21）：FastAPI 回环/Host/Origin/写请求头校验、稳定错误、分页、运行控制、会话/Agent/outbox、配置与显式只读诊断 API 已接通；React/TypeScript/Vite + Radix Tabs 提供概览/会话/设置，内置构建产物由 serve 同源提供，无需 Node 服务器。137 项 Python 离线测试、Ruff、前端类型/构建、wheel/sdist 与 Windows 干净安装/真实 HTTP 检查通过。随后用户按人工清单完成页面/配置/诊断、dry-run、暂停/恢复/停止、一次 live 收件核对以及重启默认状态/历史保留检查，并确认全部通过；P04-02-live 和 P04-03-human 据用户确认标为 passed，证据来源为用户人工操作及收件核对，不是助手 UI 自动化。未要求用户刻意制造 unknown，相关故障分支仍以离线验证为依据。证据 `.local/acceptance/phase-4/report.json`，人工清单见 api-workbench.md。v4 自动实施到此停止，未进入当时的 Phase 5（本版 Phase 7）。

### Phase 5：macOS 固定收发与最小 Agent 原型验证

目标：先在本机固定组合证明「能读到真实新消息、能向正确测试好友发出并查库确认、能由现有 LLM 连续回复」。此阶段不要求先完成工作台适配。

目标文件（待新增/修改）：`third_party/wechat_mac_toolkit/`、`adapters/wechat/mac_db.py/mac_bridge.py/mac_profile.py`、原生桥构建脚本、平台契约、config/cli/prototype 的最小扩展、Mac 绑定/bootstrap/验收脚本、tests/adapter 与 tests/prototype、`docs/mac-probe.md`、复用登记和第三方声明。

任务按顺序执行：

- [x] 固定 Gist revision、核对 MIT 和必要源码/资源，记录来源与本地补丁；将 Reader 的 Zstandard 接入主项目支持的 Python，声明 SQLCipher/Swift/LLDB 依赖并先用合成数据验证。
- [ ] 实现只读 doctor 和显式原生账号/好友绑定。复验已有密钥；确需首次捕获时执行受控临时副本 bootstrap，记录原版签名/路径、选定账号、超时、退出与恢复结果，密钥只落私有目录。
- [ ] 实现 Mac 数据库读取、发送者/方向解析、消息身份和增量游标；启动建基线，读取结果与 inbox/游标事务提交后才推进消费确认；满批、坏库、旧快照和账号/源库变化有明确失败状态。
- [ ] 实现人工预选单聊的原生发送桥，先 dry-run 再一次显式固定发送。原型允许短单行文本（先以不超过 200 字验证），输入前和发送前检查目标、空草稿、主窗/焦点和全文；发送快捷键事先配置，一次操作只尝试一次。
- [ ] 以 outbox_id 驱动原生操作 ID，发送前保存数据库水位，发送后核对同会话新增本人记录和完整正文；返回应用三态，不把上游 already_sent/UI 成功直接映射为 verified_sent。异常/超时可能已发则 unknown，禁止换 ID 重试。
- [ ] 提取 Prototype 所需的连接、账号代数、联系人与身份契约，扩展 CLI 工厂和原型 G1 检查以识别 mac_db；保留 Windows 现有入口、ID 和报告兼容，公共层改动先跑 Windows 合成回归，不另写一套模型循环。
- [ ] Mac G1 通过后，用原有 LangGraph/CompatibleModel/账本执行有界 dry-run/live，沿用默认 15 秒轮询、至少 30 秒发送间隔、每分钟至多 2 次、最多 3 条；超长/原型不支持的输出拒发，不静默截断。
- [ ] 记录环境、能力限制、合成测试、实机/人工结果及耗时，形成独立 Mac G1/G2 报告；完成后停止 worker，不把 Gist 的运行记录计入本项目 passed。

验收：

- P05-01：合成加密 DB/WAL 下验证正确/错误密钥、只读拒写、未提交不可见、checkpoint/reset、同秒/同文、跨分库与满批；Windows 原有适配器/原型合成回归通过。未覆盖的格式边界列明，无密钥/正文进入公共日志。
- P05-02：本机 doctor 无激活/取钥/签名副作用；账号、目录和好友绑定唯一。取钥/密钥复验后的真实只读查询成功，恢复原版后仍可读新到消息；单纯 HMAC、schema 或旧历史查询不替代新鲜度验证。
- P05-03：测试好友发 5 条文本，含连续同文；另核对本人消息。消息数量、内容、顺序和方向逐条正确，重读不重复入库，未知身份/方向及非白名单不触发模型。
- P05-04：dry-run 不写草稿/剪贴板或注入事件；一次固定 live 在目标会话出现新的本人完整文本记录，用户确认对端收件。错标题/已有草稿/失焦/窗口遮挡等拒绝；原生无法确认的条件不得猜发，反例证据标明合成或实机。
- P05-05：旧同文、多条匹配、按键后异常、回读超时、桥进程退出或崩溃均不误报成功；同 outbox_id 不二次发送，重启保留 unknown；resolve 不操作微信。
- P05-06：P05-01–05 的必需项和人工收件核实后，Mac G1 passed。随后 dry-run 正确，再真实完成至少 3 轮 LLM 问答，含上下文追问；本人消息不自循环，达到上限后停发，用户逐轮确认收件，Mac G2 passed。
- P05-07：分别记录轮询/模型/发送/回读耗时和原型能力限制；不将仅 UI 核验、人工补发或人工调整后的结果记成无人介入成功。原型限制不能反向缩小 Windows 配置或功能。

完成条件与证据：Mac G1/G2 均通过，报告写入 `.local/acceptance/mac/phase-5/{g1,g2,report}.json`，含 `plan_version=v5`、`platform=macOS`、`foundation=mac_db`、Gist revision、准确环境和本机绑定指纹。未通过对应项为 failed/not_tested，并说明阻塞。取钥/可靠发送失败时留在本阶段，不进入 Phase 6，也不重试已经可能发送的操作。

完成记录（2026-10-21，未完成）：用户已授权 Phase 5–6。固定 Gist/MIT/逐文件哈希内化、Python 3.12 Zstandard、只读 SQLCipher DB/WAL、分库分页与事务游标、独立 Mac profile/绑定脚本、Swift 桥构建/精确草稿与遮挡检查、原生 outbox 幂等/三态/人工处理和 Mac 原型 gate 已实现。166 项 pytest、12 项额外 SQLCipher 合成自检、Swift 编译/纯函数自检、只读 doctor 和 DeepSeek Flash 连接验证通过。实际为 macOS 27.0.1 / arm64 / 微信 4.1.15（270115），完全磁盘访问授权后目录可读。首次临时副本取钥在 Apple LLDB 1703 创建目标的 Mach-O 符号解析中 SIGBUS，未捕获密钥；原版哈希/签名保持并已恢复。系统 true 目标也复现，同版 Xcode LLDB 同样失败；无依赖目标创建仅为线索，尚未验证能运行捕获。已写停用标记避免反复崩溃。P05-01 离线项通过；P05-02 取钥失败，P05-03–07 实机项 not_tested，G1 failed/G2 not_tested，未进入 Phase 6。详情见 [mac-probe.md](mac-probe.md)，私有证据在 `.local/acceptance/mac/phase-5/`。Windows 原有报告未改写。

### Phase 6：macOS 与 Windows 已有应用功能对齐

目标：在 Phase 5 通过的 Mac 通道上，达到当前 Windows Phase 1–4 的应用能力与发送控制要求。两平台共用正式服务、API、工作台和账本实现；技术底层分别采用原生适配器。知识/长期记忆留到 Phase 7。

目标文件：adapters/base 与平台绑定契约、config/settings_store、runtime/service/worker/prototype、storage 兼容迁移、cli/api/ui、Mac 原生发送桥、平台依赖与构建/安装脚本、tests/runtime/api/adapter、README/overview/mac-probe/api-workbench 和许可证资料。

任务：

- [ ] 收敛适配器的连接/关闭、绑定身份/联系人、源库文件身份、能力和初始化结果接口；把 Replica profile 字段、db_storage 路径、缓存清理与平台错误映射移回各自适配器，RuntimeService 使用统一契约。
- [ ] 按平台/基座、账号代数/绑定、微信版本识别 G1/G2，验证报告与本机环境一致；保留 Windows v4 原始报告及其受限兼容识别，不改写历史报告、不复制 Windows passed 到 Mac、不仅放宽版本字符串检查。
- [ ] 保留 Windows 既有账本、消息 ID、游标、上下文和 unknown；新增 Mac 元数据可迁移、可恢复。账号、进程寿命、源库替换/代数及应用账本变化仍拒绝继续，同一客户端只允许一个执行通道。
- [ ] 将人工预选限制扩展到与 Windows 相同的已绑定单聊定位/导航：当前不在目标聊天时可在发送前导航并重新核验，歧义/同名拒绝，不要求用户为每条正常回复手动切换。一个测试好友范围不扩展为多账号/群聊。
- [ ] 对齐模型输出长度设置及发送行为；验证中文/英文、标点、emoji、空格/换行和接近长度上限的内容。应用统一根据能力校验，不能静默截断、拆分或丢空白；无法精确核验的内容在发送前拒绝并明确限制。仍仅支持 200 字单行时不能标全量文字能力对齐，差异须列入待完成项。
- [ ] 接通正式 serve 的停止/dry-run 默认值、显式开始、暂停/恢复/停止、代数取消、限流/合并、崩溃恢复与 unknown 人工处理；原生桥超时/退出受控，模型迟到结果不得穿过发送边界。
- [ ] 复用概览/会话/设置及诊断 API，展示实际平台/基座、权限、连接、能力与初始化状态；Windows UIA 开关等不适用项标明。前端只做类型/构建/必要逻辑验证，由用户打开工作台验收。
- [ ] 完成 Mac extra/锁、SQLCipher 定位与架构检查、Swift 桥可复现构建、原生辅助进程关闭及私有缓存/权限策略；两平台分别从干净源码目录安装。更新说明/许可，并回归 Windows 现有 CLI、服务和真实收发。

对齐清单（均待本阶段验证）：

| 能力 | Windows 已有依据 | Mac 达标条件 |
| --- | --- | --- |
| 绑定、消息读取与去重 | P01-02/03/05、P02-03/04 | 同等身份强度、稳定事件、增量/本人过滤；不以 OCR 快照冒充消息 |
| 目标定位与单次发送 | Replica send_text_once、P01-04 | 可定位已绑定单聊，目标/草稿/主窗/焦点/全文检查，发送后不回退第二路径 |
| 发送确认与恢复 | ReplicaAdapter.send_text、outbox | 新记录水位+本人/会话/全文，三态及 unknown 停发，同操作 ID 不重试 |
| Agent 与运行节奏 | P02-01–05 | 相同上下文/预算、合并/串行/限流/上限，无自循环 |
| 生命周期与历史 | P03-01–04 | 原位迁移、暂停代数、停止等待、重启基线及未决发送恢复 |
| API、设置与工作台 | P04-01–04 | 原有入口接 Mac 真实后端，配置掩码/保存及状态同步可用 |
| 安装与隔离 | Windows extra、干净安装记录 | Mac 无 Windows 原生依赖，平台版本/能力明确且可复现安装 |

验收：

- P06-01：统一契约/报告检查拒绝错平台、错基座、错版本或绑定；Windows v4 记录仍能按原身份识别，Mac 不能借用；无原生库时可导入并运行纯逻辑测试。
- P06-02：Windows 旧账本原位升级不丢消息、不重算 ID、不重发；Mac 的账号/进程/源库/账本变化、睡眠恢复或断连有明确停止/重连路径。
- P06-03：Mac 从其他已打开会话导航到唯一绑定测试好友，固定回复及 G2 通过；同名、草稿、遮挡、窗口变化和发送中异常按约定停发。输出格式/长度矩阵中每项的成功或拒绝与声明能力一致，未完成差异不能隐藏。
- P06-04：正式服务验证开始/暂停/恢复/停止、迟到模型取消、队列/限流、崩溃 sending→unknown、pending→paused 与人工处理；跨重启不自动补发旧队列。
- P06-05：API/配置/权限诊断和构建检查通过；用户在 Mac 工作台验收设置、会话、运行记录、dry-run/live 和微信状态同步；初始化成功与已连接/实际收件分别展示。
- P06-06：Mac/Windows 干净目录各自完成依赖安装、CLI/serve 和原生收发代表用例，记录实际系统/微信版本及本次结果；历史 Windows 通过记录不替代本次跨平台改动后的回归。

完成条件与证据：对齐表逐项有证据，P06-01–06 必需项通过，Mac 工作台人工验收通过，Windows 回归无新增阻断；Mac 报告 `.local/acceptance/mac/phase-6/report.json`，Windows 回归 `.local/acceptance/windows/phase-6/report.json`。能力差异仍阻断目标功能时保持未完成，不靠降低公共约束或缩小 Windows 功能通过。

完成记录：未开始。Phase 5 Mac G1/G2 未通过，没有进入正式服务/导航/工作台对齐；Windows 本次原生回归与 Mac 工作台人工验收均 not_tested。

### Phase 7：知识检索与按联系人隔离的长期记忆

目标文件：knowledge/、memory/、agent/ 检索/记忆节点、相应仓储/API、工作台知识与记忆入口。

任务：

- [ ] 先支持本地 TXT/Markdown 知识导入、分块、jieba 中文切词与 FTS5 检索、来源引用、删除后不再召回；不增加向量服务。
- [ ] 在既有 LangGraph 中加入确定边界的检索和记忆读取/更新；无知识命中时明确说明，不编造来源。
- [ ] 区分短期上下文与长期事实；按账号/联系人隔离，支持偏好更正、查看/删除与跨重启保留。
- [ ] 工作台可导入/删除知识、查看/更正/忘记记忆，并展示真实处理结果。
- [ ] 聊天和文档不能修改系统设置、调用任意命令或读取其他联系人资料。

验收：

- P07-01：虚构知识问答可定位来源，无命中和删除后结果正确。
- P07-02：记住测试偏好，重启后仍可使用；更正与忘记生效，其他联系人不可见。
- P07-03：知识/记忆入口接真实 API，失败有明确状态；用户分别在已验收的 Windows/Mac 组合核对回复。
- P07-04：模型输入受上下文预算限制，知识与记忆不会无界增长或直接进入运维日志。

完成记录：未开始。

### Phase 8：可选业务工具、文件与语音入口

选择状态：未选择。Phase 7 后可直接进入 Phase 9；不为可选项预留无动作入口。

可选任务：

- [ ] 业务工具：虚构订单查询和工单创建，Pydantic 参数校验/联系人范围约束；写入工具有会话级确认、过期与幂等。
- [ ] 文件：按需扩展文本 PDF/DOCX 解析，复用成熟库；文件导入/分析明确标注人工来源。
- [ ] 语音：复用基座可获取的本地素材或人工转写入口；ASR 为独立可替换配置，不承诺未下载音频可读。
- [ ] 只对选中项接工作台、Agent 和测试；未选择项在 README 写明不纳入。

验收：

- P08-01：选中工具参数、权限、取消/确认/幂等和超时分支正确，无真实业务写入。
- P08-02：选中文件/语音能力使用合成样例和真实可得输入验证，不把占位符当正文；两平台素材获取能力分别声明。
- P08-03：选中功能在最终应用与演示中可操作，其余入口隐藏。

完成记录：未开始；未选择不标 passed，交付清单注明不纳入。

### Phase 9：双平台集成回归、真实录像与源码交付

目标文件：scripts/acceptance/、docs/demo-script.md、docs/delivery-checklist.md、package/verify 命令与 dist/submission/。

任务：

- [ ] 以正式服务回放同文/重复事件、本人/未知过滤、模型失败、发送未知、暂停/重启和知识/记忆更新，必要自动检查通过。
- [ ] 在 Windows、Mac 各一个已验收组合完成代表性微信对话及工作台操作；记录版本、窗口条件、延迟和已知限制，不要求各平台第二版本或 24 小时运行。
- [ ] 给出 3–5 分钟真实录像脚本：启动→好友提问与追问→知识问答→记忆→暂停恢复→工作台记录；覆盖两平台实际运行，可用主片加另一平台补充片；选中 Phase 8 时再加入相应场景。
- [ ] 用户录制并核对视频；真实读写、人工操作和实际等待如实呈现，剪辑标明，未实现能力不展示为已实现。
- [ ] 交付包含应用源码、Windows 内置基座、Mac 参考源码与原生桥构建说明、平台依赖/锁文件、合成样例、许可/NOTICE、启动说明、脱敏验收摘要和视频；排除 .env、密钥、解密库、校准截图、私聊、临时微信副本与运行缓存，不分发微信客户端。
- [ ] 两平台从干净目录核对包内相对路径、uv 本地 path 依赖、SQLCipher/桥定位和启动；只打本地包，不默认推送、发布或上传。

验收：

- P09-01：必要 Python/前端检查通过，两平台关键故障回放与运行状态一致。
- P09-02：Windows/Mac 干净目录均可安装并启动完整应用，third_party 和原生桥不依赖开发机绝对路径，外部系统依赖有明确安装/构建步骤。
- P09-03：视频文件实际存在、可播放，覆盖两平台真实闭环和支持限制，经用户确认。
- P09-04：源码包/历史/录像不含秘密或无关私聊，许可与两平台上游补丁记录齐备。

完成记录：未开始。缺任一平台必需的 G1/G2、功能对齐、人工验收或真实录像时不得标整个应用完成。

## 7. 验证、日志与协作纪律

- 自动验证针对契约、身份/去重、事务/崩溃、Agent/接口和构建。微信、模型效果、界面和视频由用户核对，mock 不替代真人结果。
- 助手不自行打开页面、Playwright、CUA 或 GitNexus；不创建子 agent、新会话、worktree 或自动 relay。前端只做静态/构建和必要逻辑测试。
- 原生微信依赖懒加载，纯逻辑测试可跨平台；Windows 原生验证保留 Replica 路线，Mac 在 Phase 5/6 验证本地 Reader/Swift 桥与真实收发。应用工作台不由助手打开；阶段执行时的原生微信探针与用户页面验收分别记录。
- 既有 Windows 报告保留在 `.local/acceptance/phase-N/report.json`，不迁移覆盖；v5 新报告使用 `.local/acceptance/<windows或mac>/phase-N/`，Phase 5 另含 g1.json/g2.json。字段含 plan_version、platform、foundation/revision、准确系统/微信版本、账号代数/绑定指纹、阶段、commit、模式及 case/expected/actual/status/evidence_ref；绑定信息仅存私有报告。人工项未核实为 not_tested，失败为 failed，无证据不填 passed。
- 日志保留时间、事件、trace、脱敏会话/消息引用、耗时、状态和原因；不打印正文、昵称、完整 prompt、模型密钥、数据库密钥或隐藏思维链。
- 第三方生成的密钥/备份/明文库/图片/校准资源和临时应用副本同样纳入私有目录、保留期与退出/删除策略；Windows 核对 ACL，Mac 核对目录 0700/敏感文件 0600，不能只忽略应用自己的文件。临时副本停止后核实原版恢复，发送不确定时先保留核对证据，不能用缓存清理解除停发。
- 代码/文档/验证按功能形成真实英文 Conventional Commits，不默认 push；公开材料不包含聊天原话、非技术讨论或私有环境信息。

## 8. 续做与旧版本衔接

1. 下一次先读本计划和 overview，再核对对应平台接入说明、提交、私有报告与实际环境。overview/README 中尚未随实施更新的 Windows-only 描述是代码现状，不代表本计划新增 Mac 阶段已完成。
2. 下一实施入口为 Phase 5：参考固定 Gist 的数据库/原生界面路线；不安装旧 wxauto4，不继续猜旧 Mac AX 消息控件标识。旧 AX/视觉文件仅复用经核对的必要逻辑与测试。
3. Windows Phase 1–4/G1/G2/人工验收保持 completed；Mac G1/G2 在 Phase 5 独立形成。Phase 5 原型先受对应 G1 检查控制；Phase 6 正式服务仅在本机匹配的 G1/G2 有效后开始，不能借用另一平台报告。
4. 编号映射：v4 Phase 1–4 不变；v4 Phase 5（知识记忆）→v5 Phase 7，v4 Phase 6（可选增强）→v5 Phase 8，v4 Phase 7（交付）→v5 Phase 9。更早的 18 阶段已在 v4 收敛；按主题继续映射到本版，不恢复旧执行顺序。
5. 新增用例使用 P05/P06；原尚未实施的知识/增强/交付用例顺延为 P07/P08/P09。任何既存旧编号/报告保留原 plan_version、日期与含义，用「版本+平台+阶段+用例」识别，不覆盖或改写旧测试结果。
6. 本次已授权实施 Phase 5–6，已执行 Phase 5 软件和首次取钥。后续按 Phase 5→6→7→已选择的 8→9 推进，原型失败先解决本阶段阻塞；Windows 已通过不豁免共享层改动后的回归。
7. v5 实施记录采用实际 platform/foundation；Windows v4 原始报告通过明确兼容映射及本机绑定校验识别，Mac 只能使用自己的 v5 报告。每次收尾同步 overview/README/接入说明，避免计划目标和已实现能力混写。
8. 运行时遇到上游缺陷只做必要且可追溯的补丁；改变产品范围、控制路线或支持声明须明确更新本计划。

## 9. 最终完成条件

Phase 1–7 与 Phase 9 的必需任务、Windows 和 Mac 各自的 G1/G2、Phase 6 对齐验收、两平台工作台人工验收和真实视频齐备；Phase 8 仅对明确选择的项目验收。应用可分别从干净 Windows/Mac 源码包按平台步骤安装启动，原生读取/发送隔离，Agent/知识/记忆/状态/API/UI 接通，发送不确定时停止，许可证和来源清楚，交付无秘密与私聊。仅通道库、固定会话短文本原型、离线截图、模型控制台或阶段文档不能作为最终完成。

当前交付事实为 Windows Phase 1–4 已完成，Mac Phase 5 软件已实现但首次取钥阻塞、G1/G2 未过，Phase 6 未开始。修复开发工具后继续 Phase 5 实机验收，再进入已授权 Phase 6；不自动实施 Phase 7–9。两平台测试均采用单好友低频、至少 30 秒发送间隔、单次最多 3 条回复；不承诺避免账号限制。
