# macOS DB 接入与工作台（Phase 5–6）

2026-10-22。状态以 [执行计划](wechat-agent-plan.md) 为准。
Phase 5–6 已在用户授权的降级范围内通过，严格 Mac G1/G2 未通过。
用户授权跳过 Mac 的截图/空草稿/粘贴全文/遮挡核验；正式服务复用共享账本、API 和工作台。
Phase 5 原型两轮回复保持原记录；Phase 6 新增两轮正式回复、两条自然格式消息精确 DB 确认，
用户确认工作台、切窗、完整收件及保持登录全部通过。worker 已停止，服务重启默认 stopped/dry-run。
Windows 本次合成兼容回归通过，真实原生回归按用户选择待验证；不自动进入 Phase 7。
历史固定发送后曾出现安全退登；持久安全锁及 unknown 停发仍生效。

窗口/输入/截图问题的后续检索见 [Mac 自动化调研](mac-automation-research.md)。
独立窗及系统内容选择器已实测，当前组合仍只能取得黑画面或下层画面。
官方独立窗置顶已验证，不能解决捕获。降级模式直接使用独立窗 AX 标题/焦点和 DB 确认。
用户未找到隐藏主窗开关；`sharingState=0` 只作诊断线索，不能断言设置页一定存在对应开关。

## 已实现的边界

### 本轮显式降级模式

私有 Mac profile 新增以下字段，默认仍是 `main` / `visual`：

~~~json
{
  "window_mode": "independent",
  "send_preflight": "ax-window-db",
  "window_width": 598,
  "window_height": 640,
  "composer_top": 0.775
}
~~~

上述尺寸/输入位置是本机本轮记录，不是其他机器的通用坐标。独立窗必须唯一匹配绑定好友精确标题；
运行前人工清空输入框。助手自动激活/AXRaise 目标窗，每次点击、粘贴和回车前核对 AX 焦点、
进程、标题和几何。一次 Cmd+V、一次发送快捷键，随后独立 DB 水位/本人/会话/全文确认。
不截图、不执行 OCR，**空草稿、粘贴全文和遮挡未核验**；报告明确 `ui_checks_degraded=true`。
异常后仍遵循 unknown 不重试和持久安全锁，人工 resolve 不重发。

该 profile 配合显式原型参数可运行流程验证：

~~~sh
uv run wechat-agent prototype --mode dry-run --duration 180 --max-replies 1 \
  --allow-degraded-mac-ui --output .local/acceptance/mac/phase-5/degraded-agent-dry.json
uv run wechat-agent prototype --mode live --duration 900 --max-replies 3 \
  --allow-degraded-mac-ui --output .local/acceptance/mac/phase-5/degraded-agent-live.json
~~~

这不通过严格 G1/G2。Phase 6 已开放同一 `serve` 入口，额外验收依据见下文；默认 `visual` 仍沿用原门禁和以下视觉检查。
实际收发使用自然日常对话；首次监听建立基线，早于基线的来信不会触发回复。
下文的 bootstrap、历史故障及严格视觉要求继续保留作参考。

### Phase 6 正式服务

~~~sh
uv run wechat-agent serve
~~~

本机配置须显式选择 `WECHAT_ADAPTER=mac_db` 和上述降级 profile。服务启动不连接微信，
每次强制 stopped/dry-run；手动访问 `http://127.0.0.1:8765`，在工作台开始。
开始前要求本机匹配的 `.local/acceptance/mac/phase-5/degraded-flow.json`、
`degraded-fixed-send.json` 及其成功原生回执：平台/来源 revision、客户端版本/构建、
绑定和源库指纹一致，报告为用户已接受的降级流程。未决原生操作先停发，不调用模型。
兼容微信新增 `message/media_<数字>.db` 或 `media/media_<数字>.db`：必须能用当前源库身份
精确重现原验收的源库指纹，才允许把额外的语音库加入读取。原有数据库的删除、替换或其他新增分片
仍会拦截；既有验收报告不重写，应用账本保持原绑定锚点，运行中会继续固定新加入语音库的身份。
DATA_DIR 可配置，上述路径以默认 `.local` 为例；不能复制其他账号或 Windows 报告放行。

