"""Encrypted synthetic fixtures; never open real WeChat or inject desktop events."""

import json
import os
from contextlib import ExitStack, closing
from types import SimpleNamespace

import pytest

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.mac_bridge import toolkit_module
from wechat_reply_agent.adapters.wechat.mac_db import MacAdapter
from wechat_reply_agent.adapters.wechat.mac_profile import MacProfile
from wechat_reply_agent.config import Settings
from wechat_reply_agent.domain.messages import SendIntent
from wechat_reply_agent.storage.database import Ledger


def row(local=1, sender="friend", text="same", database="message_0.db"):
    return {
        "database": database,
        "local_id": local,
        "local_type": 1,
        "create_time": 100,
        "sender_id": sender,
        "text": text,
    }


class Bridge:
    def __init__(self):
        self.rows = []
        self.salts = {"message_0.db": "salt"}
        self.attempts = 0
        self.behavior = "success"

    def connect(self):
        return {"keys": "verified"}

    def assert_session(self):
        pass

    def snapshot(self, username):
        return {
            "salts": self.salts.copy(),
            "cursor": {
                s: max((r["local_id"] for r in self.rows if r["database"] == s), default=0)
                for s in self.salts
            },
        }

    def read(self, username, after=None, limit=200):
        rows = (
            self.rows
            if after is None
            else [r for r in self.rows if r["local_id"] > after.get(r["database"], 0)]
        )
        return [
            r for name in self.salts for r in [x for x in rows if x["database"] == name][:limit]
        ]

    def send_once(self, intent):
        self.attempts += 1
        if self.behavior == "refuse":
            return {"attempted": False, "code": "draft_or_target_unverified"}
        if self.behavior == "crash":
            raise RuntimeError("PRIVATE NATIVE DATA")
        if self.behavior == "duplicate":
            self.rows.extend([row(2, "self", intent.reply_text), row(3, "self", intent.reply_text)])
        elif self.behavior == "success":
            self.rows.append(row(2, "self", intent.reply_text))
        return {"attempted": True}

    def close(self):
        pass


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "db_storage"
    root.mkdir()
    profile = MacProfile(
        account_ref="account",
        self_username="self",
        account_generation="g1",
        db_root=root,
        key_file=tmp_path / "keys.json",
        wechat_version="synthetic",
        wechat_build="1",
        account_confirmed=True,
        composer_top=0.7,
        window_width=880,
        window_height=640,
        contacts=(
            {
                "alias": "test",
                "username": "friend",
                "title": "Unique",
                "wechat_id": "native-id",
                "single_chat_confirmed": True,
            },
        ),
    )
    settings = Settings(
        _env_file=None,
        wechat_adapter="mac_db",
        data_dir=tmp_path,
        wechat_account_ref="account",
        wechat_allowlist=["test"],
        send_mode="live",
        mac_verify_timeout_seconds=1,
    )
    bridge = Bridge()
    adapter = MacAdapter(settings, profile, bridge)
    adapter.connect()
    return settings, adapter, bridge


def intent(adapter, text="reply", **updates):
    return SendIntent(
        conversation=adapter.resolve_conversation("test"),
        reply_text=text,
        mode=adapter.settings.send_mode,
        **updates,
    )


def test_baseline_paged_same_second_same_text_and_transactional_cursor(setup):
    settings, adapter, bridge = setup
    bridge.rows = [row()]
    _, baseline = adapter.poll_events()
    bridge.salts["message_1.db"] = "salt-1"
    bridge.rows.extend(row(i) for i in range(2, 405))
    bridge.rows.append(row(1, database="message_1.db"))
    events, cursor = adapter.poll_events(baseline)
    assert len(events) == 201
    assert len({e.event_id for e in events}) == 201
    assert all(e.direction == "incoming" and e.text == "same" for e in events)
    assert max(e.local_id for e in events) == 201
    with closing(Ledger(settings.data_dir / "test.sqlite3")) as ledger:
        with pytest.raises(AdapterError, match="queue_full"):
            ledger.ingest("scope", events, cursor, lambda e: True, 1)
        assert ledger.cursor("scope") is None
        replay, _ = adapter.poll_events(baseline)
        assert {e.event_id for e in events} == {e.event_id for e in replay}
    more, cursor2 = adapter.poll_events(cursor)
    last, _ = adapter.poll_events(cursor2)
    assert len(more) == 200 and len(last) == 3
    assert not ({e.event_id for e in events} & {e.event_id for e in more})


