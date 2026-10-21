from typing import Protocol

from wechat_reply_agent.domain.messages import (
    ConversationRef,
    Health,
    InboundEvent,
    SendIntent,
    SendResult,
)


class AdapterError(RuntimeError):
    """Public error codes only: never include desktop text or system exception payloads."""


class WechatAdapter(Protocol):
    def health(self) -> Health: ...
    def poll_events(self, cursor: str | None = None) -> tuple[list[InboundEvent], str]: ...
    def resolve_conversation(self, alias: str) -> ConversationRef: ...
    def send_text(self, intent: SendIntent) -> SendResult: ...