发送前自动抬高/恢复已打开的唯一绑定独立窗，复核 DB 中标题与原生 username；
从微信其他会话或其他前台窗口切回无需逐条人工操作。独立窗必须保持打开，
不搜索联系人或创建关闭的独立窗。标题歧义/变化、窗口缺失、焦点或进程变化均拒绝。

降级模式支持最多 1000 Unicode 标量，允许 LF、中文/英文、标点、emoji（含组合序列）和空格；
保留模型输出空白，不截断、不拆分。拒绝其他控制字符、无效代理字符、空白或超长输出。
应用默认 `MAX_REPLY_CHARACTERS=500`，开始时检查不超过通道能力；本机实际发送验证为
70 字混合格式及 481 字多段落自然对话，DB 全文与用户完整收件均通过，1000 字边界为合成/Swift 自检。

暂停/恢复/停止、限流、unknown 和迟到结果取消共用正式服务；恢复重建基线。
API 人工处理同步原生 journal 和应用 outbox，仅记结论不重发。源库文件/盐或账本变化、
睡眠/时钟异常间隔停止并要求重连。诊断展示实际权限，设置页标明 Windows UIA/OCR 不适用。
详见 [API 与工作台](api-workbench.md)。

### 默认视觉模式

`mac_db` 使用固定 Gist revision
`c98dbb10cf23c30e83d5d744905101b0880887a0` 的 Reader/SQLCipher/Swift 基础。
来源、完整 MIT 和逐文件原始哈希位于 `third_party/wechat_mac_toolkit/`。
应用 Python 3.12/3.13；压缩文本使用 zstandard，不依赖 Python 3.14。
SQLCipher 由 Homebrew 独立提供；Swift 编译桥，Apple Python/LLDB 仅用于独立首次取钥。
Windows extra 不安装 Mac 原生依赖，Mac 不加载 Replica 原生依赖。

读取直连只读加密 DB/WAL；不导出明文库、不回退旧快照。每个联系人/分库以 local_id
推进分页，满批继续下次读取；游标只随应用 inbox 事务提交。事件标识含 Mac 来源、
账号代数、账号引用、原生会话、分库/local_id；发送者按每库 Name2Id 解析。
启动记录基线，不回复启动前历史；进程、账号目录、客户端版本或源库文件/盐变化会停发。
新建/替换源库需要重新核实绑定，不承诺热换库、停机补收或全格式兼容。

默认视觉通道只支持人工预选的唯一测试好友、已校准输入区域、单行且不超过 200 字。
应用保留 500 字默认上限；视觉通道须单独配置 `MAX_REPLY_CHARACTERS=200`，降级通道可保持 500。
不能精确 OCR 核验的文字、空白/布局、控制字符或超长输出拒绝，不能截断/拆分。
live 发送前自动激活已绑定的微信进程，并通过 AXRaise 抬高唯一匹配校准尺寸的主窗口；
必要时恢复该主窗的最小化状态。它不会更改其他应用或搜索联系人，也不是永久悬浮置顶。
doctor/connect/应用 dry-run 不激活窗口；原生只读预检本身同样不激活。
抬高之后，原生桥检查固定进程、前台可见且无遮挡主窗、精确标题、空草稿、窗口几何和输入全文。
macOS 27 的透明 Dock 可能被系统报告为整屏窗口；仅当其真实 AX 面板可唯一确认且不与
微信相交时排除透明区域，实际 Dock 遮挡、普通遮挡或未知布局仍拒绝。
空草稿要求两张新画面通过原有严格检查，以等待光标闪烁和激活动画结束。
发送前再次核对目标/草稿/焦点；仅按绑定的 enter 或 cmd-enter 一次。
输入已参考固定 Windows 基座的 `uia_driver._paste_into` 和项目的 `send_text_once`：
使用系统剪贴板一次 Cmd+V，随后精确回读草稿，代替逐段 CGEvent Unicode 输入。
操作结束时恢复原剪贴板；检测到用户/其他应用已复制新内容时保留新内容。
构建自检只使用独立命名剪贴板，不触碰用户剪贴板或微信。
上述限制属于严格视觉通道；已通过的 Phase 6 降级工作台使用前述独立窗导航与文本能力，不能借此声称视觉通道通过。