@pytest.mark.parametrize(
    "sender,kind,direction,confidence",
    [
        ("self", 1, "outgoing", 1),
        ("friend", 1, "incoming", 1),
        (None, 1, "unknown", 0),
        ("other", 1, "unknown", 0),
        ("friend", 10000, "system", 1),
    ],
)
def test_direction_requires_native_username(setup, sender, kind, direction, confidence):
    _, adapter, _ = setup
    data = row(sender=sender)
    data["local_type"] = kind
    event = adapter.normalize(adapter.resolve_conversation("test"), data)
    assert event.direction == direction and event.confidence == confidence


def test_replaced_or_regressed_source_degrades(setup):
    _, adapter, bridge = setup
    bridge.rows = [row(5)]
    _, cursor = adapter.poll_events()
    bridge.rows = []
    with pytest.raises(AdapterError, match="boundary_changed"):
        adapter.poll_events(cursor)
    assert adapter.degraded


def test_binding_cursor_is_not_transferable(setup):
    _, adapter, _ = setup
    _, cursor = adapter.poll_events()
    adapter.profile = adapter.profile.model_copy(update={"account_generation": "g2"})
    with pytest.raises(AdapterError, match="cursor_binding_changed"):
        adapter.poll_events(cursor)


def test_dry_run_has_no_native_or_receipt_side_effects(setup):
    settings, adapter, bridge = setup
    settings.send_mode = "dry-run"
    assert adapter.send_text(intent(adapter)).basis == "dry_run"
    assert not bridge.attempts and not (settings.data_dir / "macos").exists()


@pytest.mark.parametrize("text", ["x" * 201, "a\nb", "a\tb", "a\x7fb"])
def test_unsupported_prototype_output_refused_before_native_action(setup, text):
    _, adapter, bridge = setup
    result = adapter.send_text(intent(adapter, text))
    assert result.outcome == "not_sent" and result.error == "mac_prototype_text_unsupported"
    assert not bridge.attempts


def test_send_requires_new_exact_self_record_and_same_id_never_retries(setup):
    _, adapter, bridge = setup
    bridge.rows = [row(1, "self", "reply")]
    send = intent(adapter)
    result = adapter.send_text(send)
    assert result.outcome == "verified_sent" and result.basis == "local_db_confirmed"
    assert adapter.send_text(send) == result and bridge.attempts == 1


@pytest.mark.parametrize("behavior", ["old_only", "duplicate", "crash"])
def test_ambiguous_old_or_post_key_failure_stays_unknown_after_restart(setup, behavior):
    settings, adapter, bridge = setup
    bridge.rows = [row(1, "self", "reply")]
    bridge.behavior = behavior
    send = intent(adapter)
    assert adapter.send_text(send).outcome == "unknown"
    restored = MacAdapter(settings, adapter.profile, bridge)
    restored.connect()
    assert restored.send_text(send).outcome == "unknown"
    assert restored.send_text(intent(restored)).outcome == "not_sent"
    assert bridge.attempts == 1


def test_preflight_refusal_proves_no_dispatch(setup):
    _, adapter, bridge = setup
    bridge.behavior = "refuse"
    result = adapter.send_text(intent(adapter))
    assert result.outcome == "not_sent" and result.basis == "draft_or_target_unverified"


@pytest.mark.parametrize("stage", ["focus", "preflight", "timeout"])
def test_native_focus_and_preflight_failures_never_dispatch(setup, monkeypatch, stage):
    from wechat_reply_agent.adapters.wechat import mac_bridge

    settings, adapter, _ = setup
    bridge = mac_bridge.MacBridge(settings, adapter.profile)
    bridge.process = {"pid": 123}
    bridge.reader = SimpleNamespace(
        resolve=lambda title: [{"username": "friend", "remark": "Unique", "nick_name": ""}]
    )
    monkeypatch.setattr(bridge, "check", lambda: None)
    calls = []

    def native(command, **kwargs):
        calls.append(command)
        if stage == "timeout":
            raise mac_bridge.subprocess.TimeoutExpired(command, 10)
        if command[1] == "focus":
            return SimpleNamespace(
                returncode=2 if stage == "focus" else 0,
                stdout='{"type":"error","reason":"wechat_activation_failed"}',
            )
        assert "--dry-run" in command, "failed preparation must never inject input"
        return SimpleNamespace(
            returncode=2,
            stdout='{"type":"error","reason":"main_window_obscured"}',
        )

    monkeypatch.setattr(mac_bridge.subprocess, "run", native)
    result = bridge.send_once(intent(adapter))
    assert not result["attempted"]
    assert calls[0][1] == "focus"
    state = settings.data_dir / "macos/send-state"
    assert not list(state.glob("*.dispatch.json"))
    assert not list(state.glob("*.text"))
    if stage == "preflight":
        assert result["code"] == "mac_send_preflight_rejected:main_window_obscured"


