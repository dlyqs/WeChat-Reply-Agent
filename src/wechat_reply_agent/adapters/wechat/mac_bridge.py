"""Lazy SQLCipher/Swift bridge. Never imports Mac GUI frameworks into the worker."""

import hashlib
import importlib.util
import json
import os
import platform
import plistlib
import subprocess
import sys
import time
from pathlib import Path

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.mac_security import (
    record_security_stop,
    require_security_clear,
    security_stopped,
)
from wechat_reply_agent.privacy import private_directory

TOOLKIT = Path(__file__).resolve().parents[4] / "third_party/wechat_mac_toolkit"

NATIVE_FAILURES = frozenset(
    {
        "wechat_account_security_prompt",
        "screen_locked",
        "accessibility_permission_required",
        "screen_recording_and_accessibility_permissions_required",
        "process_binding_changed",
        "main_window_unavailable",
        "calibrated_main_window_not_unique",
        "main_window_restore_failed",
        "wechat_activation_failed",
        "main_window_raise_failed",
        "wechat_lost_focus",
        "main_window_obscured",
        "main_window_not_visible",
        "window_inventory_unavailable",
        "expected_one_visible_main_window",
        "window_must_fit_one_display",
        "calibrated_window_size_changed",
        "chat_title_not_verified",
        "composer_not_empty_or_wrong_composer_top",
        "same_text_already_visible",
        "no_frame_after_filter_refresh",
        "capture_not_started",
        "clipboard_snapshot_unavailable",
        "clipboard_changed_before_paste",
        "clipboard_write_failed",
        "draft_verification_failed",
        "draft_changed_before_send",
        "window_moved_before_typing",
        "window_moved_before_send",
        "send_result_uncertain",
        "keyboard_event_failed",
        "composer_changed_before_typing",
        "target_window_geometry_unavailable",
        "target_window_focus_or_geometry_changed",
        "clipboard_changed_before_send",
        "degraded_requires_independent_window",
        "target_window_not_unique",
    }
)


def native_failure(result):
    """Only return known error codes; native output can contain private diagnostics."""
    for line in reversed(result.stdout.splitlines()):
        try:
            event = json.loads(line)
            code = str(event.get("reason", "")).split(";", 1)[0]
            if event.get("type") == "error" and code in NATIVE_FAILURES:
                return code
        except (ValueError, AttributeError):
            pass
    return "native_command_failed"


def toolkit_module(name):
    """Use a private module name; never execute upstream command-line entry points."""
    qualified = f"_wechat_mac_{name}"
    if qualified not in sys.modules:
        spec = importlib.util.spec_from_file_location(qualified, TOOLKIT / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        if name == "wechat_db":
            # Upstream uses an absolute sibling import; give it only during module loading.
            previous = sys.modules.get("sqlcipher_probe")
            sys.modules["sqlcipher_probe"] = toolkit_module("sqlcipher_probe")
            try:
                spec.loader.exec_module(module)
            finally:
                if previous is None:
                    del sys.modules["sqlcipher_probe"]
                else:
                    sys.modules["sqlcipher_probe"] = previous
        else:
            spec.loader.exec_module(module)
        sys.modules[qualified] = module
    return sys.modules[qualified]


def run(command, timeout=10):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=True)
    except (OSError, subprocess.SubprocessError):
        raise AdapterError("mac_native_command_failed") from None


def client_version(app):
    try:
        with (app / "Contents/Info.plist").open("rb") as stream:
            info = plistlib.load(stream)
        if info["CFBundleIdentifier"] != "com.tencent.xinWeChat":
            raise ValueError
        return str(info["CFBundleShortVersionString"]), str(info["CFBundleVersion"])
    except (OSError, KeyError, ValueError):
        raise AdapterError("mac_client_unavailable") from None


def process_binding(app, root):
    pids = run(["/usr/bin/pgrep", "-x", "WeChat"]).stdout.split()
    if len(pids) != 1:
        raise AdapterError("mac_unique_process_required")
    pid = pids[0]
    executable = run(["/bin/ps", "-p", pid, "-o", "comm="]).stdout.strip()
    if Path(executable).resolve() != (app / "Contents/MacOS/WeChat").resolve():
        raise AdapterError("mac_original_process_required")
    files = run(["/usr/sbin/lsof", "-Fn", "-p", pid]).stdout.splitlines()
    roots = {
        Path(s[1:].split("/db_storage/")[0]) / "db_storage"
        for s in files
        if s.startswith("n") and "/db_storage/" in s
    }
    if roots != {root.resolve()}:
        raise AdapterError("mac_process_account_mismatch")
    birth = run(["/bin/ps", "-p", pid, "-o", "lstart="]).stdout.strip()
    return {"pid": int(pid), "birth": birth}


