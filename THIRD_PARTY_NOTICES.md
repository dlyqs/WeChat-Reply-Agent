# Third-party notices

Original project code is offered under the PolyForm Noncommercial License 1.0.0
in LICENSE. This does not replace or restrict the original licenses of the
third-party material identified below or of separately installed dependencies.
No wxauto/wxauto4 source code or binary is bundled with this project; the Windows
probe uses documented APIs through a separately installed dependency.

## wechatauto-replica

Vendored at third_party/wechatauto_replica/, version 1.2.7.0, commit
 d322c4a9b1124228820bab363e5676016f188fc6, from
https://github.com/fanyuantaier/wechatauto-replica.
The complete Apache-2.0 license is retained at
third_party/wechatauto_replica/LICENSE; original imported file hashes and local
modification statements are in UPSTREAM_FILES.json and UPSTREAM.md there.
Runtime PNG resources retain the upstream license. This project's noncommercial
license does not replace the upstream license. Dependencies retain their respective
licenses distributed in package metadata; exact versions are recorded in uv.lock.

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
wechat-mac-rpa Vision request and bounding-box handling are adapted below.

## wechat-mac-rpa

Adapted the local Vision OCR request and bounding-box conversion from
`src/ocr/vision_ocr.py` at commit
`0c129a5bb255a6640694c73fcdf178e7c3dda49b` of
https://github.com/wq19901103wq/wechat-mac-rpa.
Local implementation: `src/wechat_reply_agent/adapters/wechat/vision_diagnostic.py`.
This is a read-only feasibility diagnostic, without the upstream Agent or sender.

```text
MIT License

Copyright (c) 2026 wechat-mac-rpa contributors

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