def test_native_failure_never_exports_arbitrary_diagnostic_text():
    from wechat_reply_agent.adapters.wechat.mac_bridge import native_failure

    result = SimpleNamespace(
        stdout='{"type":"error","reason":"private message or key"}\n["private"]'
    )
    assert native_failure(result) == "native_command_failed"


def test_prepared_receipt_from_crash_is_never_resent(setup):
    settings, adapter, bridge = setup
    send = intent(adapter)
    import hashlib

    from wechat_reply_agent.cli import write_private

    write_private(
        settings.data_dir
        / "macos/operations"
        / f"{hashlib.sha256(send.outbox_id.encode()).hexdigest()}.json",
        {
            "payload": hashlib.sha256(send.model_dump_json().encode()).hexdigest(),
            "outbox_id": send.outbox_id,
            "status": "prepared",
        },
    )
    assert adapter.send_text(send).outcome == "unknown"
    assert bridge.attempts == 0


def test_mac_import_and_doctor_are_lazy(setup, monkeypatch):
    from wechat_reply_agent.adapters.wechat import mac_bridge

    monkeypatch.setattr(mac_bridge.platform, "system", lambda: "Linux")
    settings, adapter, _ = setup
    adapter._bridge = None
    assert not adapter.health().healthy and adapter._bridge is None
    assert mac_bridge.environment(settings) == {
        "platform": "Linux",
        "architecture": mac_bridge.platform.machine(),
        "python": mac_bridge.platform.python_version(),
        "macos": mac_bridge.platform.mac_ver()[0],
        "account_security_stop": False,
    }


def test_security_stop_blocks_connected_adapter_and_bootstrap_before_native_work(
    setup, monkeypatch
):
    from wechat_reply_agent import cli
    from wechat_reply_agent.adapters.wechat.mac_security import record_security_stop

    settings, adapter, bridge = setup
    send = intent(adapter)
    record_security_stop(settings)

    def forbidden(*args, **kwargs):
        raise AssertionError("security stop must precede native work")

    monkeypatch.setattr(bridge, "connect", forbidden)
    monkeypatch.setattr(bridge, "read", forbidden)
    with pytest.raises(AdapterError, match="mac_account_security_stop_active"):
        adapter.connect()
    with pytest.raises(AdapterError, match="mac_account_security_stop_active"):
        adapter.poll_events()
    result = adapter.send_text(send)
    assert result.outcome == "not_sent" and result.error == "mac_account_security_stop_active"
    assert bridge.attempts == 0
    monkeypatch.setattr("wechat_reply_agent.adapters.wechat.mac_bootstrap.bootstrap", forbidden)
    with pytest.raises(AdapterError, match="mac_account_security_stop_active"):
        cli.execute(SimpleNamespace(command="mac-bootstrap"), settings, adapter)


def test_security_stop_doctor_does_not_launch_helper(setup, monkeypatch):
    from wechat_reply_agent.adapters.wechat import mac_bridge
    from wechat_reply_agent.adapters.wechat.mac_security import record_security_stop

    settings, adapter, _ = setup
    record_security_stop(settings)

    def forbidden(*args, **kwargs):
        raise AssertionError("security-stop diagnosis is filesystem-only")

    monkeypatch.setattr(mac_bridge, "run", forbidden)
    health = adapter.health()
    assert not health.healthy and health.reason == "mac_account_security_stop_active"


def test_security_reset_requires_manual_confirmation_preserves_evidence_and_gates(setup):
    from wechat_reply_agent.adapters.wechat.mac_security import (
        clear_security_stop,
        require_security_clear,
        stop_path,
    )

    settings, _, _ = setup
    marker = stop_path(settings)
    marker.parent.mkdir()
    marker.write_text("unknown marker format")
    gate = settings.data_dir / "g1.json"
    gate.write_text('{"g1":"failed"}')
    with pytest.raises(AdapterError, match="mac_account_security_stop_active"):
        require_security_clear(settings)
    with pytest.raises(AdapterError, match="manual_login_confirmation_required"):
        clear_security_stop(settings)
    assert marker.exists()
    result = clear_security_stop(settings, confirmed=True)
    assert result["native_actions"] == 0 and result["gates_unchanged"]
    assert not marker.exists() and gate.read_text() == '{"g1":"failed"}'
    history = list((marker.parent / "security-history").glob("*.json"))
    assert len(history) == 1
    assert json.loads(history[0].read_text())["previous_marker"] == "unknown marker format"


