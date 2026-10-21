# Phase 7–9 交付与最终人工验收

本轮授权完成代码与助手可做的离线验证，真实微信、界面、最终录像由用户执行。
Phase 8 未选择，业务工具、PDF/DOCX、语音入口不纳入交付，不显示空入口。
阶段事实以 [执行计划](wechat-agent-plan.md) 为准；公开摘要为 [acceptance-summary.json](acceptance-summary.json)。

## 助手可自动执行

```sh
uv sync --locked --extra mac  # Windows 改为 --extra windows
uv run pytest -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run wechat-agent replay --suite all --output .local/acceptance/offline/phase-9/replay.json
uv build
uv run wechat-agent verify --output .local/acceptance/offline/phase-9/verify.json
uv run wechat-agent package --draft --output dist/submission/wechat-reply-agent-source-draft.zip
```

前端在 `ui/` 执行 `npm ci && npm run typecheck && npm run build`，无需启动页面。
`replay` 调用正式 RuntimeService、Prototype、SQLite 和 LangGraph；Windows/macOS 为合成平台契约，绝非原生收发测试。
覆盖同文合并与重复事件、本人/未知方向过滤、模型失败、unknown 重启阻断、暂停迟到结果和恢复、知识来源与记忆更新、崩溃 sending→unknown / processing→paused。

打包只读取源码允许目录，排除 `.git`、环境文件、运行目录、依赖缓存、数据库、密钥、原生二进制和临时微信副本。
包内 `delivery-manifest.json` 记录每个文件 SHA256、待验收项和草稿/正式类型；已知秘密模式扫描通过不能代替人工隐私检查。
Windows 内置基座与 Mac 参考源码、许可证、补丁记录、前端构建和合成样例均应在包中。

## 用户最终实测（两平台分别记录）

- [ ] Windows：记录系统/微信准确版本及窗口条件，重新验证原生读取、固定发送及多轮 Agent，核对对端完整收件；旧 Phase 1–4 报告保留。
- [ ] Mac：当前显式降级模式依然需要人工空草稿/窗口核对；严格视觉 G1/G2 仍未通过。补足严格证据前，不把最终双平台条件标通过。
- [ ] P07-01：导入虚构茶铺 Markdown，好友问价格/营业日，回复包含实际来源；无命中明确说明，删除后不再召回旧知识。
- [ ] P07-02：好友发送“记住我的偏好：饮品=乌龙茶”，在相同范围重启后询问；更正为白茶、忘记后分别确认。另一联系人和 dry-run / live 范围不可见。
- [ ] P07-03：分别在 Windows/Mac 核对知识导入/删除、检索、记忆查看/更正/忘记、运行中拒绝编辑及错误提示；操作均能对应后台结果。
- [ ] P07-04：按实际输入预算检查执行记录与回复；日志不含知识、记忆、聊天正文、模型密钥或完整 prompt。
- [ ] P09-02：两平台各在干净目录安装、启动 stopped / dry-run 工作台；Mac 安装 SQLCipher、构建 Swift 桥。环境不借用开发机账号/密钥或绝对源码路径。
- [ ] P09-03：按 [真实录像脚本](demo-script.md) 录制并完整播放，覆盖两平台；标明实际延迟、人工准备、降级与剪辑。
- [ ] P09-04：人工检查源码包、录像和公开摘要，不含密钥、私聊、昵称、账号路径及未授权画面。

每项证据写入私有 `.local/acceptance/<windows或mac>/phase-7/`、`phase-9/`；公开摘要只填写状态/版本/脱敏结论。
未测试填 `not_tested`，失败填 `failed`，无证据不填 `passed`。视频人工确认后才更新 `video_review`；隐私检查完成后才更新 `privacy_review`。

## 从干净源码目录安装

解压源码草稿包，在 `wechat-reply-agent/` 根目录执行：

Windows x64 / Python 3.12：
```powershell
uv sync --locked --extra windows
uv run wechat-agent --help
uv run wechat-agent serve
```

macOS Apple Silicon / Python 3.12 或 3.13：
```sh
brew install sqlcipher
uv sync --locked --extra mac
uv run python scripts/build_mac_bridge.py
WECHAT_ADAPTER=mac_db uv run wechat-agent serve
```

Mac 需要 Xcode Command Line Tools；Swift 桥构建只执行合成自检，不自动取钥/登录/发消息。详见 [Mac 接入](mac-probe.md) 和 [Windows 接入](windows-probe.md)。
可复用 `scripts/acceptance/phase6_install_check.py --archive dist/wechat_reply_agent-0.1.0.tar.gz --output <全新私有目录>` 自动检查当前平台锁定安装、原生桥构建与 stopped HTTP；新 Phase 9 wrapper 见 `scripts/acceptance/phase9_install_check.py`。
Phase 9 同样接受实际源码 ZIP：`uv run python scripts/acceptance/phase9_install_check.py --archive dist/submission/wechat-reply-agent-source-draft.zip --output .local/acceptance/mac/phase-9/source-install-new`（Windows 将证据目录改为 windows）。本机 Mac 源码草稿 ZIP 已通过此检查；两平台新界面/真实回复依然待人工验收。
服务器不自动打开浏览器，用户自行打开工作台；纯 HTTP 检查不是界面人工验收。

## 最终本地打包

所有最终条件有真实证据后，在公开摘要将相应 gate 更新为 `passed`，再执行：
```sh
uv run wechat-agent verify --video /absolute/path/real-demo.mp4 --output .local/acceptance/offline/phase-9/final-verify.json
uv run wechat-agent package --video /absolute/path/real-demo.mp4 --output dist/submission/wechat-reply-agent-final.zip
```

视频媒体检查需要系统 `ffprobe`（可随 FFmpeg 安装）；缺失返回 `probe_unavailable`，不会伪造可播放结论。
`verify` 的退出码只反映源码是否齐全，完整交付以 `delivery_status=ready` 为准；`package` 默认拒绝缺人工验收/视频的正式包，`--draft` 明确允许待验收草稿。输出文件已存在时拒绝覆盖。
只生成本地包，不上传、发布或推送。即使源码和离线检查通过，也不能将当前整个应用标记最终完成。
