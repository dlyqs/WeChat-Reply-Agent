from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Direction(StrEnum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ConversationRef(Contract):
    account_ref: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    contact_alias: str = Field(min_length=1)
    profile: str
    identity_basis: str
    confidence: float = Field(ge=0, le=1)


class LocalAttachment(Contract):
    kind: Literal["file", "voice"]
    status: Literal["pending", "available", "missing", "error"] = "pending"
    name: str | None = None
    byte_size: int | None = Field(default=None, ge=0)
    format: str | None = None
    reason: str | None = None
    checked_at: float = 0


class InboundEvent(Contract):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    source_message_id: str | None = None
    account_ref: str | None = None
    account_generation: str | None = None
    native_session: str | None = None
    shard: str | None = None
    local_id: int | None = None
    sort_seq: int | None = None
    source_created_at: int | None = None
    sender_username: str | None = None
    occurrence_ref: str
    direction: Direction
    type: Literal["text", "unknown", "file", "voice", "transcript", "system"] = "text"
    text: str | None = None
    attachment_ref: str | None = None
    attachment: LocalAttachment | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    confidence: float = Field(ge=0, le=1)


class SendIntent(Contract):
    outbox_id: str = Field(default_factory=lambda: str(uuid4()))
    conversation: ConversationRef
    input_event_refs: tuple[str, ...] = ()
    reply_text: str = Field(min_length=1, max_length=1000)
    run_generation: int = 0
    mode: Literal["dry-run", "live"] = "dry-run"
    status: Literal["pending"] = "pending"

    @model_validator(mode="after")
    def safe_identity(self):
        if self.conversation.confidence < 1 or not self.reply_text.strip():
            raise ValueError("a uniquely resolved identity and nonempty text are required")
        return self


class SendResult(Contract):
    outcome: Literal["verified_sent", "not_sent", "unknown"]
    basis: str
    error: str | None = None
    evidence_ref: str | None = None


class AdapterCapabilities(Contract):
    profile: str
    message_types: tuple[str, ...] = ("text",)
    raw_attachments: bool = False
    identity: str = "local alias + manually bound exact visible single-chat title"
    send_confirmation: str = "unknown after Return; recipient delivery requires human confirmation"
    window_conditions: str = (
        "foreground, unlocked, single main window, user-selected test single-chat"
    )
    direction_basis: str = "screenshot heuristic; uncertain/unsupported content is unknown"
    tested: bool = False
    max_text_characters: int = 1000
    supports_newlines: bool = True
    ui_checks_degraded: bool = False


class Health(Contract):
    healthy: bool
    reason: str
    environment: dict[str, str | bool | None]
    capabilities: AdapterCapabilities