def test_native_security_notice_creates_durable_stop_before_input(setup, monkeypatch):
    from wechat_reply_agent.adapters.wechat import mac_bridge
    from wechat_reply_agent.adapters.wechat.mac_security import security_stopped

    settings, adapter, _ = setup
    bridge = mac_bridge.MacBridge(settings, adapter.profile)
    bridge.process = {"pid": 123}
    bridge.reader = SimpleNamespace(
        resolve=lambda title: [{"username": "friend", "remark": "Unique", "nick_name": ""}]
    )
    monkeypatch.setattr(bridge, "check", lambda: None)

    def native(command, **kwargs):
        assert command[1] == "focus", "account-security prompt must stop before paste"
        return SimpleNamespace(
            returncode=2,
            stdout='{"type":"error","reason":"wechat_account_security_prompt"}',
        )

    monkeypatch.setattr(mac_bridge.subprocess, "run", native)
    result = bridge.send_once(intent(adapter))
    assert not result["attempted"] and security_stopped(settings)


def test_security_stop_cannot_be_bypassed_by_an_old_passing_gate(setup):
    from wechat_reply_agent.adapters.wechat.mac_acceptance import require_gate
    from wechat_reply_agent.adapters.wechat.mac_security import record_security_stop

    settings, adapter, _ = setup
    record_security_stop(settings)
    with pytest.raises(AdapterError, match="mac_account_security_stop_active"):
        require_gate(settings, adapter.profile)


def test_readonly_session_check_latches_security_prompt_without_activation(setup, monkeypatch):
    from wechat_reply_agent.adapters.wechat import mac_bridge
    from wechat_reply_agent.adapters.wechat.mac_security import security_stopped

    settings, adapter, _ = setup
    bridge = mac_bridge.MacBridge(settings, adapter.profile)
    bridge.process = {"pid": 123}
    bridge.reader = SimpleNamespace(
        resolve=lambda title: [{"username": "friend", "remark": "Unique", "nick_name": ""}]
    )
    monkeypatch.setattr(bridge, "check", lambda: None)

    def native(command, **kwargs):
        assert command[1] == "session-check"
        assert "--text" not in command and "--text-file" not in command
        return SimpleNamespace(
            returncode=2,
            stdout='{"type":"error","reason":"wechat_account_security_prompt"}',
        )

    monkeypatch.setattr(mac_bridge.subprocess, "run", native)
    with pytest.raises(AdapterError, match="mac_session_not_ready:wechat_account_security_prompt"):
        bridge.assert_session()
    assert security_stopped(settings)


def test_connect_does_not_report_connected_when_session_window_is_missing(setup, monkeypatch):
    _, adapter, bridge = setup

    def unavailable():
        raise AdapterError("mac_session_not_ready:calibrated_main_window_not_unique")

    monkeypatch.setattr(bridge, "assert_session", unavailable)
    with pytest.raises(AdapterError, match="mac_session_not_ready"):
        adapter.connect()
    assert not adapter.connected and adapter.degraded and bridge.attempts == 0


@pytest.fixture
def encrypted(tmp_path):
    sql = toolkit_module("sqlcipher_probe")
    try:
        sql.library()
    except (OSError, RuntimeError):
        pytest.skip("external SQLCipher not installed; pure adapter cases still run")
    root = tmp_path / "db_storage"
    (root / "message").mkdir(parents=True)
    (root / "contact").mkdir()
    keys = {}
    reader_module = toolkit_module("wechat_db")
    with ExitStack() as stack:
        table = "Msg_" + __import__("hashlib").md5(b"friend").hexdigest()
        writers = []
        for name in ("message_0.db", "message_1.db"):
            path = root / "message" / name
            key = os.urandom(32).hex()
            keys[str(path)] = key
            db = stack.enter_context(sql.DB(path, key, fixture_write=True))
            db.query(
                "PRAGMA journal_mode=WAL; PRAGMA wal_autocheckpoint=0; "
                "CREATE TABLE Name2Id(user_name TEXT); "
                "INSERT INTO Name2Id VALUES('self'),('friend'); "
                f'CREATE TABLE "{table}"(local_id INTEGER PRIMARY KEY, server_id INTEGER, '
                "local_type INTEGER, create_time INTEGER,real_sender_id INTEGER,"
                "message_content BLOB); PRAGMA wal_checkpoint(TRUNCATE);"
            )
            writers.append(db)
        key_file = tmp_path / "keys.json"
        key_file.write_text(json.dumps(keys))
        key_file.chmod(0o600)
        yield SimpleNamespace(
            sql=sql,
            reader=reader_module.Reader(root, key_file),
            root=root,
            writers=writers,
            table=table,
            key_file=key_file,
            keys=keys,
        )