outbox_id 固定映射到应用原生回执及 Swift journal，均位于同一私有 DATA_DIR。
prepared/dispatching/unknown 不换 ID 重发；UI 成功或绿色气泡不能直接确认。
成功依据为发送前分库水位之后唯一的同会话本人完整文本记录；旧同文、多候选、
超时、崩溃或可能发生发送后的错误均保持 unknown。对端收件仍由用户确认。
`resolve` 仅记录人工结论，不操作微信，也不释放同 ID 的再次发送能力。

## 安装与独立初始化

~~~sh
uv sync --locked --extra mac
brew install sqlcipher
uv run python scripts/build_mac_bridge.py
uv run wechat-agent doctor --output .local/acceptance/mac/phase-5/doctor.json
~~~

默认 SQLCipher 动态库路径为 Homebrew 的 `opt/sqlcipher/lib/libsqlcipher.dylib`，
可通过 `SQLCIPHER_LIBRARY` 显式选择；实际加载不接受普通 SQLite ABI。
桥默认构建到 `DATA_DIR/macos/bin/wechat-ui`，支持 `MAC_BRIDGE_PATH` 显式覆盖。
原生桥 doctor 只做权限/运行状态预检，不申请权限、不截图、不激活微信、不取钥或重签。
微信数据目录读取需系统允许本应用访问；出现 `mac_database_access_denied_full_disk_access_required`
时由用户在系统设置授权，不能用 sudo 或改变系统保护绕过。

先复验已有私有密钥；没有有效密钥时才执行独立初始化。用户须正常退出原版微信：

~~~sh
uv run wechat-agent mac-bootstrap \
  --db-root '<选定账号的 db_storage 绝对路径>' \
  --state-dir .local/macos/bootstrap-<本次标识> \
  --timeout 180 \
  --output .local/acceptance/mac/phase-5/bootstrap-result.json
~~~

这会创建和重签私有临时副本，使用 Apple LLDB 捕获仅与选定目录数据库盐匹配且
页 HMAC 验证有效的密钥。用户处理临时窗口/手机登录。应用限制超时、记录原版哈希/
签名，结束时只关闭自己创建的临时进程、禁用临时 bundle，并请求启动原版。
不重签原版、不关闭 SIP、不使用 Hook；副本共享客户端状态，不能当成独立沙箱。
bootstrap 失败不等于连接成功；恢复后仍需真实新来信验证。普通 connect/start 不取钥。

### 工具链故障与恢复记录

本机 macOS 27.0.1、微信 4.1.15（270115）、Apple LLDB 1703 / Swift 6.2 / SDK 26.0。
首次 capture 在 CreateTarget 的 Mach-O 符号解析中 SIGBUS，尚未启动临时微信进程，
未取得密钥。独立系统 `/usr/bin/true` 目标也能复现；Xcode 内同版 LLDB 同样失败。
不加载依赖的目标创建成功仅是定位线索，未验证能运行捕获，不作为可用替代路线。
原版哈希/签名保持，原版已恢复启动。私有证据见 phase-5 下的
`lldb-failure-summary.json`、`lldb-*.log` 和 bootstrap 目录的 `bootstrap.json`。

应用写入 `DATA_DIR/macos/bootstrap-blocked.json`；同父目录的新 bootstrap 也会在执行
原生命令前拒绝。需要先修复/更新匹配当前系统的 Apple 开发工具，单独验证其正常工作，
再由明确的人工修复动作处理停用标记；不自动循环运行会崩溃的探针。
不保证升级一定解决，恢复后仍须从取钥/原版恢复/新鲜度逐项重新验收。

更新后的 SDK 27.0 / Apple LLDB 2103.0.34.103 / Swift 6.4 已通过默认系统目标创建。
`scripts/acceptance/mac_toolchain_check.py` 随后用自有 C 程序和合成 SQLCipher 库，验证了
Apple Python/LLDB 的启动、PBKDF 断点捕获、HMAC 验证和 SQLCipher 查询；返回码 0，
没有访问微信。旧停用标记及证据已保留为 resolved。
随后在用户正常退出及授权临时副本后，19/19 个数据库密钥通过 HMAC 验证，临时进程
退出并禁用副本，原版哈希/签名保持并恢复运行。恢复原版后已读到五条新增来信及一条
本人消息；数量、连续同文、顺序、方向和实际空格均经核对，重读不重复入库。
复验命令（目录必须全新；所有测试材料仍是私有合成数据）：

