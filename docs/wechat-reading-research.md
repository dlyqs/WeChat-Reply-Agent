# 微信消息读取技术调研

调研日期：2026-10-21（Asia/Shanghai）。目标环境：macOS 27.0.1 / arm64 / 微信 4.1.5（31960）；最终读取不依赖 OCR。本文是候选研究，不改变主计划的阶段状态或授权边界，也不代表实机兼容验收。

本轮通过 GitHub 搜索/文件/元数据接口和公开网页检索筛查十余个项目，实际查看 README、关键源码、当前仓库状态及许可。只读取公开资料，没有安装或执行候选取钥/解密/发送程序，没有读取私人聊天数据库。搜索引擎缓存的功能描述不能作为仓库当前可用的证据。

## 结论

存在多条无 OCR 路线。与当前 Mac 目标最相关的是：经本人授权取得逐库密钥 → SQLCipher 只读打开本地 DB 与有效 WAL → 解析会话/发送者/消息 ID → 持久化增量游标 → Agent。密钥获取和日常读取是两个不同阶段；日常读盘不必持续通过截图，也不必持续调试进程。不同版本和发行包的密钥形态、签名和权限前提仍需实测，不能保证 sudo 即可成功。

读取与发送应分别验收。数据库可读不能证明可以安全发送；修改本地数据库也不能替代真正向好友发消息。当前 AX 发送控件在本机不可见的问题仍需单独解决。

## 主要候选

