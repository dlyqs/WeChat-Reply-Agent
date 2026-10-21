# 个人微信 AI 回复 Agent 执行计划

更新日期：2026-10-22（Asia/Shanghai）。计划版本：v5。
本文件是阶段状态、实施顺序和完成条件的唯一来源；代码导航见 [overview.md](overview.md)。

~~~text
execution mode: close_phase_6_degraded_mac
automatic start phase: 6
automatic stop phase: 6 (Mac accepted; Windows native regression deferred by user)
execution state: phase_6_mac_passed_windows_native_pending_worker_stopped
conversation relay: off
current change: shared service/API/workbench and ledger; explicit degraded Mac native adapter
last completed implementation scope: Windows phases 1-4; Mac phases 5-6 user-authorized degraded flow
next implementation phase: none automatic; Phase 7 requires a new request
windows foundation: wechatauto-replica 1.2.7.0
windows upstream commit: d322c4a9b1124228820bab363e5676016f188fc6
macOS reference: acmerfight/0a01249ef72970d07a2603dbb629e80f
macOS reference revision: c98dbb10cf23c30e83d5d744905101b0880887a0
~~~

本轮执行以 Phase 6「本轮范围与完成记录」为准：用户确认本机 Mac 全部验收通过，并明确将 Windows 真实回归留待验证。Phase 5 的降级授权继续适用；旧交接清单及严格验收条件保留，不能用降级流程结果改写严格 G1/G2；不自动进入 Phase 7。

v5 在 v4 的 Phase 4 后插入 Phase 5「macOS 原型验证」和 Phase 6「macOS 与 Windows 已有功能对齐」；原 Phase 5/6/7 分别顺延为 Phase 7/8/9。Windows Phase 1–4 的完成事实、用例和私有报告保持原样。Mac Phase 5 降级流程已通过；Phase 6 正式服务、工作台、绑定独立窗导航、多行/emoji/近长度上限发送和两轮真实 Agent 回复已通过本机及用户验收。Windows 合成回归通过，真实回归延期；严格视觉 G1/G2 仍未完成。

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

上游记录为 macOS 15.6.1 / Apple Silicon / 微信 4.1.15；本机现状为 macOS 27.0.1 / arm64 / 微信 4.1.15（270115，App Store），取钥、新消息读取及降级模式真实收发已通过。旧 AX 探针在此组合找不到消息列表与输入框，保留作历史；新通道不以这些 AX 子控件可见为前提。

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
| third_party/wechat_mac_toolkit/、adapters/wechat/mac_db.py、mac_bridge.py | Mac 只读数据库/取钥辅助与原生界面桥、MacAdapter/profile/能力和三态发送；与 Windows 原生包隔离 |
| adapters/wechat/base.py、binding.py、domain/ 平台契约 | 统一连接/关闭、绑定身份、源库文件身份、能力与报告依据；运行服务不直接理解第三方 profile 或目录 |
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
- Phase 6 已提取 RuntimeBinding 与适配器契约，Prototype/RuntimeService 不再读取 Replica profile 字段或拼原生库路径；报告检查、缓存和错误映射归属各平台适配器。Windows 保留原绑定指纹与受限 v4 报告兼容，Mac 使用本机匹配依据，不伪造 Replica profile 或报告。

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

Windows 与 mac_db 均已实现 doctor/connect/probe/resolve/prototype/serve；Mac 另有独立 mac-bootstrap。Mac 降级正式服务要求显式 independent/ax-window-db profile、本机匹配且用户接受的 Phase 5 降级报告及原生固定发送回执，无未决原生操作；默认 visual 仍要求严格 G1/G2，不借用 Windows 报告。旧 mac_ax 只有历史探针。replay/verify/package 仍是后续目标，不能标为已可执行。干净安装验证脚本不是 Phase 9 的 verify/package 命令。

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
| Phase 5 | macOS 固定收发与最小 Agent 原型 | 必需，新增 | completed_degraded | 191 项测试及 Swift 自检通过；固定自然对话一次收件、真实模型两轮及 DB 确认通过，用户接受实际轮数并要求标通过；worker 已停止，严格 G1/G2 未过 |
| Phase 6 | macOS 与 Windows 已有应用功能对齐 | 必需，新增 | completed_degraded | Mac 正式服务/工作台、窗口导航及自然对话收件经用户确认通过；222 项测试、构建及 Mac 干净安装通过；Windows 合成回归通过，真实回归按用户决定待验证；严格 Mac G1/G2 未过 |
| Phase 7 | 知识检索与长期记忆 | 必需，原 Phase 5 | pending | Phase 6；在两平台共用的 Agent/API 上扩展 |
| Phase 8 | 业务工具、文件与语音入口 | 可选，未选择，原 Phase 6 | pending | Phase 7；未选择则记录不纳入并转 Phase 9 |
| Phase 9 | 双平台集成回归、录像与交付 | 必需，原 Phase 7 | pending | Phase 6/7，以及已选择的 Phase 8 项 |

