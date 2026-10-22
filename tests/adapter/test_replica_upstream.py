"""Exercise the actual vendored methods with SQLite/desktop doubles, on every OS."""

import ast
import glob
import os
import shutil
import sqlite3
import sys
import threading
import types
from pathlib import Path

import pytest

VENDOR = Path(__file__).resolve().parents[2] / "third_party/wechatauto_replica/wechatauto"


def method(file, cls, name, **namespace):
    module = ast.parse((VENDOR / file).read_text(encoding="utf-8"))
    node = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == cls)
    function = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == name)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    tree = ast.fix_missing_locations(ast.Module(body=[future, function], type_ignores=[]))
    exec(compile(tree, str(VENDOR / file), "exec"), namespace)
    return namespace[name]


def test_replica_media_uses_real_vendor_extractors_with_exact_shard(tmp_path, monkeypatch):
    import re

    from wechat_reply_agent.adapters.wechat.local_media import ReplicaLocalMedia
    from wechat_reply_agent.domain.messages import InboundEvent, LocalAttachment

    audio = b"\x02#!SILK_V3synthetic"
    media = tmp_path / "media_0.db"
    resources = tmp_path / "message_resource.db"
    with sqlite3.connect(media) as conn:
        conn.executescript(
            "CREATE TABLE Name2Id(user_name TEXT); INSERT INTO Name2Id VALUES('friend');"
            "CREATE TABLE VoiceInfo(chat_name_id,svr_id,create_time,voice_data);"
        )
        conn.execute("INSERT INTO VoiceInfo VALUES(1,101,100,?)", (audio,))
    with sqlite3.connect(resources) as conn:
        conn.executescript(
            "CREATE TABLE MessageResourceInfo(message_id,message_svr_id);"
            "CREATE TABLE MessageResourceDetail(message_id,packed_info);"
            "INSERT INTO MessageResourceInfo VALUES(1,102);"
        )
        conn.execute("INSERT INTO MessageResourceDetail VALUES(1,?)", (b"order.pdf",))
    file = tmp_path / "account/msg/file/2026-10/order (1).pdf"
    file.parent.mkdir(parents=True)
    file.write_bytes(b"data")
    calls = []

    class DB:
        account_dir = str(tmp_path / "account")
        _db_files = [(p.name, str(p), 0) for p in (media, resources)]

        def _open(self, rel):
            conn = sqlite3.connect(tmp_path / rel)
            conn.row_factory = sqlite3.Row
            return conn

        def get_message_row(self, user, local, local_type=None, shard=None):
            calls.append((user, local, shard))
            assert shard == "message__message_1.db"
            return {
                "server_id": 100 + local,
                "local_type": 34 if local == 1 else 6 << 32 | 49,
                "create_time": 1792627200,
                "content": None,
            }

    downloader = type(
        "Downloader",
        (),
        {
            "__init__": lambda self, db, **kwargs: setattr(self, "db", db),
            "download_voice": method("media.py", "MediaDownloader", "download_voice", os=os),
            "_file_name": method("media.py", "MediaDownloader", "_file_name", os=os, re=re),
        },
    )
    monkeypatch.setitem(
        sys.modules, "wechatauto.media", types.SimpleNamespace(MediaDownloader=downloader)
    )
    extractor = ReplicaLocalMedia(DB(), tmp_path / "private")
    for local, kind, expected in ((1, "voice", audio), (2, "file", b"data")):
        event = InboundEvent(
            event_id=str(local),
            conversation_id="friend",
            occurrence_ref=str(local),
            local_id=local,
            shard="message__message_1.db",
            type=kind,
            direction="incoming",
            confidence=1,
            attachment=LocalAttachment(kind=kind, byte_size=4 if kind == "file" else None),
        )
        info, ref = extractor.acquire(event)
        assert info.status == "available" and Path(ref).read_bytes() == expected
    assert all(shard == "message__message_1.db" for _, _, shard in calls)


