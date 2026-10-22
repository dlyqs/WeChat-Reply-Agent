"""Bounded imports and Chinese FTS5 retrieval with stable source references."""

import hashlib
import logging
import re
import threading
import time
from pathlib import PurePosixPath
from uuid import uuid4

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.storage.database import Ledger

MAX_DOCUMENT_BYTES = 48_000
MAX_DOCUMENTS = 200
MAX_TOTAL_BYTES = 8_000_000
_tokenizer = None
_tokenizer_lock = threading.Lock()
STOP_WORDS = {
    "的",
    "了",
    "是",
    "我",
    "你",
    "在",
    "有",
    "吗",
    "呢",
    "和",
    "与",
    "到",
    "这",
    "那",
    "什么",
    "怎么",
    "多少",
    "一下",
    "可以",
    "请问",
    "帮我",
    "一个",
    "一台",
    "分别",
}


def excerpt(content, words, characters):
    lowered = content.lower()
    useful = [word for word in words if word not in STOP_WORDS]
    starts = {0, max(0, len(content) - characters)}
    for word in useful:
        at = lowered.find(word)
        while at >= 0:
            starts.add(max(0, at - characters // 4))
            starts.add(max(0, at - characters * 3 // 4))
            at = lowered.find(word, at + max(1, len(word)))

    def score(start):
        window = lowered[start : start + characters]
        return sum(min(len(w), 8) if len(w) > 1 else 0.1 for w in useful if w in window)

    start = max(sorted(starts), key=score)
    return content[start : start + characters]


def tokenize(text):
    global _tokenizer
    with _tokenizer_lock:
        if _tokenizer is None:
            import jieba

            jieba.setLogLevel(logging.ERROR)
            _tokenizer = jieba.Tokenizer()
            # Do not write jieba's cache to the shared system temporary directory.
            with _tokenizer.get_dict_file() as dictionary:
                _tokenizer.FREQ, _tokenizer.total = _tokenizer.gen_pfdict(dictionary)
            _tokenizer.initialized = True
        return list(
            dict.fromkeys(
                word.lower()
                for word in _tokenizer.cut_for_search(text[:48_000], HMM=False)
                if re.fullmatch(r"[^\W_]+", word, re.UNICODE)
            )
        )


class KnowledgeStore:
    def __init__(self, path, base_id=None):
        self.path = path
        self.base_id = base_id

    def bases(self):
        ledger = Ledger(self.path)
        try:
            return [
                dict(row)
                for row in ledger.db.execute("""
                SELECT b.*,count(d.id) document_count,coalesce(sum(d.chunk_count),0) chunk_count,
                coalesce(sum(d.byte_size),0) byte_size FROM knowledge_bases b
                LEFT JOIN knowledge_memberships m ON m.base_id=b.id
                LEFT JOIN knowledge_documents d ON d.id=m.document_id
                GROUP BY b.id ORDER BY b.kind='demo' DESC,b.created,b.id""")
            ]
        finally:
            ledger.close()

    @staticmethod
    def require_base(db, base_id):
        row = db.execute("SELECT * FROM knowledge_bases WHERE id=?", (base_id,)).fetchone()
        if not row:
            raise AdapterError("knowledge_base_not_found")
        return row

    def create_base(self, name, description="", base_id=None, kind="custom", enabled=True):
        if not name.strip() or len(name) > 60 or len(description) > 300:
            raise AdapterError("knowledge_base_invalid")
        ledger = Ledger(self.path)
        try:
            with ledger.db:
                ledger.db.execute("BEGIN IMMEDIATE")
                if ledger.db.execute("SELECT count(*) FROM knowledge_bases").fetchone()[0] >= 20:
                    raise AdapterError("knowledge_base_capacity_reached")
                base_id = base_id or uuid4().hex
                ledger.db.execute(
                    "INSERT INTO knowledge_bases VALUES(?,?,?,?,?,?)",
                    (base_id, name.strip(), description.strip(), int(enabled), kind, time.time()),
                )
            return next(b for b in self.bases() if b["id"] == base_id)
        finally:
            ledger.close()

    def update_base(self, base_id, changes):
        if not changes or changes.keys() - {"name", "description", "enabled"}:
            raise AdapterError("knowledge_base_invalid")
        if (
            "name" in changes
            and (not changes["name"].strip() or len(changes["name"]) > 60)
            or "description" in changes
            and len(changes["description"]) > 300
        ):
            raise AdapterError("knowledge_base_invalid")
        ledger = Ledger(self.path)
        try:
            with ledger.db:
                self.require_base(ledger.db, base_id)
                for key, value in changes.items():
                    ledger.db.execute(
                        f"UPDATE knowledge_bases SET {key}=? WHERE id=?",
                        (int(value) if key == "enabled" else value.strip(), base_id),
                    )
                ledger.db.execute("DELETE FROM context")
            return next(b for b in self.bases() if b["id"] == base_id)
        finally:
            ledger.close()

    def delete_base(self, base_id):
        if base_id == "personal":
            raise AdapterError("default_knowledge_base_required")
        ledger = Ledger(self.path)
        try:
            with ledger.db:
                self.require_base(ledger.db, base_id)
                ledger.db.execute("DELETE FROM knowledge_bases WHERE id=?", (base_id,))
                ledger.db.execute(
                    "DELETE FROM knowledge_documents WHERE id NOT IN "
                    "(SELECT document_id FROM knowledge_memberships)"
                )
                ledger.db.execute("DELETE FROM context")
        finally:
            ledger.close()

    def documents(self, limit=50, offset=0, base_id=None):
        ledger = Ledger(self.path)
        try:
            return [
                dict(r)
                for r in ledger.db.execute(
                    "SELECT d.* FROM knowledge_documents d WHERE (? IS NULL OR EXISTS "
                    "(SELECT 1 FROM knowledge_memberships m WHERE m.document_id=d.id "
                    "AND m.base_id=?)) ORDER BY d.created DESC,d.id LIMIT ? OFFSET ?",
                    (base_id, base_id, limit, offset),
                )
            ]
        finally:
            ledger.close()

    def document(self, document_id):
        ledger = Ledger(self.path)
        try:
            row = ledger.db.execute(
                "SELECT * FROM knowledge_documents WHERE id=?", (document_id,)
            ).fetchone()
            if not row:
                raise AdapterError("knowledge_document_not_found")
            chunks = ledger.db.execute(
                "SELECT content FROM knowledge_chunks WHERE document_id=? ORDER BY ordinal",
                (document_id,),
            ).fetchall()
            content = "".join(c[0] if i == 0 else c[0][80:] for i, c in enumerate(chunks))
            return dict(row) | {"content": content}
        finally:
            ledger.close()

    def import_text(self, name, content, base_id="personal"):
        if (
            not isinstance(name, str)
            or len(name) > 120
            or PurePosixPath(name).name != name
            or "\\" in name
            or PurePosixPath(name).suffix.lower() not in (".txt", ".md", ".markdown")
            or any(ord(c) < 32 for c in name)
            or not isinstance(content, str)
            or not content.strip()
            or any(ord(c) < 32 and c not in "\n\r\t" for c in content)
        ):
            raise AdapterError("knowledge_document_invalid")
        try:
            byte_size = len(content.encode("utf-8"))
        except UnicodeError:
            raise AdapterError("knowledge_document_invalid") from None
        if byte_size > MAX_DOCUMENT_BYTES:
            raise AdapterError("knowledge_document_too_large")
        content = content.replace("\r\n", "\n").replace("\r", "\n").strip()
        digest = hashlib.sha256(content.encode()).hexdigest()
        chunks = [content[i : i + 600] for i in range(0, len(content), 520)]
        indexed = [(chunk, " ".join(tokenize(chunk))) for chunk in chunks]
        ledger = Ledger(self.path)
        try:
            with ledger.db:
                ledger.db.execute("BEGIN IMMEDIATE")
                self.require_base(ledger.db, base_id)
                existing = ledger.db.execute(
                    "SELECT * FROM knowledge_documents WHERE digest=?", (digest,)
                ).fetchone()
                if existing:
                    linked = ledger.db.execute(
                        "INSERT OR IGNORE INTO knowledge_memberships VALUES(?,?)",
                        (existing["id"], base_id),
                    ).rowcount
                    return dict(existing) | {"duplicate": not bool(linked), "base_id": base_id}
                count, size = ledger.db.execute(
                    "SELECT count(*),coalesce(sum(byte_size),0) FROM knowledge_documents"
                ).fetchone()
                if count >= MAX_DOCUMENTS or size + byte_size > MAX_TOTAL_BYTES:
                    raise AdapterError("knowledge_capacity_reached")
                doc_id = uuid4().hex
                ledger.db.execute(
                    "INSERT INTO knowledge_documents VALUES(?,?,?,?,?,?)",
                    (doc_id, name, digest, byte_size, len(chunks), time.time()),
                )
                ledger.db.execute(
                    "INSERT INTO knowledge_memberships VALUES(?,?)", (doc_id, base_id)
                )
                for ordinal, (chunk, tokens) in enumerate(indexed, start=1):
                    chunk_id = f"{doc_id}:{ordinal}"
                    ledger.db.execute(
                        "INSERT INTO knowledge_chunks VALUES(?,?,?,?)",
                        (chunk_id, doc_id, ordinal, chunk),
                    )
                    ledger.db.execute("INSERT INTO knowledge_fts VALUES(?,?)", (chunk_id, tokens))
                return dict(
                    ledger.db.execute(
                        "SELECT * FROM knowledge_documents WHERE id=?", (doc_id,)
                    ).fetchone()
                ) | {"duplicate": False, "base_id": base_id}
        finally:
            ledger.close()

    def delete(self, document_id, base_id=None):
        ledger = Ledger(self.path)
        try:
            with ledger.db:
                if base_id:
                    if not ledger.db.execute(
                        "DELETE FROM knowledge_memberships WHERE document_id=? AND base_id=?",
                        (document_id, base_id),
                    ).rowcount:
                        raise AdapterError("knowledge_document_not_found")
                    ledger.db.execute(
                        "DELETE FROM knowledge_documents WHERE id=? AND NOT EXISTS "
                        "(SELECT 1 FROM knowledge_memberships WHERE document_id=?)",
                        (document_id, document_id),
                    )
                elif not ledger.db.execute(
                    "DELETE FROM knowledge_documents WHERE id=?", (document_id,)
                ).rowcount:
                    raise AdapterError("knowledge_document_not_found")
                # An old answer in history must not reintroduce deleted knowledge.
                ledger.db.execute("DELETE FROM context")
        finally:
            ledger.close()

    def search(self, query, limit=3, snippet_characters=600, base_id=None):
        base_id = base_id or self.base_id
        words = [word for word in tokenize(query[:2000]) if word not in STOP_WORDS][:32]
        if re.search(r"多少钱|售价|价格|price|cost", query, re.IGNORECASE):
            words = list(dict.fromkeys([*words, "售价", "价格"]))
        if not words:
            return []
        expression = " OR ".join('"' + w.replace('"', '""') + '"' for w in words)
        ledger = Ledger(self.path)
        try:
            rows = [
                dict(r)
                for r in ledger.db.execute(
                    """SELECT c.id AS source_ref,d.name,c.ordinal,c.content
                FROM knowledge_fts JOIN knowledge_chunks c ON c.id=knowledge_fts.chunk_id
                JOIN knowledge_documents d ON d.id=c.document_id
                WHERE knowledge_fts MATCH ? AND EXISTS (
                    SELECT 1 FROM knowledge_memberships m JOIN knowledge_bases b ON b.id=m.base_id
                    WHERE m.document_id=d.id AND b.enabled=1 AND (? IS NULL OR b.id=?))
                ORDER BY bm25(knowledge_fts),c.id LIMIT ?""",
                    (expression, base_id, base_id, min(max(limit, 1), 5)),
                )
            ]
            for row in rows:
                content = row["content"]
                if len(content) > snippet_characters:
                    # Preserve the query hit when fitting a long chunk into the prompt budget.
                    row["content"] = excerpt(content, words, snippet_characters)
                    row["excerpted"] = True
            return rows
        finally:
            ledger.close()
