# WeChat Reply Agent

macOS 个人微信 AI 回复项目。当前交付 **Phase 1 通道候选原型**：只读诊断、当前测试单聊的可见消息读取、显式固定文本发送。尚未实现模型、自动轮询、去重持久化、管理工作台；真实微信兼容性和 G1 未验证。阶段状态见 [实施计划](docs/wechat-agent-plan.md)。

默认 `dry-run`、空白名单，不启动微信、不自动打开浏览器、不修改系统权限。使用中的微信账号由用户自己登录并核实。本地别名/会话 ID 都不是原生 wxid。

## 安装

需要 macOS 登录桌面会话、Python 3.12（支持范围 3.12–3.13）及 [uv](https://docs.astral.sh/uv/getting-started/installation/)。初始只使用 Python；Phase 1 无 Node/UI 依赖。

```sh
uv sync --locked --extra mac
cp .env.example .env
mkdir -p .local
chmod 700 .local
cp examples/profiles/ax-candidate.json .local/wechat-profile.json
chmod 600 .env .local/wechat-profile.json
uv run wechat-agent --help
```

**不要执行本页的真实探针，除非你正在本机进行 G1 测试。助手只执行离线测试。**

先用文本编辑器修改私有 profile：填写准确微信版本、发行渠道、界面语言、两位测试联系人的唯一窗口标题；自行核实是单聊及当前登录账号后，将相应 `account_confirmed`、`single_chat_confirmed` 改为 `true`。别名、标题、会话 ID 必须各自唯一，不能用群聊或含糊的同名联系人。测试时保持联系人在左侧会话列表中可见。所有字段严格匹配，不剥离尾部数字或做模糊搜索。

在 `.env` 中设置 `WECHAT_ALLOWLIST=["test-a","test-b"]`；`WECHAT_ACCOUNT_REF` 必须与 profile 相同。默认示例的 `Messages` 是上游英文消息列表标题，其他语言需要实机确认；找不到时返回 `ax_control_missing_or_ambiguous`，不会猜控件。不要仅凭通用名称猜改 profile 并试发。

配置优先级：进程环境 > `.env` > 默认值。白名单为 JSON 数组。无须模型 Key；请勿向聊天粘贴 `.env`、原始消息或截图。完整配置编辑和数据库将在通过 G1/G2 后按 Phase 3 实现。

## 用户执行 G1

完整用例与记录字段见 [原型报告](docs/prototype-report.md)。以下由用户亲自在本机操作：

1. 保持屏幕解锁、微信前台、仅一个主窗口，手动打开测试 A 的单聊。先执行只读诊断：

   ```sh
   uv run wechat-agent doctor --output .local/acceptance/phase-1/doctor.json
   ```

   诊断只使用预检 API，不弹出权限请求、不激活窗口、不读取聊天正文。`healthy` 仅表示基础权限/进程可用，不是 G1 通过。缺少 Accessibility 或屏幕录制权限时，由用户在系统设置中自行授权实际使用的终端/Python 并重新启动终端；程序不代操作。

2. 两位测试联系人各发送 5 条，包括两条连续同文；本人也发送一条。每位联系人手动切换到对应单聊后执行：

   ```sh
   uv run wechat-agent probe read --contact test-a --limit 5 --output .local/acceptance/phase-1/read-a.json
   uv run wechat-agent probe read --contact test-b --limit 5 --output .local/acceptance/phase-1/read-b.json
   ```

   **每条命令前均需手动打开对应单聊**。核对文本、顺序、重复同文的两个出现记录、方向。读取仅当前可见快照，不滚动、不补全历史、不承诺跨帧稳定 ID。方向来自截图采样启发式，confidence 0.7，必须人工逐条核实；对称/缺失坐标标为 unknown。系统、附件、混合内容不作为本原型的自动回复输入。

3. 先保持 `.env` 的 `SEND_MODE=dry-run`，在目标聊天空白输入框点击聚焦后验证不发出：

   ```sh
   uv run wechat-agent probe send --contact test-a --text 'G1 固定测试回复 A' --confirm-send
   ```

   预期 `not_sent`，无文字写入。真实测试时，由用户把 `.env` 改为 `SEND_MODE=live`，分别打开、聚焦 A/B 单聊的空输入框，每位执行一次明确固定回复：

   ```sh
   uv run wechat-agent probe send --contact test-a --text 'G1 固定测试回复 A' --confirm-send --output .local/acceptance/phase-1/send-a.json
   uv run wechat-agent probe send --contact test-b --text 'G1 固定测试回复 B' --confirm-send --output .local/acceptance/phase-1/send-b.json
   ```

   不要连续粘贴执行两条命令；每条命令前单独手动打开对应会话并聚焦。**程序不自动激活/点击输入框**，在终端切换回来后微信通常失去前台。可在自己的终端以延迟方式安排单条命令，随后在延迟内手动回到目标微信单聊，例如：

   ```sh
   sleep 5 && uv run wechat-agent probe send --contact test-a --text 'G1 固定测试回复 A' --confirm-send
   ```

   若来不及切回，必须返回 `wechat_not_foreground` 或 `input_not_focused`，停发即符合预期；不得取消焦点校验。读取命令也可同样延迟，以便手动切回前台。

   按回车的正常结果为 **`unknown`（退出码 3）**，因为本原型不能验证对端送达；必须由两位联系人确认各自收到且对象正确。私有回执写入 `.local/probe-sends/<outbox_id>.json`，崩溃前也有预写记录。不得将退出码 3 当作可自动重试的故障；查明实际结果前不要重复发送。每条新 probe send 都是用户授权的新发送意图，当前不提供自动去重/恢复。发送回执不含正文。

4. 反例：在 B 会话执行 A 的 send、聚焦其他控件、保留原有草稿、最小化或切到其他应用。预期拒绝/不按回车。若输入后焦点/会话变化，可能留下本次测试草稿；程序保留现场，不盲目清空其他会话。已经投递给系统的键盘事件无法撤回，遇到任何对象错误立即停止测试、改回 dry-run。

5. 使用下方离线报告命令初始化报告；**它不做实机测试，也不会填入 passed**。在私有 report.json 中由用户逐项补实际结果、状态、证据路径，并注明联系方式已脱敏：

   ```sh
   uv run python scripts/acceptance/phase1_report.py
   ```

   汇总给助手时仅提供系统/架构/版本/渠道/语言、用例编号、通过/失败、脱敏错误码和失败现象。原始聊天和联系人绑定留本机。测试结束改回 `SEND_MODE=dry-run`、`WECHAT_ALLOWLIST=[]`。

## 故障与安全边界

| 错误/现象 | 处理 |
| --- | --- |
| `mac_extra_not_installed` | `uv sync --locked --extra mac`；离线环境不需要 mac extra |
| `permissions_or_app` | 用户核实权限、微信是否运行及解锁桌面；程序不自动修复 |
| `profile_missing_or_invalid` / `account_binding_unconfirmed` | 在本机核实私有 profile 和 account_ref，不用真实 wxid 冒充本地 ID |
| `contact_not_allowlisted` / `contact_binding_unconfirmed` | 用户核对测试别名和单聊绑定 |
| `ax_control_missing_or_ambiguous` | 保留脱敏环境和错误；版本可能不暴露 AX，停止，不猜坐标发消息 |
| `current_chat_mismatch` / `wechat_not_foreground` | 手动切到正确聊天；禁止绕过复核 |
| `existing_draft_preserved` / `input_not_focused` | 用户确认草稿并选择空输入框，程序不覆盖已有内容 |
| `screenshot_scale_mismatch` | Retina 坐标未验证，停读；回报环境，禁止靠猜缩放修正方向 |
| `another_probe_running` | 同数据目录仅允许一个探针；不通过换目录并发操作微信 |
| `unknown` / 退出码 3 | 人工确认对端是否收到，不自动重发 |

本候选依赖 AX 和屏幕录制，只处理前台可见单聊；不会自动导航好友、获取附件或历史。只通过显示标题绑定身份，用户必须人工排除同名联系人、账号切换和隐藏同名会话；看到一个相同标题不能证明全局身份唯一。任何账号/联系人变更后重新核实绑定。发送前的复核不能消除最后瞬间的 GUI 竞态，因此 G1 必须由测试联系人收件确认，当前不得启动无人值守 worker。

截图仅在读取时驻留内存，消息原文仅写入用户指定的本地 JSON。私有报告新目录权限 0700、文件 0600，原子写入；已有目录由用户自行核对权限。运维日志不包含原文/昵称/密钥。Phase 1 没有保留期自动清理，测试后用户自行删除不需要的本地证据，保留必要的失败记录。

## 离线开发验证

不需要微信、GUI 权限或模型 Key：

```sh
uv sync --locked
uv run pytest tests/adapter -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv build
```

测试使用合成 AX 桥和 FakeAdapter，不调用真实原生探针；FakeAdapter 不能从 CLI 冒充微信。`doctor/probe` 是本阶段可用命令，其余计划命令尚未实现。锁文件含 mac 可选依赖；真实版本支持矩阵仍为 `not_tested`。

来源与许可：[复用登记](docs/reuse-register.md)、[第三方声明](THIRD_PARTY_NOTICES.md)。当前不远程发送内容、不需要任何模型 Key。
