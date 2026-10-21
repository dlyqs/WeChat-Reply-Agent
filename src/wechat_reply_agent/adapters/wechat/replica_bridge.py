"""Only this bridge imports Replica. doctor never constructs or imports it."""

import hashlib
import importlib.metadata
import json
import logging
import os
import platform
import shutil
import struct
import subprocess
import time
from contextlib import contextmanager, redirect_stderr, redirect_stdout

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.privacy import private_directory


@contextmanager
def quiet_native():
    # Upstream has direct prints in key extraction as well as library log calls.
    disabled = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with open(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            yield
    finally:
        logging.disable(disabled)


def environment():
    result = {
        "platform": platform.system(),
        "python_x64": struct.calcsize("P") == 8,
        "replica_installed": False,
        "wechat_running": False,
        "wechat_version": None,
        "signature": None,
    }
    try:
        result["replica_installed"] = importlib.metadata.version("wechatauto-replica") == "1.2.7.0"
    except importlib.metadata.PackageNotFoundError:
        pass
    if platform.system() == "Windows":
        # Fixed read-only command, no profile/keys/window activation or process writes.
        code = (
            "$p=Get-Process Weixin -ErrorAction SilentlyContinue | Select-Object -First 1;"
            "if($p){[pscustomobject]@{version=$p.MainModule.FileVersionInfo.FileVersion;"
            "signature=[string](Get-AuthenticodeSignature -LiteralPath $p.Path).Status}"
            "|ConvertTo-Json -Compress}"
        )

        try:
            proc = subprocess.run(
                [shutil.which("pwsh") or "powershell", "-NoProfile", "-Command", code],
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            )
            if proc.stdout.strip():
                data = json.loads(proc.stdout)
                result.update(
                    wechat_running=True, wechat_version=data["version"], signature=data["signature"]
                )
        except (OSError, ValueError, subprocess.SubprocessError):
            result["signature"] = "unavailable"
    return result


class ReplicaBridge:
    def __init__(self, settings, profile):
        self.settings, self.profile = settings, profile
        self.db = self.gui = None
        self.process_identity = None
        self.database_identities = None

    def connect(self):
        if platform.system() != "Windows":
            raise AdapterError("windows_required")
        private = self.settings.data_dir.resolve() / "replica" / self.profile.account_generation
        for path in (private, private / "layout", private / "tmp", private / "db"):
            private_directory(path)
        os.environ["WECHATAUTO_LAYOUT_DIR"] = str(private / "layout")
        os.environ["WECHATAUTO_PRIVATE_TMP"] = str(private / "tmp")
        with quiet_native():
            from wechatauto.db import WeChatDB
            from wechatauto.param import WxParam

            WxParam.ENABLE_FILE_LOGGER = False
            WxParam.ENABLE_OCR = self.settings.wechat_ocr_enabled
            WxParam.ENABLE_UIA_GATE = self.settings.wechat_uia_gate_enabled
            self.db = WeChatDB(
                db_dir=str(self.profile.db_root),
                account=self.profile.account,
                workdir=str(private / "db"),
                keys_file=str(private / "db" / "keys.json"),
                strict_account=True,
            )
            # A folder name and cached keys do not prove the active process account.
            identity = self.db.extract_master_key()
            if not identity or identity[2] != self.profile.self_username:
                self.db = None
                raise AdapterError("active_account_unverified")
            if self.db.wxid != self.profile.self_username:
                self.db = None
                raise AdapterError("account_mismatch")
            self.process_identity = self._processes()
            self.database_identities = self._database_identities()
            manifest = private / "database-identities.json"
            if manifest.exists():
                expected = json.loads(manifest.read_text(encoding="utf-8"))
                if any(self.database_identities.get(k) != v for k, v in expected.items()):
                    raise AdapterError("database_replaced_rebind_required")
            from wechat_reply_agent.cli import write_private

            write_private(manifest, self.database_identities)
            # Explicit connect alone is allowed to calibrate and activate the UIA gate.
            from wechatauto.guia import WeChatGUI

            self.gui = WeChatGUI()
            self.gui._cached_db = self.db
            uia = self.gui._get_uia()
        return {
            "keys": "ready",
            "account": "verified",
            "private_cache": "ready",
            "gui": "initialized",
            "uia": "available" if uia else "unavailable",
            "ocr_enabled": self.settings.wechat_ocr_enabled,
            "g1": "not_tested",
        }

    @staticmethod
    def _processes():
        import psutil

        return sorted(
            (p.pid, p.create_time())
            for p in psutil.process_iter(["name"])
            if (p.info["name"] or "").lower() == "weixin.exe"
        )

    def assert_account(self):
        if self.db is None or self._processes() != self.process_identity:
            raise AdapterError("client_changed_reconnect_required")
        with quiet_native():
            identity = self.db.extract_master_key()
        if not identity or identity[2] != self.profile.self_username:
            raise AdapterError("active_account_changed")
        current = self._database_identities()
        if any(current.get(k) != v for k, v in self.database_identities.items()):
            raise AdapterError("database_replaced_rebind_required")

    def _database_identities(self):
        result = {}
        for file in (self.profile.db_root / self.profile.account / "db_storage").rglob("*.db"):
            if "migrate" in file.parts:
                continue
            stat = file.stat()
            with file.open("rb") as stream:
                salt = hashlib.sha256(stream.read(16)).hexdigest()
            result[str(file.relative_to(self.profile.db_root))] = [stat.st_ino, salt]
        return result

    def read(self, username, since=None, limit=10000):
        self.assert_account()
        with quiet_native():
            if since is None:
                return self.db.get_messages(username, limit=limit)
            return self.db.scan_messages_inclusive(username, since_seq=since, limit=limit)

    def send_once(self, title, text):
        self.assert_account()
        with quiet_native():
            return self.gui.send_text_once(text, title)

    def wait_new(self, username, since, predicate, timeout=8):
        deadline = time.monotonic() + timeout
        while True:
            for row in self.read(username, since):
                if predicate(row):
                    return row
            if time.monotonic() >= deadline:
                return None
            time.sleep(1)
