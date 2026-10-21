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
    def __init__(self, path):
        self.path = path

    def documents(self, limit=50, offset=0):
        ledger = Ledger(self.path)
        try:
            return [
                dict(r)
                for r in ledger.db.execute(
                    "SELECT * FROM knowledge_documents ORDER BY created DESC,id LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            ]
        finally:
            ledger.close()

    def import_text(self, name, content):
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
                existing = ledger.db.execute(
                    "SELECT * FROM knowledge_documents WHERE digest=?", (digest,)
                ).fetchone()
                if existing:
                    return dict(existing) | {"duplicate": True}
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
                ) | {"duplicate": False}
        finally:
            ledger.close()

    def delete(self, document_id):
        ledger = Ledger(self.path)
        try:
            with ledger.db:
                if not ledger.db.execute(
                    "DELETE FROM knowledge_documents WHERE id=?", (document_id,)
                ).rowcount:
                    raise AdapterError("knowledge_document_not_found")
                # An old answer in history must not reintroduce deleted knowledge.
                ledger.db.execute("DELETE FROM context")
        finally:
            ledger.close()

    def search(self, query, limit=3, snippet_characters=600):
        words = tokenize(query[:2000])[:32]
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
                WHERE knowledge_fts MATCH ? ORDER BY bm25(knowledge_fts),c.id LIMIT ?""",
                    (expression, min(max(limit, 1), 5)),
                )
            ]
            for row in rows:
                content = row["content"]
                if len(content) > snippet_characters:
                    # Preserve the query hit when fitting a long chunk into the prompt budget.
                    word = next(
                        (w for w in sorted(words, key=len, reverse=True) if w in content.lower()),
                        "",
                    )
                    position = content.lower().find(word) if word else 0
                    start = max(0, position - snippet_characters // 3)
                    row["content"] = content[start : start + snippet_characters]
                    row["excerpted"] = True
            return rows
        finally:
            ledger.close()
