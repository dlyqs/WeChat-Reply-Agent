# macOS DB 原型接入（Phase 5）

2026-10-21。状态以 [执行计划](wechat-agent-plan.md) 为准。
当前实现与离线验证已落盘；Mac G1/G2 未通过，Phase 6 未进入。
本机首次取钥被 Apple LLDB 的 SIGBUS 阻塞，没有真实发送或运行 live Agent。

## 已实现的边界

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

发送只支持人工预选的唯一测试好友、已校准输入区域、单行且不超过 200 字。
应用保留 Windows 原有的 500 字默认上限；Mac 原型应单独配置 `MAX_REPLY_CHARACTERS=200`。
不能精确 OCR 核验的文字、空白/布局、控制字符或超长输出拒绝，不能截断/拆分。
原生桥检查固定进程、前台可见且无遮挡主窗、精确标题、空草稿、窗口几何和输入全文。
发送前再次核对目标/草稿/焦点；仅按绑定的 enter 或 cmd-enter 一次。
该限制尚不满足 Phase 6 的导航和完整文字能力对齐，不能宣称已支持 Mac 工作台。

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

### 当前工具链阻塞与恢复

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

原型仍使用同一 LangGraph、模型客户端和账本：

~~~sh
uv run wechat-agent prototype --mode dry-run --duration 120 --max-replies 3 \
  --output .local/acceptance/mac/phase-5/prototype-dry.json
uv run wechat-agent prototype --mode live --duration 600 --max-replies 3 \
  --output .local/acceptance/mac/phase-5/prototype-live.json
~~~

G1 未过不得运行；默认轮询 15 秒，发送至少间隔 30 秒、每分钟至多 2 次，
单轮最多 3 条。三轮真实问答及上下文追问、逐轮对端收件后才可形成 G2。
`serve` 的 Mac 接入属于 Phase 6，当前明确拒绝启动该未完成路径。

## 离线验证与私有资料

`uv run pytest -q` 覆盖 Mac 身份/满批/事务、发送旧同文/多候选/异常/重启/人工处理、
报告隔离和 Windows 原有回归。装好 SQLCipher 后额外运行真实合成加密 DB/WAL：
错误密钥、只读拒写、提交/未提交、checkpoint/reset、跨分库、同秒同文、Zstandard。
`sqlcipher_probe.py self-test` 另含坏 WAL 帧校验；不代表真实微信损坏恢复已验证。

秘密、回执、用户名、正文、截图和临时副本只在私有 DATA_DIR；目录 0700、
密钥/报告/文本 0600。不要把 `.env`、账号目录或 bootstrap 缓存加入 Git/交付包。
临时副本在原版恢复且证据核对后可删除；保留必要故障摘要及 unknown 回执，
不能通过清缓存解除停发。前端未修改，也没有打开浏览器或执行 CUA/Playwright。
