# 复用登记

更新：2026-10-21。下列 commit 是精确审阅快照，所有真实微信兼容性均 `not_tested`。研究用完整下载文件只存 Git 忽略的 `.local/research/`，应用不依赖该目录或上游完整项目。

| 来源 | 精确版本/许可 | 审阅的文件/符号 | 采用方式与改动 | 验证范围 |
| --- | --- | --- | --- | --- |
| [wechat-mac-rpa](https://github.com/wq19901103wq/wechat-mac-rpa/tree/0c129a5bb255a6640694c73fcdf178e7c3dda49b) | `0c129a5bb255a6640694c73fcdf178e7c3dda49b` / MIT，Copyright 2026 wechat-mac-rpa contributors | `src/action/message_sender.py`: `WeChatMessageSender._ensure_wechat_frontmost/_focus_input/_verify`；`src/layout/layout_parser.py`: `LayoutParser.parse/_detect_self_bubbles`；根 `LICENSE` | A 首先审阅。坐标输入、自动激活/重试、依赖主题的图像布局需要用户环境校准，本阶段不移植代码、不引入后台/Agent；只借鉴前台复核与验证输入的设计原则 | 源码审阅；没有截图或真实微信验证 |
| [WeChat-MCP](https://github.com/BiboyQG/WeChat-MCP/tree/5ffd0b4d80655bc5e284b3cea06a0a7b0278fa57) | `5ffd0b4d80655bc5e284b3cea06a0a7b0278fa57` / MIT，Copyright 2025 Banghao Chi | `src/wechat_mcp/wechat_accessibility.py`: `ax_get/dfs/get_current_chat_name/collect_chat_elements/axvalue_to_point/axvalue_to_size`；`fetch_messages_by_chat_utils.py`: `get_messages_list/classify_sender_for_message/count_colored_pixels`；`reply_to_messages_by_chat_utils.py`: `find_input_field/send_message`；根 `LICENSE` | 改编为 `adapters/wechat/mac_ax.py` 的 `NativeAX`、`classify_direction`、`MacAXAdapter`。保留识别符与薄层 AX/采样方式；删去激活/搜索/点击/滚动/正文日志、正文 hash 对齐和直接发键成功即视为完成的做法；增加严格唯一匹配、用户绑定、草稿/焦点/二次会话校验、懒加载、unknown 结果、遍历限制。MIT 声明见 THIRD_PARTY_NOTICES | 合成桥和像素测试、无 GUI 的构建检查；不是实机验证。B 仅作为可撤销的 G1 候选，不证明比 A 更快/更准，不冻结最终适配器 |
| Pydantic / pydantic-core | `2.14.1` / `2.50.1`，MIT | 包 API：BaseModel/Field/validators | 依赖；不可变契约、设置与 profile 校验 | pytest 真实依赖 |
| pydantic-settings / python-dotenv | `2.16.1` / `1.2.4`，MIT / BSD-3-Clause | BaseSettings/SettingsConfigDict | 依赖；环境 > .env > 默认值，不返回原始设置 | 优先级与非法配置测试 |
| PyObjC Cocoa/Quartz/ApplicationServices | `uv.lock` 精确版本；MIT | mac extra 的 AppKit/ApplicationServices/Quartz 原生桥 | 依赖；只读权限预检、AX、受控 Return；不在离线测试中调用桌面 API | 锁解析/安装检查；真实调用待用户 |
| Pillow | `uv.lock` 精确版本；HPND | ImageGrab / crop/convert/getdata | mac extra；仅内存采样，不保存截图 | 分类逻辑使用合成像素；截图/Retina 待用户 |
| pytest / Ruff / Hatchling | 精确版本见 `uv.lock`（Hatchling 为构建隔离依赖受主版本约束）；MIT / MIT / MIT | 测试、lint/format、PEP 517 构建 | 开发依赖/构建工具，不复制代码 | 离线验证及 wheel/sdist 构建 |

锁文件是应用和开发依赖精确安装版本来源，安装使用 `uv sync --locked`；Mac 原生依赖只通过 `--extra mac` 安装。uv 0.13.4 是本次离线执行工具，按工作区 `.local/tooling/` 安装，未修改全局 Python。执行 Python 3.12.14；不把具体开发机路径写入产品入口。

最终适配器/profile 仍须 G1/G2 证据确认。AX 控件或方向不可靠时停止，最多按计划进行两轮证据修正后再讨论视觉备选，不同时启用两个发送器。