def insert(fixture, local, text="same", shard=0):
    fixture.writers[shard].query(
        f"INSERT INTO \"{fixture.table}\" VALUES({local},0,1,100,2,x'{text.encode().hex()}')"
    )


def test_mac_local_file_and_voice_from_encrypted_resources(encrypted, tmp_path):
    from wechat_reply_agent.adapters.wechat.local_media import MacLocalMedia
    from wechat_reply_agent.domain.messages import InboundEvent, LocalAttachment

    f = encrypted
    resource = f.root / "message/message_resource.db"
    media = f.root / "media/media_0.db"
    media.parent.mkdir()
    audio = b"\x02#!SILK_V3synthetic-audio"
    schemas = {
        resource: (
            "CREATE TABLE ChatName2Id(user_name TEXT);"
            "INSERT INTO ChatName2Id VALUES('other'),('friend');"
            "CREATE TABLE MessageResourceInfo(message_id INTEGER,chat_id INTEGER,"
            "message_local_id INTEGER,message_svr_id INTEGER);"
            "CREATE TABLE MessageResourceDetail(message_id INTEGER,packed_info BLOB,size INTEGER);"
            "INSERT INTO MessageResourceInfo VALUES(1,1,1,101),(2,2,1,101);"
            "INSERT INTO MessageResourceDetail VALUES(1,x'77726f6e672e706466',4),"
            "(2,x'6f726465722e706466',4);"
        ),
        media: (
            "CREATE TABLE Name2Id(user_name TEXT);"
            "INSERT INTO Name2Id VALUES('other'),('friend');"
            "CREATE TABLE VoiceInfo(chat_name_id INTEGER,svr_id INTEGER,"
            "create_time INTEGER,voice_data BLOB);"
            f"INSERT INTO VoiceInfo VALUES(1,102,200,x'77726f6e67'),(2,102,100,x'{audio.hex()}');"
        ),
    }
    for path, schema in schemas.items():
        key = os.urandom(32).hex()
        f.keys[str(path)] = key
        with f.sql.DB(path, key, fixture_write=True) as writer:
            writer.query(schema)
    f.key_file.write_text(json.dumps(f.keys))
    f.writers[0].query(
        f"INSERT INTO \"{f.table}\" VALUES(1,101,{6 << 32 | 49},1792627200,2,x'');"
        f"INSERT INTO \"{f.table}\" VALUES(2,102,34,1792627200,2,x'');"
    )
    source = f.root.parent / "msg/file/2026-10/order(1).pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"data")
    before = {p: p.read_bytes() for p in (resource, media)}
    extractor = MacLocalMedia(f.reader, tmp_path / "private")
    for local_id, kind, expected in ((1, "file", b"data"), (2, "voice", audio)):
        event = InboundEvent(
            event_id=str(local_id),
            conversation_id="friend",
            occurrence_ref=str(local_id),
            shard="message_0.db",
            local_id=local_id,
            type=kind,
            direction="incoming",
            confidence=1,
            attachment=LocalAttachment(kind=kind),
        )
        info, ref = extractor.acquire(event)
        assert info.status == "available"
        assert __import__("pathlib").Path(ref).read_bytes() == expected
        assert info.byte_size == len(expected)
    assert {p: p.read_bytes() for p in before} == before
    # Missing audio stays a recorded unavailable attachment; it does not trigger a download.
    with f.sql.DB(media, f.keys[str(media)], fixture_write=True) as writer:
        writer.query("DELETE FROM VoiceInfo")
    info, ref = extractor.acquire(event)
    assert info.status == "missing" and info.reason == "not_downloaded" and ref is None


def test_mac_reader_exports_only_safe_file_metadata(encrypted):
    from wechat_reply_agent.adapters.wechat.local_media import describe_media

    f = encrypted
    xml = (
        "<msg><appmsg><title>order.pdf</title><type>6</type><appattach>"
        "<totallen>4</totallen><aeskey>PRIVATE</aeskey></appattach></appmsg></msg>"
    )
    f.writers[0].query(f"INSERT INTO \"{f.table}\" VALUES(1,101,49,100,2,x'{xml.encode().hex()}');")
    row = f.reader.read("friend")[0]
    assert describe_media(row).name == "order.pdf"
    assert "PRIVATE" not in json.dumps(row)


