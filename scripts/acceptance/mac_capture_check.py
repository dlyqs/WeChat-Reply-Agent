"""Bounded read-only native capture comparison; never sends or changes a profile."""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.mac_acceptance import context
from wechat_reply_agent.adapters.wechat.mac_bridge import TOOLKIT, bridge_path
from wechat_reply_agent.cli import create_adapter, probe_lock, write_private
from wechat_reply_agent.config import Settings
from wechat_reply_agent.privacy import private_directory


def check_capture(settings, *, mode, backend, output):
    if settings.wechat_adapter != "mac_db":
        raise AdapterError("mac_db_adapter_required")
    if not output.resolve().is_relative_to(settings.data_dir.resolve()):
        raise AdapterError("capture_output_must_be_private")
    if output.exists() or list(output.parent.glob(output.stem + ".frame*")):
        raise AdapterError("capture_output_exists")
    adapter = create_adapter(settings, profile_required=True)
    started = time.monotonic()
    report = {
        "phase": 5,
        "mode": "native_readonly_capture",
        "window_mode": mode,
        "capture_backend": backend,
        "input_events": 0,
        "model_calls": 0,
        "window_preparation": "operator_preselected",
        "status": "failed",
        "gates_unchanged": True,
    }
    try:
        with probe_lock(settings.data_dir):
            adapter.connect()
            profile = adapter.profile
            if len(profile.contacts) != 1:
                raise AdapterError("single_bound_friend_required")
            report.update(context(profile))
            binary = bridge_path(settings).resolve()
            build = json.loads(binary.with_suffix(".build.json").read_text())
            if build["binary"] != hashlib.sha256(binary.read_bytes()).hexdigest() or any(
                hashlib.sha256((TOOLKIT / name).read_bytes()).hexdigest() != digest
                for name, digest in build["sources"].items()
            ):
                raise AdapterError("mac_bridge_build_stale")
            report["bridge_build"] = build
            import AppKit

            pasteboard = AppKit.NSPasteboard.generalPasteboard()
            before = pasteboard.changeCount()
            private_directory(output.parent)
            command = [
                str(binary),
                "capture-picker" if backend == "picker" else "capture-check",
                "--pid",
                str(adapter._bridge.process["pid"]),
                "--chat",
                profile.contacts[0].title,
                "--window-mode",
                mode,
                "--snapshot",
                str(output.with_suffix(".frame").resolve()),
            ]
            if backend != "picker":
                command += ["--capture-backend", backend]
            result = subprocess.run(command, capture_output=True, text=True, timeout=140)
            report["clipboard_unchanged"] = before == pasteboard.changeCount()
            report["exit_code"] = result.returncode
            report["events"] = [json.loads(line) for line in result.stdout.splitlines()]
            passed_event = (
                "capture_recording_finished" if backend == "picker" else "capture_check_passed"
            )
            passed = any(
                e.get("type") == passed_event
                and (backend != "picker" or e.get("title_verified") is True)
                for e in report["events"]
            )
            if result.returncode == 0 and passed and report["clipboard_unchanged"]:
                report["status"] = "passed"
            report["reason"] = (
                "exact_target_frames_verified"
                if report["status"] == "passed"
                else "capture_or_exact_title_verification_failed"
            )
    except AdapterError as exc:
        report["reason"] = str(exc)
    except subprocess.TimeoutExpired:
        report["reason"] = "capture_check_timeout"
    except Exception:
        report["reason"] = "capture_check_failed"
    finally:
        adapter.close()
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_private(output, report)
    print(json.dumps({k: report[k] for k in ("status", "reason", "input_events", "model_calls")}))
    return 0 if report["status"] == "passed" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-mode", choices=("main", "independent"), required=True)
    parser.add_argument(
        "--backend", choices=("display", "window", "stream", "picker"), required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        return check_capture(
            Settings(), mode=args.window_mode, backend=args.backend, output=args.output
        )
    except AdapterError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    raise SystemExit(main())
