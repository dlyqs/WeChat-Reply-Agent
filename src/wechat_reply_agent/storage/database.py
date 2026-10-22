"""Application ledger: versioned migration and transactional poll/cursor commits."""

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.domain.messages import InboundEvent
from wechat_reply_agent.privacy import private_directory


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        private_directory(path.parent)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        if os.name != "nt":
            for private in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
                try:
                    private.chmod(0o600)
                except FileNotFoundError:
                    pass
        if self.db.execute("PRAGMA user_version").fetchone()[0] > 4:
            self.db.close()
            raise AdapterError("database_version_unsupported")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS inbox(
          id TEXT PRIMARY KEY, conversation TEXT NOT NULL, scope TEXT NOT NULL,
          payload TEXT NOT NULL, status TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cursors(scope TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox(
          id TEXT PRIMARY KEY, input_key TEXT UNIQUE NOT NULL, scope TEXT NOT NULL,
          intent TEXT NOT NULL, state TEXT NOT NULL, result TEXT,
          created REAL NOT NULL, attempted_at REAL, resolution TEXT);
        CREATE TABLE IF NOT EXISTS outbox_inputs(
          input_id TEXT PRIMARY KEY REFERENCES inbox(id),
          outbox_id TEXT NOT NULL REFERENCES outbox(id));
        CREATE TABLE IF NOT EXISTS context(
          id INTEGER PRIMARY KEY, scope TEXT NOT NULL, conversation TEXT NOT NULL,
          role TEXT NOT NULL, content TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_runs(
          id INTEGER PRIMARY KEY, scope TEXT NOT NULL, input_refs TEXT NOT NULL,
          result TEXT NOT NULL, model_ms REAL NOT NULL, poll_ms REAL NOT NULL, send_ms REAL);
        CREATE TABLE IF NOT EXISTS runtime_state(
          id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL);
        INSERT OR IGNORE INTO runtime_state(id,generation) VALUES(1,0);

        """)
        from wechat_reply_agent.storage.migrations import migrate

        try:
            migrate(self.db)
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def begin_run(self):
        with self.db:
            self.db.execute(
                "UPDATE inbox SET status='paused' WHERE status IN ('pending','processing')"
            )
            self.db.execute("UPDATE outbox SET state='paused' WHERE state='pending'")
            self.db.execute("UPDATE outbox SET state='unknown' WHERE state='sending'")
            self.db.execute("UPDATE runtime_state SET generation=generation+1")
        if self.db.execute(
            "SELECT 1 FROM outbox WHERE state IN ('unknown','paused') AND resolution IS NULL"
        ).fetchone():
            raise AdapterError("unresolved_outbox_stop_required")
        return self.db.execute("SELECT generation FROM runtime_state").fetchone()[0]

    def ingest(self, scope, events, cursor, eligible, queue_max, baseline=False):
        added = 0
        with self.db:
            for event in events:
                status = "baseline" if baseline else ("pending" if eligible(event) else "filtered")
                cur = self.db.execute(
                    "INSERT OR IGNORE INTO inbox VALUES(?,?,?,?,?)",
                    (event.event_id, event.conversation_id, scope, event.model_dump_json(), status),
                )
                if cur.rowcount:
                    self.db.execute(
                        "INSERT OR IGNORE INTO conversations(id,scope,account_ref) VALUES(?,?,?)",
                        (event.conversation_id, scope, event.account_ref),
                    )
                    self.db.execute(
                        "INSERT INTO messages(id,conversation,scope,payload,status) "
                        "VALUES(?,?,?,?,?)",
                        (
                            event.event_id,
                            event.conversation_id,
                            scope,
                            event.model_dump_json(),
                            status,
                        ),
                    )
                added += cur.rowcount if status == "pending" else 0
            pending = self.db.execute(
                "SELECT count(*) FROM inbox WHERE status='pending'"
            ).fetchone()[0]
            if pending > queue_max:
                raise AdapterError("queue_full_degraded")
            self.db.execute(
                "INSERT INTO cursors VALUES(?,?) ON CONFLICT(scope) "
                "DO UPDATE SET value=excluded.value",
                (scope, cursor),
            )
        return added

    def cursor(self, scope):
        row = self.db.execute("SELECT value FROM cursors WHERE scope=?", (scope,)).fetchone()
        return row[0] if row else None

    def attachment_candidates(self, scope, now, limit=5):
        rows = self.db.execute(
            "SELECT payload FROM inbox WHERE scope=? AND status!='cleared' "
            "AND json_extract(payload,'$.attachment.kind') IN ('file','voice') "
            "AND coalesce(json_extract(payload,'$.attachment.checked_at'),0) <= ? "
            "AND NOT EXISTS (SELECT 1 FROM history_redactions h "
            "WHERE h.kind='inbox' AND h.record_id=inbox.id) "
            "ORDER BY coalesce(json_extract(payload,'$.attachment.checked_at'),0),"
            "rowid DESC LIMIT ?",
            (scope, now - 30, limit),
        ).fetchall()
        return [InboundEvent.model_validate_json(r[0]) for r in rows]

    def record_attachment(self, event_id, attachment, attachment_ref):
        with self.db:
            for table in ("inbox", "messages"):
                self.db.execute(
                    f"UPDATE {table} SET payload=json_set(payload,'$.attachment',json(?),"
                    "'$.attachment_ref',?) WHERE id=? AND status!='cleared' "
                    "AND NOT EXISTS (SELECT 1 FROM history_redactions h "
                    "WHERE h.kind='inbox' AND h.record_id=?)",
                    (attachment.model_dump_json(), attachment_ref, event_id, event_id),
                )

    def batch(self, scope, window_ms):
        rows = self.db.execute(
            "SELECT payload FROM inbox WHERE scope=? AND status='pending' ORDER BY rowid", (scope,)
        ).fetchall()
        if not rows:
            return []
        first = InboundEvent.model_validate_json(rows[0][0])
        batch = [first]
        anchor = first.source_created_at or first.observed_at.timestamp()
        for row in rows[1:]:
            event = InboundEvent.model_validate_json(row[0])
            timestamp = event.source_created_at or event.observed_at.timestamp()
            if (
                event.conversation_id != first.conversation_id
                or abs(timestamp - anchor) * 1000 > window_ms
            ):
                break
            batch.append(event)
        return batch

    def history(self, scope, conversation):
        rows = self.db.execute(
            "SELECT role,content FROM (SELECT * FROM context WHERE scope=? AND conversation=? "
            "ORDER BY id DESC LIMIT 40) ORDER BY id",
            (scope, conversation),
        ).fetchall()
        return [dict(r) for r in rows]

    def finish_model(self, scope, batch, result, intent, model_ms, poll_ms):
        refs = [e.event_id for e in batch]
        key = hashlib.sha256(json.dumps(sorted(refs)).encode()).hexdigest()
        with self.db:
            if intent and result.memory_actions:
                from wechat_reply_agent.memory.store import apply_changes

                apply_changes(
                    self.db, scope, batch[0].conversation_id, result.memory_actions, "explicit_chat"
                )
                self.db.execute(
                    "DELETE FROM context WHERE scope=? AND conversation=?",
                    (scope, batch[0].conversation_id),
                )
            run = self.db.execute(
                "INSERT INTO agent_runs(scope,input_refs,result,model_ms,poll_ms) "
                "VALUES(?,?,?,?,?)",
                (scope, json.dumps(refs), result.model_dump_json(), model_ms, poll_ms),
            )
            for ref in refs:
                self.db.execute(
                    "UPDATE inbox SET status=? WHERE id=?",
                    (
                        "processed"
                        if intent
                        else "paused"
                        if result.status == "cancelled"
                        else "failed",
                        ref,
                    ),
                )
            if intent:
                self.db.execute(
                    "INSERT INTO outbox VALUES(?,?,?,?,?,?,?,NULL,NULL)",
                    (
                        intent.outbox_id,
                        key,
                        scope,
                        intent.model_dump_json(),
                        "pending",
                        None,
                        time.time(),
                    ),
                )
                for ref in refs:
                    self.db.execute(
                        "INSERT INTO outbox_inputs VALUES(?,?)", (ref, intent.outbox_id)
                    )
        return run.lastrowid

    def can_send(self, now, min_interval, max_per_minute):
        row = self.db.execute("SELECT max(attempted_at) FROM outbox").fetchone()
        if row[0] is not None and now - row[0] < min_interval:
            return False
        count = self.db.execute(
            "SELECT count(*) FROM outbox WHERE attempted_at>?", (now - 60,)
        ).fetchone()[0]
        return count < max_per_minute

    def sending(self, outbox_id, now):
        with self.db:
            cur = self.db.execute(
                "UPDATE outbox SET state='sending',attempted_at=? WHERE id=? AND state='pending'",
                (now, outbox_id),
            )
            if cur.rowcount != 1:
                raise AdapterError("outbox_not_pending")

    def sent(self, scope, intent, batch, result, run_id, send_ms):
        with self.db:
            self.db.execute(
                "UPDATE outbox SET state=?,result=? WHERE id=?",
                (result.outcome, result.model_dump_json(), intent.outbox_id),
            )
            self.db.execute("UPDATE agent_runs SET send_ms=? WHERE id=?", (send_ms, run_id))
            if result.outcome == "verified_sent" or (
                intent.mode == "dry-run" and result.basis == "dry_run"
            ):
                for role, content in [
                    ("user", "\n".join(e.text for e in batch)),
                    ("assistant", intent.reply_text),
                ]:
                    self.db.execute(
                        "INSERT INTO context(scope,conversation,role,content) VALUES(?,?,?,?)",
                        (scope, intent.conversation.conversation_id, role, content),
                    )

    def resolve(self, outbox_id, resolution):
        if resolution not in ("sent", "discarded"):
            raise AdapterError("resolution_invalid")
        with self.db:
            cur = self.db.execute(
                "UPDATE outbox SET resolution=? "
                "WHERE id=? AND state IN ('unknown','paused') AND resolution IS NULL",
                (resolution, outbox_id),
            )
            if cur.rowcount != 1:
                raise AdapterError("unknown_outbox_missing")

    def summary(self, scope):
        return {
            "inbox": dict(
                self.db.execute(
                    "SELECT status,count(*) FROM inbox WHERE scope=? GROUP BY status", (scope,)
                ).fetchall()
            ),
            "outbox": dict(
                self.db.execute(
                    "SELECT state,count(*) FROM outbox WHERE scope=? GROUP BY state", (scope,)
                ).fetchall()
            ),
            "timings": [
                dict(r)
                for r in self.db.execute(
                    "SELECT id,model_ms,poll_ms,send_ms FROM agent_runs WHERE scope=?", (scope,)
                )
            ],
        }
