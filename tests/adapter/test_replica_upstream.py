"""Exercise the actual vendored methods with SQLite/desktop doubles, on every OS."""

import ast
import glob
import os
import shutil
import sqlite3
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
