"""Read the manually selected Windows test chat once through wxauto4; never send.

Uses documented ChatInfo/GetAllMessage APIs, without copying upstream code.
The library constructor may activate WeChat. UI IDs are valid only within the
current UI lifetime; this diagnostic is not an incremental message consumer.
"""

import argparse
import contextlib
import io
import json
import logging
import os
import platform
import tempfile
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_DIR = ROOT / ".local"
WXAUTO_VERSION = "41.1.7"


class ProbeError(Exception):
    """Only stable, non-sensitive error codes cross the diagnostic boundary."""


def private_path(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(PRIVATE_DIR.resolve()):
        raise ProbeError("path_must_be_under_local")
    return resolved


def load_binding(path: Path) -> str:
    try:
        binding = json.loads(private_path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProbeError("invalid_private_profile") from exc
    if not isinstance(binding, dict):
        raise ProbeError("invalid_private_profile")
    if (
        binding.get("account_confirmed") is not True
        or binding.get("single_chat_confirmed") is not True
    ):
        raise ProbeError("test_binding_not_confirmed")
    title = binding.get("expected_chat_title")
    if not isinstance(title, str) or not title.strip():
        raise ProbeError("expected_title_required")
    return title


def require_chat(info, expected_title: str):
    if not isinstance(info, dict) or info.get("chat_name") != expected_title:
        raise ProbeError("current_chat_mismatch")
    if info.get("chat_type") != "friend":
        raise ProbeError("single_friend_chat_required")


def read_snapshot(client, expected_title: str, limit: int) -> dict:
    require_chat(client.ChatInfo(), expected_title)
    messages = client.GetAllMessage()
    require_chat(client.ChatInfo(), expected_title)
    if not isinstance(messages, list):
        raise ProbeError("unsupported_message_shape")
    result = []
    for message in messages[-limit:]:
        kind = getattr(message, "type", "unknown")
        content = getattr(message, "content", None)
        if kind != "text" or not isinstance(content, str):
            continue
        attr = getattr(message, "attr", None)
        ui_id = getattr(message, "id", None)
        result.append(
            {
                "visible_index": len(result),
                "ui_id": ui_id if isinstance(ui_id, str) else None,
                "direction": {"friend": "incoming", "self": "outgoing"}.get(attr, "unknown"),
                "type": "text",
                "text": content,
            }
        )
    return {
        "mode": "windows_uia_snapshot",
        "sending": False,
        "g1": "not_tested",
        "messages": result,
        "identity_basis": "manually confirmed account and exact visible friend-chat title",
        "limitations": [
            "Visible loaded messages only; no history backfill or automatic chat navigation",
            "UI IDs change when UI is recreated; not native or persistent message IDs",
            "Text and direction require human verification before G1 can pass",
        ],
    }


def write_report(path: Path, payload: dict):
    path = private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".read-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextlib.contextmanager
def quiet_library():
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            yield
    finally:
        logging.disable(previous)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=PRIVATE_DIR / "windows-probe/read.json")
    parser.add_argument("--limit", type=int, default=20, choices=range(1, 51), metavar="1..50")
    args = parser.parse_args(argv)
    try:
        if os.name != "nt":
            raise ProbeError("windows_required")
        if platform.python_version_tuple()[:2] != ("3", "12"):
            raise ProbeError("python_312_required")
        private_path(args.output)
        expected_title = load_binding(args.profile)
        if version("wxauto4") != WXAUTO_VERSION:
            raise ProbeError("wxauto4_version_mismatch")
        with quiet_library():
            from wxauto4 import WeChat

            report = read_snapshot(WeChat(), expected_title, args.limit)
        report["library_version"] = WXAUTO_VERSION
        write_report(args.output, report)
        count = len(report["messages"])
        print(json.dumps({"status": "snapshot_read", "text_count": count, "sending": False}))
        return 0 if count else 2
    except Exception as exc:
        code = str(exc) if isinstance(exc, ProbeError) else "windows_read_failed"
        print(json.dumps({"status": "rejected", "code": code, "sending": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