def test_real_sqlcipher_readonly_wal_commit_checkpoint_reset(encrypted):
    f = encrypted
    path = f.root / "message/message_0.db"
    main = path.read_bytes()
    insert(f, 1)
    assert path.read_bytes() == main
    assert f.reader.read("friend", self_id="self")[0]["text"] == "same"
    f.writers[0].query("BEGIN")
    insert(f, 2, "uncommitted")
    assert len(f.reader.read("friend", self_id="self")) == 1
    f.writers[0].query("ROLLBACK")
    with f.reader.open(path) as read:
        with pytest.raises(RuntimeError):
            read.query(f'DELETE FROM "{f.table}"')
    f.writers[0].query("PRAGMA wal_checkpoint(TRUNCATE)")
    insert(f, 3, "after reset")
    assert [int(r["local_id"]) for r in f.reader.read("friend", self_id="self")] == [1, 3]
    with pytest.raises(RuntimeError), f.sql.DB(path, "00" * 32):
        pass


def test_real_sqlcipher_cross_shard_pages_and_zstandard(encrypted):
    f = encrypted
    import zstandard

    for i in range(1, 204):
        insert(f, i)
    insert(f, 1, shard=1)
    raw = zstandard.ZstdCompressor().compress("压缩文本".encode())
    f.writers[1].query(f"INSERT INTO \"{f.table}\" VALUES(2,0,1,100,2,x'{raw.hex()}')")
    rows = f.reader.read(
        "friend", limit=200, after={"message_0.db": 0, "message_1.db": 0}, self_id="self"
    )
    assert len(rows) == 202
    assert (
        next(r for r in rows if r["database"] == "message_1.db" and int(r["local_id"]) == 2)["text"]
        == "压缩文本"
    )
    remaining = f.reader.read(
        "friend", limit=200, after={"message_0.db": 200, "message_1.db": 2}, self_id="self"
    )
    assert len(remaining) == 3


def test_failed_query_never_falls_back_to_old_snapshot(encrypted):
    f = encrypted
    insert(f, 1)
    assert len(f.reader.read("friend", self_id="self")) == 1
    # Correct manifest lookup with wrong key must fail on the next open.
    f.key_file.write_text(json.dumps({name: "00" * 32 for name in f.keys}))
    with pytest.raises(RuntimeError):
        f.reader.read("friend", self_id="self")


def test_native_human_resolution_never_resends_same_id(setup):
    from wechat_reply_agent.adapters.wechat.mac_db import resolve_native_operation

    settings, adapter, bridge = setup
    bridge.behavior = "crash"
    send = intent(adapter)
    assert adapter.send_text(send).outcome == "unknown"
    resolve_native_operation(settings, send.outbox_id, "discarded")
    restored = MacAdapter(settings, adapter.profile, bridge)
    restored.connect()
    assert restored.send_text(send).outcome == "unknown"
    assert bridge.attempts == 1
    # Different ID becomes possible only after manual resolution.
    bridge.behavior = "success"
    restored.connect()
    assert restored.send_text(intent(restored)).outcome == "verified_sent"
    assert bridge.attempts == 2


def test_mac_gate_rejects_windows_and_wrong_binding(setup, monkeypatch):
    from wechat_reply_agent.adapters.wechat import mac_acceptance
    from wechat_reply_agent.cli import write_private

    settings, adapter, _ = setup
    expected = {
        "plan_version": "v5",
        "platform": "macOS",
        "foundation": "mac_db",
        "binding_fingerprint": "correct",
        "input_method": "clipboard-v1",
    }
    monkeypatch.setattr(mac_acceptance, "context", lambda profile: expected)
    monkeypatch.setattr(mac_acceptance.platform, "system", lambda: "Darwin")
    path = settings.data_dir / "acceptance/mac/phase-5/g1.json"
    for invalid in (
        {"platform": "Windows", "foundation": "replica", "plan_version": "v4"},
        {"binding_fingerprint": "wrong"},
        {"recipient_confirmed": False},
        {"input_method": "unicode-events"},
        {"native_stability_verified": False},
    ):
        report = (
            expected
            | {
                "g1": "passed",
                "recipient_confirmed": True,
                "fresh_messages_verified": True,
                "native_stability_verified": True,
            }
            | invalid
        )
        write_private(path, report)
        with pytest.raises(AdapterError, match="matching_report_required"):
            mac_acceptance.require_gate(settings, adapter.profile)
    write_private(
        path,
        expected
        | {
            "g1": "passed",
            "recipient_confirmed": True,
            "fresh_messages_verified": True,
            "native_stability_verified": True,
        },
    )
    mac_acceptance.require_gate(settings, adapter.profile)


