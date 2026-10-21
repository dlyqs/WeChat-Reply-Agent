# Third-party notices

## WeChat-MCP

Adapted AX traversal, control identifiers, message-list lookup, input writing and
screenshot direction sampling from https://github.com/BiboyQG/WeChat-MCP at
commit 5ffd0b4d80655bc5e284b3cea06a0a7b0278fa57.
Files: wechat_accessibility.py, fetch_messages_by_chat_utils.py,
reply_to_messages_by_chat_utils.py under src/wechat_mcp/.
Local implementation: src/wechat_reply_agent/adapters/wechat/mac_ax.py.
The original license follows in full.

```text
MIT License

Copyright (c) 2025 Banghao Chi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Other dependencies

Dependencies are installed separately and retain their distributed licenses.
Exact runtime/dev/mac package versions are recorded in uv.lock. See
[reuse register](docs/reuse-register.md) for scope and license classification.
wechat-mac-rpa was reviewed only; no source from it is bundled.