原授权为 Phase 5–6；用户先接受 Phase 5 降级结果，再明确要求继续 Phase 6，最终确认 Mac 全部验收通过、Windows 真实回归待验证。默认原型仍要求 G1；显式降级 profile 与 `--allow-degraded-mac-ui` 同时启用时允许降级原型。正式服务则要求匹配的已接受 Phase 5 降级证明和原生回执。该例外不改变 Windows 门禁，不将严格 G1/G2 标通过，也不授权 Phase 7–9。

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
- [x] 实现只读 doctor 和显式原生账号/好友绑定。复验已有密钥；确需首次捕获时执行受控临时副本 bootstrap，记录原版签名/路径、选定账号、超时、退出与恢复结果，密钥只落私有目录。
- [x] 实现 Mac 数据库读取、发送者/方向解析、消息身份和增量游标；启动建基线，读取结果与 inbox/游标事务提交后才推进消费确认；满批、坏库、旧快照和账号/源库变化有明确失败状态。
- [ ] 完成人工预选单聊的原生发送桥。当前已支持 live 前激活绑定进程、AXRaise 抬高主窗；下一步优先验证并适配微信独立聊天窗的官方置顶能力，自动准备目标窗口后核验遮挡/焦点。主窗与独立窗分别绑定和校准，不能沿用另一布局的坐标。先 dry-run 再一次显式固定发送。原型允许短单行文本（先以不超过 200 字验证），输入前和发送前检查目标、空草稿、目标窗口/焦点和全文；发送快捷键事先配置，一次操作只尝试一次。
- [ ] 以 outbox_id 驱动原生操作 ID，发送前保存数据库水位，发送后核对同会话新增本人记录和完整正文；返回应用三态，不把上游 already_sent/UI 成功直接映射为 verified_sent。异常/超时可能已发则 unknown，禁止换 ID 重试。
- [x] 提取 Prototype 所需的连接、账号代数、联系人与身份契约，扩展 CLI 工厂和原型 G1 检查以识别 mac_db；保留 Windows 现有入口、ID 和报告兼容，公共层改动先跑 Windows 合成回归，不另写一套模型循环。
- [ ] Mac G1 通过后，用原有 LangGraph/CompatibleModel/账本执行有界 dry-run/live，沿用默认 15 秒轮询、至少 30 秒发送间隔、每分钟至多 2 次、最多 3 条；超长/原型不支持的输出拒发，不静默截断。
- [ ] 记录环境、能力限制、合成测试、实机/人工结果及耗时，形成独立 Mac G1/G2 报告；完成后停止 worker，不把 Gist 的运行记录计入本项目 passed。

验收：

- P05-01：合成加密 DB/WAL 下验证正确/错误密钥、只读拒写、未提交不可见、checkpoint/reset、同秒/同文、跨分库与满批；Windows 原有适配器/原型合成回归通过。未覆盖的格式边界列明，无密钥/正文进入公共日志。
- P05-02：本机 doctor 无激活/取钥/签名副作用；账号、目录和好友绑定唯一。取钥/密钥复验后的真实只读查询成功，恢复原版后仍可读新到消息；单纯 HMAC、schema 或旧历史查询不替代新鲜度验证。
- P05-03：测试好友发 5 条文本，含连续同文；另核对本人消息。消息数量、内容、顺序和方向逐条正确，重读不重复入库，未知身份/方向及非白名单不触发模型。
- P05-04：dry-run 不写草稿/剪贴板或注入事件；一次固定 live 在目标会话出现新的本人完整文本记录，用户确认对端收件。错标题/已有草稿/失焦/窗口遮挡等拒绝；原生无法确认的条件不得猜发，反例证据标明合成或实机。
- P05-05：旧同文、多条匹配、按键后异常、回读超时、桥进程退出或崩溃均不误报成功；同 outbox_id 不二次发送，重启保留 unknown；resolve 不操作微信。
- P05-06：P05-01–05 的必需项、实际退登后新增的 P05-08 和人工收件核实后，Mac G1 passed。随后 dry-run 正确，再真实完成至少 3 轮 LLM 问答，含上下文追问；本人消息不自循环，达到上限后停发，用户逐轮确认收件，Mac G2 passed。
- P05-07：分别记录轮询/模型/发送/回读耗时和原型能力限制；不将仅 UI 核验、人工补发或人工调整后的结果记成无人介入成功。原型限制不能反向缩小 Windows 配置或功能。
- P05-08（实际退登后的回归）：复用已有密钥、仅原版客户端，完成 5 分钟只读观察、新版单次粘贴发送及观察，再继续 G2。已知安全提示持久停发，人工重登/显式 reset 仅解除锁、不改写 gate。记录有限观察窗口，不能据此宣称免退登或免封号。

