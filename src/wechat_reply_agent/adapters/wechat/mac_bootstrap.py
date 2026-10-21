"""Explicit, bounded temporary-copy key initialization, separate from connect/start."""

import hashlib
import json
import os
import platform
import signal
import subprocess
import time
from pathlib import Path

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.mac_bridge import TOOLKIT, client_version, run
from wechat_reply_agent.privacy import private_directory


def bootstrap(root, state, app=Path("/Applications/WeChat.app"), timeout=180):
    from wechat_reply_agent.cli import write_private

    if platform.system() != "Darwin" or platform.machine() != "arm64" or os.geteuid() == 0:
        raise AdapterError("native_unprivileged_apple_silicon_required")
    block = state.resolve().parent / "bootstrap-blocked.json"
    if block.exists():
        raise AdapterError("mac_lldb_repair_required_see_private_report")
    if subprocess.run(["/usr/bin/pgrep", "-x", "WeChat"], capture_output=True).returncode == 0:
        raise AdapterError("quit_wechat_normally_before_bootstrap")
    root, app, state = root.resolve(strict=True), app.resolve(strict=True), state.resolve()
    try:
        list(root.iterdir())
    except PermissionError:
        raise AdapterError("mac_database_access_denied_full_disk_access_required") from None
    if root.name != "db_storage" or not list(root.rglob("*.db")) or not 10 <= timeout <= 300:
        raise AdapterError("mac_bootstrap_arguments_invalid")
    if state.exists() and list(state.iterdir()):
        raise AdapterError("mac_bootstrap_state_exists_use_fresh_directory")
    private_directory(state)
    version, build = client_version(app)
    executable = app / "Contents/MacOS/WeChat"
    original_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
    signature = run(["/usr/bin/codesign", "-dvv", str(app)])
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], 30)
    report = {
        "plan_version": "v5",
        "platform": "macOS",
        "foundation": "mac_db",
        "mode": "bootstrap",
        "wechat_version": version,
        "wechat_build": build,
        "original_executable_sha256": original_hash,
        "original_signature": signature.stdout + signature.stderr,
        "db_root": str(root),
        "started_at": time.time(),
        "capture": "not_started",
        "restoration": "not_tested",
    }
    write_private(state / "bootstrap.json", report)
    shadow, disabled = state / "WeChat-trial.app", state / "WeChat-trial.disabled"
    process = None
    try:
        run(["/usr/bin/ditto", str(app), str(shadow)], 90)
        run(["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(shadow)], 60)
        run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(shadow)], 30)
        lldb_python = run(["/usr/bin/lldb", "-P"]).stdout.strip()
        # LLDB's Python is supplied by Apple, never the application's Python ABI.
        env = dict(os.environ, PYTHONPATH=lldb_python)
        env.pop("PYTHONHOME", None)
        print(
            json.dumps(
                {
                    "event": "mac.bootstrap.login_required",
                    "message": "Use temporary WeChat window; finish phone login if requested",
                }
            ),
            flush=True,
        )
        with (state / "capture.jsonl").open("x", encoding="utf-8") as log:
            os.chmod(state / "capture.jsonl", 0o600)
            process = subprocess.Popen(
                [
                    "/usr/bin/python3",
                    str(TOOLKIT / "capture_keys.py"),
                    "--exe",
                    str(shadow / "Contents/MacOS/WeChat"),
                    "--db-root",
                    str(root),
                    "--out",
                    str(state / "keys.json"),
                    "--timeout",
                    str(timeout),
                ],
                env=env,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            try:
                code = process.wait(timeout=timeout + 20)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                raise AdapterError("mac_bootstrap_interrupted") from None
        report["capture"] = "keys_saved" if (state / "keys.json").exists() else "no_keys"
        report["capture_exit_code"] = code
        if code < 0:
            write_private(
                block,
                {
                    "reason": "native_debugger_crashed",
                    "signal": -code,
                    "macos": platform.mac_ver()[0],
                    "lldb_version": run(["/usr/bin/lldb", "--version"]).stdout.strip(),
                    "automatic_retry": False,
                    "repair": (
                        "Repair/upgrade Apple developer tools and verify independently "
                        "before clearing this marker"
                    ),
                },
            )
    finally:
        # Cleanup only the process whose executable is the exact owned temporary copy.
        pids = subprocess.run(
            ["/usr/bin/pgrep", "-x", "WeChat"], capture_output=True, text=True
        ).stdout.split()
        for pid in pids:
            actual = run(["/bin/ps", "-p", pid, "-o", "comm="]).stdout.strip()
            if Path(actual) == shadow / "Contents/MacOS/WeChat":
                os.kill(int(pid), signal.SIGTERM)
                for _ in range(30):
                    if subprocess.run(["/bin/kill", "-0", pid], capture_output=True).returncode:
                        break
                    time.sleep(0.1)
                else:
                    os.kill(int(pid), signal.SIGKILL)
        if shadow.exists():
            ls = (
                "/System/Library/Frameworks/CoreServices.framework/"
                "Frameworks/LaunchServices.framework/Support/lsregister"
            )
            subprocess.run([ls, "-u", str(shadow)], capture_output=True, timeout=10)
            shadow.rename(disabled)
        unchanged = hashlib.sha256(executable.read_bytes()).hexdigest() == original_hash
        unchanged = (
            unchanged
            and subprocess.run(
                ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)],
                capture_output=True,
                timeout=30,
            ).returncode
            == 0
        )
        report["original_unchanged"] = unchanged
        if unchanged:
            restored = subprocess.Popen(
                [str(executable)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            report["restoration"] = "original_launch_requested"
            report["restored_pid"] = restored.pid
        report["finished_at"] = time.time()
        write_private(state / "bootstrap.json", report)
    if not (state / "keys.json").exists():
        raise AdapterError("mac_bootstrap_no_keys_see_private_report")
    return {"keys": "captured_requires_connect_validation", "original": report["restoration"]}
