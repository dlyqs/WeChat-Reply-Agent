# 复用登记

更新：2026-10-21。固定 Replica 已内化并完成本机 Windows G1；旧 Mac/wxauto4 条目保留历史事实。阶段状态见主计划，原生证据仅在私有目录。

| 来源 | 精确版本/许可 | 审阅的文件/符号 | 采用方式与改动 | 验证范围 |
| --- | --- | --- | --- | --- |
| [wechatauto-replica](https://github.com/fanyuantaier/wechatauto-replica/tree/d322c4a9b1124228820bab363e5676016f188fc6) | 1.2.7.0 / d322c4a9b1124228820bab363e5676016f188fc6 / Apache-2.0 | 完整 wechatauto 包及 PNG 资源 | 已作为独立本地 path 依赖内置；严格账号/缓存、新鲜度、inclusive scan、一次发送和脱敏补丁详见 third_party/wechatauto_replica/UPSTREAM.md，原始哈希见 UPSTREAM_FILES.json | Windows 4.1.15.56 G1 已验证；故障/拒绝边界为合成测试；不承诺完整 WAL 恢复或多版本 |
| [wxauto4 文档](https://docs.wxauto.org/docs/install.html) / [PyPI](https://pypi.org/project/wxauto4/41.1.7/) | 分发包 `41.1.7`；Python 3.12 x64 Windows wheel SHA256 `096a365ba71060c1af3c1f096342d5a16609452f51bcaf46e7359dd54235ebbf`；当前分发条款待安装核查，不假定沿用旧 wxauto 的许可 | 文档 `ChatInfo/GetAllMessage` 与 Message 的 `type/attr/id/content`；GitHub wxauto4 快照 `d0ae14d3e435807b4dead393af9d014529bbac78` 只有停止更新 README | 独立诊断依赖；`scripts/probes/windows_read.py` 自行编写 API 调用和目标核验，不复制或附带上游源码/二进制。15 个分发依赖及哈希见 `scripts/probes/windows-requirements.txt` | 在 Mac 仅解析 Windows 依赖与合成目标/方向测试；未安装原生包、未运行 Windows 微信，不标兼容 |
| [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0.txt) | 标准许可原文，SPDX `PolyForm-Noncommercial-1.0.0` | 完整标准条款，保留原文；增加项目 Required Notice 行 | 用于本项目原创代码；第三方原有许可不受替换，详见 THIRD_PARTY_NOTICES | 构建时核对许可表达式与归档许可文件 |
| [wechat-mac-rpa](https://github.com/wq19901103wq/wechat-mac-rpa/tree/0c129a5bb255a6640694c73fcdf178e7c3dda49b) | `0c129a5bb255a6640694c73fcdf178e7c3dda49b` / MIT，Copyright 2026 wechat-mac-rpa contributors | `src/action/message_sender.py`: `WeChatMessageSender._ensure_wechat_frontmost/_focus_input/_verify`；`src/layout/layout_parser.py`: `LayoutParser.parse/_detect_self_bubbles`；根 `LICENSE` | A 首先审阅。坐标输入、自动激活/重试、依赖主题的图像布局需要用户环境校准，初次审阅不移植发送/布局代码；AX 实测不可用后，改编 `src/ocr/vision_ocr.py` 的 Vision 请求/坐标转换至 `vision_diagnostic.py`，另审阅 `src/capture/window_capture.py`；只读 OCR 备选，不引入后台/Agent/视觉发送 | AX 实测后转向视觉可行性验证；已过合成图片的真实本地 Vision OCR，不代表微信读取或发送验收 |
| [WeChat-MCP](https://github.com/BiboyQG/WeChat-MCP/tree/5ffd0b4d80655bc5e284b3cea06a0a7b0278fa57) | `5ffd0b4d80655bc5e284b3cea06a0a7b0278fa57` / MIT，Copyright 2025 Banghao Chi | `src/wechat_mcp/wechat_accessibility.py`: `ax_get/dfs/get_current_chat_name/collect_chat_elements/axvalue_to_point/axvalue_to_size`；`fetch_messages_by_chat_utils.py`: `get_messages_list/classify_sender_for_message/count_colored_pixels`；`reply_to_messages_by_chat_utils.py`: `find_input_field/send_message`；根 `LICENSE` | 改编为 `adapters/wechat/mac_ax.py` 的 `NativeAX`、`classify_direction`、`MacAXAdapter`。保留识别符与薄层 AX/采样方式；删去激活/搜索/点击/滚动/正文日志、正文 hash 对齐和直接发键成功即视为完成的做法；增加严格唯一匹配、用户绑定、草稿/焦点/二次会话校验、懒加载、unknown 结果、遍历限制。MIT 声明见 THIRD_PARTY_NOTICES | 合成桥和像素测试、无 GUI 的构建检查；不是实机验证。B 仅作为可撤销的 G1 候选，不证明比 A 更快/更准，不冻结最终适配器 |
| Pydantic / pydantic-core | `2.14.1` / `2.50.1`，MIT | 包 API：BaseModel/Field/validators | 依赖；不可变契约、设置与 profile 校验 | pytest 真实依赖 |
| pydantic-settings / python-dotenv | `2.16.1` / `1.2.4`，MIT / BSD-3-Clause | BaseSettings/SettingsConfigDict | 依赖；环境 > .env > 默认值，不返回原始设置 | 优先级与非法配置测试 |
| PyObjC Cocoa/Quartz/ApplicationServices | `uv.lock` 精确版本；MIT | mac extra 的 AppKit/ApplicationServices/Quartz 原生桥 | 依赖；只读权限预检、AX、受控 Return；新增 Vision/CoreML 12.2.2 的 mac extra，执行本机 OCR，不调用远程服务 | 锁解析/安装检查；真实只读 doctor 已运行；AX 控件在微信 4.1.5（31960）不暴露；Vision 微信截图待采集 |
| Pillow | `uv.lock` 精确版本；HPND | ImageGrab / crop/convert/getdata | mac extra；仅内存采样，不保存截图 | 分类逻辑使用合成像素；截图/Retina 待用户 |
| pytest / Ruff / Hatchling | 精确版本见 `uv.lock`（Hatchling 为构建隔离依赖受主版本约束）；MIT / MIT / MIT | 测试、lint/format、PEP 517 构建 | 开发依赖/构建工具，不复制代码 | 离线验证及 wheel/sdist 构建 |

锁文件是应用和开发依赖精确安装版本来源，安装使用 `uv sync --locked`；Mac 原生依赖只通过 `--extra mac` 安装。uv 0.13.4 是本次离线执行工具，按工作区 `.local/tooling/` 安装，未修改全局 Python。执行 Python 3.12.14；不把具体开发机路径写入产品入口。

旧 wxauto4/Mac 条目保留实际审阅与采用事实，不再作为当前基座候选继续安装。Replica 以主计划 G1/G2 证据确认支持组合；OCR 可用，但账号/方向/会话不确定时停发，不同时启用两个发送器。内化时保留上游 Apache-2.0，不将其原有许可替换为项目非商业许可。

Phase 2 新增 LangGraph（MIT）和 HTTPX（BSD-3-Clause）依赖；DeepSeek 仅通过配置 API 调用，不复制模型权重或服务端代码。当前锁定分发包许可摘要见 [dependency-licenses.md](dependency-licenses.md)。

本次 Windows 实现使用 Python 3.12.1 和 uv 0.13.4。此前 Mac 工具安装记录是历史事实，不代表本次 Windows 安装位置。

Phase 3–4 新增 FastAPI / Starlette / Uvicorn 作为本地同源 API 和静态服务器，
不复用其示例产品代码。React / React DOM / Radix Tabs 用于工作台组件与可访问导航；
页面和运行交互为本项目原创。精确版本分别见 uv.lock 与 ui/package-lock.json；
完整新增依赖声明见 backend-api-licenses.md、frontend-licenses.md，构建产物随附声明。
