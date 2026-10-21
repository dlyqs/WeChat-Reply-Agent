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
- An explicit native focus step activates only the pinned WeChat process and raises its
  uniquely calibrated AX main window before read-only preflight. It does not set a
  persistent floating window level, search chats, type, or affect other applications.
- Display-sized transparent Dock surfaces are excluded only when the system Dock's
  unique AX panel is verified outside the target. Intersecting panels and unknown
  layouts still block. Empty-draft checks require two fresh passing frames.
- Short headers use isolated, upscaled, language-specific OCR with no expected-word
  hints or language correction; the exact-match/confidence requirements remain.
- Message reads select only ASCII-numbered message shards; FTS/resource databases
  are not treated as chat shards. Integrity checks retain all databases actually used.
- Temporary-copy bootstrap bounds child lifetime and records restoration on all exits.
- Explicit prepared-copy resume checks pinned executable hashes and account root,
  including an authorized relocated copy, without copying or signing it again.
- Input now follows the pinned Windows adapter's clipboard-paste pattern: one Cmd+V,
  exact draft readback, one Enter. A clipboard lease restores the original only if no
  other writer has changed it; self-tests use a private named pasteboard.
- Read-only AX session checks precede polling/input. A known account-security prompt,
  when accessible through AX, produces a stable code for the application's durable
  stop. No login automation or account-security guarantees are implemented.
- The explicit `ax-window-db` mode selects one independent AX window by exact bound
  title/size, checks focused-window identity and geometry at the input boundaries,
  pastes once and presses the configured send key once. It skips screenshots, draft
  and occlusion checks; the application records degraded assurance and requires an
  additional prototype opt-in. Native key dispatch is never delivery confirmation.
- `WindowCapture.swift` and `DegradedSend.swift` are original project extensions under
  the root LICENSE. Existing upstream files and modifications retain MIT. The diagnostic
  captures display/window/direct-stream frames or a user-selected system-picker stream,
  validates exact title evidence and records a short silent video. It rejects wrong-window
  selection, empty/black or mismatching frames; no input, client modification or gate change.
- Capture backend labels match the active backend; diagnostic refresh preserves the
  selected backend. Existing diagnostic PNGs are not overwritten.

Application limits: Phase 5 only, manually selected single friend, <=200 Python
characters, single line, no control characters. OCR must reproduce the full draft
exactly; unsupported glyphs/layouts are refused. No target navigation claimed.
Only an independent new exact self-sent database record can confirm a send.
Upstream UI/already-sent reports are never delivery evidence.

Resolved runtime blocker: Apple LLDB 1703 CreateTarget crashed in Mach-O symbol
parsing on the current macOS 27 host, including a system true target. Application
bootstrap recorded the crash, restored the original app and blocked repeated
initialization until developer tools were repaired. Updated LLDB 2103 passed synthetic
capture and real local key verification. The first fixed send was DB/recipient-confirmed,
followed by an account-security logout. The clipboard revision needs native stability
acceptance; it is not evidence of avoiding account restrictions.
