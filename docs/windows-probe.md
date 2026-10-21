# Windows UI Automation 读取诊断

目标是先确认固定桌面环境下能够直接取得测试单聊文本。当前不是自动回复 worker，不能以离线测试代替真实兼容验收。

## 候选环境

Windows 10/11 x64、Python 3.12、wxauto4 41.1.7。微信候选为 4.1.8.107，依据[上游免费版文档](https://docs.wxauto.org/docs/install.html)，需先验证本人账号能正常登录。已核对 PyPI 存在对应 cp312/win_amd64 wheel；当前未在 Windows 安装或运行。

当前 `cluic/wxauto4` GitHub 树只有“停止更新”README，不能通过克隆取得与 PyPI 分发包等价的源码。旧 `cluic/wxauto` 公开实现针对 3.9.11.17，不能替代当前 4.x 分发包。采用单独安装的依赖调用其公开 API，不将其二进制或源码纳入本项目交付；后续分发仍须核对该包随附条款。

## 执行顺序

安装与终端操作由助手在具备执行访问的 Windows 环境中完成。当前 Mac 终端不能直接操作另一台尚未连接的 Windows 电脑。取得 Windows 执行访问后，在仓库根目录使用 PowerShell：

```powershell
py -3.12 -m venv .local/windows-probe/venv
& ./.local/windows-probe/venv/Scripts/python.exe -m pip install --require-hashes -r scripts/probes/windows-requirements.txt
Copy-Item examples/profiles/windows-read-candidate.json .local/windows-read-profile.json
```

助手填写私有 profile 的准确 `expected_chat_title`；使用者核实当前登录账号与唯一测试单聊后，才将两个 confirmed 字段置 true。示例没有真实联系人。用户负责打开客户端、手机登录、选定测试聊天、发送测试消息及核对结果。

```powershell
& ./.local/windows-probe/venv/Scripts/python.exe scripts/probes/windows_read.py --profile .local/windows-read-profile.json --output .local/windows-probe/read.json
```

探针只调用 `ChatInfo()` 和 `GetAllMessage()`，读取前后严格核对相同标题和 `friend` 类型，不搜索、滚动、切换会话或发送。第三方库的构造函数可能激活微信。窗口标题依赖人工绑定，不代表原生唯一身份。只返回最近已加载消息中的文本，正文仅写入忽略目录的报告；终端只输出数量/稳定错误码。Windows 文件权限继承用户目录 ACL，应在该电脑核实，Git 忽略规则不等于访问控制。

退出码 0 表示取得非空文本快照；2 表示空快照或拒绝。两者都不会将 G1 自动标为通过。发生错误时不输出原始异常，避免带出昵称或正文；没有 UIA 文本时停在诊断阶段，不启用 OCR。

## G1 演示验收

在一个已核实的测试好友单聊中准备 5 条文本，含两条连续同文和一条本人消息。核对每条内容、顺序、出现次数和方向，再核对切换聊天/群聊时拒绝输出。通过后才实现显式固定回复与模型闭环。探针没有发送函数。

消息 `id` 是 UI ID，[上游明确说明切换 UI 后会改变](https://docs.wxauto.org/docs/class/Message.html)，不能冒充微信服务端 ID 或持久增量游标。演示期间固定会话，重启/切换后重新建立基线，不自动回复既有历史；后续消费逻辑另行实现。

固定窗口位置可降低发送校准成本。优先以 UIA 获取输入框位置和会话信息，再点击、粘贴、回车；坐标 fallback 必须与校准窗口、缩放和会话绑定。发送后核对本地出现的本人消息及对端收件，结果不明时暂停，不自动重发。
