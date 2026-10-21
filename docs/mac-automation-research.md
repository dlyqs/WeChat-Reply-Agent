# Mac 微信自动化问题调研

## 本轮实测补充（2026-10-22）

已验证本机独立聊天窗为 598×640，AX 仍只有三个窗口按钮，没有可写编辑框。
官方“窗口→置顶”菜单勾选且窗口层级变为 3，功能有效；置顶前后捕获均失败。
显示器截图出现下层画面，单窗截图无帧，直接单窗流为黑画面。
用户在 Apple 系统内容选择器中选中了准确的独立窗，四个原始帧仍为黑画面；
实际 2.477 秒无声 MP4 解码也为黑画面（RGB 最大值 2）。诊断后恢复未置顶。
这些结果只描述本机组合，不归因于未经证实的客户端内部机制。

用户随后授权先以降级模式跑通流程。采用独立 AX 窗口精确标题/尺寸/焦点核验，
一次 Cmd+V、一次发送键，再用独立 DB 新增本人完整文本记录确认；跳过截图、
空草稿、输入全文及遮挡核验，明确记录 `ui_checks_degraded=true`。
自然对话固定发送收到一次，真实 LangGraph 两轮回复均经 DB 确认，用户接受并要求标通过，
worker 已停止。严格 G1/G2 及稳定性验收仍未完成；没有修改客户端、再次取钥或弱化 unknown 停发。
以下研究与原验证顺序作为历史参考保留，当前入口见 [Mac 接入](mac-probe.md)。

调研日期：2026-10-22。范围：窗口置前/持续置顶、点击输入框、中文粘贴、单次发送、截图缺失、账号安全退登，以及读取替代方案。
本轮按用户要求优先检索 GitHub、微信官方更新记录、Apple 文档/开发者论坛及直接排查报告；没有安装或运行检索到的项目，没有发送微信消息。
阶段状态仍以 [执行计划](wechat-agent-plan.md) 为准。以下区分源码事实、第三方报告、本机证据与待验证方案。

## 结论与修正

Mac 具备激活窗口、移动鼠标、点击、剪贴板粘贴和回车能力。当前阻塞主要在窗口内容核验，不能据此解释成 Mac 无法完成这些输入动作。

优先候选为：**原版微信的测试好友独立聊天窗口 → 微信自带置顶 → 校准输入框 → 单次 Cmd+V → 核验全文 → 单次 Enter → 现有数据库回读**。
它复用微信自己的窗口功能和项目已验证的读取链路；独立聊天窗口能否在本机正常截图、原生桥如何适配其布局，尚待验证。

