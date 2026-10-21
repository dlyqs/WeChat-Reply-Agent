"""Bounded read models and manual resolution for the local workbench."""

import json

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.storage.database import Ledger


class Repository:
    def __init__(self, path):
        self.path = path

    def read(self, sql, params=()):
        ledger = Ledger(self.path)
        try:
            return [dict(row) for row in ledger.db.execute(sql, params)]
        finally:
            ledger.close()

    def conversations(self, limit, offset):
        return self.read(
            """SELECT c.id,c.scope,c.account_ref,ct.alias,
            (SELECT count(*) FROM inbox i
             WHERE i.scope=c.scope AND i.conversation=c.id) message_count
            FROM conversations c LEFT JOIN contacts ct ON ct.scope=c.scope AND ct.username=c.id
            ORDER BY c.scope,c.id LIMIT ? OFFSET ?""",
            (limit, offset),
        )

    def messages(self, conversation, scope, limit, offset):
        rows = self.read(
            "SELECT id,payload,status FROM inbox WHERE conversation=? AND scope=? "
            "ORDER BY rowid DESC LIMIT ? OFFSET ?",
            (conversation, scope, limit, offset),
        )
        return [
            {
                "id": r["id"],
                "status": r["status"],
                **{
                    key: json.loads(r["payload"]).get(key)
                    for key in ("text", "direction", "type", "observed_at")
                },
            }
            for r in rows
        ]

    def outbox(self, limit, offset):
        rows = self.read(
            "SELECT id,scope,intent,state,result,created,resolution FROM outbox "
            "ORDER BY created DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        for row in rows:
            intent = json.loads(row.pop("intent"))
            result = json.loads(row.pop("result") or "{}")
            row.update(
                reply_text=intent["reply_text"],
                mode=intent["mode"],
                input_refs=intent["input_event_refs"],
                basis=result.get("basis"),
            )
        return rows

    def runs(self, limit, offset):
        rows = self.read(
            "SELECT * FROM agent_runs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        )
        return [self.run_view(row) for row in rows]

    @staticmethod
    def run_view(row):
        result = json.loads(row["result"])
        return {
            "trace_id": str(row["id"]),
            "scope": row["scope"],
            "input_refs": json.loads(row["input_refs"]),
            "status": result["status"],
            "reason": result.get("reason"),
            "reply_text": result.get("reply_text"),
            "sources": result.get("sources", []),
            "knowledge_status": result.get("knowledge_status", "disabled"),
            "model_ms": row["model_ms"],
            "poll_ms": row["poll_ms"],
            "send_ms": row["send_ms"],
        }

    def run(self, trace_id):
        rows = self.read("SELECT * FROM agent_runs WHERE id=?", (trace_id,))
        if not rows:
            raise AdapterError("run_not_found")
        return self.run_view(rows[0])

    def recover(self):
        ledger = Ledger(self.path)
        try:
            try:
                ledger.begin_run()
            except AdapterError:
                pass  # Unknown remains durable and blocks the next start.
            with ledger.db:
                ledger.db.execute("UPDATE runtime_state SET state='stopped',reason='recovered'")
        finally:
            ledger.close()

    def runtime_state(self, state, reason):
        ledger = Ledger(self.path)
        try:
            with ledger.db:
                ledger.db.execute("UPDATE runtime_state SET state=?,reason=?", (state, reason))
            return ledger.db.execute("SELECT generation FROM runtime_state").fetchone()[0]
        finally:
            ledger.close()

    def resolve(self, outbox_id, resolution):
        ledger = Ledger(self.path)
        try:
            ledger.resolve(outbox_id, resolution)
        finally:
            ledger.close()
