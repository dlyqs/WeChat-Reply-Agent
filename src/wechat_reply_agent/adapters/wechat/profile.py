import json
from pathlib import Path

from pydantic import Field, model_validator

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.domain.messages import Contract


class ContactBinding(Contract):
    alias: str = Field(min_length=1)
    title: str = Field(min_length=1)
    local_conversation_id: str = Field(min_length=1)
    single_chat_confirmed: bool = False


class AXProfile(Contract):
    name: str = "ax-candidate-v1"
    account_ref: str
    # User verifies account, version, locale and exact test-contact identities locally.
    account_confirmed: bool = False
    wechat_version: str = Field(min_length=1)
    distribution: str = Field(min_length=1)
    language: str = Field(min_length=1)
    messages_title: str = "Messages"
    title_identifier: str = "big_title_line_h_view"
    input_identifier: str = "chat_input_field"
    contacts: tuple[ContactBinding, ...] = ()

    @model_validator(mode="after")
    def unique_bindings(self):
        for field in ("alias", "title", "local_conversation_id"):
            values = [getattr(c, field) for c in self.contacts]
            if len(values) != len(set(values)):
                raise ValueError("ambiguous contact bindings")
        return self


def load_profile(path: Path) -> AXProfile:
    try:
        return AXProfile.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise AdapterError("profile_missing_or_invalid") from exc
