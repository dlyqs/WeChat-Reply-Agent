"""Mac structured events and durable, single-attempt sends; no GUI success shortcuts."""

import hashlib
import json
import time

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.mac_bridge import MacBridge, environment
from wechat_reply_agent.adapters.wechat.mac_security import require_security_clear
from wechat_reply_agent.domain.messages import (
    AdapterCapabilities,
    ConversationRef,
    Direction,
    Health,
    InboundEvent,
    SendResult,
)


def row_key(row):
    try:
        local = int(row["local_id"])
        shard = row["database"]
        if local <= 0 or not shard or "/" in shard:
            raise ValueError
        return shard, local
    except (KeyError, ValueError, TypeError):
        raise AdapterError("source_identity_missing") from None


class MacAdapter:
    def __init__(self, settings, profile=None, bridge=None):
        self.settings, self.profile, self._bridge = settings, profile, bridge
        self.connected = self.degraded = False

    def health(self):
        env = environment(self.settings)
        degraded_ui = self.profile is not None and self.profile.send_preflight == "ax-window-db"
        if self.profile:
            env.update(
                send_preflight=self.profile.send_preflight, window_mode=self.profile.window_mode
            )
        ready = (
            env.get("platform") == "Darwin"
            and env.get("architecture") == "arm64"
            and all(
                env.get(k)
                for k in (
                    "sqlcipher_available",
                    "bridge_built",
                    "accessibility",
                    "wechat_running",
                )
            )
            and (degraded_ui or env.get("screen_recording"))
            and not env.get("screen_locked", True)
        )
        return Health(
            healthy=bool(ready),
            reason="mac_account_security_stop_active"
            if env.get("account_security_stop")
            else "environment_ready_connect_required"
            if ready
            else "environment_unavailable",
            environment=env,
            capabilities=AdapterCapabilities(
                profile="mac-db-v1",
                identity="explicit original process/account + native friend username",
                direction_basis="per-shard Name2Id mapping",
                send_confirmation="new exact self record: local_db_confirmed; recipient unverified",
                window_conditions=(
                    "explicit degraded mode; unique focused independent AX window; "
                    "draft, pasted text and occlusion unverified; DB confirmation only; "
                    "<=200 single-line characters"
                    if degraded_ui
                    else "manual preselected single friend; raise the bound main window; "
                    "frontmost unobscured main window; "
                    "<=200 characters, single line, exact OCR draft; no navigation"
                ),
                tested=False,
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
        if not p.db_root.is_dir():
            raise AdapterError("database_root_missing")
        try:
            list(p.db_root.iterdir())
        except PermissionError:
            raise AdapterError("mac_database_access_denied_full_disk_access_required") from None
        private = self.settings.data_dir.resolve()
        if not p.key_file.resolve().is_relative_to(private):
            raise AdapterError("mac_keys_must_be_in_private_data_dir")

    def connect(self):
        require_security_clear(self.settings)
        self.validate_profile()
        if self._bridge is None:
            self._bridge = MacBridge(self.settings, self.profile)
        try:
            result = self._bridge.connect()
            self._bridge.assert_session()
            self.connected, self.degraded = True, False
            return result
        except Exception as exc:
            self.connected, self.degraded = False, True
            if isinstance(exc, AdapterError):
                raise
            raise AdapterError("mac_connect_failed") from None

    def close(self):
        if self._bridge:
            self._bridge.close()
        self.connected = False

    def resolve_conversation(self, alias):
        self.validate_profile()
        if alias not in self.settings.wechat_allowlist:
            raise AdapterError("contact_not_allowlisted")
        contacts = [c for c in self.profile.contacts if c.alias == alias]
        if len(contacts) != 1 or not contacts[0].single_chat_confirmed:
            raise AdapterError("contact_binding_required")
        return ConversationRef(
            account_ref=self.profile.account_ref,
            conversation_id=contacts[0].username,
            contact_alias=alias,
            profile=self.profile.name,
            identity_basis="original process account + verified native username + unique title",
            confidence=1,
        )

    def _ready(self):
        require_security_clear(self.settings)
        if not self.connected or self.degraded:
            raise AdapterError("mac_not_connected")
        try:
            self._bridge.assert_session()
        except AdapterError:
            self.degraded = True
            raise

    def normalize(self, ref, row):
        shard, local_id = row_key(row)
        p = self.profile
        sender = row.get("sender_id")
        kind = int(row["local_type"])
        direction = (
            Direction.SYSTEM
            if kind == 10000
            else Direction.OUTGOING
            if sender == p.self_username
            else Direction.INCOMING
            if sender == ref.conversation_id
            else Direction.UNKNOWN
        )
        source = hashlib.sha256(
            json.dumps(
                [
                    "mac_db",
                    p.account_generation,
                    p.account_ref,
                    ref.conversation_id,
                    shard,
                    local_id,
                ]
            ).encode()
        ).hexdigest()
        return InboundEvent(
            event_id=source,
            source_message_id=source,
            occurrence_ref=source,
            account_ref=p.account_ref,
            account_generation=p.account_generation,
            native_session=ref.conversation_id,
            conversation_id=ref.conversation_id,
            shard=shard,
            local_id=local_id,
            sort_seq=int(row["create_time"]),
            source_created_at=int(row["create_time"]),
            sender_username=sender,
            direction=direction,
            type="text" if kind == 1 else "system" if kind == 10000 else "unknown",
            text=row.get("text") if kind == 1 else None,
            confidence=1 if direction != Direction.UNKNOWN else 0,
        )

    @staticmethod
    def check_boundary(before, now):
        for shard, salt in before["salts"].items():
            if (
                now["salts"].get(shard) != salt
                or now["cursor"].get(shard, -1) < before["cursor"][shard]
            ):
                raise AdapterError("database_boundary_changed")

    def read_recent(self, alias, limit=5):
        self._ready()
        ref = self.resolve_conversation(alias)
        return [
            self.normalize(ref, row) for row in self._bridge.read(ref.conversation_id, limit=limit)
        ]

    def poll_events(self, cursor=None):
        self._ready()
        try:
            p = self.profile
            state = (
                json.loads(cursor)
                if cursor
                else {
                    "version": 1,
                    "generation": p.account_generation,
                    "binding": p.fingerprint(),
                    "sessions": {},
                }
            )
            if (
                state["version"] != 1
                or state["generation"] != p.account_generation
                or state["binding"] != p.fingerprint()
            ):
                raise AdapterError("cursor_binding_changed")
            events = []
            for alias in self.settings.wechat_allowlist:
                ref = self.resolve_conversation(alias)
                now = self._bridge.snapshot(ref.conversation_id)
                mark = state["sessions"].get(ref.conversation_id)
                if mark is None:
                    if cursor is not None:
                        raise AdapterError("cursor_binding_changed")
                    # Baseline does not import history. New commits after this watermark remain new.
                    state["sessions"][ref.conversation_id] = now
                    continue
                self.check_boundary(mark, now)
                rows = self._bridge.read(ref.conversation_id, after=mark["cursor"], limit=200)
                # Per-shard pages advance only through returned rows, never to snapshot max.
                next_mark = {"salts": now["salts"], "cursor": dict(mark["cursor"])}
                for row in rows:
                    shard, local = row_key(row)
                    if local <= mark["cursor"].get(shard, 0):
                        raise AdapterError("database_boundary_changed")
                    events.append(self.normalize(ref, row))
                    next_mark["cursor"][shard] = max(local, next_mark["cursor"].get(shard, 0))
                self.check_boundary(mark, self._bridge.snapshot(ref.conversation_id))
                state["sessions"][ref.conversation_id] = next_mark
            return events, json.dumps(state, sort_keys=True)
        except Exception as exc:
            self.degraded = True
            if isinstance(exc, AdapterError):
                raise
            raise AdapterError("mac_read_failed_degraded") from None

    def send_text(self, intent):
        if intent.mode == "dry-run":
            return self._send_text(intent)
        from wechat_reply_agent.cli import probe_lock

        try:
            with probe_lock(self.settings.data_dir / "macos/operation-lock"):
                return self._send_text(intent)
        except AdapterError as exc:
            return SendResult(outcome="not_sent", basis=str(exc), error=str(exc))

    def _send_text(self, intent):
        from wechat_reply_agent.cli import write_private

        try:
            if intent.mode != "dry-run":
                require_security_clear(self.settings)
            ref = self.resolve_conversation(intent.conversation.contact_alias)
            if ref != intent.conversation:
                raise AdapterError("target_mismatch")
            if intent.mode != self.settings.send_mode:
                raise AdapterError("mode_mismatch")
            text = intent.reply_text
            if len(text) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in text):
                raise AdapterError("mac_prototype_text_unsupported")
            if intent.mode == "dry-run":
                return SendResult(outcome="not_sent", basis="dry_run")
            self._ready()
            if any(
                value is None
                for value in (
                    self.profile.composer_top,
                    self.profile.window_width,
                    self.profile.window_height,
                )
            ):
                raise AdapterError("mac_composer_calibration_required")
            directory = self.settings.data_dir / "macos/operations"
            path = directory / f"{hashlib.sha256(intent.outbox_id.encode()).hexdigest()}.json"
            payload = hashlib.sha256(intent.model_dump_json().encode()).hexdigest()
            if path.exists():
                previous = json.loads(path.read_text())
                if previous.get("payload") != payload:
                    raise AdapterError("outbox_id_payload_changed")
                if previous.get("result"):
                    return SendResult.model_validate(previous["result"])
                self.degraded = True
                return SendResult(outcome="unknown", basis="previous_attempt_stop_required")
            # An unresolved native receipt blocks subsequent IDs, including direct callers.
            for old in directory.glob("*.json"):
                record = json.loads(old.read_text())
                if not record.get("resolution") and (
                    not record.get("result") or record["result"]["outcome"] == "unknown"
                ):
                    raise AdapterError("unresolved_native_operation_stop_required")
            baseline = self._bridge.snapshot(ref.conversation_id)
            record = {
                "payload": payload,
                "outbox_id": intent.outbox_id,
                "baseline": baseline,
                "status": "prepared",
                "send_preflight": self.profile.send_preflight,
                "window_mode": self.profile.window_mode,
                "ui_checks_degraded": self.profile.send_preflight != "visual",
            }
            write_private(path, record)
        except Exception as exc:
            code = str(exc) if isinstance(exc, AdapterError) else "mac_send_preparation_failed"
            return SendResult(outcome="not_sent", basis=code, error=code)
        try:
            receipt = self._bridge.send_once(intent)
            if not receipt["attempted"]:
                result = SendResult(
                    outcome="not_sent", basis=receipt["code"], error=receipt["code"]
                )
            else:
                deadline = time.monotonic() + self.settings.mac_verify_timeout_seconds
                while True:
                    self.check_boundary(baseline, self._bridge.snapshot(ref.conversation_id))
                    # A full page cannot establish uniqueness; retain unknown for manual review.
                    rows = self._bridge.read(
                        ref.conversation_id, after=baseline["cursor"], limit=1000
                    )
                    matches = [
                        r
                        for r in rows
                        if int(r["local_id"]) > baseline["cursor"].get(r["database"], 0)
                        and r.get("sender_id") == self.profile.self_username
                        and int(r["local_type"]) == 1
                        and r.get("text") == text
                    ]
                    if (
                        any(
                            sum(r["database"] == name for r in rows) >= 1000
                            for name in {r["database"] for r in rows}
                        )
                        or len(matches) > 1
                    ):
                        raise AdapterError("ambiguous_send_confirmation")
                    if len(matches) == 1:
                        result = SendResult(
                            outcome="verified_sent",
                            basis="local_db_confirmed",
                            evidence_ref=self.normalize(ref, matches[0]).source_message_id,
                        )
                        break
                    if time.monotonic() >= deadline:
                        raise AdapterError("send_verification_timeout")
                    time.sleep(0.5)
        except Exception:
            self.degraded = True
            result = SendResult(outcome="unknown", basis="send_unconfirmed_stop_required")
        record.update(result=result.model_dump(), status=result.outcome)
        write_private(path, record)
        return result


def resolve_native_operation(settings, outbox_id, resolution):
    """Journal-only human resolution: no native calls, key lookup or resend."""
    from wechat_reply_agent.cli import write_private

    path = (
        settings.data_dir
        / "macos/operations"
        / (hashlib.sha256(outbox_id.encode()).hexdigest() + ".json")
    )
    if path.exists():
        record = json.loads(path.read_text())
        if record.get("outbox_id") != outbox_id or resolution not in ("sent", "discarded"):
            raise AdapterError("native_resolution_invalid")
        record["resolution"] = resolution
        write_private(path, record)
