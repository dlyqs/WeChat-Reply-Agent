import json
import subprocess
import sys

import pytest

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.replica import ReplicaAdapter
from wechat_reply_agent.adapters.wechat.replica_profile import ReplicaContact, ReplicaProfile
from wechat_reply_agent.config import Settings
from wechat_reply_agent.domain.messages import Direction, SendIntent


def row(local_id=1, seq=10, shard="message_0.db", sender="friend", text="same", **extra):
    return dict(
        local_id=local_id,
        sort_seq=seq,
        shard=shard,
        sender_username=sender,
        content=text,
        type="text",
        **extra,
    )


class Bridge:
    def __init__(self):
        self.rows = [row()]
        self.after = []
        self.sent = 0
        self.reads = 0
        self.fail_read = False
        self.receipt = {"attempted": True, "code": "enter_invoked"}

    def connect(self):
        return {"account": "verified"}

    def read(self, username, since=None, limit=10000):
        self.reads += 1
        if self.fail_read:
            raise RuntimeError("PRIVATE_NATIVE_ERROR")
        return [r for r in self.rows if since is None or r["sort_seq"] >= since]

    def send_once(self, title, text):
        self.sent += 1
        if isinstance(self.receipt, Exception):
            raise self.receipt
        return self.receipt

    def wait_new(self, username, since, predicate):
        return next((r for r in self.after if predicate(r)), None)


@pytest.fixture
def replica(tmp_path):
    (tmp_path / "account" / "db_storage").mkdir(parents=True)
    settings = Settings(
        _env_file=None,
        wechat_adapter="replica",
        data_dir=tmp_path,
        wechat_allowlist=["test"],
        send_mode="live",
    )
    profile = ReplicaProfile(
        account_ref=settings.wechat_account_ref,
        account="account",
        self_username="self",
        account_generation="gen1",
        db_root=tmp_path,
        account_confirmed=True,
        wechat_version="offline",
        contacts=(
            ReplicaContact(
                alias="test", username="friend", title="Unique", single_chat_confirmed=True
            ),
        ),
    )
    bridge = Bridge()
    adapter = ReplicaAdapter(settings, profile, bridge)
    adapter.connect()
    return adapter, bridge


def intent(adapter, mode="live"):
    return SendIntent(
        conversation=adapter.resolve_conversation("test"), reply_text="same", mode=mode
    )


def test_import_and_doctor_never_import_native():
    code = """
import sys
from wechat_reply_agent.adapters.wechat.replica import ReplicaAdapter
from wechat_reply_agent.config import Settings
ReplicaAdapter(Settings(_env_file=None)).health()
assert not any(n.startswith(('wechatauto.', 'uiautomation', 'AppKit')) for n in sys.modules)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "sender,numeric,expected",
    [
        ("friend", 2, Direction.INCOMING),
        ("self", 99, Direction.OUTGOING),
        ("", 2, Direction.UNKNOWN),
        ("unrelated", 2, Direction.UNKNOWN),
    ],
)
def test_direction_uses_native_shard_identity(replica, sender, numeric, expected):
    a, _ = replica
    ref = a.resolve_conversation("test")
    event = a.normalize(ref, row(sender=sender, sender_id=numeric))
    assert event.direction == expected
    assert event.source_message_id == event.occurrence_ref


def test_equal_sequence_across_polls_and_shards(replica):
    a, b = replica
    first, cursor = a.poll_events()
    assert len(first) == 1
    b.rows += [row(local_id=2), row(shard="message_1.db")]
    second, cursor = a.poll_events(cursor)
    assert len(second) == 2
    assert len({e.source_message_id for e in first + second}) == 3
    assert a.poll_events(cursor)[0] == []
    b.rows.append(row(local_id=3, seq=11))
    assert len(a.poll_events(cursor)[0]) == 1


def test_cursor_generation_rejects(replica):
    a, _ = replica
    with pytest.raises(AdapterError, match="cursor_invalid"):
        a.poll_events(json.dumps({"generation": "old", "sessions": {}}))
    assert a.degraded


def test_missing_source_identity_does_not_guess(replica):
    a, b = replica
    b.rows = [row(shard="")]
    with pytest.raises(AdapterError, match="source_identity_missing"):
        a.poll_events()


def test_read_failure_degrades_without_raw_exception(replica):
    a, b = replica
    b.fail_read = True
    with pytest.raises(AdapterError, match="^replica_read_failed_degraded$"):
        a.poll_events()
    assert a.degraded


def test_dry_run_has_no_native_calls(replica):
    a, b = replica
    a.settings.send_mode = "dry-run"
    assert a.send_text(intent(a, "dry-run")).basis == "dry_run"
    assert b.sent == b.reads == 0


def test_watermark_failure_never_sends(replica):
    a, b = replica
    b.fail_read = True
    result = a.send_text(intent(a))
    assert result.outcome == "not_sent" and b.sent == 0


@pytest.mark.parametrize(
    "after",
    [
        [row(sender="self")],  # old identical text
        [row(local_id=2, sender="friend", sender_id=2)],  # numeric 2 is not self
        [row(local_id=2, sender="self", text="same suffix")],
        [row(local_id=2, sender="self", seq=9)],
        [],
    ],
)
def test_old_or_wrong_readback_is_unknown(replica, after):
    a, b = replica
    b.rows = [row(sender="self")]
    b.after = after
    assert a.send_text(intent(a)).outcome == "unknown"
    assert b.sent == 1 and a.degraded
    assert a.send_text(intent(a)).outcome == "not_sent"
    assert b.sent == 1


def test_new_self_same_sequence_different_shard_confirms(replica):
    a, b = replica
    b.after = [row(shard="message_1.db", sender="self")]
    result = a.send_text(intent(a))
    assert result.outcome == "verified_sent" and result.basis == "local_db_confirmed"
    assert result.evidence_ref and b.sent == 1


def test_native_exception_after_enter_never_retries(replica):
    a, b = replica
    b.receipt = RuntimeError("PRIVATE_TEXT")
    result = a.send_text(intent(a))
    assert result.outcome == "unknown" and b.sent == 1
    assert "PRIVATE" not in result.model_dump_json()


@pytest.mark.parametrize(
    "code", ["target_mismatch", "draft_or_target_unverified", "focus_or_content_mismatch"]
)
def test_pre_enter_refusal_is_not_sent(replica, code):
    a, b = replica
    b.receipt = {"attempted": False, "code": code}
    assert a.send_text(intent(a)).outcome == "not_sent"
    assert b.sent == 1


@pytest.mark.parametrize("username", ["group@chatroom", "self"])
def test_group_and_self_refuse(replica, username):
    a, b = replica
    contact = a.profile.contacts[0].model_copy(update={"username": username})
    a.profile = a.profile.model_copy(update={"contacts": (contact,)})
    with pytest.raises(AdapterError, match="single_friend_chat_required"):
        a.resolve_conversation("test")
    assert b.sent == 0


def test_whitelist_is_required(replica):
    a, _ = replica
    a.settings.wechat_allowlist = []
    with pytest.raises(AdapterError, match="contact_not_allowlisted"):
        a.resolve_conversation("test")
