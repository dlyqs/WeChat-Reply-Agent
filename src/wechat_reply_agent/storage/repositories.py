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
             WHERE i.scope=c.scope AND i.conversation=c.id AND NOT EXISTS
             (SELECT 1 FROM history_redactions h
              WHERE h.kind='inbox' AND h.record_id=i.id)) message_count
            FROM conversations c LEFT JOIN contacts ct ON ct.scope=c.scope AND ct.username=c.id
            WHERE EXISTS (SELECT 1 FROM inbox i WHERE i.scope=c.scope AND i.conversation=c.id
                AND NOT EXISTS (SELECT 1 FROM history_redactions h
                                WHERE h.kind='inbox' AND h.record_id=i.id))
            ORDER BY c.scope,c.id LIMIT ? OFFSET ?""",
            (limit, offset),
        )

    def messages(self, conversation, scope, limit, offset):
        rows = self.read(
            "SELECT id,payload,status FROM inbox WHERE conversation=? AND scope=? "
            "AND NOT EXISTS (SELECT 1 FROM history_redactions h "
            "WHERE h.kind='inbox' AND h.record_id=inbox.id) "
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

    def outbox(self, limit, offset, scope=None, conversation=None):
        rows = self.read(
            "SELECT id,scope,intent,state,result,created,resolution FROM outbox "
            "WHERE NOT EXISTS (SELECT 1 FROM history_redactions h "
            "WHERE h.kind='outbox' AND h.record_id=outbox.id) "
            "AND (? IS NULL OR scope=?) AND (? IS NULL OR "
            "json_extract(intent,'$.conversation.conversation_id')=?) "
            "ORDER BY created DESC LIMIT ? OFFSET ?",
            (scope, scope, conversation, conversation, limit, offset),
        )
        for row in rows:
            intent = json.loads(row.pop("intent"))
            result = json.loads(row.pop("result") or "{}")
            row.update(
                conversation_id=intent["conversation"]["conversation_id"],
                reply_text=intent["reply_text"],
                mode=intent["mode"],
                input_refs=intent["input_event_refs"],
                basis=result.get("basis"),
            )
        return rows

    def runs(self, limit, offset):
        rows = self.read(
            "SELECT * FROM agent_runs WHERE NOT EXISTS (SELECT 1 FROM history_redactions h "
            "WHERE h.kind='run' AND h.record_id=CAST(agent_runs.id AS TEXT)) "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
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
        rows = self.read(
            "SELECT * FROM agent_runs WHERE id=? AND NOT EXISTS "
            "(SELECT 1 FROM history_redactions h WHERE h.kind='run' "
            "AND h.record_id=CAST(agent_runs.id AS TEXT))",
            (trace_id,),
        )
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

    def dashboard(self):
        return self.read("""SELECT
            (SELECT count(*) FROM inbox i WHERE NOT EXISTS (SELECT 1 FROM history_redactions h
                WHERE h.kind='inbox' AND h.record_id=i.id)) messages,
            (SELECT count(*) FROM outbox o WHERE NOT EXISTS (SELECT 1 FROM history_redactions h
                WHERE h.kind='outbox' AND h.record_id=o.id)) replies,
            (SELECT count(*) FROM agent_runs a WHERE NOT EXISTS (SELECT 1 FROM history_redactions h
                WHERE h.kind='run' AND h.record_id=CAST(a.id AS TEXT))) runs,
            (SELECT count(*) FROM memories) memories,
            (SELECT count(*) FROM outbox WHERE state IN ('unknown','paused')
                AND resolution IS NULL) unresolved,
            (SELECT avg(model_ms) FROM agent_runs a WHERE NOT EXISTS
                (SELECT 1 FROM history_redactions h WHERE h.kind='run'
                 AND h.record_id=CAST(a.id AS TEXT))) model_ms""")[0]

    def clear_history(self, scope=None, conversation=None, forget_memories=False):
        if bool(scope) != bool(conversation):
            raise AdapterError("history_selection_invalid")
        inbox_where = "(? IS NULL OR (scope=? AND conversation=?))"
        outbox_where = (
            "(? IS NULL OR (scope=? AND json_extract(intent,'$.conversation.conversation_id')=?))"
        )
        args = (scope, scope, conversation)
        run_where = """(? IS NULL OR (scope=? AND EXISTS (
            SELECT 1 FROM json_each(agent_runs.input_refs) r JOIN inbox i ON i.id=r.value
            WHERE i.conversation=? AND i.scope=agent_runs.scope)))"""
        ledger = Ledger(self.path)
        try:
            with ledger.db:
                ledger.db.execute("BEGIN IMMEDIATE")
                if ledger.db.execute(
                    "SELECT 1 FROM outbox WHERE "
                    + outbox_where
                    + " AND state IN ('pending','sending','unknown','paused') "
                    "AND resolution IS NULL LIMIT 1",
                    args,
                ).fetchone():
                    raise AdapterError("history_unresolved_outbox")
                counts = {}
                for kind, table, where in (
                    ("inbox", "inbox", inbox_where),
                    ("outbox", "outbox", outbox_where),
                    ("run", "agent_runs", run_where),
                ):
                    ids = ledger.db.execute(
                        "SELECT id FROM "
                        + table
                        + " WHERE "
                        + where
                        + " AND NOT EXISTS (SELECT 1 FROM history_redactions h WHERE h.kind=? "
                        "AND h.record_id=CAST(" + table + ".id AS TEXT))",
                        (*args, kind),
                    ).fetchall()
                    counts[kind] = len(ids)
                    ledger.db.executemany(
                        "INSERT OR IGNORE INTO history_redactions VALUES(?,?)",
                        [(kind, str(row[0])) for row in ids],
                    )
                ledger.db.execute(
                    "UPDATE inbox SET payload=json_set(payload,'$.text',NULL,"
                    "'$.attachment_ref',NULL),status='cleared' WHERE " + inbox_where,
                    args,
                )
                ledger.db.execute(
                    "UPDATE messages SET payload=json_set(payload,'$.text',NULL,"
                    "'$.attachment_ref',NULL),status='cleared' WHERE " + inbox_where,
                    args,
                )
                ledger.db.execute(
                    "UPDATE outbox SET intent=json_set(intent,'$.reply_text','[已清除]') "
                    "WHERE " + outbox_where,
                    args,
                )
                ledger.db.execute(
                    "UPDATE agent_runs SET result=json_set(result,'$.reply_text',NULL,"
                    "'$.sources',json('[]')) WHERE " + run_where,
                    args,
                )
                ledger.db.execute("DELETE FROM context WHERE " + inbox_where, args)
                counts["memories"] = 0
                if forget_memories:
                    counts["memories"] = ledger.db.execute(
                        "DELETE FROM memories WHERE (? IS NULL OR (scope=? AND contact=?))", args
                    ).rowcount
            return {
                "cleared": counts,
                "deduplication_preserved": True,
                "knowledge_preserved": True,
                "wechat_unchanged": True,
            }
        finally:
            ledger.close()