def test_degraded_mode_is_explicit_and_cannot_pass_formal_gates(setup, monkeypatch):
    from wechat_reply_agent.adapters.wechat import mac_acceptance

    settings, adapter, _ = setup
    monkeypatch.setattr(mac_acceptance.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mac_acceptance, "context", lambda p: {})
    with pytest.raises(AdapterError, match="explicit_degraded_profile_required"):
        mac_acceptance.require_degraded_prototype(settings, adapter.profile)
    profile = MacProfile.model_validate(
        adapter.profile.model_dump()
        | {"window_mode": "independent", "window_width": 598, "send_preflight": "ax-window-db"}
    )
    mac_acceptance.require_degraded_prototype(settings, profile)
    with pytest.raises(AdapterError, match="explicit_prototype_flag"):
        mac_acceptance.require_gate(settings, profile)
    from wechat_reply_agent.adapters.wechat.mac_security import record_security_stop

    record_security_stop(settings)
    with pytest.raises(AdapterError, match="security_stop_active"):
        mac_acceptance.require_degraded_prototype(settings, profile)


def test_independent_window_never_inherits_visual_main_calibration(setup):
    from pydantic import ValidationError

    _, adapter, _ = setup
    with pytest.raises(ValidationError, match="explicit degraded mode"):
        MacProfile.model_validate(adapter.profile.model_dump() | {"window_mode": "independent"})
    with pytest.raises(ValidationError, match="requires one bound independent"):
        MacProfile.model_validate(adapter.profile.model_dump() | {"send_preflight": "ax-window-db"})


def test_degraded_health_declares_missing_draft_assurance_without_screen_permission(
    setup, monkeypatch
):
    from wechat_reply_agent.adapters.wechat import mac_db

    _, adapter, _ = setup
    env = {
        "platform": "Darwin",
        "architecture": "arm64",
        "sqlcipher_available": True,
        "bridge_built": True,
        "screen_recording": False,
        "accessibility": True,
        "wechat_running": True,
        "screen_locked": False,
    }
    monkeypatch.setattr(mac_db, "environment", lambda s: env.copy())
    assert not adapter.health().healthy
    adapter.profile = MacProfile.model_validate(
        adapter.profile.model_dump()
        | {"window_mode": "independent", "window_width": 598, "send_preflight": "ax-window-db"}
    )
    health = adapter.health()
    assert health.healthy and "unverified" in health.capabilities.window_conditions
    assert health.environment["send_preflight"] == "ax-window-db"


def test_degraded_bridge_pins_same_window_mode_through_focus_preflight_and_dispatch(
    setup, monkeypatch
):
    from wechat_reply_agent.adapters.wechat import mac_bridge

    settings, adapter, _ = setup
    adapter.profile = MacProfile.model_validate(
        adapter.profile.model_dump()
        | {"window_mode": "independent", "window_width": 598, "send_preflight": "ax-window-db"}
    )
    bridge = mac_bridge.MacBridge(settings, adapter.profile)
    bridge.process = {"pid": 123}
    bridge.reader = SimpleNamespace(
        resolve=lambda title: [{"username": "friend", "remark": "Unique", "nick_name": ""}]
    )
    monkeypatch.setattr(bridge, "check", lambda: None)
    commands = []

    def native(command, **kwargs):
        commands.append(command)
        assert command[command.index("--window-mode") + 1] == "independent"
        assert command[command.index("--chat") + 1] == "Unique"
        if command[1] == "send":
            assert command[command.index("--preflight") + 1] == "ax-window-db"
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(mac_bridge.subprocess, "run", native)
    assert bridge.send_once(intent(adapter))["attempted"]
    assert [c[1] for c in commands] == ["focus", "send", "send"]
    assert "--dry-run" in commands[1] and "--dry-run" not in commands[2]


def test_connect_does_not_bootstrap_or_load_gui_if_profile_missing(setup):
    settings, _, _ = setup
    from wechat_reply_agent.cli import create_adapter

    adapter = create_adapter(settings, profile_required=False)
    assert adapter.profile is None and adapter._bridge is None
    with pytest.raises(AdapterError, match="account_binding_required"):
        adapter.connect()
    assert adapter._bridge is None


def test_bootstrap_refuses_running_original_before_any_copy(tmp_path, monkeypatch):
    from wechat_reply_agent.adapters.wechat import mac_bootstrap

    monkeypatch.setattr(mac_bootstrap.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mac_bootstrap.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(mac_bootstrap.os, "geteuid", lambda: 501)
    monkeypatch.setattr(
        mac_bootstrap.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0)
    )
    with pytest.raises(AdapterError, match="quit_wechat_normally"):
        mac_bootstrap.bootstrap(tmp_path, tmp_path / "state")
    assert not (tmp_path / "state").exists()


