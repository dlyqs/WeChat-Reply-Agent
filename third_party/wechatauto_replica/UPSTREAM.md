# Vendored wechatauto-replica

Source: https://github.com/fanyuantaier/wechatauto-replica
Commit: d322c4a9b1124228820bab363e5676016f188fc6
Version: 1.2.7.0. Imported 2026-10-21. License: Apache-2.0 (LICENSE).

Imported the complete tracked `wechatauto/` package (including its three PNG runtime
assets, py.typed, compatibility modules and examples), pyproject.toml, LICENSE and
README_pypi.md. No upstream NOTICE file exists at this commit. UPSTREAM_FILES.json
records the SHA256 of every original imported file, before local changes. No .git,
account data, developer instructions or caches are part of this source snapshot.

The package remains a separate Windows-only path dependency; uv.lock resolves its
original dependency ranges. UIA, pywin32, Pillow, psutil, cryptography, winsdk,
imageio-ffmpeg, zstandard, pyautogui, OpenCV, pyperclip and colorama retain their own
licenses; installed distribution metadata contains their full terms. Runtime PNG
assets retain the upstream package license. No OCR model weights are bundled;
OCR uses Windows WinRT. App-original code has its own noncommercial license.

## Local modifications (2026-10-21)

- 2026-10-22: normalized database rows additionally retain `type_code`, so the host
  distinguishes type-49 file subtype 6 from links/cards without retaining raw XML.
  The host reuses MediaDownloader.download_voice and its file-name metadata parser;
  only already-local content is acquired into per-message private directories.

- db.py: optional strict_account requires explicit account/root/cache; disables both
  account-switching recovery methods and other-account key-cache reads; stable keys
  stay under workdir. Strict reads reject failed main snapshot/WAL merges instead of
  returning an old snapshot. Negative WAL stamps force a fresh rebuild. A failed
  shard open closes already opened connections. scan_messages_inclusive provides
  >= sort_seq scanning, deterministic shard/local-id order and fail-closed overflow.
  The host owns boundary identities and durable cursors; Listener is not used.
- logger.py: replace library-owned global handlers, stdout replacement and plaintext
  file logs with a silent host-owned logger. The host also suppresses direct native
  stdout/stderr and third-party logging inside serialized native calls.
- guia.py: allow private layout/OCR-temp directories through environment settings;
  honor ENABLE_UIA_GATE. Add send_text_once as the only app sending entry: exact
  title, empty draft, foreground/focus/content checks, one Enter, explicit attempted
  receipt and no retry/fallback after Enter. Existing permissive send_msg, click_send
  and sender_id-based confirmations are not used by the app. OCR fallback requires
  exact title/content and refuses whitespace it cannot confirm. Uncertain OCR
  conditions refuse sending; calibration is environment-specific.
- uia_driver.py: remove fallback writes to the global screen-reader setting. Qt
  accessibility gate activation remains enabled only through explicit connect.

App bridge validates the active account, process lifetime and encrypted DB identity,
uses a bound DB for readback, and requires a new shard/local-id self row with exact
full text. This confirms local DB state only. Recipient confirmation is manual.

## Limits and validation

Synthetic tests exercise the actual patched inclusive scan, strict stale/corrupt
snapshot branches and single-Enter method with native/SQLite doubles. Real fixed
read/send was exercised on Windows with WeChat 4.1.15.56; detailed private evidence
is under DATA_DIR/acceptance/phase-1. G1 status is maintained only in the plan/report.

WAL cumulative checksums, full committed-frame semantics and a general WAL recovery
engine are not implemented. Upstream page/salt checks and SQLite quick_check remain;
these are not a guarantee of lossless or perfectly fresh reads. Scan overflow,
account/process/DB identity changes and detectable snapshot errors stop the app.
No claim of multi-version compatibility or server delivery is made.
