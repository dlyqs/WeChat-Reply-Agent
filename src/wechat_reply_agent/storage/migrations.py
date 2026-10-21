"""Additive migrations retain Phase 2 message IDs, intents, context and cursors."""

from wechat_reply_agent.adapters.wechat.base import AdapterError


def migrate(db):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version > 3:
        raise AdapterError("database_version_unsupported")
    if version == 3:
        return
    if version < 2:
        migrate_v2(db)
    with db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS knowledge_documents(
            id TEXT PRIMARY KEY, name TEXT NOT NULL, digest TEXT UNIQUE NOT NULL,
            byte_size INTEGER NOT NULL, chunk_count INTEGER NOT NULL, created REAL NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS knowledge_chunks(
            id TEXT PRIMARY KEY, document_id TEXT NOT NULL
            REFERENCES knowledge_documents(id) ON DELETE CASCADE,
            ordinal INTEGER NOT NULL, content TEXT NOT NULL)""")
        db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
            USING fts5(chunk_id UNINDEXED, tokens, tokenize='unicode61')""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS knowledge_chunk_delete
            AFTER DELETE ON knowledge_chunks BEGIN
            DELETE FROM knowledge_fts WHERE chunk_id=OLD.id; END""")
        db.execute("""CREATE TABLE IF NOT EXISTS memories(
            scope TEXT NOT NULL, contact TEXT NOT NULL, key TEXT NOT NULL,
            value TEXT NOT NULL, source TEXT NOT NULL, updated REAL NOT NULL,
            PRIMARY KEY(scope,contact,key))""")
        db.execute("PRAGMA user_version=3")


def migrate_v2(db):
    with db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("PRAGMA user_version").fetchone()[0] >= 2:
            return
        db.execute("CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        db.execute("""CREATE TABLE IF NOT EXISTS contacts(
            scope TEXT NOT NULL, alias TEXT NOT NULL, username TEXT NOT NULL,
            PRIMARY KEY(scope,alias), UNIQUE(scope,username))""")
        db.execute("""CREATE TABLE IF NOT EXISTS conversations(
            id TEXT NOT NULL, scope TEXT NOT NULL, account_ref TEXT NOT NULL,
            PRIMARY KEY(scope,id))""")
        db.execute("""CREATE TABLE IF NOT EXISTS messages(
            id TEXT PRIMARY KEY REFERENCES inbox(id), conversation TEXT NOT NULL,
            scope TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL)""")
        db.execute("INSERT OR IGNORE INTO messages SELECT * FROM inbox")
        db.execute("""INSERT OR IGNORE INTO conversations
            SELECT DISTINCT conversation,scope,json_extract(payload,'$.account_ref') FROM inbox""")
        db.execute("CREATE INDEX IF NOT EXISTS inbox_queue ON inbox(scope,status)")
        db.execute("CREATE INDEX IF NOT EXISTS messages_page ON messages(scope,conversation)")
        db.execute("ALTER TABLE runtime_state ADD COLUMN state TEXT NOT NULL DEFAULT 'stopped'")
        db.execute("ALTER TABLE runtime_state ADD COLUMN reason TEXT NOT NULL DEFAULT 'recovered'")
        db.execute("""CREATE TRIGGER IF NOT EXISTS inbox_status_update
            AFTER UPDATE OF status ON inbox
            BEGIN UPDATE messages SET status=NEW.status WHERE id=NEW.id; END""")
        db.execute("PRAGMA user_version=2")


def bind_identity(db, fingerprint, account_ref=None, generation=None):
    with db:
        if (
            account_ref
            and db.execute(
                "SELECT 1 FROM inbox WHERE json_extract(payload,'$.account_ref')!=? "
                "OR json_extract(payload,'$.account_generation')!=? LIMIT 1",
                (account_ref, generation),
            ).fetchone()
        ):
            raise AdapterError("account_or_database_binding_changed")
        old = db.execute("SELECT value FROM metadata WHERE key='binding'").fetchone()
        if old and old[0] != fingerprint:
            raise AdapterError("account_or_database_binding_changed")
        db.execute("INSERT OR IGNORE INTO metadata VALUES('binding',?)", (fingerprint,))
