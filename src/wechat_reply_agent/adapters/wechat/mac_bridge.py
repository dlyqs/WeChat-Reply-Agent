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
from wechat_reply_agent.privacy import private_directory

TOOLKIT = Path(__file__).resolve().parents[4] / "third_party/wechat_mac_toolkit"


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
            for relative in self.identity:
                if relative != "contact/contact.db" and not (
                    relative.startswith("message/message_") and relative.endswith(".db")
                ):
                    continue
                with reader.open(p.db_root / relative) as db:
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
                "--state-dir",
                str(state.resolve()),
                "--send-key",
                p.send_key,
                "--pid",
                str(self.process["pid"]),
            ]
            # Preflight has no activation, pasteboard access, click or key injection.
            preflight = subprocess.run(
                command + ["--dry-run"], capture_output=True, text=True, timeout=20
            )
            if preflight.returncode:
                return {"attempted": False, "code": "mac_send_preflight_rejected"}
            self.check()
            receipt = (
                state / f"{hashlib.sha256(intent.outbox_id.encode()).hexdigest()}.dispatch.json"
            )
            write_private(
                receipt, {"status": "dispatching", "outbox_id": intent.outbox_id, "at": time.time()}
            )
            subprocess.run(command, capture_output=True, text=True, timeout=30)
            return {"attempted": True, "code": "mac_native_attempt_finished"}
        finally:
            path.unlink(missing_ok=True)

    def close(self):
        self.reader = None