完成条件与证据：Mac G1/G2 均通过，报告写入 `.local/acceptance/mac/phase-5/{g1,g2,report}.json`，含 `plan_version=v5`、`platform=macOS`、`foundation=mac_db`、Gist revision、准确环境和本机绑定指纹。未通过对应项为 failed/not_tested，并说明阻塞。取钥/可靠发送失败时留在本阶段，不进入 Phase 6，也不重试已经可能发送的操作。

#### Phase 5 本轮范围调整（2026-10-22）

用户在本轮明确允许 Mac 降级或跳过这些界面检查，先完成流程，不以最终完成度为目标；并要求后续实际收发使用类似真人日常对话的内容。此授权覆盖下述显式模式，严格验收记录继续保留。

- `window_mode=independent`、`send_preflight=ax-window-db`：绑定唯一好友独立窗口，按 AX 精确标题/尺寸、前台及焦点复核，使用配置的输入位置，一次 Cmd+V、一次发送快捷键。独立窗布局单独记录；不启用截图/OCR，不核验空草稿、输入全文或遮挡，报告明确 `ui_checks_degraded=true`。
- 仍保留原版进程/账号/库身份、白名单、文本长度、outbox 操作 ID、单次发送、水位之后唯一的同会话本人完整文本记录确认、unknown 停发及账号安全锁。数据库全文确认只能说明发送结果，不能补足发送前草稿检查。
- 默认仍为 visual；降级 profile 不能通过严格 `require_gate`。流程验证额外要求 `prototype --allow-degraded-mac-ui`，复用现有 LangGraph、模型客户端和账本；不写另一套循环，不把 G1/G2 改为 passed，不接 Mac serve。
- 本机复验原版/已有密钥成功。用户打开的独立窗为 598×640，AX 只有三个窗口按钮，没有编辑框。显示器截图为下层画面、单窗截图无有效帧、单窗流及系统选择器流为黑画面；系统选择器选中正确窗口，2.477 秒 MP4 解码仍为黑画面（RGB 最大值 2）。官方置顶已实测（勾选且层级 3），仍不可捕获，诊断后恢复未置顶。截图路线未通过。
- 降级原生 dry-run 已通过，剪贴板未改、输入事件为 0。一次自然聊天固定发送经新本人全文 DB 记录确认；用户确认只收到一次且仍登录。只读模型回放使用用户明确指出的真实来信，生成 23 字回复且未发送；它标为显式回放，不算新消息自动轮次。首次 180 秒监听因来信在启动基线前到达，没有调用模型，报告如实保留。
- 真实 live 使用 15 秒轮询、至少 30 秒发送间隔，实际完成两轮模型回复，每条均由唯一新增本人完整文本记录确认；本人消息被过滤，没有自循环。用户确认“测试成功”并要求标记通过，接受当前轮数；收到确认后主动停止 worker，未达到三条上限，不能记录为三轮或自动上限停机。降级流程 `passed`，严格 P05-04/08 稳定性与 G1/G2 仍未通过，不自动进入 Phase 6。

证据入口：`.local/acceptance/mac/phase-5/{degraded-flow,report}.json`（降级流程 passed），`g1.json/g2.json`（严格状态保留），`degraded-{preflight-recheck,fixed-send,agent-dry,agent-dry-replay,agent-live}.json`，以及 `native-ui/independent-*`。诊断复现脚本 `scripts/acceptance/mac_capture_check.py`；窗口/输入降级代码 `WindowCapture.swift`、`DegradedSend.swift`。私有 profile 保留原账号代数，独立窗模式和降级状态进入绑定指纹与报告；旧绑定已归档，不重取密钥。 实现提交 `f5a5156`；191 项测试、Ruff、Swift 自检及 wheel/sdist 检查通过，源码包包含四个原生源文件且不含私有运行材料。