def test_cli_resolves_native_and_application_receipts_without_actions(setup):
    from wechat_reply_agent.cli import execute, parser

    settings, adapter, bridge = setup
    bridge.behavior = "crash"
    send = intent(adapter)
    assert adapter.send_text(send).outcome == "unknown"
    with closing(Ledger(settings.data_dir / "prototype.sqlite3")) as ledger:
        ledger.db.execute(
            "INSERT INTO outbox(id,input_key,scope,intent,state,created) VALUES(?,?,?,?,?,?)",
            (send.outbox_id, "input", "scope", send.model_dump_json(), "unknown", 0),
        )
        ledger.db.commit()
    args = parser().parse_args(
        ["resolve", "--ledger", "--outbox-id", send.outbox_id, "--resolution", "discarded"]
    )
    assert execute(args, settings, adapter) == 0
    assert bridge.attempts == 1
    with closing(Ledger(settings.data_dir / "prototype.sqlite3")) as ledger:
        assert (
            ledger.db.execute(
                "SELECT resolution FROM outbox WHERE id=?", (send.outbox_id,)
            ).fetchone()[0]
            == "discarded"
        )


def test_known_crash_blocks_bootstrap_before_running_any_native_command(tmp_path, monkeypatch):
    from wechat_reply_agent.adapters.wechat import mac_bootstrap
    from wechat_reply_agent.cli import write_private

    monkeypatch.setattr(mac_bootstrap.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mac_bootstrap.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(mac_bootstrap.os, "geteuid", lambda: 501)
    write_private(tmp_path / "bootstrap-blocked.json", {"reason": "native_debugger_crashed"})

    def forbidden(*args, **kwargs):
        raise AssertionError("native execution must remain disabled")

    monkeypatch.setattr(mac_bootstrap.subprocess, "run", forbidden)
    with pytest.raises(AdapterError, match="mac_lldb_repair_required"):
        mac_bootstrap.bootstrap(tmp_path, tmp_path / "new-attempt")


@pytest.mark.parametrize("change", ["account", "original", "temporary", "keys_exist"])
def test_prepared_bootstrap_rejects_changed_binding(tmp_path, change):
    import hashlib

    from wechat_reply_agent.adapters.wechat.mac_bootstrap import prepared_report
    from wechat_reply_agent.cli import write_private

    root = tmp_path / "db_storage"
    state = tmp_path / "bootstrap"
    executable = state / "WeChat-trial.app/Contents/MacOS/WeChat"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"owned temporary fixture")
    report = {
        "db_root": str(root),
        "original_executable_sha256": "original-hash",
        "temporary_executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
    }
    write_private(state / "bootstrap.json", report)
    assert prepared_report(root, state, "original-hash") == report
    if change == "account":
        root = tmp_path / "other_account"
    elif change == "original":
        report["original_executable_sha256"] = "changed"
        write_private(state / "bootstrap.json", report)
    elif change == "temporary":
        executable.write_bytes(b"changed temporary fixture")
    else:
        (state / "keys.json").write_text("{}")
    with pytest.raises(AdapterError, match="prepared_copy_binding_invalid"):
        prepared_report(root, state, "original-hash")


def test_reader_excludes_fts_and_resource_databases(encrypted):
    fixture = encrypted
    insert(fixture, 1)
    # These are independent WCDB indexes/resources, not numbered message shards.
    # An unavailable key or custom tokenizer here must not block the selected chat.
    for name in ("message_fts.db", "message_resource.db"):
        (fixture.root / "message" / name).write_bytes(b"unrelated encrypted data")
    assert len(fixture.reader.read("friend", self_id="self")) == 1
    assert set(fixture.reader.snapshot("friend")["cursor"]) == {"message_0.db", "message_1.db"}


def test_prepared_bootstrap_accepts_same_pinned_copy_after_user_move(tmp_path):
    import hashlib

    from wechat_reply_agent.adapters.wechat.mac_bootstrap import prepared_report
    from wechat_reply_agent.cli import write_private

    root, state = tmp_path / "db_storage", tmp_path / "private-state"
    moved = tmp_path / "Downloads/WeChat-trial.app"
    executable = moved / "Contents/MacOS/WeChat"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"exact owned copy")
    report = {
        "db_root": str(root),
        "original_executable_sha256": "original",
        "temporary_executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
    }
    write_private(state / "bootstrap.json", report)
    assert prepared_report(root, state, "original", moved) == report
    assert executable.read_bytes() == b"exact owned copy"
