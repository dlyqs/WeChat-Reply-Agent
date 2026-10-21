# WeChat Reply Agent

基于 wechatauto-replica 的个人微信 AI 回复应用。目标是在固定 Windows 环境中完成“测试好友发消息 → Agent 处理 → 微信回复”，并提供本地工作台、知识检索、联系人记忆和真实演示视频。

当前已内置固定 Replica 基座，Windows 微信 4.1.15.56 已完成 G1 固定收发验收。最小 LangGraph、DeepSeek 兼容客户端和 SQLite 原型账本已实现，真实三轮 G2 已通过（含上下文追问）；测试 worker 已自动停止。工作台、知识/长期记忆和最终应用尚未完成。

执行顺序、阶段状态及完成条件见 [执行计划](docs/wechat-agent-plan.md)，当前代码事实见 [开发入口](docs/overview.md)。

## 技术路线与运行范围

| 部分 | 方案 |
| --- | --- |
| 微信基座 | [wechatauto-replica 1.2.7.0](https://github.com/fanyuantaier/wechatauto-replica/tree/d322c4a9b1124228820bab363e5676016f188fc6)，固定源码快照，已作为 third_party 本地 path 依赖内置 |
| 消息读取 | 基座的本地数据库解密/WAL 读取，按其实现读取微信进程中的密钥材料并缓存 |
| 回复发送 | 基座 UIA 优先、坐标/OCR fallback、剪贴板粘贴与回车；允许其 UIA 热激活运行时标志写入 |
| Agent | LangGraph、可配置模型/人设、多轮上下文、知识检索与按联系人隔离的记忆 |
| 应用 | Python 3.12、FastAPI、SQLite、React/TypeScript/Vite；API/UI 不直接调用第三方 GUI 方法 |
| 环境 | 一台 Windows 10/11 x64 电脑、一个账号和测试好友单聊；固定微信版本、保持桌面解锁与窗口可见 |
| 节奏 | 默认 15 秒轮询，可配置；不要求实时、多系统、多版本或全天候运行 |

微信 4.1.15.53 为上游记录的测试组合，可优先验证；本项目本次实际验证的是 4.1.15.56，不要求为适配擅自覆盖当前客户端或聊天数据。OCR 已允许使用，不再强制关闭。详细初始化步骤和 G1 用例见 [Windows 接入](docs/windows-probe.md)。

## 集成与当前可用内容

已实现的原型链路为：ReplicaAdapter → 身份/白名单过滤 → SQLite inbox → 会话队列 → Agent → outbox → 基座发送 → 回读/人工核对。应用单独管理游标、状态和失败，不把模型与发送直接放进可自动重试的监听回调。

现有代码可运行离线检查：

~~~sh
uv sync --locked --extra windows
uv run pytest tests/adapter -q
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
uv run wechat-agent probe send --contact test-a --text "测试回复" --confirm-send
uv run wechat-agent prototype --mode dry-run --duration 120 --max-replies 3
~~~

复制 `.env.example` 为本机 `.env`，设置 JSON 白名单及模型密钥。绑定脚本拒绝覆盖已有 profile，也拒绝多个候选账号/联系人；已有 profile 需人工核实后处理。doctor 只读；connect 和读取探针会显式初始化原生路径，允许取钥、校准与 UIA gate。probe send 默认 dry-run；真实固定发送还需 `SEND_MODE=live` 和 `--confirm-send`。prototype live 使用显式 `--mode live`，且必须先有 v4 Replica G1 passed 报告。

测试默认每 15 秒读取、至少 30 秒发送间隔、每分钟至多 2 次，单次最多 3 条后自动停止。先发一条，收到回复再进行下一轮。Ctrl+C 停止；不确定发送在 SQLite 里保留 unknown，重启拒绝继续，人工核实后用 `resolve --ledger --outbox-id <id> --resolution sent或discarded` 记录，不会重新发送。probe 的未知回执使用相同命令但不加 `--ledger`。

原型启动重新建基线，不补发旧历史；上下文按账号代数/会话/运行模式隔离。模型调用不执行工具，失败不自动发送替代话术。正式迁移/服务控制归 Phase 3，`serve` 尚未实现。

旧 scripts/probes/windows_read.py 使用 wxauto4，旧 Mac doctor/probe 使用 AX；均保留作研究参考，不作为当前 Windows 路线的安装或验收入口。

## 使用与数据边界

默认 dry-run、空白名单和停止状态。只在明确绑定的测试账号/好友上开启 live；有既存草稿、焦点/会话无法确认或发送结果 unknown 时暂停，不自动重发。基座回读仅证明本地出现发出记录，对端收件仍需核对。

安装、依赖与终端操作由助手完成；用户负责微信客户端、手机登录、测试消息、收件确认、界面验收和录像。前端不自行打开页面做视觉检查。

模型 Key、微信密钥、明文快照、消息/截图/校准记录仅留私有 DATA_DIR，不进入 Git、日志或公开交付。远程模型仅接收配置场景需要的输入。低频和旧版本不构成免于账号限制的保证。

本期不提供群聊、多账号并发、朋友圈、批量营销、全量历史导入或长期无人值守承诺。可选业务工具、文件/语音入口按计划选择后实现，未实现时不显示入口。

## 许可证

原创应用代码采用 [PolyForm Noncommercial License 1.0.0](LICENSE)，属于公开源码、非商业许可项目。未授予商业部署、付费产品集成、收费服务或其他商业用途许可；免费提供的商业服务也不自动成为非商业用途。商业使用须另行取得相关权利人的书面许可，具体以许可证正文为准。

内置的 wechatauto-replica 保留 Apache-2.0，已有第三方改编代码与依赖保留原许可证；本项目不能收回第三方原有许可权利。来源、采用状态和补丁见 [复用登记](docs/reuse-register.md) 与 [第三方声明](THIRD_PARTY_NOTICES.md)。

本项目面向本人授权账号与测试对象的个人研究和辅助工作流，不提供诈骗、骚扰、垃圾营销或未经授权获取信息的支持。用途说明不修改标准 LICENSE 条款，公开源码不代表微信官方授权。