| 项目 | 技术与证据 | 当前判断 |
| --- | --- | --- |
| [stkoecn/im-mcp](https://github.com/stkoecn/im-mcp) | Python；Mac LLDB 取钥、WCDB/SQLCipher 页解密、WAL 合并、消息解析、SQLite 索引、MCP 查询；核心读取源码齐全 | 新增优先审计候选，适合复用结构化读取与索引设计。无需 OCR，但目前是定时快照同步，最低 5 分钟，不是实时自动回复通道；WAL 有效性、快照一致性与密钥日志仍需改造。无发送工具，本机 4.1.5 未验证。详见下节。 |
| [Luofeng-Cloud/WeChat-AI-AutoReply](https://github.com/Luofeng-Cloud/WeChat-AI-AutoReply) | Windows Win32 截图/消息投递 + RapidOCR + 像素变更检测 + 模型自动回复；MIT | 不适合作为当前 Mac 无 OCR 接入。Zero-Mouse 指鼠标动作方式，读取和发送前会话核验仍用 OCR；作者也确认是 Windows 版。可参考变更检测与发送前复核思路。 |
| [jackwener/wx-cli-again](https://github.com/jackwener/wx-cli-again) | Rust / SQLCipher / 本地 daemon / DB+WAL 更新 / watch；公开源码含 Cargo.lock、查询/取钥/缓存/测试代码；Apache-2.0 | 优先做独立源码审计和合成数据验证。README 安装指向 private 的 botiverse/wx-cli，但当前公开仓库确实有源码快照；应审计这个快照并自行构建，不能照抄私有上游安装说明。取钥涉及进程读取，缺少密钥时可进入 LLDB 断点路径；不是零侵入接口。 |
| [acmerfight 的 Mac 本地工具 Gist](https://gist.github.com/acmerfight/0a01249ef72970d07a2603dbb629e80f) | 实际提供 wechat_db.py、sqlcipher_probe.py、bootstrap_keys.py、capture_keys.py、测试和验证文档；MIT；读取端是 DB+WAL、分库 local_id 游标和 ack | 值得与 Rust 候选并列审计读取部分。作者记录环境 macOS 15.6.1 / arm64 / 微信 4.1.15，不是本机环境。首次方案调试并重签临时应用副本，作者声称保留原版签名和 SIP；通用 bootstrap 封装、人工逐步实测与合成测试的验证层级不同。其 Swift 发送端仍使用 OCR，不能整体作为本项目无 OCR 方案。 |
| [hicccc77/WeFlow](https://github.com/hicccc77/WeFlow) | 跨平台本地记录查看/分析；HTTP API 与 SSE 新消息事件；已读 keyProviderService、wcdbCore、messagePushService 和组件契约 | 能参考结构化数据 API 和推送，但当前原生读取/解密组件全部外置，clone 后不具备完整取钥和查询能力。LICENSE 为 CC BY-NC-SA 4.0，不能当作 MIT/Apache 代码直接复用到任意交付。 |
| [huohuoer/wechat-cli](https://github.com/huohuoer/wechat-cli) | Python SQLCipher 页读取、消息查询、macOS C 扫描器；Apache-2.0 | 源码可审阅，但 macOS 扫描器有自动重签原版微信分支；new-messages 只是 SessionTable 最新摘要差分，不能直接作为逐条消息监听器。 |
| [leeguooooo/wechat-use](https://github.com/leeguooooo/wechat-use) | 面向 agent 的 Mac 读写 API、daemon/listen、HTTP/MCP/Wechaty；当前说明固定专用 4.1.9 副本，原生后台及有限被动内存读取 | 产品形态很接近目标，但不适配当前 4.1.5 的现成保证。需要激活，采用自定义非商业许可，包含分发限制；不是可任意嵌入的宽松开源依赖。仅审阅公开说明，未验证核心二进制或实际行为。 |
| [TANGandXUE/wcdb-key-tool](https://github.com/TANGandXUE/wcdb-key-tool) | 三平台取钥组件，含 macOS Python 源码、HMAC 验证、LLDB 派生分支；MIT | 它是取钥/解密部件，不是完整的新消息服务。README 对版本的概括与源码分支说明并不完全一致；macOS 文件说明含 4.1.10+ 断点分支、原版重签前提和全局 LLDB 清理，应审计后隔离改造，不能直接运行安装片段。 |
| [cluic/wxauto](https://github.com/cluic/wxauto) / [当前 wxauto 文档](https://docs.wxauto.org/docs/install.html) | Windows UI Automation；公开 GitHub 源码 VERSION 为 3.9.11.17；另行分发的 wxauto4 文档声明支持 Windows 微信 4.1，免费版列至 4.1.8.107 | Windows 候选，有机会同时收发；旧 GitHub 开源快照与当前 4.x 包必须区分。不应把该文档当作本机 Mac 或任意 Windows 4.x 的兼容证据。 |
| [lich0821/WeChatFerry](https://github.com/lich0821/WeChatFerry) | Windows Hook/注入 + RPC，有消息接收与发送；MIT | 原仓库已 archived，2026-07-10 最后推送；不是当前 Mac 4.1.5 的直接方案。 |
| [Wechaty](https://github.com/wechaty/wechaty) / [ItChat](https://github.com/littlecodersh/ItChat) | Wechaty 是框架，接入能力取决于 Puppet；ItChat/puppet-wechat 是 Web 会话路线 | 有成熟消息事件抽象，但安装 SDK 不代表当前账号能登录协议或当前 Mac 可读。要检查具体 provider、登录限制和维护状态，不能只看框架 stars。 |
| [CosmosShadow/UseChat](https://github.com/CosmosShadow/UseChat) | 公开 README 明确截图、系统 OCR hints 与视觉模型共同读取；支持 agent 接口 | 属于 Computer Use 视觉路线，不符合最终无 OCR 的读取要求；不因 CLI/MCP 封装就变成结构化底层读取。 |

## 用户指定项目的进一步核查

本次核对固定源码快照、README、依赖、同步/查询/取钥实现、测试和相关 issue；没有安装项目或执行初始化、取钥、解密、发送。以下运行能力均为源码结论或作者记录，不能替代本机验证。

### WeChat-AI-AutoReply：Windows OCR 自动回复

固定快照：`696ebc314b2f67a3469f6b9e53726b5090f54554`。`wechat_ai_bot_dev.py` 导入 RapidOCR，并直接调用 `ctypes.windll.user32/gdi32/shcore/kernel32`；实际扫描函数先截图和像素差分，再调用 OCR 识别内容。像素哨兵和缩放能减少 OCR 工作量，没有改变文字来源。[平台依赖](https://github.com/Luofeng-Cloud/WeChat-AI-AutoReply/blob/696ebc314b2f67a3469f6b9e53726b5090f54554/wechat_ai_bot_dev.py#L13-L21)、[读取链路](https://github.com/Luofeng-Cloud/WeChat-AI-AutoReply/blob/696ebc314b2f67a3469f6b9e53726b5090f54554/wechat_ai_bot_dev.py#L938-L995)

其 Zero-Mouse 采用 Win32 消息/按键机制实现动作；发送前仍 OCR 顶栏和侧栏确认目标，点击纠偏后再次 OCR 复核。作者在 [Mac 支持 issue](https://github.com/Luofeng-Cloud/WeChat-AI-AutoReply/issues/3#issuecomment-6163086699) 明确答复当前是 Windows 版，Mac 要替换系统 API 并适配 OCR 布局。[发送实现](https://github.com/Luofeng-Cloud/WeChat-AI-AutoReply/blob/696ebc314b2f67a3469f6b9e53726b5090f54554/wechat_ai_bot_dev.py#L767-L830)

[#5](https://github.com/Luofeng-Cloud/WeChat-AI-AutoReply/issues/5) 有用户报告空白画面被识别为符号并反复回复；这仅是 issue 报告，不推断所有版本均有此问题。本项目不能将其“零风险”或响应速度宣传作为实测事实。可参考静止画面过滤和发送复核，不采用其核心通道满足 Mac 无 OCR 目标。

### im-mcp：无 OCR 读取源码齐全，实时链路仍需补齐

固定快照：`405675b619397adc1b2d2549bb0cee1714ad46f7`，Python 包版本 0.0.1。微信链路为：源库与 WAL → 解密快照 → ETL 导入 `app.db`/FTS5 → MCP 查询。其“只读”指不向微信发送或写入原始消息；工具会保存密钥、明文快照和自身索引。核心能力在当前公开仓库中，不是仅有 MCP 外壳或依赖私有原生组件。

值得采用的部分：

- **实际实现 Mac 取钥**：`capture_passphrase_lldb` attach 微信进程，在 `CCKeyDerivationPBKDF` 设置断点，按 arm64/x86_64 寄存器读取口令原料，再 PBKDF2 派生和 HMAC 验证。已有口令可复用；Mac 4.1 默认走 LLDB 分支，需要重新登录触发。故障提示包含重签原版微信建议，说明 MCP 封装没有消除调试权限/签名条件；本轮未执行该建议。[捕获实现](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/tools/key_tool.py#L1095-L1207)、[4.1 路由](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/tools/key_tool.py#L1889-L1948)、[权限失败提示](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/tools/key_tool.py#L1322-L1329)
- **消息标识比纯时间戳更合适**：索引以 `(source_file, session_username, local_id)` 唯一约束去重，UPSERT 保留已有行的 `id`；`get_messages_since(after_id=...)` 按递增索引 ID 分页，返回 `next_cursor/has_more`，不会因两条消息同文或同秒而直接合并。该 ID 是中间索引 ID，不能命名为微信服务端消息 ID；消费方仍须持久化 inbox 后再提交游标。[schema](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/database.py#L75-L85)、[UPSERT](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/adapters/v4.py#L206-L220)、[游标工具](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/server.py#L1328-L1418)
- **可参考解析与查询边界**：读取解密库使用 SQLite `mode=ro`，解析真实会话/发送者映射；Name2Id 读取失败会跳过该分库，避免身份键漂移。它提供历史、搜索、通讯录等读取工具，没有发送工具。

不能直接接入自动回复的缺口：

| 发现 | 对本项目的影响与需要补齐的内容 |
| --- | --- |
| 自动同步默认 30 分钟、最小 5 分钟；每次重新解密再 ETL | 查询已建索引快，不等于新消息发现快。`get_messages_since` 本身不刷新源库；当前周期不满足轮询 ≤2 秒与回复 P95 ≤20 秒目标。需要验证真正的按变更分库刷新/增量读取，不能只把定时器改成 1 秒。[同步配置和流程](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/auto_sync.py#L40-L48)、[刷新入口](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/auto_sync.py#L169-L181) |
| WAL 合并按固定帧长度遍历，只取页号/提交页数，没有校验头部 magic/page size、帧与头部的 salt、累计 checksum | 从源码推断，WAL reset 后残留旧帧和并发更新存在误合并风险；页数比较与 SQLite quick_check 不能证明快照来自同一代、内容最新。这是静态审计发现，尚未构造复现；采用前需验证 WCDB 实际格式并补合成 WAL reset/截断/坏帧/并发 checkpoint 用例。SQLite 标准明确以 salt 与 checksum 判定有效帧。[当前合并实现](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/tools/key_tool.py#L1722-L1789)、[SQLite 官方格式](https://sqlite.org/fileformat2.html#wal_file_format) |
| 主库解密和 WAL 读取分两步进行，直接覆写输出；WAL 失败可回退主库并继续 | 未看到足够证据保证活动源库的单一时点快照或刷新失败后停发。需要有界重试/一致性检查、临时快照原子发布和明确 degraded 状态，不能把旧快照查询成功当作已读到最新消息。[解密主流程](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/tools/key_tool.py#L1680-L1719)、[WAL 回退](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/tools/key_tool.py#L1840-L1858) |
| `after_id` 只覆盖新插入行；身份是中间库局部状态 | 正常 UPSERT 不漂移；但删库重建、账号切换仍需 account/index generation，不能沿用旧游标。已有行内容更新不会被 `id > cursor` 发出；若要处理撤回/更新需单独变更事件。`after_time` 仍是严格时间大于，不推荐作为唯一游标。 |
| 取钥日志输出口令前缀，4.0 raw-key 分支还打印完整 enc_key；默认捕获无限等待 | 接入前须去除秘密日志并设置有界超时、受控退出和私有存储权限，不能直接运行原初始化器并收集全部 stdout。[口令前缀日志](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/tools/key_tool.py#L1246-L1255)、[raw-key 日志](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/tools/key_tool.py#L1452-L1460)、[默认超时](https://github.com/stkoecn/im-mcp/blob/405675b619397adc1b2d2549bb0cee1714ad46f7/src/wechat_mcp/tools/__init__.py#L50-L54) |

作者 README 记录的 Mac 实测版为 arm64 微信 4.1.35.15、Intel 4.1.15，不含本机 4.1.5（31960）/macOS 27.0.1 组合；“支持 4.x”不能代替该组合验收。已查看同步 mock 测试、合成 SQLite 时间分页测试和基础 MCP 测试，未运行上游测试，也未获得上述实时/WAL/本机兼容性的实测证据。`pyproject.toml` 声明 MIT，但当前仓库树没有 LICENSE/COPYING 正文；复制代码前还需核对上游来源与完整许可声明。

推荐把 im-mcp 提升为**结构化消息解析/索引层的优先候选**，与 Gist 的 Reader/ack 和 Rust daemon/WAL 方案交叉审计；不将它整体包装成已完成的实时自动回复器。最终应用可直接复用可审计的 Python 读取部件，不必为了 MCP 再增加一个 Agent。发送端、本机取钥可行性、实时新鲜度和崩溃后消费语义仍分别验收，G1 状态不变。

## 已失效或缺少核心实现的依赖链

- [sjzar/chatlog](https://github.com/sjzar/chatlog/blob/main/README.md)：作者于 2025-10-20 移除代码和提交历史，当前仅保留移除说明，不是可直接安装的原仓库。
- `ylytdeng/wechat-decrypt`、`TE0dollary/chatlog-bot`、`r266-tech/wechat-cli`：本轮 GitHub API 实际返回 451 / Repository access blocked（DMCA）。未从搜索缓存或未知镜像假装获取到可用原版。
- [Thearas/wechat-db-decrypt-macos](https://github.com/Thearas/wechat-db-decrypt-macos)：当前树只剩 README 一行说明，无实际取钥程序。
- [xingfanxia/wechat-mac-reader](https://github.com/xingfanxia/wechat-mac-reader)：确实提出 DB 读取 + 文件变更监控/HTTP/Webhook + AX 发送的组合，架构非常接近本项目；但它依赖上述已移除的 Thearas 与被阻断的 chatlog-bot，README 还要求关闭 SIP，发送仍依赖本机不可用的 AX。不能把 setup 脚本成功克隆主仓库当作整套能力可用。
- [robbin/wechat-exporter](https://github.com/robbin/wechat-exporter)：2026-10-17 更新后明确改为实现规范，不附现成解密器或 MCP server。适合作为格式/WAL/验收研究资料，不是已经完成运行程序的依赖。

这些是具体的可用性检查结果，不据此评价仍未验证的分支或 fork。

## 两个直接影响自动回复的源码发现

1. Python wechat-cli 的 `wechat_cli/commands/new_messages.py` 读取 SessionTable，将每个会话的最后摘要作为 last_message 返回。两次轮询间多个气泡不等价于多条事件，不能直接满足连续同文与完整增量要求。[源码](https://github.com/huohuoer/wechat-cli/blob/a3789232d4f79bf0b30634d9dadbce71e4acd601/wechat_cli/commands/new_messages.py#L115)
2. Rust wx-cli-again 的 watch 检查 session DB/WAL/SHM 修改时间，后端确实读取消息表。但 `q_new_messages` 以每会话秒级时间戳及 `create_time > since_ts` 分页，状态也只保存时间戳。从代码推断，同秒分批落盘/截断后的未返回同秒记录存在漏读风险；需要合成用例验证并改为消息级稳定 ID/复合游标，不应直接承诺无损。watch 还在消费者持久化确认前推进自身状态，自动回复需独立 inbox/ack。[查询源码](https://github.com/jackwener/wx-cli-again/blob/077a54cbfe679bda963cd038d8440422907fc797/src/daemon/query.rs#L3598)、[watch 源码](https://github.com/jackwener/wx-cli-again/blob/077a54cbfe679bda963cd038d8440422907fc797/src/cli/watch.rs#L115)

Gist 的读取端提供分库 local_id 与显式 ack，是更贴近可靠 inbox 的设计参考；仍需验证数据库替换、同文、重启、积压、多库、只读 WAL 和消费失败，不因存在 ack 命令就自动验收。

## 推荐研究顺序与边界

1. 若坚持当前 Mac + 无 OCR，优先审计 im-mcp 的消息解析/稳定索引与 Gist 的只读 Reader/ack，结合 wx-cli-again 的 daemon/WAL 方案，分离取钥和日常读取。先对合成 SQLCipher DB/WAL、连续同文、同秒消息、游标/ack/崩溃恢复和 WAL reset 验证；im-mcp 的现有定时快照不能直接满足实时要求。
2. 首次取钥只比较具体可审计路径：已有有效密钥复用、受权进程读取、临时副本调试。对“无需 SIP / sudo 即可 / 绝不封号”等 README 保证不作本项目承诺。Gist 记录在其 Hardened Runtime 环境中 root 仍无法申请读取端口，与另一项目的概括存在环境差异，必须以本机事实为准。
3. 发送端另测，保留白名单、唯一身份、草稿/焦点校验、unknown 禁止盲重发。DB 回读能提供发送后证据，不能撤销错对象发送，不能替代发送前身份核对。
4. 原计划排除了聊天数据库/内存/Hook；本轮仅研究这些候选，尚未授权执行。采用新路线前需明确调整接入边界和 G1 用例；不擅自关闭 SIP、重签主微信、安装指定版本副本、读取真实数据库或执行断点取钥。
5. 如果数据库/取钥边界保持禁止，保留剪贴板原文提取或经实测的其他环境 UIA 候选；目前没有充分证据保证它们能满足当前 Mac 的完整自动监听需求。

## 源码快照与外部资料

| 来源 | 本次读取版本 |
| --- | --- |
| Luofeng-Cloud/WeChat-AI-AutoReply | `696ebc314b2f67a3469f6b9e53726b5090f54554` |
| stkoecn/im-mcp | `405675b619397adc1b2d2549bb0cee1714ad46f7`，Python 包版本 0.0.1 |
| wx-cli-again | `077a54cbfe679bda963cd038d8440422907fc797`，Cargo 版本 0.6.3 |
| huohuoer/wechat-cli | `a3789232d4f79bf0b30634d9dadbce71e4acd601` |
| WeFlow | `fb58afa9876c6b334887a33471dd5f0077eedec4` |
| robbin/wechat-exporter | `02ede934e8a344888d71a8c2bca06b177be65d5f` |
| Thearas/wechat-db-decrypt-macos | `2278f6a83c61b1811244afbedd121bd0ac47f05b`，只剩说明 |
| acmerfight Gist | `c98dbb10cf23c30e83d5d744905101b0880887a0`，更新 2026-10-20 |

同时阅读了 [Wechaty 官方 provider 说明](https://wechaty.js.org/docs/puppet-providers/)、[wxauto 当前环境文档](https://docs.wxauto.org/docs/install.html) 和 [2026-03-27 跨平台研究文章](https://yage.ai/share/wechat-uia-platform-feasibility-survey-20260327.html)。后者用作线索：其中部分项目现状、平台兼容和系统权限概括已被当前原仓库或本机证据推翻，未照搬其可用性或零风险结论。

上述快照仅作研究记录，没有将候选代码导入正式包。后续若采用，应另审完整许可和具体源码，并更新复用登记。