历史严格验收记录（2026-10-22，本轮范围调整前，未完成）：固定 Gist/MIT/哈希内化、只读 SQLCipher DB/WAL、事务游标、独立绑定/bootstrap、Swift 桥、原生 outbox 幂等/三态及 Mac 原型 gate 已实现。176 项 pytest、Swift 编译/自检、合成加密库及工具链捕获检查通过。实际为 macOS 27.0.1 / arm64 / 微信 4.1.15（270115，App Store）。SDK 27.0 / LLDB 2103 / Swift 6.4 解决旧 LLDB 1703 崩溃；受控临时副本取得 19/19 个 HMAC 有效密钥，原版哈希/签名保持、恢复并读到新消息。五条来信（含连续同文）、一条本人消息及空格、顺序、方向均已核对，重读不重复入库。新增 live 前自动激活/抬高绑定主窗、尺寸校验、标题 OCR 精确复核及透明 Dock 面板判定；实际原生只读预检通过。固定发送前的空草稿/遮挡拒绝均为 not_sent；已处理光标闪烁，真实草稿经用户清空后，自动抬高窗口、一次固定发送和新增本人全文回读已通过（verified_sent/local_db_confirmed），对端收件已由用户确认，随后发生账号安全退登。已参考 Windows 输入路径改为一次剪贴板粘贴，增加 AX 会话预检和持久停发锁；用户正常重登后的 5 分钟只读观察已完成，未自动重新取钥；新版真实粘贴与发送后观察尚未完成。P05-01/02/03/05 有对应合成或实机证据，P05-04 固定发送和收件通过但安全退登仍阻断 G1；P05-08 新输入路径/稳定性复验未完成，G1/G2 未通过，P05-06/07 未完成，Phase 6 未进入。私有证据见 `.local/acceptance/mac/phase-5/`；Windows 原有报告未改写。

后续记录（2026-10-22）：正常重登后的 300.222 秒只读观察已完成（20 次检查，模型调用/输入事件均为 0，未记录到原生会话错误）。新版粘贴路径尚未实际输入，被截图预检拒绝；主窗口缺失/截到下层画面，用户未找到隐藏主窗开关。按用户要求先集中调研，结果见 [Mac 自动化调研](mac-automation-research.md)。官方独立聊天窗置顶功能作为下一候选，截图可用性和桥适配尚未验证；不据此改写 G1/G2。当前暂缓真实发送测试，Phase 6 仍未进入。

#### Phase 5 续做清单（2026-10-22 交接）

用户将新开对话验证可行性并完成本阶段。新的执行者先核对当前工作区和私有证据，再按本节推进；既有 Phase 5–6 授权继续有效，Phase 6 仍以 Mac G1/G2 为前置条件。原生窗口操作和已限定的单好友测试在原任务范围内；新对话先确认本机实际登录、目标窗口和草稿状态，不把本次旧进程号或“原版已登录”的历史回复当成当前状态。

**已有事实与当前阻塞**

| 项目 | 截至交接的事实 | 续做要求 |
| --- | --- | --- |
| 工作区 | 当前分支 `dev`；最近提交 `a703707`；其后剪贴板、停发锁、AX 会话检查、捕获实验和文档仍有未提交修改 | 先查 `git status`/diff；保留已有改动和回执，不 reset 工作区、不只看 HEAD 判断功能 |
| 环境 | 上次实测 macOS 27.0.1 / arm64 / App Store 微信 4.1.15（270115），SDK 27 / LLDB 2103 / Swift 6.4 | 重新核对实际版本、原版路径/签名、进程及账号绑定；变化需要重新验证 |
| 取钥与读取 | 19/19 密钥 HMAC 验证通过；原版恢复，五条来信含连续同文及本人消息、顺序/方向/空格与去重已核对 | 优先复用有效密钥和只读 DB/WAL，不重复临时副本登录或取钥流程 |
| 旧固定发送 | `send-live-after-draft-cleared.json`：一次发送、新增本人全文回读及对端收件成功，随后出现账号安全重登提示 | 保留历史成功与安全事件；旧 Unicode 路径的成功不能放行新剪贴板/独立窗路径 |
| 当前输入 | 一次 Cmd+V、全文核验、一次 Enter、剪贴板所有权恢复已实现；独立命名剪贴板自检通过 | 新版真实粘贴尚未执行，不能写成已验证；不用逐字 Unicode 输入作为默认路线 |
| 新版失败 | `send-live-clipboard-v1.json` 明确 `not_sent`，在输入前因无帧被拒绝；后续只读预检又出现截到下层画面/标题不匹配 | 不重发旧 outbox；只有原操作明确未发送时，才可创建下一次独立测试；unknown 始终停发 |
| 截图与控件 | 主窗 sharing state 为 0；主窗截图失败/画面缺失；AX 只有窗口外壳；用户找不到隐藏主窗设置 | 不再反复要求寻找同一开关；不把该标记单独当成所有捕获方式都不可用的证明 |
| 安全恢复 | 用户已正常重登，停发锁曾显式 reset，旧事件归档；随后只读观察 300.222 秒、20 次检查、无模型或输入事件 | 新对话重新核对当前锁/登录状态。仅在用户确已正常登录后显式 reset；reset 不改 gate，不登录、不发送 |
| 阶段门禁 | `g1.json/g2.json/report.json` 仍未通过；当前要求 `input_method=clipboard-v1` 和 `native_stability_verified=true`，另核对版本/绑定/源库 | 独立窗模式/校准的变化也要进入可核对的验收上下文；不能用旧主窗证据或直接编辑 passed 绕过验证 |

