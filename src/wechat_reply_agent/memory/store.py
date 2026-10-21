"""Only explicit preference commands can create durable facts; no model extraction."""

import re
import time

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.storage.database import Ledger

MAX_FACTS = 20


def validate_fact(key, value=None):
    if (
        not isinstance(key, str)
        or not key.strip()
        or key != key.strip()
        or not re.fullmatch(r"[\w\u4e00-\u9fff -]{1,40}", key)
    ):
        raise AdapterError("memory_fact_invalid")
    if value is not None and (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 200
        or any(ord(c) < 32 for c in value)
    ):
        raise AdapterError("memory_fact_invalid")


def commands(events):
    changes = []
    for event in events:
        text = (event.text or "").strip()
        found = re.fullmatch(r"(?:请)?(?:记住|更正)我的偏好[：:]\s*([^=＝]+)[=＝](.+)", text)
        forgotten = re.fullmatch(r"(?:请)?忘记我的偏好[：:]\s*(.+)", text)
        try:
            if found:
                key, value = (s.strip() for s in found.groups())
                validate_fact(key, value)
                changes.append({"key": key, "value": value})
            elif forgotten:
                key = forgotten[1].strip()
                validate_fact(key)
                changes.append({"key": key, "value": None})
        except AdapterError:
            continue
    return changes[:4]


def apply_changes(db, scope, contact, changes, source):
    for change in changes:
        key, value = change["key"], change["value"]
        validate_fact(key, value)
        if value is None:
            db.execute(
                "DELETE FROM memories WHERE scope=? AND contact=? AND key=?", (scope, contact, key)
            )
        else:
            exists = db.execute(
                "SELECT 1 FROM memories WHERE scope=? AND contact=? AND key=?",
                (scope, contact, key),
            ).fetchone()
            count = db.execute(
                "SELECT count(*) FROM memories WHERE scope=? AND contact=?", (scope, contact)
            ).fetchone()[0]
            if not exists and count >= MAX_FACTS:
                raise AdapterError("memory_capacity_reached")
            db.execute(
                """INSERT INTO memories VALUES(?,?,?,?,?,?)
                ON CONFLICT(scope,contact,key) DO UPDATE SET value=excluded.value,
                source=excluded.source,updated=excluded.updated""",
                (scope, contact, key, value.strip(), source, time.time()),
            )


class MemoryStore:
    def __init__(self, path):
        self.path = path

    @staticmethod
    def require_contact(db, scope, contact):
        if not db.execute(
            "SELECT 1 FROM contacts WHERE scope=? AND username=?", (scope, contact)
        ).fetchone():
            raise AdapterError("memory_contact_not_found")

    def contacts(self):
        ledger = Ledger(self.path)
        try:
            return [
                dict(r)
                for r in ledger.db.execute(
                    "SELECT scope,alias,username AS contact FROM contacts ORDER BY scope,alias"
                )
            ]
        finally:
            ledger.close()

    def read(self, scope, contact):
        ledger = Ledger(self.path)
        try:
            self.require_contact(ledger.db, scope, contact)
            return [
                dict(r)
                for r in ledger.db.execute(
                    "SELECT key,value,source,updated FROM memories WHERE scope=? AND contact=? "
                    "ORDER BY key LIMIT ?",
                    (scope, contact, MAX_FACTS),
                )
            ]
        finally:
            ledger.close()

    def change(self, scope, contact, key, value):
        ledger = Ledger(self.path)
        try:
            with ledger.db:
                ledger.db.execute("BEGIN IMMEDIATE")
                self.require_contact(ledger.db, scope, contact)
                apply_changes(
                    ledger.db, scope, contact, [{"key": key, "value": value}], "workbench"
                )
                # Old prompt history must not reintroduce a corrected or forgotten preference.
                ledger.db.execute(
                    "DELETE FROM context WHERE scope=? AND conversation=?", (scope, contact)
                )
        finally:
            ledger.close()