~~~sh
uv run python scripts/acceptance/mac_toolchain_check.py \
  --directory .local/acceptance/mac/phase-5/toolchain-check-<新标识>
~~~

## 绑定、读取与发送探针

取钥成功、恢复原版并登录后，绑定脚本根据明确微信号唯一查询原生 username，
对照唯一显示标题；本人 username 需与账号目录及每个相关分库 Name2Id 一致。
拒绝覆盖已有 profile、多个联系人、同名或群聊。未提供 composer-top 时可先只读验证，
发送将返回 `mac_composer_calibration_required`，不能猜测输入框位置。

~~~sh
uv run python scripts/acceptance/bind_mac.py \
  --db-root '<已核实账号目录>' \
  --key-file .local/macos/bootstrap-<本次标识>/keys.json \
  --alias test-a --wechat-id '<测试好友微信号>' --title '<精确标题>' \
  --composer-top '<人工校准比例>' --send-key enter \
  --window-width '<校准窗口宽度（点）>' --window-height '<校准窗口高度（点）>' \
  --output .local/macos/profile.json
uv run wechat-agent connect --output .local/acceptance/mac/phase-5/connect.json
uv run wechat-agent probe read --contact test-a --limit 5 \
  --output .local/acceptance/mac/phase-5/read.json
uv run wechat-agent probe send --contact test-a --text '测试回复' --confirm-send
~~~

在 `.env` 显式设置 `WECHAT_ADAPTER=mac_db`、新 profile、账号引用、JSON 白名单和
模型配置；发送模式默认 dry-run。dry-run 不写草稿、剪贴板或注入事件。
固定 live 还需显式 `SEND_MODE=live`。源库新鲜度、5 条测试消息含连续同文、
本人过滤、固定发送及对端收件等完成后，才可形成自己的 `g1.json`。
Mac gate 逐项核对平台、基座/revision、系统/微信版本、绑定和源库指纹及人工收件事实，
不接受 Windows v4 passed 报告。

自动抬高窗口的实际原生只读预检已通过，剪贴板计数不变。固定发送曾在输入前因遮挡
或空草稿检查拒绝，回执均为 not_sent。用户清空后，自动抬高窗口、一次固定发送、
新增本人全文回读及用户对端收件均已确认；随后实际出现安全退登，G1/G2 保持未通过。
原生准备失败会返回已知脱敏原因码，
激活/预检失败或超时不会进入输入与回车路径。可能已经发送后的异常仍为 unknown。

## 账号安全事件与稳定性复验

已观察到的英文提示为 `For account security, log in again.`。它不能区分临时副本登录、
取钥、客户端状态、原生输入或其他服务端因素；目前没有确认根因，不承诺免退登/免封号。
Windows 源码对照只证明输入路径差异，不构成 Mac 账号安全证明。

原生 `session-check` 只读检查绑定进程的 AX 主窗和已知提示，不激活、截图或输入；
窗口存在本身不等于登录认证成功。连接、轮询和发送前都使用该证据。已知提示在 AX
可读取时，应用写入 `DATA_DIR/macos/security-stop.json` 并阻断后续连接/读取/live/
bootstrap/原型 gate；未知弹窗/窗口仍按会话或遮挡不明停发，不猜测登录状态。
用户报告的安全退登同样写入该锁。重启、人工 resolve 或旧 passed 报告不会解除。

用户先通过原版客户端和手机正常登录，再显式记录人工恢复：

~~~sh
uv run wechat-agent mac-security-reset --confirm-manual-login \
  --output .local/acceptance/mac/phase-5/manual-login-reset.json
uv run python scripts/acceptance/mac_stability.py --duration 300 \
  --output .local/acceptance/mac/phase-5/stability-readonly.json
~~~

