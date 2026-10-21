# 项目开发入口

更新日期：2026-10-21（Asia/Shanghai）。执行规格和阶段状态唯一来源为 [wechat-agent-plan.md](wechat-agent-plan.md)。

## 当前路线与交付

v4 以 wechatauto-replica 1.2.7.0 / d322c4a9b1124228820bab363e5676016f188fc6 作为微信控制基座：Windows 固定环境、数据库消息读取、UIA/坐标/OCR 混合发送。允许基座的取钥与 Qt accessibility 运行时标志写入，OCR 默认启用；不再实施旧 wxauto4 或 Mac 无 OCR 选型。

内化方式为 third_party/wechatauto_replica/ 本地依赖，加 ReplicaAdapter/Bridge；微信底层来自上游，应用负责 Agent、inbox/outbox、配置/运行状态、知识/记忆和本地工作台。固定一个账号/测试单聊，默认 15 秒轮询，不要求多系统、多版本或长期无人值守。

计划收敛为 7 阶段：1 基座/G1、2 Agent/G2、3 配置仓储与控制、4 API/工作台、5 知识记忆、6 可选工具附件、7 集成录像交付。现有自动范围仍为 1–3，实现暂停；本次仅计划修订，没有开始新阶段。Phase 1 仍 blocked，Windows 实机证据尚未回传。

## 当前已经存在的产物

已有 Python 包、不可变事件/适配器契约、Settings、日志、FakeAdapter、MacAXAdapter、旧 CLI 和独立 wxauto4 读取探针；62 项合成 adapter/probe 测试通过，已有锁/构建验证。Mac 微信 4.1.5（31960）实测未暴露消息 AX 控件。上述都是旧路线产物与证据，不代表 Replica 已导入或验收。

尚无 third_party 基座、本项目 ReplicaAdapter、模型/Agent、正式仓储/worker、API 或前端。当前 CLI 仍含 Mac/fcntl 依赖，不能直接在 Windows 充当最终应用。connect/prototype/serve 是新计划目标，尚不可执行。

| 现有文件 | 当前职责/后续处理 |
| --- | --- |
| src/wechat_reply_agent/domain/、adapters/wechat/base.py | 消息/会话/发送契约与协议，继续复用并补数据库消息身份 |
| config.py、observability.py、adapters/wechat/fake.py | 最小设置、脱敏日志和离线适配器，继续扩展 |
| cli.py、adapters/wechat/mac_ax.py、profile.py | 旧 Mac 探针与绑定；平台代码隔离后保留历史能力 |
| vision_diagnostic.py、scripts/probes/vision_read.py | 旧 OCR 可行性诊断，不作为 Replica 发送实现 |
| scripts/probes/windows_read.py、windows-requirements.* | 旧 wxauto4 独立探针，归档参考，不再安装这套依赖 |
| docs/windows-probe.md | 新 Replica Windows 接入/G1 操作顺序 |
| docs/prototype-report.md、wechat-reading-research.md | 历史事实与公开源码调研，不覆盖新计划 |
| docs/reuse-register.md、THIRD_PARTY_NOTICES.md、LICENSE | 来源、许可与拟内化基座登记 |
| .local/、dist/ | 私有数据/证据与构建产物，Git 忽略 |

计划中的模块/目录以主计划第 3 节为准，不在入口文档重复维护另一张完成表。上游补丁优先处理并列 sort_seq、本人身份、发送水位/重试、WAL 新鲜度与秘密缓存边界。

## 续做与验证

续做先核对 Windows 工作区当前提交和真实结果，再按主计划 Phase 1 内化基座。安装/终端由助手执行，微信登录/界面/收件和录像由用户核对；已有 Windows 成果不能被此 Mac 工作区的未验证状态覆盖。

现有离线入口为 uv run pytest tests/adapter -q、uv run ruff check src tests scripts、uv run ruff format --check src tests scripts、uv build。本次只修改文档，不重跑已通过的代码测试，也不新增 Windows 兼容结论。

默认 dry-run、空白名单；模型不直接调用 GUI，所有发送经持久化 outbox。对端送达由用户核对，unknown 停发且不自动重试。第三方库日志、密钥/备份、解密快照和校准资源都纳入私有存储与脱敏边界。

不自行打开网页、Playwright/CUA、GitNexus，不创建子 agent、新会话、worktree 或自动 relay。原创代码采用 PolyForm Noncommercial 1.0.0，基座保留 Apache-2.0，已有 MIT 改编声明保留。提交只记客观技术变更和验证结果，不默认 push。
