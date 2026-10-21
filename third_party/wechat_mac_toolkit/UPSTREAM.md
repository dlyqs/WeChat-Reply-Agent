# WeChat Mac toolkit

Source: https://gist.github.com/acmerfight/0a01249ef72970d07a2603dbb629e80f
Revision: `c98dbb10cf23c30e83d5d744905101b0880887a0` (2026-10-20).
License: MIT, copyright 2026 Contributors; complete original LICENSE retained.
`upstream-files.json` contains original UTF-8 byte hashes and immutable source URLs.
The cached public GitHub API response identified that exact revision; byte lengths
were checked against its file metadata before import. No agent playbook imported.

Selected files: SQLCipher ctypes reader and WAL inspection, structured message Reader, temporary-copy
bootstrap and LLDB capture, Swift capture/send helpers, upstream build script.
`send_verified.py` was reviewed as a reference; application receipts and independent
DB verification are implemented in the application, not delegated to that script.

Local patches:

- Reader uses `zstandard` on Python 3.12/3.13 (bounded decompression).
- SQLCipher loading also verifies `cipher_version` rather than accepting plain SQLite.
- Reader queries run on active read-only SQLCipher connections, including committed WAL;
  no decrypted snapshot fallback and no writes to the source chat database.
- Swift sender requires the pinned process, frontmost unobscured main window and fresh
  frames. It checks exact header/composer text instead of deleting spaces or applying
  compatibility normalization. It rechecks target, draft, geometry and focus at dispatch.
- Temporary-copy bootstrap bounds child lifetime and records restoration on all exits.

Application limits: Phase 5 only, manually selected single friend, <=200 Python
characters, single line, no control characters. OCR must reproduce the full draft
exactly; unsupported glyphs/layouts are refused. No target navigation claimed.
Only an independent new exact self-sent database record can confirm a send.
Upstream UI/already-sent reports are never delivery evidence.

Observed runtime blocker: Apple LLDB 1703 CreateTarget crashes in Mach-O symbol
parsing on the current macOS 27 host, including a system true target. Application
bootstrap records the crash, restores the original app and blocks repeated
initialization until developer tools are repaired. No key extraction or native
sending compatibility is claimed.
