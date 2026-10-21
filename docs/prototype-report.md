# Phase 1 / G1 原型报告

本文保留旧 Mac AX/视觉与无 OCR 路线的历史事实，不作为当前验收步骤。当前按 [主计划 v4](wechat-agent-plan.md) 内化 wechatauto-replica，已允许基座的数据库取钥、UIA 运行时标志写入与 OCR。新 Windows G1 见 [接入说明](windows-probe.md)；旧测试结果不迁移为新基座通过。

日期：2026-10-21（Asia/Shanghai）。**G1 未验收，Phase 1 blocked。** 当前有可执行候选代码和离线证据，不代表微信已可接入。授权为自动执行 Phase 1–3；计划要求 G1→G2 顺序通过，当前不得进入 Phase 2/3。

## 交付与选择

- 最终包内实现 Settings、不可变事件/会话/发送契约、协议、FakeAdapter、MacAXAdapter、doctor/read/send CLI。
- 审阅 A 的发送/布局实现后，先提供 B 的薄层 AX 候选供 G1：可以精确寻找会话标题、消息列表和输入框，并通过 AX 写入文本，减少校准坐标的需求。**这只是原型尝试，尚无证据证明 AX 比视觉更准确/更快，默认方案/profile 的最终落定留给 G1/G2。** 若 AX 不可用，停发并记录，不静默变成坐标点击。
- 不自动打开或激活微信，不搜索/滚动/切换聊天，不改权限，不操作剪贴板，不启动 Agent/模型/UI。仅当前前台主窗口；用户预先选定单聊并聚焦空白输入框。
- 联系人由用户核实账号与单聊、绑定唯一别名/完整标题/本地会话 ID。重复/未知、非白名单、焦点不明、最小化、已有草稿均拒绝。标题不能证明原生身份或排除不可见的同名联系人；必须用户核实。
- 方向采用上游截图采样的保守启发式；输出 confidence 0.7 或 unknown。快照保留同文气泡不同出现序号，不宣称跨帧去重/稳定 source_message_id。
- SendResult 在 Return 尝试后始终 unknown，只有真人对端确认才提供 G1 的收件证据。JSON 回执预写 + 单探针锁，不自动重试。该阶段不提供 Phase 2 的 SQLite 已处理记录或 Phase 5 的完整 outbox 恢复。

## 自动验证事实

执行 Python 3.12.14 / macOS arm64 开发环境；macOS 具体版本和微信版本/渠道/语言由用户在 G1 报告中采集，本次未运行真实诊断。全程未启动页面、Playwright、GitNexus、真实微信 probe/worker 或子 agent。

| 检查 | 实际结果 | 边界 |
| --- | --- | --- |
| `uv sync --locked` 与 `--extra mac` | 通过 | uv 0.13.4 仅安装在忽略目录 `.local/tooling/`；未修改全局 Python |
| `uv run pytest tests/adapter -q` | **47 passed** | 合成 AX 桥、像素和临时目录，不调用真实桌面 API |
| `uv run ruff check src tests scripts` | 通过 | Python 静态检查 |
| `uv run ruff format --check src tests scripts` | 通过 | 18 个 Python 文件 |
| `uv lock --check` | 通过 | 应用/dev/mac 可选依赖锁一致 |
| `uv run wechat-agent --help` | 通过 | doctor/probe 入口可用，无桌面调用 |
| Mac extra 导入/符号检查 | 通过 | 只 import + hasattr，未调用原生 API；不是权限或适配实测 |
| `uv build` 与归档清单检查 | 通过 | wheel/sdist；应用与 MIT notice 存在，无 `.env`/`.local` 私有数据 |

本机离线 JUnit 证据：`.local/acceptance/phase-1/pytest.xml`。本机统一报告：`.local/acceptance/phase-1/report.json`。两者 Git 忽略；公开本页只保存脱敏事实。

主要覆盖：默认 dry-run/空名单、环境优先级、非法名单/profile、未知身份拒绝 SendIntent、重复映射、完整事件字段、连续同文两个出现记录、权限不可用诊断、窗口/会话/焦点/草稿防护、写入后的竞态停发、按键异常 unknown 且不重试、原子报告保存失败不覆盖旧结果、0600/0700 权限、实例锁、日志/异常脱敏、懒加载原生模块和非 Mac 环境诊断分支。

## G1 用户必验清单

下表为旧 Mac AX 用例，原命令保留在版本历史中。当前 Replica G1 以 [Windows 接入说明](windows-probe.md) 为准。原始联系人/消息/截图只留本机，公开仅保留脱敏摘要。

