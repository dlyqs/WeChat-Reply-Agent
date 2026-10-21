# 项目开发入口

更新日期：2026-10-21（Asia/Shanghai）。阶段状态唯一来源为 [wechat-agent-plan.md](wechat-agent-plan.md)。

## 当前现实

已建立 Python 包和 Phase 1 的 AX 通道候选（在当前微信实测不暴露消息控件），正在验证本地 Vision OCR 只读备选，提供 doctor、probe read、probe send、56 项离线测试、依赖锁和构建产物。**Phase 1 因 G1 实机证据缺失而 blocked**；没有真实微信、模型或 UI 验收结论。尚无自动回复 worker、SQLite 仓储、模型客户端或前端。

用户已授权“请自动完成 phase1-3”，保存为 `auto_until` 1–3，relay off。必须依次通过 G1、G2；不跳过人工关口。Phase 2/3 等待依赖，本轮未实施。G1 的完整命令、记录方式和失败出口见 [README](../README.md) 与 [原型报告](prototype-report.md)。

## 已有代码导航

| 文件/目录 | 实际职责 |
| --- | --- |
| `src/wechat_reply_agent/cli.py` | doctor/probe；私有 JSON 原子输出、单探针锁、发送前预写回执，不开浏览器 |
| `src/wechat_reply_agent/config.py` | Phase 1 最小 Settings；环境 > .env > 默认值，dry-run/空名单默认；Phase 3 再完整实现配置契约 |
| `src/wechat_reply_agent/domain/messages.py` | ConversationRef/InboundEvent/SendIntent/SendResult/Capabilities/Health 不可变契约 |
| `src/wechat_reply_agent/adapters/wechat/base.py` | WechatAdapter 协议、稳定脱敏 AdapterError |
| `src/wechat_reply_agent/adapters/wechat/mac_ax.py` | 懒加载 NativeAX、截图方向采样、当前单聊唯一匹配与发送复核；待 G1 验证 |
| `src/wechat_reply_agent/adapters/wechat/profile.py` | 用户本地账号/单聊绑定与重复字段校验；不会将昵称伪装成原生 wxid |
| `src/wechat_reply_agent/adapters/wechat/fake.py` | 离线测试适配器；CLI 不能用 fake 冒充真实微信 |
| `src/wechat_reply_agent/observability.py` | 结构化 JSON 边界日志，无正文/昵称/凭据 |
| `src/wechat_reply_agent/adapters/wechat/vision_diagnostic.py`、`scripts/probes/vision_read.py` | 本机截图/OCR 可行性诊断，严格目标标题匹配；不判断发送方向、不发送、不是正式视觉适配器 |
| `tests/adapter/` | 56 项合成桥、身份/发送守卫、配置、私有输出、故障和 CLI 测试 |
| `examples/profiles/ax-candidate.json` | 待用户填写并确认的合成 profile 模板；默认未确认 |
| `scripts/acceptance/phase1_report.py` | 私有 G1 报告初始化，不覆盖旧报告、不做桌面操作、不填写 passed |
| `pyproject.toml`、`uv.lock`、`.env.example` | Python 依赖/CLI、精确锁、最小安全配置模板；mac 依赖单独 extra |
| `docs/reuse-register.md`、`THIRD_PARTY_NOTICES.md` | 精确上游快照、采用符号/修改/边界与 MIT 声明 |
| `.local/`（忽略） | 本地工具、私有 profile、收发证据、回执与报告，不能提交 |
| `dist/`（忽略） | 当前开发 wheel/sdist，不是 Phase 18 的最终提交包 |

未来模块（尚未存在）：Phase 2 `llm/runtime/routing/storage` 最小闭环；Phase 3 正式配置和身份仓储；后续 Agent/知识/记忆/附件/API/UI 按主计划依次落实。原型保留在正式包内继续扩展，不另建丢弃的系统。

## 验证与定位

离线检查入口为 `uv run pytest tests/adapter -q`、`uv run ruff check src tests scripts`、`uv run ruff format --check src tests scripts`、`uv build`；无需微信和模型 Key。自动测试不调用真实桌面 API。用户更新分工后已执行真实只读 doctor：权限可用、桌面解锁、微信未运行；前台读取因 AX 控件缺失被拒绝，无消息正文读取或发送。新增本机 Vision 只读可行性探针，合成图片 OCR 已通过。

身份失败先查 profile 的账号确认、唯一别名/完整标题和当前前台会话；读取失败查权限/AX 消息列表标题；方向由截图启发式决定，低置信/unknown 必须实测。发送前检查 dry-run、白名单、空草稿、输入焦点和再次会话匹配；按 Return 后仍是 unknown，必须核实收件。当前快照 occurrence 不是跨帧稳定 ID，没有自动去重/历史补收保证。

## 固定协作边界

不自行拉起页面、浏览器、Playwright/CUA，不使用 GitNexus，不创建新会话、worktree、子 agent。用户已更新分工：安装和终端命令由助手执行，用户负责打开微信、手机登录、界面操作及真实效果核对。真实发送先明确测试会话和授权。G1/G2 的人工结果不可用 mock 代替。

每次续做先读主计划和本入口。默认 dry-run、空白名单；真实发送只由用户显式命令启动。不得输出已有 `.env` 或私聊，公开只留脱敏摘要。每阶段代码/测试/人工结果/文档/本地 Conventional Commit 齐备才完成，不默认 push。Phase 11–14 前端只做静态/构建验证，视觉由用户验收。