def test_inclusive_sql_and_cross_shard_order_and_overflow():
    scan = method("db.py", "WeChatDB", "scan_messages_inclusive")
    conns = []
    for shard in ("a", "b"):
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.execute("CREATE TABLE msgs(sort_seq INTEGER, local_id INTEGER, shard TEXT)")
        c.executemany(
            "INSERT INTO msgs VALUES (?,?,?)", [(9, 1, shard), (10, 2, shard), (10, 3, shard)]
        )
        conns.append((c, "msgs"))

    class DB:
        _MSG_ORDER_ASC = "ORDER BY sort_seq ASC, local_id ASC"

        def _run_msg_query(self, user, build):
            return build(conns)

        def _shard_rows(self, tables, sql, args, order_ext, per_shard_limit):
            return [
                r
                for c, t in tables
                for r in c.execute(
                    f"SELECT * FROM {t} {sql} ORDER BY sort_seq,local_id LIMIT ?",
                    (*args, per_shard_limit),
                )
            ]

        def _shard_maps(self, tables):
            return {}

        def _msg_row_to_dict(self, row, maps):
            return dict(row)

    try:
        assert [(r["shard"], r["local_id"]) for r in scan(DB(), "friend", 10)] == [
            ("a", 2),
            ("a", 3),
            ("b", 2),
            ("b", 3),
        ]
        with pytest.raises(RuntimeError, match="scan_overflow"):
            scan(DB(), "friend", 10, limit=3)
    finally:
        for c, _ in conns:
            c.close()


@pytest.mark.parametrize("wal_failure", [False, True])
def test_strict_snapshot_does_not_fall_back_to_old_database(tmp_path, wal_failure):
    db_path = tmp_path / "encrypted.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE messages(id INTEGER)")
    conn.commit()
    conn.close()
    work = tmp_path / "private"
    work.mkdir()
    shutil.copyfile(db_path, work / "message.db")  # old valid snapshot
    wal = tmp_path / "source-wal"
    wal.write_bytes(b"x" * 100)

    class DB:
        strict_account = True
        _keys = {"message.db": b"x" * 32}
        workdir = str(work)
        WAL_HEADER_SZ = 32

        def _db_path(self, rel):
            return str(db_path)

        def _wal_path(self, rel):
            return str(wal) if wal_failure else None

        def _decrypt_file(self, src, dst, key):
            shutil.copyfile(src, dst)

        def _check_merged(self, path):
            return wal_failure

        def _merge_wal(self, *args):
            raise RuntimeError("corrupt WAL")

    open_db = method(
        "db.py",
        "WeChatDB",
        "_open_unlocked",
        os=os,
        glob=glob,
        time=types.SimpleNamespace(time=lambda: 0, sleep=lambda _: None),
        threading=threading,
        sqlite3=sqlite3,
        shutil=shutil,
        STAMP_VERSION=3,
        wxlog=types.SimpleNamespace(debug=lambda *a: None),
    )
    with pytest.raises(
        RuntimeError, match="wal_merge_failed" if wal_failure else "snapshot_validation_failed"
    ):
        open_db(DB(), "message.db")


def test_strict_account_disables_both_fallbacks():
    db = types.SimpleNamespace(strict_account=True)
    assert method("db.py", "WeChatDB", "_try_other_accounts")(db) is False
    assert method("db.py", "WeChatDB", "_select_account_by_keys")(db, [b"x"]) is False
    db.workdir = "/private/data"
    assert method("db.py", "WeChatDB", "_stable_key_dirs", os=os)(db) == [
        os.path.join("/private/data", "stable-keys")
    ]


@pytest.mark.parametrize("enter_error", [False, True])
def test_actual_native_send_method_enters_at_most_once(enter_error):
    calls = []

    class Edit:
        HasKeyboardFocus = True
        value = ""

        def SendKeys(self, key, **kwargs):
            calls.append(key)
            if enter_error:
                raise RuntimeError("after Enter")

    e = Edit()
    uia = types.SimpleNamespace(
        current_chat=lambda: "Unique",
        _chat_input=lambda: e,
        _read_edit_value=lambda edit: edit.value,
        _paste_into=lambda edit, text, **kw: setattr(edit, "value", text),
    )
    gui = types.SimpleNamespace(
        ensure_visible=lambda: True,
        _get_uia=lambda: uia,
        main_hwnd=123,
        _input=types.SimpleNamespace(
            _user32=types.SimpleNamespace(GetForegroundWindow=lambda: 123)
        ),
    )
    send = method(
        "guia.py", "WeChatGUI", "send_text_once", time=types.SimpleNamespace(sleep=lambda _: None)
    )
    result = send(gui, "test", "Unique")
    assert result["attempted"] is True and calls == ["{Enter}"]
    e.value = "user draft"
    result = send(gui, "test", "Unique")
    assert result["attempted"] is False and calls == ["{Enter}"]