| 用例 | 前置/操作 | 通过标准 | 当前结果 |
| --- | --- | --- | --- |
| P01-01 | 合成事件/身份测试 | 字段齐全、未知身份不可发送 | passed（自动） |
| P01-02 | 用户填写 profile，执行 doctor；检查无权限/未运行分支 | 环境准确；无权限只诊断，不发送、不改设置 | 离线分支通过；实机 not_tested |
| P01-03 | 两联系人各发 5 条，含连续同文；手动逐个打开后 read；核对本人消息 | 会话、顺序、出现次数和每条方向正确 | not_tested |
| P01-04 | 先 dry-run；live 对 A/B 各发 1 条；额外验证错会话/无焦点/草稿/最小化 | 两位真人收件确认正确对象；不确定情形拒绝；unknown 不自动重试 | not_tested |

记录字段：macOS 版本、CPU、微信准确版本、官网/App Store、界面语言、profile 名称、窗口/解锁条件、两位测试联系人可用性、第二版本环境是否存在、日期、用例编号/实际结果/证据引用。第二版本此阶段只采集可用性，不要求安装或降级。

**失败出口**：发生错对象/非白名单发送即停止，改回 dry-run/空名单；方向不可靠或找不到 AX 控件时保持 blocked，提交脱敏错误/版本信息。按计划同一问题最多两轮证据修正，仍失败才讨论视觉备选。不得把低置信度、mock、正常退出码或单纯按回车当作 G1 passed。

**解除阻塞**：用户完成 P01-02 实机项、P01-03/04，提供脱敏证据并确认 G1；随后按保留的 auto_until 1–3 授权执行 Phase 2，G2 通过后才实施 Phase 3。无需再次授权这些范围内的开发。

## 真实接入补记：AX 不可用，转只读视觉诊断

用户更新分工后已由助手执行真实只读诊断和探针，用户亲自登录/切换微信。环境 macOS 27.0.1 / arm64 / 微信 4.1.5（31960）；所需权限已具备，桌面解锁。微信前台时触发的读取返回 `ax_control_missing_or_ambiguous`，未读到消息、未发送内容。

定向 AX 结构检查只有 5 个节点：一个窗口、三个按钮、一个 group；无会话列表、消息列表或输入框。微信公开的 AXEnhancedUserInterface 虽标为可写，但启用请求返回 -25208，前后保持 false；未改系统权限。该版本 AX 候选当前不可用，不标支持，也不继续猜 AX 识别符。

按原计划验证 A 的本地 Vision OCR 备选：新增只读 `vision_diagnostic.py`、`scripts/probes/vision_read.py` 和 mac Vision extra。截图只驻内存，先严格匹配窗口顶部目标标题，公开日志只输出数量/错误；本地报告只保存标题右侧内容候选，排除侧栏、标题与底部输入区。OCR 行不冒充规范化消息，不判断方向、不具备发送能力。没有有效截图或标题时拒绝，不从坐标猜发。

当前 56 项离线测试通过；另以合成图片验证了真实 Apple Vision OCR。私有 AX 结构证据 `.local/acceptance/phase-1/ax-{structure,enhanced-structure}.json`，前台等待/读取状态另存本地 JSON。G1 P01-03/04 仍未通过，视觉诊断结果只能决定后续适配，不替代收发验收。

## 无 OCR 路线核查（用户新增偏好）

已停止视觉等待任务，暂不继续 OCR 采样。对当前客户端进行只读元信息检查：主窗口仍只有 5 个 AX 节点；另外检查 13 个同应用包内辅助进程，未发现暴露的 AX 窗口。应用包没有发现 `.sdef` 脚本字典，Info.plist 没有 NSAppleScriptEnabled/OSAScriptingDefinition 声明，因此没有发现可直接调用的聊天 AppleScript 对象接口，不能声称微信支持 `get messages` 一类命令。

应用菜单能读取到 Copy / Select All / Paste，但观察时均 disabled。剪贴板提取原始文本仍有验证价值；尚未测试它能否复制消息、保留联系人/方向/消息边界或支持可靠增量。快捷键/鼠标注入能够承担操作动作，不代表可以识别正确会话或可靠读取消息。

Computer use 可通过截图/可访问文本作观察，再执行点击、键盘操作。原生 AX 缺失时，视觉模型仍需从图像理解微信内容，不能被当作结构化、无视觉识字的消息接口。可辅助开发定位/临时操作，不据此承诺长期无人值守接入。

下一候选是当前 Mac 的复制/剪贴板取文可行性；若失败，再比较 Windows UI Automation（需改变纯 Mac worker 形态）或数据库读取（会改变原计划不读聊天数据库/不读进程内存/不 Hook 的边界）。这些仅研究比较，未安装 Windows、降级微信、读取数据库/进程内存或发送消息。私有脱敏结构化结果见 `.local/acceptance/phase-1/non-ocr-investigation.json`。

参考：[Apple UI scripting](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/AutomatetheUserInterface.html)、[OpenAI computer use](https://developers.openai.com/api/docs/guides/tools-computer-use)、[Windows wxauto 环境与技术边界](https://docs.wxauto.org/docs/install.html)、[同类 Mac AX 收缩问题](https://github.com/huj28-creator/wechat-fastbridge/issues/1)。外部项目能力描述不代表本项目已验证。
