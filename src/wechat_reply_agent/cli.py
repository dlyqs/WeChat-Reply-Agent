"""Explicit G1 probes. This module never runs a worker or opens a browser."""

import argparse
import fcntl
import json
import logging
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings.exceptions import SettingsError

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.mac_ax import MacAXAdapter
from wechat_reply_agent.adapters.wechat.profile import load_profile
from wechat_reply_agent.config import Settings
from wechat_reply_agent.domain.messages import SendIntent
from wechat_reply_agent.observability import emit


def write_private(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".report-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def probe_lock(data_dir: Path):
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(data_dir / "probe.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AdapterError("another_probe_running") from exc
        yield
    finally:
        os.close(fd)


def create_adapter(settings: Settings, *, profile_required: bool):
    if settings.wechat_adapter != "mac_ax":
        # Fake is injection-only. A CLI invocation must never pretend fake data is WeChat.
        raise AdapterError("fake_adapter_is_offline_test_only")
    try:
        profile = load_profile(settings.wechat_profile)
    except AdapterError:
        if profile_required:
            raise
        profile = None
    return MacAXAdapter(settings, profile)


def parser():
    root = argparse.ArgumentParser(prog="wechat-agent", description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Read-only permission/environment diagnostic")
    doctor.add_argument("--output", type=Path, required=True)
    probe = commands.add_parser("probe", help="User-operated current test single-chat probes")
    actions = probe.add_subparsers(dest="action", required=True)
    read = actions.add_parser("read", help="Read visible messages; never scroll or select a chat")
    read.add_argument("--contact", required=True)
    read.add_argument("--limit", type=int, choices=range(1, 51), default=5, metavar="1..50")
    read.add_argument("--output", type=Path, required=True)
    send = actions.add_parser("send", help="Explicit fixed reply; Return is not delivery proof")
    send.add_argument("--contact", required=True)
    send.add_argument("--text", required=True)
    send.add_argument("--confirm-send", action="store_true")
    send.add_argument("--output", type=Path)
    return root


def execute(args, settings: Settings, adapter):
    if args.command == "doctor":
        health = adapter.health()
        emit(
            "adapter.health",
            outcome="available" if health.healthy else "unavailable",
            reason=health.reason,
        )
        report = {
            "phase": 1,
            "mode": "diagnostic",
            "health": health.model_dump(mode="json"),
            "g1": "not_tested",
            "note": "No send, app activation or permission changes",
        }
        write_private(args.output, report)
        return 0 if health.healthy else 2
    with probe_lock(settings.data_dir):
        ref = adapter.resolve_conversation(args.contact)
        if args.action == "read":
            events, cursor = adapter.poll_events()
            report = {
                "phase": 1,
                "mode": "probe_read",
                "g1": "not_tested",
                "conversation": ref.model_dump(),
                "cursor": cursor,
                "events": [e.model_dump(mode="json") for e in events[-args.limit :]],
                "note": "Visible snapshot only; occurrence_ref is not a stable message ID",
            }
            write_private(args.output, report)
            emit("adapter.read", outcome="snapshot")
            return 0
        if not args.confirm_send:
            raise AdapterError("explicit_confirm_send_required")
        intent = SendIntent(conversation=ref, reply_text=args.text, mode=settings.send_mode)
        # Persist before the key boundary. A crash leaves unknown, never an automatic retry.
        receipt = settings.data_dir / "probe-sends" / f"{intent.outbox_id}.json"
        report = {
            "phase": 1,
            "mode": intent.mode,
            "outbox_id": intent.outbox_id,
            "g1": "not_tested",
            "outcome": "unknown",
            "basis": "probe_started",
            "note": "Check recipient manually. No automatic retries or delivery claim.",
        }
        write_private(receipt, report)
        result = adapter.send_text(intent)
        report.update(result.model_dump())
        write_private(receipt, report)
        if args.output:
            write_private(args.output, report)
        emit("send.result", outcome=result.outcome, reason=result.basis)
        # No raw text/contact/profile contents in terminal logs.
        print(
            json.dumps(
                {
                    "outbox_id": intent.outbox_id,
                    "mode": intent.mode,
                    "outcome": result.outcome,
                    "receipt": str(receipt),
                }
            )
        )
        return 3 if result.outcome == "unknown" else (0 if result.error is None else 2)


def main(argv=None):
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        settings = Settings()
        adapter = create_adapter(settings, profile_required=args.command != "doctor")
        return execute(args, settings, adapter)
    except (ValidationError, SettingsError):
        error = "configuration_invalid"
    except AdapterError as exc:
        error = str(exc)
    except Exception:
        error = "local_or_native_operation_failed"
    emit("probe.error", outcome="rejected", reason=error)
    print(json.dumps({"code": error, "message": "See README G1 troubleshooting"}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
