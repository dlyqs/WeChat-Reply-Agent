"""Explicit native identity binding, stored only in DATA_DIR."""

import json
from pathlib import Path

from pydantic import Field, model_validator

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.domain.messages import Contract


class ReplicaContact(Contract):
    alias: str = Field(min_length=1)
    username: str = Field(min_length=1)
    title: str = Field(min_length=1)
    single_chat_confirmed: bool = False


class ReplicaProfile(Contract):
    name: str = "replica-v1"
    account_ref: str = Field(min_length=1)
    account: str = Field(min_length=1)
    self_username: str = Field(min_length=1)
    account_generation: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    db_root: Path
    account_confirmed: bool = False
    wechat_version: str = Field(min_length=1)
    contacts: tuple[ReplicaContact, ...] = ()

    @model_validator(mode="after")
    def safe_binding(self):
        if (
            Path(self.account).name != self.account
            or self.account in (".", "..")
            or any(c in self.account for c in "/\\:")
        ):
            raise ValueError("invalid account directory")
        for field in ("alias", "username", "title"):
            values = [getattr(c, field) for c in self.contacts]
            if len(values) != len(set(values)):
                raise ValueError("ambiguous contact")
        return self


def load_replica_profile(path: Path):
    try:
        return ReplicaProfile.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise AdapterError("replica_profile_missing_or_invalid") from exc
