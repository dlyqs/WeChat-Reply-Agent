"""Replica normalization and fail-closed send evidence, independent of native imports."""

import hashlib
import json

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.replica_bridge import ReplicaBridge, environment
from wechat_reply_agent.domain.messages import (
    AdapterCapabilities,
    ConversationRef,
    Direction,
    Health,
    InboundEvent,
    SendResult,
)


def row_key(row):
    if (
        not row.get("shard")
        or not isinstance(row.get("local_id"), int)
        or row["local_id"] <= 0
        or not isinstance(row.get("sort_seq"), int)
    ):
        raise AdapterError("source_identity_missing")
    return f"{row['shard']}:{row['local_id']}"


class ReplicaAdapter:
    def __init__(self, settings, profile=None, bridge=None):
        self.settings, self.profile = settings, profile
        self._bridge = bridge
        self.connected = False
        self.degraded = False

    def health(self):
        env = environment()
        ready = (
            env["platform"] == "Windows"
            and env["python_x64"]
            and env["replica_installed"]
            and env["wechat_running"]
        )
        return Health(
            healthy=bool(ready),
            reason="environment_ready_connect_required" if ready else "environment_unavailable",
            environment=env,
            capabilities=AdapterCapabilities(
                profile="replica-v1",
                identity="explicit account + native single-chat username",
                direction_basis="shard Name2Id sender_username",
                tested=False,
                send_confirmation="new exact self record: local_db_confirmed; recipient unverified",
            ),
        )

    def validate_profile(self):
        p = self.profile
        if not p or not p.account_confirmed or p.account_ref != self.settings.wechat_account_ref:
            raise AdapterError("account_binding_required")
        if (
            self.settings.wechat_db_root
            and self.settings.wechat_db_root.resolve() != p.db_root.resolve()
        ):
            raise AdapterError("database_root_mismatch")
        if not (p.db_root / p.account / "db_storage").is_dir():
            raise AdapterError("database_root_missing")

    def connect(self):
        self.validate_profile()
        if self._bridge is None:
            self._bridge = ReplicaBridge(self.settings, self.profile)
        try:
            result = self._bridge.connect()
            self.connected, self.degraded = True, False
            return result
        except Exception as exc:
            self.connected, self.degraded = False, True
            if isinstance(exc, AdapterError):
                raise
            raise AdapterError("replica_connect_failed") from None

    def resolve_conversation(self, alias):
        self.validate_profile()
        if alias not in self.settings.wechat_allowlist:
            raise AdapterError("contact_not_allowlisted")
        contacts = [c for c in self.profile.contacts if c.alias == alias]
        if len(contacts) != 1 or not contacts[0].single_chat_confirmed:
            raise AdapterError("contact_binding_required")
        c = contacts[0]
        if c.username.endswith("@chatroom") or c.username == self.profile.self_username:
            raise AdapterError("single_friend_chat_required")
        return ConversationRef(
            account_ref=self.profile.account_ref,
            conversation_id=c.username,
            contact_alias=c.alias,
            profile=self.profile.name,
            identity_basis="verified native username + unique exact contact title",
            confidence=1,
        )

    def normalize(self, ref, row):
        key = row_key(row)
        p = self.profile
        sender = row.get("sender_username") or ""
        text_type = row.get("type") in ("文本", "text", 1)
        direction = Direction.UNKNOWN
        if row.get("type") in ("系统消息", "system", 10000):
            direction = Direction.SYSTEM
        elif sender == p.self_username:
            direction = Direction.OUTGOING
        elif sender == ref.conversation_id:
            direction = Direction.INCOMING
        native_id = json.dumps([p.account_generation, p.account_ref, ref.conversation_id, key])
        source_id = hashlib.sha256(native_id.encode()).hexdigest()
        return InboundEvent(
            event_id=source_id,
            source_message_id=source_id,
            occurrence_ref=source_id,
            account_ref=p.account_ref,
            account_generation=p.account_generation,
            native_session=ref.conversation_id,
            conversation_id=ref.conversation_id,
            shard=row["shard"],
            local_id=row["local_id"],
            sort_seq=row["sort_seq"],
            sender_username=sender or None,
            direction=direction,
            type="text"
            if text_type
            else ("system" if direction == Direction.SYSTEM else "unknown"),
            text=row.get("content") if text_type and isinstance(row.get("content"), str) else None,
            confidence=1 if sender and direction != Direction.UNKNOWN else 0,
        )

    def _read(self, username, since=None, limit=10000):
        if not self.connected or self.degraded:
            raise AdapterError("replica_not_connected")
        try:
            return self._bridge.read(username, since, limit)
        except Exception:
            self.degraded = True
            raise AdapterError("replica_read_failed_degraded") from None

    def poll_events(self, cursor=None):
        try:
            state = (
                json.loads(cursor)
                if cursor
                else {"generation": self.profile.account_generation, "sessions": {}}
            )
            if state["generation"] != self.profile.account_generation:
                raise ValueError
            events = []
            for alias in self.settings.wechat_allowlist:
                ref = self.resolve_conversation(alias)
                mark = state["sessions"].get(ref.conversation_id)
                rows = self._read(ref.conversation_id, mark["seq"] if mark else None)
                rows = sorted(rows, key=lambda r: (r["sort_seq"], r["shard"], r["local_id"]))
                if mark and rows and max(r["sort_seq"] for r in rows) < mark["seq"]:
                    raise AdapterError("database_boundary_changed")
                for row in rows:
                    if not mark or row_key(row) not in mark["ids"]:
                        events.append(self.normalize(ref, row))
                if rows:
                    seq = max(r["sort_seq"] for r in rows)
                    state["sessions"][ref.conversation_id] = {
                        "seq": seq,
                        "ids": sorted(row_key(r) for r in rows if r["sort_seq"] == seq),
                    }
            return events, json.dumps(state, sort_keys=True)
        except (KeyError, ValueError, TypeError):
            self.degraded = True
            raise AdapterError("cursor_invalid") from None

    def send_text(self, intent):
        try:
            ref = self.resolve_conversation(intent.conversation.contact_alias)
            if ref != intent.conversation:
                raise AdapterError("target_mismatch")
            if intent.mode != self.settings.send_mode:
                raise AdapterError("mode_mismatch")
            if intent.mode == "dry-run":
                return SendResult(outcome="not_sent", basis="dry_run")
            if not self.connected or self.degraded:
                raise AdapterError("replica_not_connected")
            before = self._read(ref.conversation_id)
            # Even an empty valid query is a valid watermark for a brand-new chat.
            ids = {row_key(r) for r in before}
            seq = max((r["sort_seq"] for r in before), default=0)
            title = next(c.title for c in self.profile.contacts if c.alias == ref.contact_alias)
        except AdapterError as exc:
            return SendResult(outcome="not_sent", basis=str(exc), error=str(exc))
        # From here an unclassified native exception may follow Enter: always unknown.
        try:
            receipt = self._bridge.send_once(title, intent.reply_text)
            if not receipt["attempted"]:
                return SendResult(outcome="not_sent", basis=receipt["code"], error=receipt["code"])

            def match(row):
                return (
                    row_key(row) not in ids
                    and row["sort_seq"] >= seq
                    and row.get("sender_username") == self.profile.self_username
                    and row.get("type") in ("文本", "text", 1)
                    and row.get("content") == intent.reply_text
                )

            row = self._bridge.wait_new(ref.conversation_id, seq, match)
            if row:
                event = self.normalize(ref, row)
                return SendResult(
                    outcome="verified_sent",
                    basis="local_db_confirmed",
                    evidence_ref=event.source_message_id,
                )
        except Exception:
            pass
        self.degraded = True
        return SendResult(outcome="unknown", basis="send_unconfirmed_stop_required")
