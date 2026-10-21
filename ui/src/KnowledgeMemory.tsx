import React, { useEffect, useState } from "react";
import { api } from "./api";

type Document = {
  id: string;
  name: string;
  chunk_count: number;
  byte_size: number;
};
type Contact = { scope: string; contact: string; alias: string };
type Fact = { key: string; value: string; source: string; updated: number };
type Hit = {
  source_ref: string;
  name: string;
  ordinal: number;
  content: string;
};

export function KnowledgeMemory({ editable }: { editable: boolean }) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [documentOffset, setDocumentOffset] = useState(0);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selected, setSelected] = useState("");
  const [facts, setFacts] = useState<Fact[]>([]);
  const [file, setFile] = useState<File>();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [factKey, setFactKey] = useState("");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const contact = contacts.find(
    (c) => JSON.stringify([c.scope, c.contact]) === selected,
  );
  const params = contact
    ? new URLSearchParams({ scope: contact.scope, contact: contact.contact })
    : undefined;

  async function refresh() {
    const [docs, people] = await Promise.all([
      api<{ items: Document[] }>(
        `/knowledge/documents?limit=50&offset=${documentOffset}`,
      ),
      api<{ items: Contact[] }>("/memories/contacts"),
    ]);
    setDocuments(docs.items);
    setContacts(people.items);
    if (params)
      setFacts((await api<{ items: Fact[] }>(`/memories?${params}`)).items);
  }
  useEffect(() => {
    void refresh().catch((e) => setError(String(e)));
  }, [documentOffset]);
  useEffect(() => {
    let alive = true;
    setFacts([]);
    setFactKey("");
    setValue("");
    if (params)
      void api<{ items: Fact[] }>(`/memories?${params}`)
        .then((data) => {
          if (alive) setFacts(data.items);
        })
        .catch((e) => {
          if (alive) setError(String(e));
        });
    return () => {
      alive = false;
    };
  }, [selected]);

  async function perform(fn: () => Promise<string>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await fn();
      await refresh();
      setNotice(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {error && (
        <div role="alert" className="alert">
          操作失败：{error}
        </div>
      )}
      {notice && (
        <div role="status" className="notice">
          {notice}
        </div>
      )}
      {!editable && <p className="notice">暂停或停止后可修改知识与记忆。</p>}
      <section>
        <h2>本地知识</h2>
        <p>
          导入 UTF-8 TXT / Markdown，单份最多 48 KB、总计 200 份 / 8
          MB。知识供本机账号使用；命中内容会随消息发送给已配置的模型。
        </p>
        <div className="form">
          <label>
            选择知识文件
            <input
              type="file"
              accept=".txt,.md,.markdown"
              disabled={busy || !editable}
              onChange={(e) => setFile(e.target.files?.[0])}
            />
          </label>
        </div>
        <button
          disabled={!file || busy || !editable}
          onClick={() =>
            void perform(async () => {
              if (!file || file.size > 48000)
                throw new Error("knowledge_document_too_large");
              const content = new TextDecoder("utf-8", { fatal: true }).decode(
                await file.arrayBuffer(),
              );
              const result = await api<{
                duplicate: boolean;
                chunk_count: number;
              }>("/knowledge/documents", "POST", { name: file.name, content });
              setHits(null);
              return result.duplicate
                ? "相同内容已存在，未重复导入。"
                : `已导入，共 ${result.chunk_count} 个知识片段。`;
            })
          }
        >
          导入知识
        </button>
        {documents.length === 0 ? (
          <div className="empty">暂无知识文件。</div>
        ) : (
          documents.map((doc) => (
            <article className="record" key={doc.id}>
              <strong>{doc.name}</strong>
              <p>
                {doc.chunk_count} 个片段 · {doc.byte_size} 字节
              </p>
              <button
                className="secondary"
                disabled={busy || !editable}
                onClick={() =>
                  void perform(async () => {
                    await api(`/knowledge/documents/${doc.id}`, "DELETE", {});
                    setHits(null);
                    return "知识已删除，后续检索不再召回；旧会话上下文已清除。";
                  })
                }
              >
                删除知识
              </button>
            </article>
          ))
        )}
        <div className="actions">
          <button
            className="secondary"
            disabled={busy || !documentOffset}
            onClick={() => setDocumentOffset(Math.max(0, documentOffset - 50))}
          >
            上一页
          </button>
          <button
            className="secondary"
            disabled={busy || documents.length < 50}
            onClick={() => setDocumentOffset(documentOffset + 50)}
          >
            下一页
          </button>
        </div>
        <p>每页 50 份，从第 {documentOffset + 1} 份开始。</p>
        <div className="form">
          <label>
            测试知识检索
            <input
              value={query}
              maxLength={2000}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </div>
        <button
          className="secondary"
          disabled={busy || !query.trim()}
          onClick={() =>
            void perform(async () => {
              const result = await api<{ items: Hit[] }>(
                `/knowledge/search?${new URLSearchParams({ q: query })}`,
              );
              setHits(result.items);
              return result.items.length
                ? `命中 ${result.items.length} 个片段。`
                : "本地知识未命中。";
            })
          }
        >
          检索
        </button>
        {hits?.map((hit) => (
          <article className="record" key={hit.source_ref}>
            <strong>
              {hit.name} #{hit.ordinal}
            </strong>
            <p className="content">{hit.content}</p>
          </article>
        ))}
      </section>
      <section>
        <h2>联系人长期记忆</h2>
        <p>
          按账号代数、联系人及 dry-run / live 隔离，每位联系人最多 20
          条偏好。仅明确指令会保存，例如“记住我的偏好：饮品=乌龙茶”“更正我的偏好：饮品=白茶”“忘记我的偏好：饮品”。成功生成回复后保存；模型失败或暂停丢弃时不写入。
        </p>
        <div className="form">
          <label>
            联系人与运行范围
            <select
              value={selected}
              disabled={busy}
              onChange={(e) => setSelected(e.target.value)}
            >
              <option value="">选择已有绑定联系人</option>
              {contacts.map((c) => (
                <option
                  key={JSON.stringify([c.scope, c.contact])}
                  value={JSON.stringify([c.scope, c.contact])}
                >
                  {c.alias} · {c.scope}
                </option>
              ))}
            </select>
          </label>
        </div>
        {!contacts.length && (
          <p>正式服务开始并建立绑定后，这里会出现联系人；重启后保留。</p>
        )}
        {contact && (
          <>
            {!facts.length && (
              <div className="empty">该联系人暂无长期偏好。</div>
            )}
            {facts.map((fact) => (
              <article className="record" key={fact.key}>
                <strong>{fact.key}</strong>
                <p className="content">{fact.value}</p>
                <small>
                  {fact.source === "explicit_chat"
                    ? "聊天明确指令"
                    : "工作台编辑"}{" "}
                  · {new Date(fact.updated * 1000).toLocaleString()}
                </small>
                <div className="actions">
                  <button
                    className="secondary"
                    disabled={busy || !editable}
                    onClick={() => {
                      setFactKey(fact.key);
                      setValue(fact.value);
                    }}
                  >
                    更正
                  </button>
                  <button
                    className="secondary"
                    disabled={busy || !editable}
                    onClick={() =>
                      void perform(async () => {
                        await api(
                          `/memories?${params}&${new URLSearchParams({ key: fact.key })}`,
                          "DELETE",
                          {},
                        );
                        return "已忘记该偏好，并清除该会话的旧上下文。";
                      })
                    }
                  >
                    忘记
                  </button>
                </div>
              </article>
            ))}
            <div className="form">
              <label>
                偏好名称
                <input
                  value={factKey}
                  maxLength={40}
                  disabled={busy || !editable}
                  onChange={(e) => setFactKey(e.target.value)}
                />
              </label>
              <label>
                偏好内容
                <input
                  value={value}
                  maxLength={200}
                  disabled={busy || !editable}
                  onChange={(e) => setValue(e.target.value)}
                />
              </label>
            </div>
            <button
              disabled={busy || !editable || !factKey.trim() || !value.trim()}
              onClick={() =>
                void perform(async () => {
                  await api("/memories", "PUT", {
                    scope: contact.scope,
                    contact: contact.contact,
                    key: factKey,
                    value,
                  });
                  setFactKey("");
                  setValue("");
                  return "偏好已保存，并清除该会话的旧上下文。";
                })
              }
            >
              保存偏好
            </button>
          </>
        )}
        <div className="actions">
          <button
            className="secondary"
            disabled={busy}
            onClick={() => void perform(async () => "列表已刷新。")}
          >
            刷新知识与记忆
          </button>
        </div>
      </section>
    </>
  );
}
