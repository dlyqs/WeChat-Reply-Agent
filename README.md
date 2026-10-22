# WeChat Reply Agent

基于 Windows wechatauto-replica 和 Mac 数据库/原生桥的个人微信 AI 回复应用。在固定桌面环境中完成“绑定好友发消息 → Agent 处理 → 微信回复”，提供本地工作台、TXT/Markdown 知识检索与联系人偏好记忆。

当前已内置固定 Replica 基座，Windows 微信 4.1.15.56 已完成历史 G1/G2 及 Phase 3–4 工作台人工验收。Phase 7 知识/长期偏好、Phase 9 正式服务离线回放和源码交付工具已实现；两平台新功能的真实回复/界面核对、Windows 新回归、Mac 严格 G1/G2 和真实录像仍待用户。Phase 8 可选增强未选择，不纳入本次交付。

执行顺序、阶段状态及完成条件见 [执行计划](docs/wechat-agent-plan.md)，当前代码事实见 [开发入口](docs/overview.md)。

首次在新 Mac / 新账号使用，请先阅读本文的 **[macOS 全链路设置](#macos-全链路设置)**：包含环境安装、独立配置、临时副本取钥、账号绑定、窗口校准、读取验证、真实发送与本机验收、工作台测试、换账号及排障。邮件中的测试步骤是概要，具体命令和前置条件以本节为准。

Mac Phase 5–6 已在显式降级模式下通过：一个已绑定独立 AX 聊天窗、一次剪贴板粘贴/发送、独立数据库确认，共用正式服务、API、账本和工作台。用户确认独立窗自动切回、两轮正式回复、含换行/emoji/长段落的消息完整收件及保持登录均通过。截图、空草稿、粘贴全文和遮挡检查未验证，严格 Mac G1/G2 未通过。本轮 Phase 7–9 未打开页面、连接或发送微信；离线和人工项分别见 [交付清单](docs/delivery-checklist.md)。

## 技术路线与运行范围

| 部分 | 方案 |
| --- | --- |
| 微信基座 | [wechatauto-replica 1.2.7.0](https://github.com/fanyuantaier/wechatauto-replica/tree/d322c4a9b1124228820bab363e5676016f188fc6)，固定源码快照，已作为 third_party 本地 path 依赖内置 |
| Mac 基座 | 固定 Gist revision 的 Reader/SQLCipher 与本地 Swift 桥，MIT 来源和补丁见 third_party/wechat_mac_toolkit |
| 消息读取 | Windows 为 Replica DB/WAL；Mac 为 SQLCipher 只读 DB/WAL、校验已有逐库密钥，首次取钥独立初始化 |
| 回复发送 | Windows UIA/坐标/OCR 与剪贴板，允许 UIA 热激活；Mac 原生独立窗、剪贴板/按键及精确 DB 回读 |
| Agent | LangGraph、可配置模型/人设、多轮上下文、jieba/FTS5 知识检索与按联系人隔离的长期偏好 |
| 应用 | Python 3.12、FastAPI、SQLite、React/TypeScript/Vite；API/UI 不直接调用第三方 GUI 方法 |
| 环境 | 固定 Windows x64 或 macOS Apple Silicon；每台本机一个账号/好友单聊、独立 DATA_DIR，桌面解锁且绑定窗口可用 |
| 节奏 | 默认 15 秒轮询，可配置；不要求实时、多版本矩阵或全天候运行 |

微信 4.1.15.53 为上游记录的测试组合，可优先验证；本项目本次实际验证的是 4.1.15.56，不要求为适配擅自覆盖当前客户端或聊天数据。OCR 已允许使用，不再强制关闭。详细初始化步骤和 G1 用例见 [Windows 接入](docs/windows-probe.md)。

## macOS 全链路设置

本节面向首次在新设备、新账号上复现的使用者，命令均在仓库根目录执行。`<...>` 是必须替换的参数，不能原样执行。以下统一使用私有目录 `.local/review-account`；已有账号继续使用其原目录，不应照抄示例覆盖原配置。

**当前是命令行半自动接入，不是工作台一键初始化。** 取钥需要人工登录及授权，窗口参数需要本机校准，正式工作台开始前还需要真实收发证据与人工验收记录。该流程不能保证在所有 macOS / 微信版本上成功。

### 1. 确认环境和接入方式

| 项目 | 要求 / 已验证范围 |
| --- | --- |
| 硬件与系统 | 当前原生取钥 / 发送路线要求 Apple Silicon、普通用户运行；本机实测 macOS 27.0.1，未完成 Intel Mac 或多系统版本矩阵 |
| 微信 | 当前 Mac 实测 4.1.15（270115）；取钥命令默认使用 `/Applications/WeChat.app`，其他安装路径不能直接照抄本节 |
| Python 与工具 | 建议 Python 3.12，安装 uv、Homebrew，以及与系统匹配的 Xcode / Command Line Tools；需能运行 Swift、LLDB 和 Apple 自带 Python |
| 发送方式 | 本节采用已实测的 `independent` + `ax-window-db` 降级方式；保持唯一绑定独立聊天窗打开、输入框为空、桌面解锁 |
| 权限 | 按系统提示给实际执行终端、原生桥及取钥临时副本授予必要的辅助功能、数据访问权限；读取账号目录可能需要完全磁盘访问权限 |
| 截图限制 | 当前组合取得的微信画面可能黑屏或为下层画面，因此本节不依赖截图 / OCR；空草稿、粘贴全文和遮挡需人工核对 |

新 Mac 尚未安装开发工具时，可先执行 `xcode-select --install`，按系统提示完成安装；已安装者不必重复。Homebrew 安装方式见 [官网](https://brew.sh/)，uv 也可按 [官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)单独安装。应用 Python 与取钥使用的 Apple Python / LLDB 是两套工具，安装 uv 不能代替后者。

权限在「系统设置 → 隐私与安全性」中按实际调用进程设置：辅助功能用于原生窗口检查和输入；完全磁盘访问权限用于受保护的账号目录；临时副本首次访问数据时可能另行提示授权。授权后如仍显示无权限，正常退出并重新打开对应终端 / 进程再检查。仅有 Command Line Tools 不代表任意新系统的 LLDB 都兼容，应以步骤3的检查结果为准。

本项目不是微信官方接口。临时副本登录、取钥和自动输入均可能触发账号限制或退登；低频并不保证免风控。只使用自己授权的测试账号和明确同意的测试好友。临时副本共享客户端状态，不是隔离沙箱。

### 2. 准备独立 `.env`

获取仓库并进入根目录：

```sh
git clone https://github.com/dlyqs/WeChat-Reply-Agent.git
cd WeChat-Reply-Agent
```

首次使用且尚无 `.env` 时执行 `cp .env.example .env`；已有 `.env` 时先保存原配置，再编辑需要变更的字段。以下值是示例，不包含真实密钥：

```dotenv
WECHAT_ADAPTER=mac_db
DATA_DIR=.local/review-account
WECHAT_ACCOUNT_REF=review-account
WECHAT_PROFILE=.local/review-account/macos/profile.json
WECHAT_ALLOWLIST=["review-friend"]
MAC_BRIDGE_PATH=.local/review-account/macos/bin/wechat-ui
SEND_MODE=dry-run

LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=填写自己的模型密钥
LLM_MAX_INPUT_TOKENS=8192
LLM_MAX_OUTPUT_TOKENS=256
MAX_REPLY_CHARACTERS=500
POLL_INTERVAL_SECONDS=15
MIN_SEND_INTERVAL_SECONDS=30
MAX_SENDS_PER_MINUTE=2
MAX_REPLIES_PER_RUN=3
```

- `WECHAT_ALLOWLIST` 是 JSON 数组，填写应用绑定别名 `review-friend`，不是显示昵称；后续绑定命令的 `--alias` 必须一致。
- `WECHAT_ACCOUNT_REF` 是本应用的账号引用，不是微信登录凭证。绑定脚本会记录当时的引用，之后不能仅改它来冒充其他账号。
- 模型地址、名称和 Key 按自己的兼容服务填写；地址保留服务商要求的 `/v1` 等前缀，不加 `/chat/completions`。
- 配置优先级为环境变量 > `.env` > 默认值。若修改 `.env` 后未生效，检查终端是否已有同名环境变量。
- `.env`、逐库密钥、profile、账本、临时副本及验收材料均是本机私有数据，不随仓库交付，也不应提交 Git。

### 3. 安装依赖、构建与检查工具链

```sh
brew install uv sqlcipher
uv sync --locked --extra mac --python 3.12
uv run python scripts/build_mac_bridge.py \
  --output .local/review-account/macos/bin/wechat-ui
uv run wechat-agent doctor \
  --output .local/review-account/acceptance/mac/doctor.json
```

构建脚本的默认输出固定为 `.local/macos/bin/wechat-ui`，**不会自动跟随 `DATA_DIR`**；因此自定义目录时要像上例一样同时设置 `--output` 和 `MAC_BRIDGE_PATH`。构建会运行原生自检，不启动或操作微信；安装后的工作台已随源码打包，正常使用无需启动 Node 服务。

`doctor` 只检查环境，不自动授予权限、登录、取钥或完成验收。先查看报告中的具体依赖 / 权限项。**尚无 profile 时，它按默认视觉模式检查，可能因未授予录屏权限而报告不可用**；完成步骤6的显式降级绑定后应再次运行，届时不依赖截图权限，但仍要求辅助功能、原生窗口检查和微信运行状态可用。不要把首次环境诊断当作已完成接入。

若 LLDB 曾崩溃，或首次取钥前希望先验证工具链，可运行合成检查：

```sh
uv run python scripts/acceptance/mac_toolchain_check.py \
  --directory .local/review-account/acceptance/mac/toolchain-check-01
```

目录应为全新目录。该检查只访问自行创建的进程和加密测试库，不访问微信；成功也不等于微信取钥成功。历史上旧 LLDB 在 macOS 27 上曾崩溃，应使用与系统匹配且实际检查通过的开发工具。

### 4. 确认目标账号的数据库目录

先用原版微信正常登录自己的测试账号，与测试好友至少产生一条已落盘的文本消息；绑定需要本地会话记录。若准备验证文件或语音，先让对应内容在本地可用，并注意媒体库可能按需打开或创建。

常见账号目录：

```text
~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/<账号目录>/db_storage
```

可只读列出候选目录：

```sh
uv run python - <<'PY'
from pathlib import Path

base = Path.home() / "Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files"
for candidate in sorted(base.glob("*/db_storage")):
    print(candidate)
PY
```

多个目录时须人工核实当前登录账号，不自动选最近修改的目录。后续 `--db-root` 必须使用同一账号的**绝对路径**。绑定、取钥和工作台必须指向同一个账号；不要清空、搬动或覆盖微信原始聊天数据库。

### 5. 通过临时副本获取密钥

1. 停止本项目已有服务、探针或原型，确保同一 `DATA_DIR` 没有其他实例运行。
2. 在微信菜单正常退出原版微信，避免同时运行原版和临时副本。
3. 替换数据库绝对路径，使用新的初始化目录执行：

```sh
uv run wechat-agent mac-bootstrap \
  --db-root "<已核实账号的 db_storage 绝对路径>" \
  --state-dir .local/review-account/macos/bootstrap-01 \
  --timeout 180 \
  --output .local/review-account/acceptance/mac/bootstrap-result-01.json
```

该步骤自动复制并重签私有临时微信副本，用 Apple LLDB 尝试捕获目标数据库密钥，并验证匹配关系。取钥期间使用者需要在临时窗口中完成登录、手机确认及系统授权；按实际需要打开测试会话，使相关库被访问。脚本不代替用户扫码、处理登录或操作账号安全提示。

成功捕获后，主要文件如下：

```text
.local/review-account/macos/bootstrap-01/
  keys.json       # 私有逐库密钥，不应公开或发送给评审者
  bootstrap.json  # 初始化、原版校验及恢复记录
  capture.jsonl   # 私有调试记录
```

结束时脚本只清理自己创建的临时进程，禁用临时副本，并在原版校验通过后请求启动原版微信。确认原版恢复并登录同一账号后，再继续绑定。原版签名不应被改写；不需要关闭 SIP，也不要使用 sudo 绕过权限。

`keys.json` 存在或输出 `captured_requires_connect_validation` 只表示捕获阶段有产物，不保证每个库都有可用密钥。**必须完成后续真实读取校验**；新创建的媒体库也不会在普通运行中自动补钥。临时副本初始化有超时和工具链限制，不能承诺任意版本都能取钥。

如果遇到副本数据访问权限问题，按系统提示为该副本授权后，才考虑 `--resume-prepared`。该选项要求沿用同一份已校验、尚无 `keys.json` 的准备记录和副本，不重新复制或重签：

```sh
uv run wechat-agent mac-bootstrap \
  --db-root "<同一账号的 db_storage 绝对路径>" \
  --state-dir .local/review-account/macos/bootstrap-01 \
  --resume-prepared \
  --prepared-app "<同一份已授权且可运行的临时副本 .app 绝对路径>" \
  --timeout 180 \
  --output .local/review-account/acceptance/mac/bootstrap-resume-result.json
```

上例是权限恢复分支，不是每次必跑的第二条命令。失败收尾可能已将副本改名为 `.disabled`，需先按私有报告核实并人工恢复原副本路径或其已授权位置，不能把 `.disabled` 路径直接作为可运行 `.app`。若同名禁用副本仍存在，程序会拒绝；已有密钥时也不支持用该选项覆盖补钥。详细恢复依据见 [Mac 初始化与历史故障记录](docs/mac-probe.md)。

### 6. 绑定账号、测试好友与独立窗口

原版微信恢复后，打开测试好友的独立聊天窗口，保持输入框为空。记录精确显示标题、窗口宽高和输入区位置；同名联系人会被拒绝。当前没有自动窗口校准向导，需使用本机辅助功能几何信息等方式核实：

- 宽高使用 macOS **逻辑点**，不是 Retina 截图像素；独立窗宽度至少360点、高度至少450点。
- `composer-top` 为输入区上边缘相对整个窗口高度的比例，允许0.45–0.88。降级发送会在该边界下方约30点点击，必须确认实际位于可输入区域。
- 已安装完整 Xcode 时，可从「Xcode → Open Developer Tool → Accessibility Inspector」查看目标窗的 AXPosition / AXSize。比例计算为 `(输入区上边缘的屏幕 Y − 窗口顶部屏幕 Y) / 窗口高度`，各值使用同一坐标系；若输入区没有可读 AX 信息，仍需人工测量并核对，不能把“未读到”当作已校准。
- `send-key` 按该微信客户端实际设置选择 `enter` 或 `cmd-enter`。
- 不直接复制他人的窗口数值；绑定后改变窗口尺寸或编辑 profile 会影响校验，需要重新核实。

将以下占位符替换为本机值：

```sh
uv run python scripts/acceptance/bind_mac.py \
  --db-root "<同一账号的 db_storage 绝对路径>" \
  --key-file .local/review-account/macos/bootstrap-01/keys.json \
  --alias review-friend \
  --wechat-id "<测试好友的明确微信号>" \
  --title "<独立聊天窗的精确显示标题>" \
  --window-mode independent \
  --send-preflight ax-window-db \
  --composer-top "<本机实测的输入区比例>" \
  --window-width "<本机实测宽度，整数点>" \
  --window-height "<本机实测高度，整数点>" \
  --send-key enter \
  --output .local/review-account/macos/profile.json
```

脚本核对本地账号、本人 username、好友微信号与唯一标题，生成新的账号代数和 profile；它不会发送消息或获取密钥，也拒绝覆盖已有 profile。首次只想验证读取时可以不填写输入参数，但真实发送仍需完整校准；本节的完整流程应填写全部参数。

再次确认 `.env` 中 `WECHAT_PROFILE`、`WECHAT_ACCOUNT_REF`、`WECHAT_ALLOWLIST` 与本次绑定一致，密钥文件在该 `DATA_DIR` 下。若切换了终端已有的环境变量，也需同步核实其覆盖值。

### 7. 验证连接、历史读取和新消息

以下检查不调用模型，也不发送微信消息：

```sh
uv run wechat-agent doctor \
  --output .local/review-account/acceptance/mac/doctor-bound.json
uv run wechat-agent connect \
  --output .local/review-account/acceptance/mac/connect.json
uv run wechat-agent probe read \
  --contact review-friend --limit 5 \
  --output .local/review-account/acceptance/mac/read-before.json
```

检查私有报告中的正文、发送者方向和消息身份。让测试好友再发一条约定的新文本，收到后再次读取：

```sh
uv run wechat-agent probe read \
  --contact review-friend --limit 5 \
  --output .local/review-account/acceptance/mac/read-after.json
```

对比确认新增消息真实出现，不把旧同文当成新来信。可连续发送两条相同文本，核对不同原生消息 ID；本人发出的消息应为 outgoing，不作为待回复入站消息。

建议先做只读观察，确认没有持续登录或原生会话错误：

```sh
uv run python scripts/acceptance/mac_stability.py \
  --duration 300 \
  --output .local/review-account/acceptance/mac/stability-readonly.json
```

该脚本不输入、不操作剪贴板、不调用模型；完成观察也不自动认定账号安全或发送验收通过。

### 8. 先验证只生成，再验证单次固定发送

确认模型 Key 已配置后，显式选择降级模式运行一轮只生成原型：

```sh
uv run wechat-agent prototype \
  --mode dry-run --duration 180 --max-replies 1 \
  --allow-degraded-mac-ui \
  --output .local/review-account/acceptance/mac/prototype-dry.json
```

在终端显示就绪之后，让白名单好友发一条**新**文本。核对原型报告和后续工作台执行记录：应实际调用模型、生成回复，但微信不收件。`--allow-degraded-mac-ui` 是对此次未做视觉复验流程的显式选择，不代表严格 G1/G2 通过。该步骤先验证基本文本链路，示例知识库可到后续工作台启用。

准备验证真实发送时，人工清空绑定窗口草稿，保持窗口、桌面及登录状态可用，先与测试好友约定一条固定测试文本。下面的 `SEND_MODE=live` 仅作用于这一条命令，不修改 `.env`：

```sh
SEND_MODE=live uv run wechat-agent probe send \
  --contact review-friend \
  --text "这是一条双方已约定的连接测试消息。" \
  --confirm-send \
  --output .local/review-account/acceptance/mac/phase-5/degraded-fixed-send.json
```

成功应为 `outcome=verified_sent`、`basis=local_db_confirmed`，并由测试好友人工确认完整收到。探针保存对应原生操作回执；退出码成功、窗口出现气泡或本地 DB 确认都不能代替对端核对。若为 unknown，先停发并按排障部分记录人工结论，不重复执行同一发送动作试图“补发”。

### 9. 验证真实模型回复并整理本机验收记录

固定发送已确认、账号仍正常登录后，再做一轮受限模型真实回复：

```sh
uv run wechat-agent prototype \
  --mode live --duration 300 --max-replies 1 \
  --allow-degraded-mac-ui \
  --output .local/review-account/acceptance/mac/phase-5/degraded-agent-live.json
```

就绪后由测试好友发一条新文本，人工核对自然回复、完整收件及登录状态。不要把 dry-run 结果或离线合成测试当成真实模型发送证据。此原型与正式工作台共用同一账本，但原型本身不自动生成正式服务要求的验收确认。

**本步仍有人工材料整理，当前没有自动录入全部验收结论的 CLI / 工作台向导。** 正式服务在 dry-run 和 live 两种模式下都检查本机验收资料。可以先打开工作台配置模型、检索知识或查看原型记录；在缺失以下资料时，其“开始运行”仍会被拒绝。

对于本节的降级模式，需在 `DATA_DIR/acceptance/mac/phase-5/` 保留：

| 材料 | 内容及来源 |
| --- | --- |
| `degraded-fixed-send.json` | 上一步真实固定发送命令生成的原始报告；包含当前环境/绑定上下文、`outbox_id`、`verified_sent` 和 `local_db_confirmed`，不得拿 dry-run 报告改值代替 |
| `degraded-flow.json` | 基于当前本机上下文，人工记录已授权采用降级模式、真实模型轮数和对端确认；字段要求见下表 |
| `DATA_DIR/macos/operations/<outbox_id 的 SHA256>.json` | 固定发送对应的真实原生成功回执，由应用生成；只有一份手写 passed 报告不能放行 |

可以生成一份**仅含实际环境事实、不含通过结论**的上下文文件，供人工核对和整理：

```sh
uv run python - <<'PY'
from wechat_reply_agent.adapters.wechat.mac_acceptance import context
from wechat_reply_agent.adapters.wechat.mac_profile import load_mac_profile
from wechat_reply_agent.cli import write_private
from wechat_reply_agent.config import Settings

settings = Settings()
profile = load_mac_profile(settings.wechat_profile)
target = settings.data_dir / "acceptance/mac/phase-5/context.json"
write_private(target, context(profile))
print("Current context saved; no acceptance decision was recorded.")
PY
```

实际收发均验证通过且本人接受上述降级边界后，以 `context.json` 的**顶层字段**为基础整理 `degraded-flow.json`（不是嵌套在 `context` 字段下），再按真实结果添加：

| 字段 | 何时可以记录对应值 |
| --- | --- |
| `status: "passed"` | 本机约定的读取、固定发送及真实模型收发均已核对通过 |
| `acceptance_mode: "user_authorized_degraded_flow"` | 使用者明确接受不做截图 / 空草稿 / 粘贴全文 / 遮挡复验的降级范围 |
| `user_confirmed_success: true` | 使用者人工确认该流程在本机可用 |
| `recipient_confirmed: true` | 测试好友确认实际完整收到模型回复 |
| `real_model_rounds` | 实际成功的真实模型发送轮数，整数且至少1；核对 live 原型报告和账本，不填预计轮数 |

这些字段是人工验收事实，不能为跳过错误提前填 true / passed。固定发送与流程报告中的平台、来源 revision、微信 / 系统版本、窗口模式、profile 指纹和源库指纹必须匹配；若资料与当前绑定不符，应重新核实原始证据，不能手改指纹放行。新增语音库仅在可精确重现原验收源库身份时兼容，已接受的原数据库删除或替换仍会拒绝。

整理完后可只读检查服务验收条件，不连接微信、不发送消息：

```sh
uv run python - <<'PY'
from wechat_reply_agent.cli import create_adapter
from wechat_reply_agent.config import Settings

settings = Settings()
adapter = create_adapter(settings, profile_required=True)
try:
    binding = adapter.runtime_binding()
    adapter.require_runtime_acceptance(binding)
    binding.check_sources()
    print("Local acceptance and source checks passed; no message was sent.")
finally:
    adapter.close()
PY
```

这仍不自动证明之后的客户端状态或未来稳定性。严格 `visual` 模式另需匹配的 `g1.json`、`g2.json` 及视觉 / 稳定性证据，本节降级结果不能替代，不能宣称严格视觉验收已经通过。

### 10. 启动工作台并设置知识库、人设

结束其他探针 / 原型后执行：

```sh
uv run wechat-agent serve
```

手动访问 [本地工作台](http://127.0.0.1:8765)。启动只提供 API / UI，不自动连接微信，每次重启均为 stopped / dry-run，即便 `.env` 里保存过 live。步骤如下：

1. 在「设置 → 模型连接」核对模型地址、模型名称和 Key，点击测试连接，再保存；连接测试只调用模型，不操作微信。
2. 在「回复风格」选择「小北 · 跨境产品助理」，保存推荐输入预算8192、输出预算256；日常聊天可选择「自然日常助理」。
3. 在「知识库」启用 NORTHLINE 示例知识库，先用“仅查资料”检查来源，必要时使用不发微信的“生成模拟回复”。也可导入自己的 UTF-8 TXT / Markdown。
4. 在设置中选择已绑定的 `review-friend`；“检查本机环境”只代表权限 / 依赖检查，不代表密钥、账号或本机验收一定通过。
5. 保持仅生成模式点击开始，由好友发新消息，核对执行记录及知识来源；模式不同的上下文 / 偏好隔离，不能期待 dry-run 记忆自动出现在 live。
6. 暂停 / 停止后，显式保存“微信发送”，再点击开始。人工确认窗口、空草稿和测试好友均正确，再发送新测试消息。

每次开始 / 恢复会加载每个已选好友最近50条消息，标记“连接前的消息”，仅展示和获取本地附件，不触发历史回复。默认15秒轮询、至少30秒发送间隔、每分钟最多2次，每次运行默认最多3条回复，达到上限自动停止。可在「设置 → 运行方式 → 每次运行最多回复」调整为1–100条，保存到 `.env` 的 `MAX_REPLIES_PER_RUN`；下一次开始 / 恢复时重新计数，仅生成回复也计入上限。每轮收到完整回复后再发下一轮。

### 11. 用三轮消息验证核心功能

以下资料是虚构演示知识，不应当作真实产品承诺；回复不要求逐字一致：

| 轮次 | 白名单测试好友发送 | 主要核对点 |
| --- | --- | --- |
| 1 | 最近准备露营有点忙。T7在海拔2200米那次实测，用了多少水、出了多少咖啡？ | 语气自然，依据知识回答52mL、31±2g，说明是特定条件实测；工作台记录真实知识来源 |
| 2 | 刚才那次的水温和粉量呢？ | 承接上一轮场景，回答92℃、16g，不要求再次重复型号和海拔 |
| 3 | 记住我的偏好：回复风格=简短，先给结论 | 联系人记忆新增对应偏好；普通聊天不会自动存为长期事实 |

随后查看会话和执行详情，核对三轮输入、输出、发送结果和来源。重新开始后核对同账号、同联系人、同模式的偏好仍保留。若需演示白名单过滤，在达到本次回复上限自动停止**之前**，由未加入白名单的授权测试账号发送一条消息，确认运行期间未触发回复。

录制方法见 [演示脚本](docs/demo-script.md)；旧脚本含另一套茶铺示例和更长流程，可按本节三轮方案精简。实际录像由使用者完成，同时核对两端收件；隐藏 Key、账号、私有路径、其他聊天和通知，剪去等待时间时如实标注。

### 12. 文件与语音验证

- 文件应先在微信本地下载完成。应用按账号目录、消息月份、文件名和可用的大小 / MD5 信息查找；支持 `(1)`、` (2)` 等自动重命名，多个候选不任意选择。
- 工作台显示“已获取到本地”后，点击“打开所在位置”可在 Finder 选中应用保存的副本，再由使用者双击打开；未成功时按钮置灰并显示原因。
- 语音需要本地媒体库中已有音频，且具有该库的有效密钥；获取成功时保存原始 `.silk`，不转写、不播放、不接多模态模型。
- “识别为语音”只代表消息类型识别，不代表理解了语音。已有文本库密钥也不代表已有 `media_*.db` 密钥；当前演示环境曾出现新语音库缺钥，必须按真实获取状态说明，不将失败列为通过。
- 运行中每轮最多检查5条附件，同一条至少间隔30秒重试。暂停 / 停止后不继续获取，但已保存副本仍可定位。历史文件也只获取本地内容，不进入模型。

### 13. 新 Mac、换账号、换版本或重新绑定

1. 停止旧服务，保留旧账号的私有目录与记录；备份时注意其中含密钥和聊天数据。
2. 新账号选择新的 `DATA_DIR`、`WECHAT_ACCOUNT_REF`、profile 和初始化目录，按本节重新取钥、绑定和验收。同步修改所有命令的输出路径及 `MAC_BRIDGE_PATH`，不要把两套账号共用一个账本。
3. 同一个账号换 Mac 也要重新核实本机数据库身份和密钥，不能假定旧机器的文件与权限仍然适用。
4. 只重新生成 profile 也会产生新账号代数并改变指纹，已有账本 / 验收资料可能不再匹配；不要反复重绑来排障，更不要只改账号别名、清账本指纹或复制他人的 passed 报告。
5. 微信升级、源库删除 / 替换、窗口参数变更时先停止并重新验证。允许新增特定媒体库不等于支持任意热换数据库，也不等于会自动取新密钥。

### 14. 常见问题与处理顺序

| 提示 / 现象 | 检查与处理 |
| --- | --- |
| `another_probe_running` | 同一 `DATA_DIR` 已有 serve / 探针 / 原型，先在原终端正常停止，不并发运行 |
| `quit_wechat_normally_before_bootstrap` | 原版微信仍在运行，先正常退出，再进行显式取钥 |
| `mac_bootstrap_state_exists_use_fresh_directory` | 初始化目录已有内容；保留证据，使用新目录，或仅在满足条件时显式恢复同一准备副本 |
| `mac_lldb_repair_required_see_private_report` | 调试器曾崩溃并写入停用记录；先检查 / 修复 Apple 工具链并运行合成验证，不循环重试或直接删除故障标记 |
| `mac_database_access_denied_full_disk_access_required` | 检查终端 / 相关进程的数据目录访问权限；不要用 sudo 或关闭系统保护代替授权 |
| `mac_bootstrap_required` / `mac_key_or_database_validation_failed` | 密钥缺失、权限不正确、未覆盖所需库或账号目录不匹配；核对私有报告和目标库，不仅看 keys.json 是否存在 |
| `profile_exists_refusing_overwrite` | 已有绑定，不自动覆盖；核实是否仍应使用原 profile，确需新绑定时使用独立目录并重新验收 |
| `mac_composer_calibration_required` / 窗口标题、尺寸、焦点不匹配 | 核实唯一独立窗、精确标题、逻辑点尺寸、输入区及发送键；不要猜坐标或放宽校验 |
| 环境检查可用，但开始提示 `mac_matching_degraded_acceptance_required` | 校验的是另一层：核对步骤9的本机报告、真实回执、版本与指纹，环境可用不会代替它 |
| `account_or_database_binding_changed` / `native_database_replaced` | 旧账本与当前账号 / 源库身份不同；停止并核实变化，按换账号 / 重绑定流程处理 |
| 已连接但没有自动回复旧消息 | 历史只展示；就绪后发新文本。已手动清除的同一原生消息不会被重新显示或触发回复 |
| 语音已识别但获取失败 | 检查音频是否落盘、媒体库密钥和结构是否可读；当前不自动下载语音或补钥 |
| `mac_account_security_stop_active` | 先在原版微信和手机正常恢复登录，再按下述显式恢复流程处理；重启或修改配置不会自动解除 |

发生账号安全停发时，先由本人确认原版微信已正常登录，再记录人工恢复并做只读观察：

```sh
uv run wechat-agent mac-security-reset --confirm-manual-login \
  --output .local/review-account/acceptance/mac/manual-login-reset.json
uv run python scripts/acceptance/mac_stability.py --duration 300 \
  --output .local/review-account/acceptance/mac/stability-after-reset.json
```

reset 仅记录人工结论，不登录、不发送，也不修改失败的验收报告。发送 unknown 必须另行查看实际微信及接收端，并在工作台标记已发 / 作废；CLI 示例：

```sh
# 原型 / 正式服务账本中的未决发送：同时处理应用账本和对应原生回执
uv run wechat-agent resolve --ledger \
  --outbox-id "<实际未决发送的 UUID>" --resolution sent

# probe send 产生的未决发送：不加 --ledger
uv run wechat-agent resolve \
  --outbox-id "<实际 probe 发送的 UUID>" --resolution discarded
```

`sent` / `discarded` 应按人工核实的实际结果选择，上例不是默认结论；resolve 不会重新发送。所有操作都应先结束运行中的工作线程 / 服务，避免实例锁冲突。更详细的平台实现、故障和未通过项目见 [Mac 接入记录](docs/mac-probe.md)，日常界面操作见 [工作台指南](docs/workbench-guide.md)。

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

测试默认每 15 秒读取、至少 30 秒发送间隔、每分钟至多 2 次，单次默认最多 3 条后自动停止。`MAX_REPLIES_PER_RUN` 可设为1–100；原型命令的 `--max-replies` 可仅覆盖本次运行，省略时使用配置值。先发一条，收到回复再进行下一轮。Ctrl+C 停止；不确定发送在 SQLite 里保留 unknown，重启拒绝继续，人工核实后用 `resolve --ledger --outbox-id <id> --resolution sent或discarded` 记录，不会重新发送。probe 的未知回执使用相同命令但不加 `--ledger`。

原型启动重新建基线，不补发旧历史；上下文按账号代数/会话/运行模式隔离。模型调用不执行工具，失败不自动发送替代话术。正式服务复用同一个 `prototype.sqlite3` 账本并自动迁移，不建立第二份历史。
Mac 每次开始/恢复会把每个已选好友最近50条消息以「连接前的消息」载入工作台，支持查看和获取本地附件，不触发历史回复。

旧 scripts/probes/windows_read.py 使用 wxauto4，旧 Mac doctor/probe 使用 AX；均保留作研究参考，不作为当前 Windows 路线的安装或验收入口。

## 本地工作台（Phase 3–4、6–7）

工作台现已升级为 **Reply Studio**：工作概览、会话与记录、知识库、联系人记忆和分组设置。
首次使用步骤、内置示例、模拟回复和记录清除见 [工作台使用指南](docs/workbench-guide.md)。

构建产物已随源码保存，安装 Python 依赖后无需 Node 服务即可运行：

~~~sh
uv sync --locked --extra windows
uv run wechat-agent serve
~~~

如果提示 `uv: command not found`，在项目根目录改用 `./.local/tooling/bin/uv run wechat-agent serve`。
更新代码后请先在原终端 Ctrl+C，再启动新版服务并刷新页面。

手动访问 `http://127.0.0.1:8765`。服务不打开浏览器，不连接微信，worker 初始 stopped，发送模式每次启动强制 dry-run；本次运行覆盖值的配置来源显示 session。设置页显式保存 live 后，再点击开始才会真实运行。`--host` 仅接受回环地址，`--port` 可更改端口。服务与探针共用 DATA_DIR 单实例锁。Ctrl+C 会停止并等待工作线程退出。

Mac 改用 `uv sync --locked --extra mac`，独立安装 SQLCipher、构建 Swift 桥，并配置 `WECHAT_ADAPTER=mac_db`；完整步骤见本文 [macOS 全链路设置](#macos-全链路设置)，平台实现与历史记录见 [Mac 初始化](docs/mac-probe.md)。安装后使用相同 `serve`，平台原生依赖不混装。

- **概览**：实际平台/基座、降级能力、运行/连接状态、模式、启停、Agent 时间线及发送/人工处理。显示本次已回复数与当前上限，提供设置入口；每次开始/恢复默认最多 3 条，可在设置调整为1–100条。需要模型 Key、绑定白名单与 10 秒以上轮询。Windows 要求本机匹配 G1/G2（v4 另需既有匹配账本）；Mac 视觉模式要求严格 G1/G2，显式降级模式要求本机匹配且用户接受的 Phase 5 降级报告及原生回执。
- **会话**：按账号代数和发送模式隔离的会话、分页消息、基线/过滤/处理状态。回复及其输入引用在概览时间线中查看。
- **设置**：校验后原子替换 `.env`，环境变量仍优先，密钥仅返回 configured 状态。空密钥保留，显式清除才删除；DATA_DIR、监听地址/端口与适配器需重启 CLI 修改。运行中不可保存设置，暂停后可保存并重新建立基线。
- **知识库**：按业务新建、启用/停用知识库，导入/预览/移除 UTF-8 TXT/Markdown；内置虚构的 NORTHLINE 北线咖啡跨境电商资料（产品、内部实测、仓储物流与售后）。右侧可检索原文，或调用已配置模型生成不发送微信的模拟回复。最多20个知识库，共200份/8 MB资料，单份48,000字节。
- **联系人记忆**：按账号、运行模式、联系人分别查看、添加、更正和忘记长期偏好；每位联系人最多20条。修改知识或更正/忘记偏好时清除相应短期上下文。
- **记录清除**：会话页可清除当前会话或全部本地记录，设置中也有数据管理入口；需先暂停/停止并输入“清除”确认，可选同时忘记偏好。会清掉可读正文和旧上下文，保留去重/游标/绑定/发送时间；不删除微信消息或知识库，存在未决发送时拒绝清除。
- **诊断**：显式只读环境/能力检查，不取钥、不热激活；点击开始才执行实际初始化。环境可用不等于已连接。

暂停/停止会废弃迟到模型结果，等待当前调用结束；已经进入发送动作的调用会先落下结果。恢复与重启均不消费旧队列。崩溃中 sending 转 unknown，pending 转 paused，人工核对并标已发/作废后才可再次运行；此操作不重发。账号、原生数据库文件身份或应用账本被替换时拒绝继续，需要人工核实并重新绑定，不能只改账号别名。

`RETENTION_DAYS` 在显式开始时清理过期平台缓存：Windows 为 Replica 密钥/快照/校准缓存，Mac 仅诊断缓存。Mac 密钥/原生回执、账本身份、去重、上下文、绑定和验收报告不会自动删除。首次迁移核对既有账号/代数，固定当前绑定和原生源库；保留 Windows 原指纹，不跨账号复用账本。清理或备份私有数据前须停止服务。

长期偏好只接受整条明确指令，例如“记住我的偏好：饮品=乌龙茶”“更正我的偏好：饮品=白茶”“忘记我的偏好：饮品”。普通陈述不自动保存。偏好按账号代数、账号、发送模式及联系人隔离；成功生成回复且运行代数仍有效时与 outbox 同事务保存，模型失败/暂停丢弃不写入。dry-run 与 live 记忆分开，发送 unknown 不自动撤销已经保存的偏好。

知识来自手动导入文件及可选择启用的虚构示例；检索命中和本联系人偏好会连同消息发送给已配置模型。每轮最多3个300字摘录，窗口根据问题词定位，受同一输入预算约束。来源始终记录在执行详情，默认不附到微信正文，可在设置中开启。无匹配资料时要求自然说明不确定，不编造。设置提供「自然日常助理」「小北 · 跨境产品助理」完整提示词预设和模型连接测试，实际模型效果仍待用户核对。

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

本期不提供群聊、多账号并发、朋友圈、批量营销、全量历史导入或长期无人值守承诺。Phase 8 未选择：订单/工单工具、PDF/DOCX 分析和语音识别均不纳入，不显示入口。

已单独支持 Windows/Mac 本地附件基础能力：监听期间收到的文件和语音保留独立类型；
只查找微信已下载的本地文件、提取已落盘语音，不主动下载、播放或转写。工作台「会话」
显示获取状态，获取成功后可点击「打开所在位置」，在 Explorer/Finder 中定位应用保存的副本。
LLM 仍只回复文本，附件内容和原始 XML 不进入模型。详细限制见[工作台指南](docs/workbench-guide.md#本地文件与语音)。

## 离线回放与源码交付（Phase 9）

```sh
uv run wechat-agent replay --suite all --output .local/acceptance/offline/phase-9/replay.json
uv run wechat-agent verify --output .local/acceptance/offline/phase-9/verify.json
uv run wechat-agent package --draft --output dist/submission/wechat-reply-agent-source-draft.zip
```

回放使用正式运行服务和合成 adapter/model，不访问微信或远程模型。源码草稿包含两平台基座来源、锁文件、前端构建、合成知识样例、完整许可与脱敏摘要；按允许目录归档并生成逐文件 SHA256，排除私有目录、环境、数据库、缓存与微信客户端。`--draft` 明确表示人工验收及录像尚未齐备。

用户按 [最终验收清单](docs/delivery-checklist.md) 完成两平台实测，并按 [3–5 分钟脚本](docs/demo-script.md) 录制、播放和检查真实视频后，可执行 `package --video /absolute/path/real-demo.mp4`。默认正式打包会检查公开摘要中的人工项及实际可解析视频，缺项拒绝。只打本地包，不上传或发布；当前不标整个应用最终完成。

## 许可证

原创应用代码采用 [PolyForm Noncommercial License 1.0.0](LICENSE)，属于公开源码、非商业许可项目。未授予商业部署、付费产品集成、收费服务或其他商业用途许可；免费提供的商业服务也不自动成为非商业用途。商业使用须另行取得相关权利人的书面许可，具体以许可证正文为准。

内置的 wechatauto-replica 保留 Apache-2.0，已有第三方改编代码与依赖保留原许可证；本项目不能收回第三方原有许可权利。来源、采用状态和补丁见 [复用登记](docs/reuse-register.md) 与 [第三方声明](THIRD_PARTY_NOTICES.md)。

本项目面向本人授权账号与测试对象的个人研究和辅助工作流，不提供诈骗、骚扰、垃圾营销或未经授权获取信息的支持。用途说明不修改标准 LICENSE 条款，公开源码不代表微信官方授权。
