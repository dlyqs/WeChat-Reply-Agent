"""Validate before atomically saving dotenv; environment remains authoritative."""

import json
import os
import tempfile
from pathlib import Path

from dotenv import dotenv_values

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.config import Settings
from wechat_reply_agent.privacy import private_directory

READ_ONLY = {"data_dir", "app_host", "app_port", "wechat_adapter"}


def inactive_fields(adapter):
    return (
        {"wechat_uia_gate_enabled", "wechat_ocr_enabled"}
        if adapter == "mac_db"
        else {"mac_bridge_path", "mac_verify_timeout_seconds"}
    )


class SettingsStore:
    def __init__(self, path=Path(".env"), settings=None, session_fields=()):
        self.path = path
        self.settings = settings or Settings(_env_file=path)
        self.session_fields = set(session_fields)

    def public(self):
        values = self.settings.model_dump(mode="json")
        values.pop("llm_api_key")
        values["llm_api_key_configured"] = bool(self.settings.llm_api_key.get_secret_value())
        env = {k.lower() for k in os.environ}
        saved = {k.lower() for k in dotenv_values(self.path)}
        return {
            "values": values,
            "sources": {
                key: "session"
                if key in self.session_fields
                else "environment"
                if key in env
                else "dotenv"
                if key in saved
                else "default"
                for key in Settings.model_fields
            },
            "readonly": sorted(READ_ONLY),
            "inactive": sorted(inactive_fields(self.settings.wechat_adapter)),
            "platform": "macOS" if self.settings.wechat_adapter == "mac_db" else "Windows",
        }

    def patch(self, changes):
        changes = dict(changes)
        clear = changes.pop("clear_llm_api_key", False)
        if not isinstance(clear, bool):
            raise AdapterError("settings_invalid")
        if changes.keys() - Settings.model_fields.keys() or changes.keys() & READ_ONLY:
            raise AdapterError("settings_field_not_editable")
        if changes.keys() & inactive_fields(self.settings.wechat_adapter):
            raise AdapterError("settings_field_not_applicable")
        if changes.get("llm_api_key") in ("", None):
            changes.pop("llm_api_key", None)
        if clear:
            changes["llm_api_key"] = ""
        # Validate supplied values even when an environment override masks them.
        Settings.model_validate(self.settings.model_dump() | changes)
        saved = dict(dotenv_values(self.path))
        for key, value in changes.items():
            saved[key.upper()] = (
                json.dumps(value, ensure_ascii=False)
                if isinstance(value, list)
                else ""
                if value is None
                else str(value)
            )
        # Construct effective settings using normal env > dotenv > defaults precedence.
        staging = self.path.resolve().parent / ".settings-private"
        private_directory(staging)
        fd, temporary = tempfile.mkstemp(dir=staging, prefix=".settings-")
        try:
            if os.name != "nt":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                for key, value in saved.items():
                    if value is not None:
                        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
                        stream.write(f"{key}='{escaped}'\n")
                stream.flush()
                os.fsync(stream.fileno())
            effective = Settings(_env_file=temporary)
            # API cannot move the running database or server through dotenv defaults.
            effective = effective.model_copy(
                update={k: getattr(self.settings, k) for k in READ_ONLY}
            )
            if "send_mode" not in changes:
                effective = effective.model_copy(update={"send_mode": self.settings.send_mode})
            os.replace(temporary, self.path)
            self.settings = effective
            self.session_fields.difference_update(changes)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return self.public()
