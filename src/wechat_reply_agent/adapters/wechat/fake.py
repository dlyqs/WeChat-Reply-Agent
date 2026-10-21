"""Deterministic offline adapter. Never imports native dependencies."""

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.domain.messages import AdapterCapabilities, Health, SendResult


class FakeAdapter:
    def __init__(self, conversations=(), events=()):
        self.conversations = tuple(conversations)
        self.events = list(events)
        self.sent = []

    def health(self):
        return Health(
            healthy=True,
            reason="offline_fake",
            environment={"offline": True},
            capabilities=AdapterCapabilities(profile="fake", tested=False),
        )

    def resolve_conversation(self, alias):
        found = [c for c in self.conversations if c.contact_alias == alias]
        if len(found) != 1 or found[0].confidence != 1:
            raise AdapterError("identity_uncertain")
        return found[0]

    def poll_events(self, cursor=None):
        return list(self.events), "offline-snapshot"

    def send_text(self, intent):
        ref = self.resolve_conversation(intent.conversation.contact_alias)
        if ref != intent.conversation:
            raise AdapterError("identity_changed")
        if intent.mode == "dry-run":
            return SendResult(outcome="not_sent", basis="offline_dry_run")
        self.sent.append(intent)
        return SendResult(outcome="verified_sent", basis="offline_fake_only")