前面把主窗口 `kCGWindowSharingState=0` 直接解释成“必须关闭设置中的某个开关”过于确定。Apple 已将 `NSWindow.SharingType.none` 标为旧机制，并明确指出它在部分共享场景仍可能影响内容；这不等于所有现代捕获方式都会失败，也不能证明用户设置页一定存在对应开关。[Apple 文档](https://developer.apple.com/documentation/appkit/nswindow/sharingtype-swift.enum/none)

此前认为“Mac 只能抬高，无法持续置顶”也需要限定：本项目当前实现只有激活和 AXRaise；**微信官方的独立聊天窗口本身支持持续置顶**。微信 4.0.5 for Mac 官方更新记录已明确列出该能力。该历史记录证明功能存在，不替代当前 4.1.15 的本机核验。[微信官方更新记录](https://weixin.qq.com/updates/mac/405)

## Windows 与 Mac 的实际差异

| 动作 | 已核对的 Windows 实现 | Mac 对应路线与当前状态 |
| --- | --- | --- |
| 置前 | Replica `bring_to_front` 使用窗口恢复、`SetWindowPos(HWND_TOPMOST)`、`SetForegroundWindow`，处理焦点限制 | `NSRunningApplication.activate` + `AXRaise` 已在本机成功；这是发送前置前，持续置顶可优先使用微信独立聊天窗自带功能 |
| 定位输入框 | UIA 能读取编辑控件；不可用时有 OCR 路径 | 本机微信 AX 仅返回窗口外壳和标准窗口按钮，缺少编辑框；需要可用图像和布局校准 |
| 输入中文 | `_paste_into` 点击取得焦点，再写剪贴板并 Ctrl+V | 系统剪贴板 + Cmd+V；项目已实现，修订后的真实粘贴尚未执行 |
| 发送 | 本项目 `send_text_once` 精确检查目标、空草稿、焦点和内容，再只按一次 Enter | 相同流程可实现；旧 Unicode 输入路径固定发送已成功，新剪贴板路径仍被截图预检拦住 |
| 确认 | 应用使用独立数据库新记录确认 | 已具备同会话新增本人完整文本回读；不以按键调用成功代替收件 |

Windows 上游源码固定于 `d322c4a9b1124228820bab363e5676016f188fc6`：
[窗口准备](https://github.com/fanyuantaier/wechatauto-replica/blob/d322c4a9b1124228820bab363e5676016f188fc6/wechatauto/guia.py)、
[点击与粘贴](https://github.com/fanyuantaier/wechatauto-replica/blob/d322c4a9b1124228820bab363e5676016f188fc6/wechatauto/uia_driver.py)。
`send_text_once` 是本项目对该版本的本地补丁，见 `third_party/wechatauto_replica/UPSTREAM.md`，不能将它误记为原始上游已有的保护。
Mac 激活接口也由 [Apple 官方文档](https://developer.apple.com/documentation/appkit/nsrunningapplication/activate(options:))说明。

## 查到的 Mac 实现：能参考什么

| 来源 | 已阅读的源码/事实 | 采用边界 |
| --- | --- | --- |
| [S7arFish/wxauto-mcp-mac](https://github.com/S7arFish/wxauto-mcp-mac/blob/9538325b3929a6c19d08889df920e9ba48352129/src/wxauto_mcp/server.py) | 激活、`set frontmost`、通过 AX 找输入框、剪贴板 Cmd+V、回车 | 证明标准输入路线已有实现；它默认搜索结果、忽略部分定位失败，发送后直接返回成功，不适合直接替换本项目回执链路 |
| [dragonking-T/wechat-controller](https://github.com/dragonking-T/wechat-controller/blob/47b6191d0af5488687f9617ab67c256804e64988/wechat_controller/input/keyboard.py) | NSPasteboard 写入正文，AppleScript `key code 9` + Command，`key code 36` 发送；鼠标使用 cliclick | 可以参考系统输入实现；README 的跨 Space 可靠性属于作者声明，仍要核对前台和实际落点 |
| [yunkai/macos-wechat-sender](https://github.com/yunkai/macos-wechat-sender/blob/main/scripts/send_wechat.py) | pyperclip 配合 pyautogui 的 Cmd+V/Return | 证明无须逐字输入中文；不能照搬其关闭子窗口、搜索后连续回车的流程 |
| [tonyshield/send-wechat-message](https://github.com/tonyshield/send-wechat-message/blob/6a649af51bf3acaa6f574008ed38ef235c490dce/scripts/focus_composer_and_set_value.sh) | 作者报告粘贴偶尔不响应，改为聚焦 AXTextArea 后写 AXValue | 可作为真实编辑控件可读写时的备用输入方案；本机 AX 树缺失时不可用。不会把读不到编辑框当成空草稿，也不会照搬清空原稿的动作 |

这些项目证明实现路径存在，不能证明当前系统/微信构建兼容，更不能证明不会触发账号限制。没有把 README 中“无法区分真人”等宣传性表述作为结论。

## 截图与 AX 缺失：与本机对应的公开证据

1. [FastBridge issue #1](https://github.com/huj28-creator/wechat-fastbridge/issues/1) 记录 macOS 26.x、微信 4.1.7.57/4.1.9.58/4.1.11.55/4.1.13：窗口只剩关闭、全屏、最小化控件，搜索、会话、标题、消息和输入框都不存在。报告者已检查权限、VoiceOver 和增强 AX 属性。它与本机现象相似，说明“授权成功”不保证微信暴露完整控件，不能据此保证 AXValue 可行。
2. [Apple 开发者论坛 thread 808016](https://developer.apple.com/forums/thread/808016) 记录 ScreenCaptureKit 初始漏掉 `NSWindowSharingNone` 窗口，切换过滤器后才可见。Apple DTS 要求提交可复现 bug，未提供通用修复承诺。现有桥已参考过滤器切换，本机后续仍有无帧/错画面的失败，不能把该技巧当成已经解决。
3. [2026-10-16 的直接排查报告](https://jiwenkang.com/posts/2026/wechat-screenshot-blank/) 针对 Mac App Store 微信 4.1.13，描述了主窗口截图空白、设置中找不到开关，而设置/媒体等其他窗口仍可见。作者提出独立聊天窗作为不改客户端的候选办法，并注明未逐一验证所有捕获工具。因此它是下一步验证方向，不能直接记为本机成功；其“服务端灰度”解释也只是推测。
4. [Apple ScreenCaptureKit 官方示例](https://developer.apple.com/documentation/screencapturekit/capturing-screen-content-in-macos) 可作为最小捕获对照；[SCContentSharingPicker](https://developer.apple.com/documentation/screencapturekit/sccontentsharingpicker) 提供系统选择捕获内容的路线。使用它仍需适配应用生命周期、授权和窗口绑定，并非按一个 API 就必然解决。

本机已记录：主窗口 sharing state 为 0，窗口截图失败，显示器截图中目标位置出现下层窗口；原生桥因此拒绝发送。该标记应保留为诊断线索，不能单独作为所有捕获后端的硬拒绝条件，也不能把截到任意非空画面当成微信截图成功。

## 安全退登：目前查明与未查明的部分

已有固定消息发送及对端收件成功的证据，之后发生了账号安全重登提示。没有可靠的对照证据能把本次退登确定归因于鼠标、Unicode 输入、剪贴板、取钥、副本登录或其他单一因素。
公开项目的成功演示及 Windows 的既有成功都不能填补这个因果缺口。

改进方向是缩小运行期间的操作范围并做可复现对照：继续复用有效密钥、只运行正常登录的原版客户端，以正常窗口操作和单次输入完成发送；每一步分别记录结果。修改客户端、注入截图补丁或再次重签不能作为本轮稳定性修复的默认方案。

本机正常重登后的 300.222 秒只读观察已完成，20 次检查，模型调用与输入事件均为 0；只说明该有限观察期间未记录到原生会话错误。新的剪贴板固定发送、发送后观察和三轮 Agent 仍未完成。人工确认持续登录与真实收件不能由窗口存在代替。

## 其他读取方案

| 方案 | 优点 | 对原任务的限制 |
| --- | --- | --- |
| 现有只读 DB/WAL，复用密钥 | 本机已验证五条新消息、连续同文、方向和去重；可确认发送的新记录 | 首次初始化与版本/分库变化需要处理；保留现有实现最有实际价值 |
| 原生 AX 读取 | 控件可用时可以取可见正文，无须数据库密钥 | 本机缺少聊天控件；可见区域、消息身份/方向仍需独立验证，不能直接替代现有消息 ID |
| 独立聊天窗 OCR | 图像可见时不依赖聊天控件树 | 本机截图可用性未验证；OCR 对连续同文、滚动和空白有歧义，适合先做界面核验 |
| 微信合并转发 + Share Extension | 使用微信主动导出的聊天归档；[WeChatBridge](https://github.com/freestylefly/WeChatBridge) 提供开源接收实现 | 用户需选消息并转发，适合人工导入/总结，不满足实时自动读取与回复 |

## 下一步验证顺序

1. 先用原版微信把已绑定测试好友打开为独立聊天窗，只验证窗口身份、截图和录屏可见性，记录其真实控件、尺寸与置顶入口；不发送。
2. 若可见，适配窗口发现、绑定、布局校准、焦点及遮挡检查，自动使用微信自带置顶。当前代码只接受主窗，不能直接拿现有主窗坐标点击独立窗。
3. 原生 dry-run 检查目标与空输入框通过，确认未修改剪贴板/草稿之后，才做一次已授权固定发送；单次粘贴、全文核验、一次回车，数据库确认及人工收件。
4. 发送后做有界只读观察并确认登录持续性；出现安全提示即停止，不循环重登或重发。通过后继续既定 G1/G2；不得用研究结论直接放行 Phase 6。
5. 独立窗也不可捕获时，用 Apple 最小示例或系统内容选择器做只读对照，将微信窗口特性与桥实现问题分开，再决定捕获后端；不继续无依据叠加截图重试。

本轮只完成检索、源码对照和文档整理。没有新增真实发送、模型轮次或验收 passed。