reset 只归档停发证据，不登录/发送，也不改写失败 gate。复验复用已有密钥，只运行
原版客户端；先做 5 分钟只读观察，再单次验证新粘贴路径并观察，最后才继续三轮 Agent。
观察脚本不调用模型、不操作剪贴板、不输入，报告保留人工登录持续性待核对状态。
新版通过 Swift 独立剪贴板自检和 Python 合成测试，真实发送/观察结果须独立记录。
正常重登后的第一轮只读观察已完成（300.222 秒、20 次检查、无模型调用/输入事件），
期间未记录到原生会话错误；新版真实粘贴发送与发送后观察仍待验证，不构成稳定性通过。

原型仍使用同一 LangGraph、模型客户端和账本：

~~~sh
uv run wechat-agent prototype --mode dry-run --duration 120 --max-replies 3 \
  --output .local/acceptance/mac/phase-5/prototype-dry.json
uv run wechat-agent prototype --mode live --duration 600 --max-replies 3 \
  --output .local/acceptance/mac/phase-5/prototype-live.json
~~~

默认视觉模式要求 G1；本轮显式降级模式的运行方式见上文。默认轮询 15 秒，发送至少间隔 30 秒、每分钟至多 2 次，
单轮最多 3 条。三轮真实问答及上下文追问、逐轮对端收件后才可形成 G2。
`serve` 的 Mac 接入已在 Phase 6 完成；视觉门禁和显式降级验收分别检查，不改写严格 G1/G2。

## 离线验证与私有资料

Phase 6 本轮 222 项 Python 测试、Ruff、Swift 构建/自检、前端类型/构建和 Mac 干净源码安装通过。
无屏幕录制权限时降级 health 可用；未明确选择降级 profile（原型另需 CLI 参数）不能绕过严格 gate。
窗口模式/降级状态进入私有绑定指纹、原生回执、发送及原型报告，Windows 路线保持原有要求。

只读捕获对照可复现为（先人工将正确窗口放到前台；脚本不激活/输入/改 profile）：

~~~sh
uv run python scripts/acceptance/mac_capture_check.py --window-mode independent \
  --backend display --output .local/acceptance/mac/phase-5/capture-display-new.json
~~~

后端可选 `display`、`window`、`stream`、`picker`。`picker` 需要用户在系统选择器中选择准确目标，
保存约 2 秒无声 MP4 和原始帧。所有输出只允许私有 DATA_DIR，已有报告/帧不覆盖；
黑画面、下层画面或不匹配的选窗不能通过。该诊断不修改验收 gate。

`uv run pytest -q` 覆盖 Mac 身份/满批/事务、发送旧同文/多候选/异常/重启/人工处理、
报告隔离和 Windows 原有回归。装好 SQLCipher 后额外运行真实合成加密 DB/WAL：
错误密钥、只读拒写、提交/未提交、checkpoint/reset、跨分库、同秒同文、Zstandard。
`sqlcipher_probe.py self-test` 另含坏 WAL 帧校验；不代表真实微信损坏恢复已验证。

秘密、回执、用户名、正文、截图和临时副本只在私有 DATA_DIR；目录 0700、
密钥/报告/文本 0600。不要把 `.env`、账号目录或 bootstrap 缓存加入 Git/交付包。
临时副本在原版恢复且证据核对后可删除；保留必要故障摘要及 unknown 回执，
不能通过清缓存解除停发。前端仅类型/构建检查，没有打开浏览器或执行 CUA/Playwright。
本轮汇总在 `.local/acceptance/mac/phase-6/report.json`，用户验收在 `workbench-human.json`，
干净安装在 `clean-install-final/report.json`；Windows 延期说明在 `.local/acceptance/windows/phase-6/report.json`。

## Phase 7–9 续做

本轮已实现共享知识/长期偏好及工作台入口、正式服务离线回放、打包和最终验收/录像脚本。
Mac Phase 9 干净目录锁安装、Swift 构建/自检、stopped/dry-run HTTP 及知识 CRUD 通过，
证据在 `.local/acceptance/mac/phase-9/`。未执行真实微信或浏览器操作；严格 Mac G1/G2
和新知识/记忆真实回复/界面均待用户。原降级模式及限制继续适用，不再次取钥或变更客户端。
下一步按 [最终验收清单](delivery-checklist.md)；Phase 8 未选择，不纳入交付。