**参考索引与适用边界**

| 参考 | 已确认的内容 | 待验证/不能推导的结论 |
| --- | --- | --- |
| [微信官方 Mac 4.0.5 更新](https://weixin.qq.com/updates/mac/405) | 独立聊天窗口支持置顶；存在默认隐藏主窗截图功能 | 当前 4.1.15 的置顶入口、状态读取、自动操作及独立窗截图仍要实测 |
| [Windows Replica 固定版本](https://github.com/fanyuantaier/wechatauto-replica/tree/d322c4a9b1124228820bab363e5676016f188fc6) | `guia.bring_to_front` 的窗口准备、`uia_driver._paste_into` 的点击/剪贴板输入可参考 | 本项目 `send_text_once` 是本地补丁，见 `third_party/wechatauto_replica/UPSTREAM.md`；不能复制上游宽松重试代替它，也不能推导免退登 |
| [Apple activate](https://developer.apple.com/documentation/appkit/nsrunningapplication/activate(options:)) / [AXRaise](https://developer.apple.com/documentation/applicationservices/kaxraiseaction) | 系统支持激活和抬高窗口；当前主窗路径已实测 | 抬高不等同持续置顶；独立窗优先使用微信自己的置顶入口 |
| [wxauto-mcp-mac 源码](https://github.com/S7arFish/wxauto-mcp-mac/blob/9538325b3929a6c19d08889df920e9ba48352129/src/wxauto_mcp/server.py) | 激活、frontmost、找输入框、Cmd+V 和回车已有实现 | 部分定位失败未严格处理，按回车后直接报成功；仅参考输入，不采用其成功判断/默认首个搜索结果 |
| [wechat-controller 键盘源码](https://github.com/dragonking-T/wechat-controller/blob/47b6191d0af5488687f9617ab67c256804e64988/wechat_controller/input/keyboard.py) / [macos-wechat-sender](https://github.com/yunkai/macos-wechat-sender/blob/main/scripts/send_wechat.py) | NSPasteboard/pyperclip 配合标准系统按键发送中文 | 可比较 Cmd+V/Return 的投递方式；不默认安装项目，不照搬清窗或连续回车流程 |
| [AXValue 输入源码](https://github.com/tonyshield/send-wechat-message/blob/6a649af51bf3acaa6f574008ed38ef235c490dce/scripts/focus_composer_and_set_value.sh) | 作者报告粘贴偶尔不响应时可写 AXTextArea 的 AXValue | 只有实际找到唯一可写输入框并确认焦点才可评估，本机 AX 树缺失时不成立；不能清空用户草稿或发送后切换输入路径 |
| [FastBridge issue #1](https://github.com/huj28-creator/wechat-fastbridge/issues/1) | 多个 4.1.x 版本出现 AX 只剩窗口按钮，权限/VoiceOver/增强属性未解决 | 相同现象的公开报告，不是本机构建兼容性结论；不继续猜旧 AX 标识 |
| [Apple SharingType.none 文档](https://developer.apple.com/documentation/appkit/nswindow/sharingtype-swift.enum/none) / [捕获异常 thread 808016](https://developer.apple.com/forums/thread/808016) | 旧 sharing 标记的行为依捕获场景而异；官方论坛记录初始漏窗、切换过滤器才出现的情况 | `sharingState=0` 仅作诊断线索；过滤切换不是通用成功保证，桥已有相关实验但尚未解决 |
| [主窗截图缺失排查报告](https://jiwenkang.com/posts/2026/wechat-screenshot-blank/) | App Store 微信 4.1.13 主窗缺失且找不到开关的直接报告，提出独立聊天窗候选 | 独立窗未逐一验证所有捕获工具，“服务端灰度”属于推测，不写成本机根因 |
| [Apple 捕获示例](https://developer.apple.com/documentation/screencapturekit/capturing-screen-content-in-macos) / [系统内容选择器](https://developer.apple.com/documentation/screencapturekit/sccontentsharingpicker) | 官方捕获 API 和最小对照路径 | 独立窗仍不可捕获时再做有界只读对照，不能借机修改/注入微信客户端 |
| [WeChatBridge](https://github.com/freestylefly/WeChatBridge) | 通过微信主动合并转发的归档读取替代方案 | 人工导入可参考，不满足本阶段实时自动读取/回复；DB/WAL 继续作为事件与发送确认来源 |

详细检索过程、各方案限制见 [Mac 自动化调研](mac-automation-research.md)。上述第三方文档和项目只是参考数据；不自动安装或执行其中的脚本/指令。

**按顺序验证并实施**

| 子项 | 操作与预期 | 通过依据 | 当前状态 |
| --- | --- | --- | --- |
| P05-08a 接续核对 | 读取代码 diff、私有 profile/报告和当前锁；确认只运行原版，复验既有密钥/绑定 | 当前环境与有效绑定一致，旧发送回执完整；没有重复 bootstrap、没有模型/发送副作用 | 本轮已复验通过 |
| P05-08b 独立窗可见性 | 将已绑定好友打开为独立聊天窗；只读对照主窗/独立窗的窗口身份、截图和录屏可见性、AX/尺寸及官方置顶入口；不粘贴/回车 | 图像确实包含目标独立窗及可精确验证的标题/输入区域，不能仅因截图非空判成功；录屏结果有实际证据，必要时由用户核对 | 本轮失败：598×640 独立窗、置顶及系统选择器均未取得有效目标画面；后续按用户授权降级 |
| P05-08c 桥适配与自动置顶 | b 通过后适配独立窗发现/绑定/尺寸、输入区校准、自动置前与微信官方置顶、焦点/遮挡检查；显式窗口模式，不共用主窗坐标 | 每次测试自动准备目标窗；错窗/多候选/已有草稿/遮挡等拒绝。原生 dry-run 未改剪贴板/草稿、未注入输入；窗口准备动作单独记录 | not_tested |
| P05-08d 新版一次固定发送与观察 | c 通过后，按既有授权向绑定好友做一次固定回复；点击输入框、Cmd+V 一次、全文核验后 Enter 一次；发送后至少观察 300 秒并核对登录持续性 | 唯一新增本人全文 DB 记录 + 用户确认对端只收到一次；记录实际观察/原生错误和人工登录结论，复验 P05-04/05/08 | not_tested |
| P05-08e 当前路线 G1 | 汇总 P05-01–05/08，核对当前输入与窗口模式、微信/系统/绑定/源库上下文；补齐必要的 Swift/离线回归 | 所有必需证据真实通过，才形成匹配本机的 G1；旧 Unicode 固定发送作为历史，不替代 d | not_tested |
| P05-06/07 Agent 与 G2 | 原严格三轮/G2 条件保留；本轮按用户授权运行显式降级流程 | 实际两轮真实模型、每条 DB 确认；用户接受实际轮数并要求标通过，worker 已按要求停止 | 降级流程 passed；严格 G2 仍 not_tested |

若 b 失败：保留证据，使用 Apple 示例/内容选择器对同一已绑定窗口做有界只读对照，核对捕获生命周期、过滤器、窗口几何和图像身份；将结论写回本表。不要无限重启捕获、降低标题/空稿核验或猜测点击。若实际出现可用的唯一 AX 编辑框，可按参考评估 AXValue；没有控件就明确记为不支持该路径。候选路线失败不等于原任务取消，也不得标阶段通过。

发送后或可能已输入/发送时出现异常：遵循当前 outbox 三态与停发锁；unknown 不换 ID 重试，不在回车后切换 AppleScript/CGEvent/点击 send 等另一条发送路径。安全重登提示的根因尚未确认，完成有限观察也不承诺免退登/免封号。

**代码与私有证据入口**

- 原生：`third_party/wechat_mac_toolkit/{WeChatUI.swift,Send.swift,UPSTREAM.md}`；当前捕获代码含探索性分支，先审阅并收敛，不直接将其当成稳定实现；`capture_ready` 的后端标签也需与实际后端一致。
- 应用：`src/wechat_reply_agent/adapters/wechat/{mac_bridge.py,mac_db.py,mac_profile.py,mac_security.py,mac_acceptance.py}`、`cli.py`；原型复用既有实现，不另写模型循环。
- 构建与观察：`scripts/build_mac_bridge.py`、`scripts/acceptance/mac_stability.py`；依赖优先使用现有 `.venv`/uv，按改动执行 Python 检查、Swift 编译/独立剪贴板自检和构建检查。历史通过次数不替代新改动的验证。
- 绑定/密钥：`.local/macos/profile.json`、`.local/macos/bootstrap-20261021-lldb2103/keys.json`；目标好友 alias/微信号以该私有绑定与用户原授权核对。PID/window ID 每次新发现，不复用历史值。
- 模型：项目忽略的 `.env` 已有用户授权保存的 DeepSeek 配置，默认发送模式 dry-run；不打印密钥，不把配置或聊天内容抄进计划，不因新对话再次索要同一密钥。
- 验收：`.local/acceptance/mac/phase-5/{g1.json,g2.json,report.json,read-freshness.json,stability-readonly.json,send-live-after-draft-cleared.json,send-live-clipboard-v1.json}` 及 `native-ui/`；旧 `*-before-native-recovery.json` 保留为历史，不覆盖当前事实。
- 私有 `preflight_check.py` 只作当前主窗路径的辅助参考；新独立窗模式未实现前不能直接用于宣称通过。真实测试使用新输出文件，保留失败/unknown 历史。

上述 `.local`、`.env` 不进公开交付。此处仅提供位置和状态，不记录聊天正文、账号目录、密钥或新一轮 passed。用户当前要求是保存交接计划，本对话到文档更新为止，不主动启动测试、模型或新会话。

### Phase 6：macOS 与 Windows 已有应用功能对齐

目标：在 Phase 5 通过的 Mac 通道上，达到当前 Windows Phase 1–4 的应用能力与发送控制要求。两平台共用正式服务、API、工作台和账本实现；技术底层分别采用原生适配器。知识/长期记忆留到 Phase 7。

目标文件：adapters/base 与平台绑定契约、config/settings_store、runtime/service/worker/prototype、storage 兼容迁移、cli/api/ui、Mac 原生发送桥、平台依赖与构建/安装脚本、tests/runtime/api/adapter、README/overview/mac-probe/api-workbench 和许可证资料。

任务：

- [x] 收敛适配器连接/关闭、绑定联系人、源库身份、能力、验收依据、缓存和错误接口；RuntimeService 使用 RuntimeBinding，不理解原生目录。
- [x] 按平台/基座、版本和本机绑定识别报告；保留 Windows 原指纹和受限 v4 兼容；Mac 显式降级服务核验既有用户接受证明及原生回执，严格门禁保持独立。
- [x] 保留 Windows 消息/游标/上下文和 unknown，新增平台元数据；校验源文件及盐、应用账本，所有原生操作在唯一执行线程关闭。
- [x] 自动抬高/恢复已打开且唯一匹配绑定标题的独立聊天窗；发送前复核联系人标题与原生 username，同名/变化拒绝。支持从其他会话切回；不创建关闭的独立窗或搜索联系人。
- [x] 显式降级通道支持 1000 Unicode 标量、LF、emoji 和空格；模型输出保留原空白，发送前按能力拒绝超长/不支持字符，不拆分截断。默认回复上限 500；实际 70/481 字自然段落发送及收件完整。
- [x] 接通 stopped/dry-run 默认、开始/暂停/恢复/停止、代数取消、限流和 unknown；API 人工处理同步应用/原生回执，仅记结论。睡眠/时钟跳变要求重连。
- [x] API/工作台展示平台、基座、降级能力和权限；Mac 禁用 Windows UIA/OCR 配置。前端仅类型/构建检查，用户人工验收通过。
- [x] Mac extra/锁、SQLCipher/Swift 构建、自检、干净源码安装及无账号 stopped/dry-run HTTP 验证通过，更新平台说明/来源；Windows 合成兼容回归通过。
- [ ] Windows 本次干净安装及真实 CLI/serve/收发回归：用户明确延期，not_tested；历史通过记录保留，不代替本次原生回归。

对齐清单（Mac 降级模式的本轮结果；严格差异见下文）：

| 能力 | Windows 已有依据 | Mac 达标条件 |
| --- | --- | --- |
| 绑定、消息读取与去重 | P01-02/03/05、P02-03/04 | 同等身份强度、稳定事件、增量/本人过滤；不以 OCR 快照冒充消息 |
| 目标定位与单次发送 | Replica send_text_once、P01-04 | 已打开的绑定独立窗自动切回，目标/焦点复核；草稿/粘贴全文/遮挡按用户授权未验证，单次发送不回退第二路径 |
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

### Phase 6 本轮范围与完成记录（2026-10-22）

用户明确要求继续 Phase 6，并延续 Mac 的视觉降级授权；本机工作台、导航、实际收件和保持登录全部由用户确认通过。用户选择先完成本机 Mac，Windows 真实回归标待验证。本轮据此记为 `completed_degraded`，不是严格双平台验收完成；上面的原始严格完成条件及 Phase 9 最终条件继续保留。

| 用例 | 本轮状态 | 证据与限制 |
| --- | --- | --- |
| P06-01 | passed | 统一绑定/能力契约，错平台/版本/来源/绑定拒绝；Windows 原指纹及受限 v4 兼容、无原生依赖导入合成回归 |
| P06-02 | passed | 旧账本兼容、源盐/文件与应用库变化、进程校验、时钟间隔停发合成验证；本机原生绑定/19 源库预检 |
| P06-03 | passed_degraded | 用户确认从其他聊天自动切回绑定独立窗、收件完整且仍登录；70 字混合格式、481 字多段落均精确 DB 确认。1000 字边界为合成/Swift 自检；视觉检查未验证，严格 G2 未通过 |
| P06-04 | passed | 本机 HTTP dry-run 全生命周期及两轮正式 live；暂停迟到模型、重启恢复/unknown、原生人工处理和限流为合成回归 |
| P06-05 | passed | API/设置/权限及构建通过；用户确认 Mac/降级提示、诊断、历史、live 与暂停/恢复/停止全部通过 |
| P06-06 Mac | passed | 本机干净源码按锁安装、Swift 构建/自检、CLI 与 stopped/dry-run HTTP；绑定环境真实收发及人工核对 |
| P06-06 Windows | not_tested | 合成回归 passed；本次原生安装/真实收发按用户决定 deferred_by_user |

222 项 Python 测试、Ruff、前端类型/构建、Swift 自检通过，实现提交 `95cb081`。正式服务实际新增两轮 Agent 回复（既有两轮 Phase 5 保持独立），均 `verified_sent/local_db_confirmed`；另两条固定格式消息也获对端完整收件确认。用户验收后主动停止 worker；未运行到三条上限，不记为自动上限停止。最终服务已重启为 stopped/dry-run，只读诊断健康、4 条历史 outbox 保留；重启后零发送，不自动实施 Phase 7。

私有汇总：`.local/acceptance/mac/phase-6/report.json`、`.local/acceptance/windows/phase-6/report.json`；分项 `acceptance-precheck.json`、`service-lifecycle.json`、`send-format.json`、`send-near-500.json`、`workbench-human.json` 和 `clean-install-final/report.json`。固定发送沿用 probe 的 Phase 5 报告结构，归属本次 Phase 6 格式矩阵，不改写原始回执。

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

1. 下一次先读本计划和 overview，再核对对应平台接入说明、提交、私有报告与实际环境。本轮收尾停在 Phase 6；Phase 7 需要新请求。
2. 当前以 Phase 6 本轮完成记录为准；Phase 5 旧交接仅作历史。独立窗和 Apple 系统选择器均已实测黑屏，不重复无依据的捕获重试。恢复严格验收仍需可核验输入界面及对应稳定性证据；不安装旧 wxauto4、不猜旧 AX 消息控件、不重复取钥。
3. Windows Phase 1–4/G1/G2/人工验收保持 completed，本次原生回归延期。Mac 默认 visual 仍要求本机严格 G1/G2；显式 independent/ax-window-db 服务要求本机匹配且用户接受的降级证明及固定发送原生回执，不能借用另一平台报告。
4. 编号映射：v4 Phase 1–4 不变；v4 Phase 5（知识记忆）→v5 Phase 7，v4 Phase 6（可选增强）→v5 Phase 8，v4 Phase 7（交付）→v5 Phase 9。更早的 18 阶段已在 v4 收敛；按主题继续映射到本版，不恢复旧执行顺序。
5. 新增用例使用 P05/P06；原尚未实施的知识/增强/交付用例顺延为 P07/P08/P09。任何既存旧编号/报告保留原 plan_version、日期与含义，用「版本+平台+阶段+用例」识别，不覆盖或改写旧测试结果。
6. 本次已授权的 Phase 5–6 Mac 降级范围已完成。后续新请求可继续 Phase 7 或补齐严格 Mac/Windows 原生回归；延期项保留，Windows 历史通过不豁免共享层改动后的真实回归。
7. v5 实施记录采用实际 platform/foundation；Windows v4 原始报告通过明确兼容映射及本机绑定校验识别，Mac 只能使用自己的 v5 报告。每次收尾同步 overview/README/接入说明，避免计划目标和已实现能力混写。
8. 运行时遇到上游缺陷只做必要且可追溯的补丁；改变产品范围、控制路线或支持声明须明确更新本计划。

## 9. 最终完成条件

Phase 1–7 与 Phase 9 的必需任务、Windows 和 Mac 各自的 G1/G2、Phase 6 对齐验收、两平台工作台人工验收和真实视频齐备；Phase 8 仅对明确选择的项目验收。应用可分别从干净 Windows/Mac 源码包按平台步骤安装启动，原生读取/发送隔离，Agent/知识/记忆/状态/API/UI 接通，发送不确定时停止，许可证和来源清楚，交付无秘密与私聊。仅通道库、固定会话短文本原型、离线截图、模型控制台或阶段文档不能作为最终完成。

当前交付事实为 Windows Phase 1–4 已完成，Mac Phase 5–6 在用户授权的降级范围内通过；正式服务/API/工作台、已打开独立窗导航、格式消息及两轮新增 Agent 回复均经本机/人工核对，worker 已停止。严格 Mac 视觉 G1/G2 未通过；Windows 本次真实回归按用户选择待验证，不记全应用最终完成，不自动实施 Phase 7。真实收发采用自然日常对话、单好友低频、至少 30 秒发送间隔、单次最多 3 条回复。
