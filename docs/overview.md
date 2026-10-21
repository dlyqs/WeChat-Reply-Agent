# 项目开发入口

更新日期：2026-10-21（Asia/Shanghai）

## 当前状态

这是个人微信自动回复 Agent 的新仓库。当前没有应用实现、依赖、启动命令或提交历史；只存在实施计划和本开发入口。不要把下列目标目录当成已经可用的模块，不要声称接入、UI 或模型已通过验证。

- 任务目标：macOS 上代个人微信号回复白名单好友单聊，包含 Agent 工具/知识调用、长短期记忆、本地工作台及真实测试视频。
- 当前执行入口：[wechat-agent-plan.md](wechat-agent-plan.md)，已细化为 18 阶段；除 1/2 外，旧 9 阶段编号已被新表替代。状态只以主表为准。
- 当前模式：`manual`；尚未获得计划后的实施授权，未开始 Phase 1。后续模式变化随计划同步，不在本文件复制阶段进度表。
- 主要风险：Mac 微信版本/发行渠道/语言/窗口状态影响 Accessibility 或 OCR；多版本稳定性必须通过用户实测。

## 已存在的文件

| 路径 | 实际职责 |
| --- | --- |
| `docs/wechat-agent-plan.md` | 18 阶段任务/用例、冻结的 CLI/API/数据契约、复用、人工关口与可提交包规范 |
| `docs/overview.md` | 说明当前代码现实，作为以后开发者的导航；不代替阶段计划 |

仓库中的 `.DS_Store` 是已有的本机文件，不是交付资产。Phase 1 建立 `.gitignore` 时应忽略，不把它提交到代码库。

## 目标结构（尚未创建）

技术方向为 Python 3.12 + FastAPI + LangGraph + SQLite，以及 React/TypeScript/Vite/Tailwind/shadcn/ui 本地工作台。原型通过前不建设完整 UI。计划已覆盖全部必做开发/交付，后续按阶段直接实现，不再开一轮大模块规划。

| 计划路径 | 职责/主要修改入口 |
| --- | --- |
| `src/wechat_reply_agent/cli.py` | doctor/probe/prototype/serve/replay/verify/package；最终单命令启动与交付 |
| `src/wechat_reply_agent/config.py` | 从 `.env` 加载、校验和脱敏配置，Key 只留后端 |
| `src/wechat_reply_agent/domain/` | 规范化消息、会话、方向、发送结果等共享契约 |
| `src/wechat_reply_agent/adapters/wechat/` | 用户环境验证后确定的 Mac 微信读取/发送适配器，不包含 Agent 策略 |
| `src/wechat_reply_agent/runtime/`、`routing/` | 轮询、过滤/去重、会话队列、启停、全局 GUI 锁 |
| `src/wechat_reply_agent/storage/` | SQLite schema/migrations、入站状态、发件箱与重启恢复 |
| `src/wechat_reply_agent/agent/` | LangGraph、提示词、受限工具、确认和预算 |
| `src/wechat_reply_agent/knowledge/` | 文档分块、FTS5 检索、来源和知识版本 |
| `src/wechat_reply_agent/memory/` | 上下文压缩、长期偏好事实、隔离、更正和删除 |
| `src/wechat_reply_agent/multimodal/` | 文件解析、转写事件入口和能力边界 |
| `src/wechat_reply_agent/api/`、`demo_services/` | REST/SSE、运行控制、配置/知识/记忆/分析 API、虚构订单/工单 HTTP 服务 |
| `src/wechat_reply_agent/observability/` | 统一 trace、脱敏事件、SSE 游标和实际用量 |
| `ui/src/` | Phase 11 概览、12 会话、13 知识/记忆/分析、14 设置诊断；共用 token/API 客户端 |
| `scripts/probes/`、`scripts/acceptance/` | 用户自行执行的真实接入和验收入口；助手不直接运行 |
| `tests/`、`examples/` | 不依赖微信的回放/故障测试和合成知识/业务样例 |
| `.local/` | 隐私运行目录及 `acceptance/phase-N/report.json` 证据，必须 Git 忽略 |
| `dist/submission/` | Phase 18 的可提交压缩包、实际视频、历史 bundle、脱敏摘要和校验和 |
| `docs/reuse-register.md`、`THIRD_PARTY_NOTICES.md` | 后续记录采用的上游 commit/依赖版本、文件、许可证和改动 |

实际文件出现或路径调整后，及时把本节改为真实导航，并明确尚未完成的部分，不能一直保留失真的目标目录表。

## 核心链路与常见问题定位

1. 消息链：适配器读取 → domain 事件 → routing 本地过滤/去重 → runtime 会话队列。漏消息/重复消息先定位这条链，不先改模型提示词。
2. 决策链：agent 构造上下文 → knowledge/memory 检索 → 受限 tools → 结果校验 → 回复。工具写入需要与当前会话绑定的明确确认。
3. 发送链：storage outbox → adapter 会话复核 → 全局串行发送 → 结果确认。发送结果未知时停在 `unknown`，不能盲目重发。
4. 管理链：ui → api REST/SSE → runtime/config。UI 显示真实状态、错误和模式，前端绝不持有模型 Key。
5. 数据链：短期 checkpoint 与长期事实分开；按本地账号/会话隔离，允许更正与删除。不能把 UI 识别到的昵称冒充微信原生 wxid。

目前以上是实施边界说明；对应代码将在计划各阶段落地后补上真实文件/符号。

## 维护与协作约束

- 后续每次“继续”先读计划与本文件；每完成一阶段同步两者，完成事实只写入该阶段，不在多份文件复制状态。
- 微信登录、授权、真实收发、多版本、前端视觉和录像由用户操作。助手写脚本、说明、离线测试并分析脱敏结果，不自行启动微信 probe、页面、Playwright 或浏览器自动验收。
- 不使用 GitNexus，不擅自创建新会话或多 agent。当前无需额外专用 executor skill。
- G1 微信读/发与 G2 最小 AI 闭环是正式开发前的硬关口；功能/UI 阶段自己的必验人工项必须当阶段通过，Phase 17 不负责补齐此前所有人工验收。
- 启用用户桌面会话中的 worker，默认 dry-run 和空白名单停发；GUI 接入不能只放 Docker/服务器后声称可用。
- 图形后台为亮色、低噪声、本地工作台；具体 token、页面信息结构和人工检查尺寸见计划第 7 节。
- 复用先审阅具体快照/许可证，只移植必要层；Agent 默认一套 LangGraph，不并行堆入多个完整机器人框架。
- 采用长期结构化边界日志；用 trace 定位链路，不记录 Key、原始聊天、完整 prompt 或隐藏推理；隐私证据留本机忽略目录。
- 真实提交随阶段按功能形成，遵循 Conventional Commits 并保留来源；不伪造历史、不默认 push。Phase 15 干净启动、16 离线故障回归、17 多版本实测、18 视频与提交包，后期不能还欠主功能开发。
- 阶段完成须代码、测试、必验人工证据、文档和真实提交齐备，不用空壳/mock/TODO 或“另行规划”填完成。原生语音按题目“应用思路”明确交付设计/转写入口，不冒充已支持。
