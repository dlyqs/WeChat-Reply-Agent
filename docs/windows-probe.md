# Replica Windows 接入与 G1

更新：2026-10-21。当前采用 [主计划 v4](wechat-agent-plan.md) 的 wechatauto-replica 基座；本文规定接入顺序，不另维护阶段状态。旧 wxauto4 和 Mac 探针保留为历史，不再作为当前安装步骤。

## 固定基座与当前事实

- 源码：fanyuantaier/wechatauto-replica，1.2.7.0，固定 SHA d322c4a9b1124228820bab363e5676016f188fc6。
- 环境：Windows 10/11 x64、Python 3.12、登录用户交互桌面。微信 4.1.15.53 是上游测试记录，必须在本机验证。
- 读取：允许基座按选定账号取钥、缓存和读取数据库/WAL；不把完整历史导入本应用。
- 发送：允许 UIA 热激活（进程中 Qt accessibility 标志写入）、坐标/OCR、窗口激活和剪贴板；OCR 默认按混合路线开启。
- 当前尚无 third_party 内置基座、ReplicaAdapter 或 Windows G1 证据；本页的新命令由 Phase 1 实现后才可执行。

## 执行顺序

安装与终端由助手在 Windows 工作区执行。先核查该工作区已有提交/证据，保留当地未提交成果；此 Mac 工作区没有的实机结果不能被假定不存在或自动覆盖。

1. 核查 Windows/CPU/Python、微信准确版本/签名/登录状态、桌面、屏幕缩放和数据位置。doctor 只读，不构造 WeChatDB/WeChatGUI，不读取密钥或修改进程。
2. 按主计划内化源码到 third_party/wechatauto_replica/，建立本地 path source、Windows extra、uv.lock、UPSTREAM.md 和必要许可。先验证导入链/资源齐备，避免启动后才缺模块。
3. 在私有 profile 绑定账号、本机数据根目录、测试好友原生 username 与显示名、本地别名 test-a。真实名称和 ID 不写入示例、公开报告或提交。
4. 显式 connect 初始化基座。输出取钥/缓存、快照、新鲜度、校准/UIA 各步骤的脱敏结果；密钥、备份、明文库和校准资料留受控 DATA_DIR，核查 Windows 当前用户 ACL。
5. 先通过 Replica 只读获取已绑定单聊的最近文本，核对发送者/方向，不调用基座全会话监听或媒体接口。
6. dry-run 验证无写入/按键；准备空白草稿与明确测试会话后执行一次带 --confirm-send 的固定回复，由对端确认。
7. 记录 plan_version=v4、foundation=replica、实际版本/路径摘要、案例状态与私有证据位置；G1 确认后再执行 Agent G2。

开发目标入口为 doctor、connect、probe read/send。当前旧 CLI 尚未适配 Windows；不能将目标命令的文档存在视为实现完成。后续 Windows 安装使用主项目锁与本地基座，不额外安装旧 scripts/probes/windows-requirements.txt。

## G1 用例与失败出口

| 用例 | 操作 | 通过依据 |
| --- | --- | --- |
| P01-01/02 | 环境检查、初始化与显式账号绑定 | doctor 无初始化副作用；connect 结果真实，账号/数据根目录吻合 |
| P01-03 | 一个好友单聊准备 5 条文本，含连续同文和本人消息 | 内容、顺序、出现次数、方向逐条正确，未知身份/方向不自动回复 |
| P01-04 | dry-run → 一次固定回复；错会话/群聊/草稿/焦点反例 | dry-run 不操作；对端确认真实回复；反例拒绝；可能已发时 unknown 不重发 |
| P01-05 | 合成同 sort_seq、跨分片、旧同文回读和坏库/旧快照错误 | 应用去重/发送确认正确，异常暴露为降级；未覆盖的 WAL 边界披露 |

UIA 不可用时可按基座混合路线使用 OCR，不能借此跳过账号/会话复核。基座初始化或 OCR 成功不能单独证明消息身份正确。窗口尺寸/缩放变化后重新校准，目标不确定停发。

若密钥、库、WAL 或 UI 路径失败，保留稳定错误与私有报告，标记 degraded/blocked；不靠增加全量导出、关闭系统保护或自动更换账号排障。若曾进入发送动作，结果无法确认则保持现场，先由对端核对，再标已发或作废。

## Agent 交接

G1 后复用同一适配器、规范化事件和私有存储。应用按间隔轮询并事务写 inbox/游标，模型消费 inbox，发送经 outbox。不要直接在基座 Listener 的重试回调中调用模型和 SendMsg。已发现的并列 sort_seq、发送者编号、旧记录回读与重试边界按主计划第 4 节验证/修复。

## 旧探针说明

scripts/probes/windows_read.py、windows-requirements.* 和 examples/profiles/windows-read-candidate.json 属于旧 wxauto4 41.1.7 路线，未经过 Windows 实测；其合成守卫测试可参考。它们不调用 Replica，不能用于本次 G1，也不应继续安装其锁文件。
