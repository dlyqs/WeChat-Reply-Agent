# 项目开发入口

更新：2026-10-21（Asia/Shanghai）。阶段状态和验收条件唯一来源：[执行计划](wechat-agent-plan.md)。

固定采用 wechatauto-replica 1.2.7.0 / d322c4a9b1124228820bab363e5676016f188fc6。
完整依赖包和运行资源已内化到 third_party/wechatauto_replica/，通过 Windows extra 和 uv path source 安装。
上游 Apache-2.0 许可、原始文件哈希和本地补丁均保留。原创应用继续采用根 LICENSE。

## 实际入口与模块

| 位置 | 当前职责 |
| --- | --- |
| cli.py | doctor/connect/probe read/send/resolve/prototype/serve；平台锁、私有报告和显式发送边界 |
| adapters/wechat/replica.py | 原生账号/单聊绑定、分片消息身份、方向、并列边界游标和发送三态 |
| adapters/wechat/replica_bridge.py | 唯一原生桥；进程账号核对、私有缓存/校准、一次发送及精确新记录回读 |
| adapters/wechat/replica_profile.py | 私有账号/好友 profile，不用显示昵称代替原生 username |
| agent/graph.py、llm/client.py | 最小 LangGraph、上下文预算、结构化结果和单次限时兼容模型请求 |
| storage/database.py、migrations.py、repositories.py | 正式 SQLite 迁移、事务账本、身份约束与分页读模型；prototype.py 为兼容导出 |
| runtime/service.py、worker.py | 单实例应用生命周期、唯一原生执行线程、代数/暂停/恢复/退出与只读诊断 |
| api/、ui/、web/ | 回环/同源 API、React/TypeScript 源码和内置构建产物 |
| settings_store.py | 设置来源、校验、掩码、私有暂存与原子保存 |
| runtime/prototype.py | 基线、事务轮询、过滤/合并、会话串行、低频发送、停止和不确定停发 |
| scripts/acceptance/bind_replica.py | 根据明确提供的好友微信号，唯一定位账号与联系人，写私有绑定；不发送 |
| tests/adapter、tests/prototype | 合成原生桥、上游补丁分支、账本/Agent/失败与恢复回归 |
| .local/acceptance/phase-1、phase-2 | Git 忽略的原始实机与人工核对证据，不进入公开源码包 |

当前 Windows 固定收发已经通过 G1；G2 的真实多轮结果只以主计划和私有报告为准。
旧 Mac AX/视觉诊断和 wxauto4 探针为历史研究，不再作为当前安装入口。
API、React 工作台与正式运行服务已实现；serve 同源提供内置构建产物，初始 stopped/dry-run。详见 [API 与工作台](api-workbench.md)。知识/长期记忆尚未实施，界面及真实微信状态同步待用户验收。

## 验证和运行纪律

Windows 使用 `uv sync --locked --extra windows`；不加 Windows extra 仍可执行纯逻辑测试。
`uv run pytest -q`、`uv run ruff check src tests scripts`、`uv run ruff format --check src tests scripts`、`uv build`。
源码归档包含 third_party 和运行资源；wheel 与应用源码分发的用途不同，不能单独安装主 wheel 就认为基座已带入。

默认 dry-run、空白名单，启动建立基线，不回复旧历史。测试轮询默认 15 秒，发送至少间隔 30 秒，
每分钟至多 2 次，单次最多 3 条回复；只绑定一个测试好友。这不是避免账号限制的保证。
unknown 不重试，CLI resolve 只记录人工已发/作废结果，不会重新发送。
秘密与私聊只写私有目录；日志/报告摘要没有模型正文或凭据。LangSmith tracing 在运行调用中关闭。

不自行打开页面、Playwright/CUA 或 GitNexus，不创建子 agent、新会话、worktree 或自动 relay。
本次用户明确要求 Phase 3–4；完成软件实现与自动验证后停止，不进入 Phase 5。工作台人工验收单独保留。
