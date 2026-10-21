"""Mac-specific binding. Keys and native usernames never leave private storage."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.domain.messages import Contract

REVISION = "c98dbb10cf23c30e83d5d744905101b0880887a0"


class MacContact(Contract):
    alias: str = Field(min_length=1)
    username: str = Field(min_length=1)
    title: str = Field(min_length=1)
    wechat_id: str = Field(min_length=1)
    single_chat_confirmed: bool = False


class MacProfile(Contract):
    name: Literal["mac-db-v1"] = "mac-db-v1"
    account_ref: str = Field(min_length=1)
    self_username: str = Field(min_length=1)
    account_generation: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    db_root: Path
    key_file: Path
    app_path: Path = Path("/Applications/WeChat.app")
    wechat_version: str = Field(min_length=1)
    wechat_build: str = Field(min_length=1)
    account_confirmed: bool = False
    contacts: tuple[MacContact, ...] = ()
    composer_top: float | None = Field(default=None, ge=0.45, le=0.88)
    window_width: int | None = Field(default=None, ge=600)
    window_height: int | None = Field(default=None, ge=450)
    send_key: Literal["enter", "cmd-enter"] = "enter"

    @model_validator(mode="after")
    def unique_contacts(self):
        for attr in ("alias", "username", "title", "wechat_id"):
            values = [getattr(c, attr) for c in self.contacts]
            if len(values) != len(set(values)):
                raise ValueError("ambiguous contact binding")
        if any(
            c.username.endswith("@chatroom") or c.username == self.self_username
            for c in self.contacts
        ):
            raise ValueError("single friend required")
        return self

    def fingerprint(self):
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


def load_mac_profile(path):
    try:
        return MacProfile.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        raise AdapterError("mac_profile_missing_or_invalid") from None