def source_identity(root):
    result = {}
    for path in sorted(root.rglob("*.db")):
        stat = path.stat()
        with path.open("rb") as stream:
            salt = stream.read(16).hex()
        result[str(path.relative_to(root))] = [stat.st_dev, stat.st_ino, salt]
    if not result:
        raise AdapterError("database_root_missing")
    return result


def bridge_path(settings):
    return settings.mac_bridge_path or settings.data_dir / "macos/bin/wechat-ui"


def environment(settings):
    env = {
        "platform": platform.system(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "macos": platform.mac_ver()[0],
    }
    env["account_security_stop"] = security_stopped(settings)
    if env["account_security_stop"]:
        return env
    if platform.system() != "Darwin":
        return env
    env["swift_available"] = Path("/usr/bin/swiftc").exists()
    env["lldb_available"] = Path("/usr/bin/lldb").exists()
    env["bootstrap_status"] = (
        "blocked_native_debugger_crash"
        if (settings.data_dir / "macos/bootstrap-blocked.json").exists()
        else "explicit_initialization_required"
    )
    try:
        env["wechat_version"], env["wechat_build"] = client_version(
            Path("/Applications/WeChat.app")
        )
    except AdapterError:
        env["wechat_version"] = None
    try:
        lib = toolkit_module("sqlcipher_probe").library()
        env["sqlcipher_available"] = bool(lib)
    except (OSError, RuntimeError, AttributeError):
        env["sqlcipher_available"] = False
    binary = bridge_path(settings)
    env["bridge_built"] = binary.is_file()
    if binary.is_file():
        try:
            status = json.loads(run([str(binary.resolve()), "doctor"]).stdout)
            env.update(
                {
                    k: status.get(k)
                    for k in (
                        "screen_locked",
                        "screen_recording",
                        "accessibility",
                        "wechat_running",
                    )
                }
            )
        except (AdapterError, ValueError):
            env["bridge_built"] = False
    return env


class MacBridge:
    def __init__(self, settings, profile):
        self.settings, self.profile = settings, profile
        self.reader = None
        self.identity = None
        self.process = None

    def connect(self):
        require_security_clear(self.settings)
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise AdapterError("native_apple_silicon_required")
        p = self.profile
        if client_version(p.app_path) != (p.wechat_version, p.wechat_build):
            raise AdapterError("mac_client_version_changed")
        run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(p.app_path)], 30)
        self.process = process_binding(p.app_path, p.db_root)
        self.identity = source_identity(p.db_root)
        if not p.key_file.is_file():
            raise AdapterError("mac_bootstrap_required")
        if p.key_file.stat().st_mode & 0o077 or p.key_file.parent.stat().st_mode & 0o077:
            raise AdapterError("mac_key_permissions_invalid")
        try:
            reader = toolkit_module("wechat_db").Reader(p.db_root, p.key_file)
            required = {p.db_root / "contact/contact.db"}
            for contact in p.contacts:
                required.update(path for path, _ in reader.paths(contact.username))
            for path in sorted(required):
                with reader.open(path) as db:
                    if db.query("PRAGMA quick_check;") != [{"quick_check": "ok"}]:
                        raise RuntimeError
            for c in p.contacts:
                rows = reader.resolve(c.username)
                if len(rows) != 1 or rows[0]["username"] != c.username:
                    raise RuntimeError
                reader.read(c.username, 1, self_id=p.self_username)
            self.reader = reader
            self.check()
        except AdapterError:
            raise
        except Exception:
            raise AdapterError("mac_key_or_database_validation_failed") from None
        return {
            "keys": "verified",
            "account": "verified",
            "private_cache": "ready",
            "gui": "available" if bridge_path(self.settings).is_file() else "unavailable",
        }

    def check(self):
        require_security_clear(self.settings)
        if not self.identity or source_identity(self.profile.db_root) != self.identity:
            raise AdapterError("native_database_replaced")
        if process_binding(self.profile.app_path, self.profile.db_root) != self.process:
            raise AdapterError("mac_process_changed_reconnect_required")
        if client_version(self.profile.app_path) != (
            self.profile.wechat_version,
            self.profile.wechat_build,
        ):
            raise AdapterError("mac_client_version_changed")

    def snapshot(self, username):
        self.check()
        result = self.reader.snapshot(username)
        self.check()
        return result

    def read(self, username, after=None, limit=200):
        self.check()
        rows = self.reader.read(
            username, limit=limit, after=after, self_id=self.profile.self_username
        )
        self.check()
        return rows

    def assert_session(self):
        """AX-only readiness check: no screenshot, activation, clipboard, or input."""
        self.check()
        command = [
            str(bridge_path(self.settings).resolve()),
            "session-check",
            "--pid",
            str(self.process["pid"]),
        ]
        if self.profile.window_width is not None and self.profile.window_height is not None:
            command += [
                "--window-width",
                str(self.profile.window_width),
                "--window-height",
                str(self.profile.window_height),
            ]
        command += ["--window-mode", self.profile.window_mode]
        if self.profile.window_mode == "independent":
            command += ["--chat", self.profile.contacts[0].title]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            raise AdapterError("mac_session_check_unavailable") from None
        if result.returncode:
            code = native_failure(result)
            if code == "wechat_account_security_prompt":
                record_security_stop(self.settings)
            raise AdapterError("mac_session_not_ready:" + code)

    def send_once(self, intent):
        from wechat_reply_agent.cli import write_private

        self.check()
        p = self.profile
        c = next(c for c in p.contacts if c.alias == intent.conversation.contact_alias)
        state = self.settings.data_dir / "macos/send-state"
        private_directory(state)
        path = state / f"{hashlib.sha256(intent.outbox_id.encode()).hexdigest()}.text"
        # Pinned payload is private, never passed as a process argument.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                stream.write(intent.reply_text)
            command = [
                str(bridge_path(self.settings).resolve()),
                "send",
                "--chat",
                c.title,
                "--text-file",
                str(path.resolve()),
                "--id",
                intent.outbox_id,
                "--composer-top",
                str(p.composer_top),
                "--window-width",
                str(p.window_width),
                "--window-height",
                str(p.window_height),
                "--state-dir",
                str(state.resolve()),
                "--send-key",
                p.send_key,
                "--pid",
                str(self.process["pid"]),
                "--window-mode",
                p.window_mode,
                "--preflight",
                p.send_preflight,
            ]
            # Live sends explicitly raise only the bound calibrated WeChat window. Doctor,
            # connect and application dry-run never activate or change the desktop.
            focus_command = [
                command[0],
                "focus",
                "--pid",
                str(self.process["pid"]),
                "--window-width",
                str(p.window_width),
                "--window-height",
                str(p.window_height),
            ]
            focus_command += ["--window-mode", p.window_mode]
            if p.window_mode == "independent":
                focus_command += ["--chat", c.title]
            native_report = (
                state / f"{hashlib.sha256(intent.outbox_id.encode()).hexdigest()}.preflight.json"
            )
            try:
                focus = subprocess.run(focus_command, capture_output=True, text=True, timeout=10)
                focus_code = native_failure(focus) if focus.returncode else "wechat_focused"
                write_private(native_report, {"focus": focus_code})
                if focus.returncode:
                    if focus_code == "wechat_account_security_prompt":
                        record_security_stop(self.settings)
                    return {"attempted": False, "code": "mac_focus_rejected:" + focus_code}
                self.check()
                # Preflight has no activation, pasteboard access, click or key injection.
                preflight = subprocess.run(
                    command + ["--dry-run"], capture_output=True, text=True, timeout=20
                )
                preflight_code = (
                    native_failure(preflight) if preflight.returncode else "send_preflight_ok"
                )
                write_private(native_report, {"focus": focus_code, "preflight": preflight_code})
                if preflight.returncode:
                    if preflight_code == "wechat_account_security_prompt":
                        record_security_stop(self.settings)
                    return {
                        "attempted": False,
                        "code": "mac_send_preflight_rejected:" + preflight_code,
                    }
            except (OSError, subprocess.TimeoutExpired):
                return {"attempted": False, "code": "mac_focus_or_preflight_unavailable"}
            self.check()
            receipt = (
                state / f"{hashlib.sha256(intent.outbox_id.encode()).hexdigest()}.dispatch.json"
            )
            write_private(
                receipt, {"status": "dispatching", "outbox_id": intent.outbox_id, "at": time.time()}
            )
            dispatched = subprocess.run(command, capture_output=True, text=True, timeout=30)
            dispatched_code = (
                native_failure(dispatched) if dispatched.returncode else "native_attempt_finished"
            )
            write_private(
                state
                / f"{hashlib.sha256(intent.outbox_id.encode()).hexdigest()}.native-result.json",
                {"exit_code": dispatched.returncode, "code": dispatched_code},
            )
            if dispatched_code == "wechat_account_security_prompt":
                record_security_stop(self.settings)
            return {"attempted": True, "code": "mac_native_attempt_finished"}
        finally:
            path.unlink(missing_ok=True)

    def close(self):
        self.reader = None
