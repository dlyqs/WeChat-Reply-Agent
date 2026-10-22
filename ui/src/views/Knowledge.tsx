import React, { useEffect, useRef, useState } from "react";
import { api, errorText, knowledgeText, reasonText, sizeText } from "../api";
import {
  CopyButton,
  Empty,
  Icon,
  Modal,
  PageHeading,
  Pill,
  Skeleton,
} from "../components";
import { useWorkspace } from "../workspace";
import type { Document, KnowledgeBase, Page, Source } from "../types";
type Hit = Source & { content: string };
type Preview = {
  status: string;
  reply_text: string | null;
  reason: string;
  sources: Source[];
  knowledge_status: string;
  preview_only: boolean;
  sent_to_wechat: boolean;
};
type Turn = { question: string; result: Preview };
export function Knowledge() {
  const { bases, busy, editable, settings, perform, navigate } = useWorkspace();
  const [selectedId, select] = useState<string>();
  const current = bases?.items.find((b) => b.id === selectedId);
  const [filter, setFilter] = useState("");
  const [documents, setDocuments] = useState<Document[]>();
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [editor, setEditor] = useState<KnowledgeBase | "new">();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [deleting, setDeleting] = useState<{
    base?: KnowledgeBase;
    doc?: Document;
  }>();
  const [document, showDocument] = useState<Document>();
  const [docError, setDocError] = useState("");
  const [question, setQuestion] = useState("");
  const [hits, setHits] = useState<Hit[]>();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [tab, setTab] = useState<"reply" | "sources">("reply");
  const [importResults, setImportResults] = useState<
    { name: string; ok: boolean; message: string }[]
  >([]);
  const [dragging, setDragging] = useState(false);
  const scroll = useRef<HTMLDivElement>(null);
  const reloadDocuments = async () => {
    if (selectedId)
      setDocuments(
        (
          await api<Page<Document>>(
            `/knowledge/documents?${new URLSearchParams({ base_id: selectedId, limit: "30", offset: String(offset) })}`,
          )
        ).items,
      );
  };
  useEffect(() => {
    setOffset(0);
    setQuestion("");
    setTurns([]);
    setHits(undefined);
    setImportResults([]);
    setDocuments(undefined);
  }, [selectedId]);
  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    void api<Page<Document>>(
      `/knowledge/documents?${new URLSearchParams({ base_id: selectedId, limit: "30", offset: String(offset) })}`,
      "GET",
      undefined,
      controller.signal,
    )
      .then((p) => {
        setDocuments(p.items);
        setError("");
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorText(e));
      });
    return () => controller.abort();
  }, [selectedId, offset, current?.document_count]);
  useEffect(() => {
    if (!document?.id) return;
    const controller = new AbortController();
    setDocError("");
    void api<Document>(
      `/knowledge/documents/${document.id}`,
      "GET",
      undefined,
      controller.signal,
    )
      .then((d) => showDocument((old) => (old?.id === d.id ? d : old)))
      .catch((e) => {
        if (!controller.signal.aborted) setDocError(errorText(e));
      });
    return () => controller.abort();
  }, [document?.id]);
  useEffect(() => {
    scroll.current?.scrollTo({
      top: scroll.current.scrollHeight,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
    });
  }, [turns]);
  const demo = current?.id === bases?.demo.id;
  const examples = demo ? bases?.demo.questions || [] : [];
  const expected = examples.find((q) => q.question === question)?.expected;
  function openEditor(base?: KnowledgeBase) {
    setEditor(base || "new");
    setName(base?.name || "");
    setDescription(base?.description || "");
  }
  async function importFiles(files: File[]) {
    if (!current || !editable || busy) return;
    if (files.length > 10) {
      setError("一次最多选择10份资料，请分批导入。");
      return;
    }
    setImportResults([]);
    await perform(async () => {
      const results: { name: string; ok: boolean; message: string }[] = [];
      for (const file of files) {
        try {
          if (file.size > 48000) throw new Error("超过单份48 KB上限");
          if (!/\.(txt|md|markdown)$/i.test(file.name))
            throw new Error("仅支持 TXT / Markdown");
          let content: string;
          try {
            content = new TextDecoder("utf-8", { fatal: true }).decode(
              await file.arrayBuffer(),
            );
          } catch {
            throw new Error("无法按 UTF-8 读取，请转换文件编码");
          }
          const result = await api<{ duplicate: boolean; chunk_count: number }>(
            "/knowledge/documents",
            "POST",
            { name: file.name, content, base_id: current.id },
          );
          results.push({
            name: file.name,
            ok: true,
            message: result.duplicate
              ? "内容已存在，未重复添加"
              : `已导入 · ${result.chunk_count}个片段`,
          });
        } catch (e) {
          results.push({ name: file.name, ok: false, message: errorText(e) });
        }
        setImportResults([...results]);
      }
      await reloadDocuments();
    });
  }
  async function retrieve() {
    if (!current) return;
    await perform(async () => {
      const data = await api<Page<Hit>>(
        `/knowledge/search?${new URLSearchParams({ q: question, base_id: current.id })}`,
      );
      setHits(data.items);
      setTab("sources");
    });
  }
  async function preview() {
    if (!current || !question.trim()) return;
    const asked = question;
    await perform(async () => {
      const history = turns
        .slice(-5)
        .filter((t) => t.result.reply_text)
        .flatMap((t) => [
          { role: "user", content: t.question },
          { role: "assistant", content: t.result.reply_text! },
        ]);
      const result = await api<Preview>("/agent/preview", "POST", {
        question: asked,
        base_id: current.id,
        history,
      });
      if (result.status !== "ready") throw new Error(reasonText(result.reason));
      setTurns((old) => [...old.slice(-5), { question: asked, result }]);
      setTab("reply");
    });
  }
  return (
    <>
      <PageHeading
        eyebrow="KNOWLEDGE, WITH CONTEXT"
        title={current ? current.name : "让助理，懂你的业务。"}
        description={
          current
            ? current.description
            : "用知识库组织资料，启用后参与回复。先试试内置示例，也可以从自己的资料开始。"
        }
        action={
          current ? (
            <button
              className="button button-secondary"
              onClick={() => select(undefined)}
            >
              <span className="rotate">
                <Icon name="arrow" size={16} />
              </span>
              全部知识库
            </button>
          ) : (
            <button
              className="button"
              disabled={busy || !editable}
              onClick={() => openEditor()}
            >
              <Icon name="plus" size={16} />
              新建知识库
            </button>
          )
        }
      />
      {!editable && (
        <div className="callout">
          <Icon name="info" />
          <p>运行中可查阅资料；暂停或停止后，可以编辑知识库和生成模拟回复。</p>
        </div>
      )}
      {error && (
        <div className="feedback feedback-error" role="alert">
          {error}
          <button
            className="icon-button"
            aria-label="关闭提示"
            onClick={() => setError("")}
          >
            <Icon name="close" />
          </button>
        </div>
      )}
      {!current ? (
        <>
          <section className="demo-banner">
            <div className="demo-symbol">
              <Icon name="coffee" size={32} />
            </div>
            <div>
              <span className="eyebrow">BUILT IN · FICTIONAL COMPANY</span>
              <h2>NORTHLINE 北线咖啡</h2>
              <p>
                一家公司，完整的业务语境。便携咖啡器具、内部实测、仓储物流与售后政策，全部为虚构演示资料。
              </p>
              <div className="tag-row">
                <Pill>便携咖啡器具</Pill>
                <Pill>美国 / 欧盟</Pill>
                <Pill>内部核准参数</Pill>
              </div>
            </div>
            <div className="demo-banner-action">
              {bases?.items.some((b) => b.id === bases.demo.id) ? (
                <button
                  className="button button-secondary"
                  onClick={() => select(bases.demo.id)}
                >
                  进入示例
                  <Icon name="arrow" size={16} />
                </button>
              ) : (
                <button
                  className="button"
                  disabled={busy || !editable}
                  onClick={() =>
                    void perform(
                      () => api("/knowledge/demo", "POST", {}),
                      "示例知识库已恢复并启用。",
                    )
                  }
                >
                  恢复示例知识库
                </button>
              )}
              <small>不接入真实订单或支付</small>
            </div>
          </section>
          <div className="list-toolbar">
            <h2>
              我的知识库{" "}
              <span className="count-label">{bases?.items.length ?? "—"}</span>
            </h2>
            <label className="search-field">
              <Icon name="search" size={16} />
              <input
                aria-label="查找知识库"
                placeholder="查找知识库…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
            </label>
          </div>
          {!bases ? (
            <Skeleton />
          ) : (
            <div className="knowledge-grid">
              {bases.items
                .filter((base) =>
                  (base.name + base.description)
                    .toLowerCase()
                    .includes(filter.toLowerCase()),
                )
                .map((base) => (
                  <article
                    className={
                      "knowledge-card " +
                      (base.kind === "demo" ? "is-demo" : "")
                    }
                    key={base.id}
                  >
                    <div className="row-between">
                      <span className="knowledge-icon">
                        <Icon
                          name={base.kind === "demo" ? "coffee" : "book"}
                          size={23}
                        />
                      </span>
                      <Pill tone={base.enabled ? "green" : "neutral"}>
                        {base.enabled ? "已启用" : "未启用"}
                      </Pill>
                    </div>
                    <button
                      className="card-title-button"
                      onClick={() => select(base.id)}
                    >
                      <h3>{base.name}</h3>
                      <Icon name="arrow" size={16} />
                    </button>
                    <p>
                      {base.description || "为助理整理一份可靠的业务资料。"}
                    </p>
                    <div className="card-bottom">
                      <span>
                        {base.document_count} 份资料 ·{" "}
                        {sizeText(base.byte_size)}
                      </span>
                      <button
                        className="text-link"
                        onClick={() => select(base.id)}
                      >
                        管理
                      </button>
                    </div>
                  </article>
                ))}
              <button
                className="knowledge-card create-card"
                disabled={busy || !editable}
                onClick={() => openEditor()}
              >
                <span className="empty-symbol">
                  <Icon name="plus" size={24} />
                </span>
                <strong>新建一个知识库</strong>
                <small>按业务或产品整理自己的资料</small>
              </button>
            </div>
          )}
          <div className="micro-note">
            <Icon name="info" size={15} />
            <span>
              只有已启用知识库中的资料会参与回复。资料保存在本机，命中片段会发送给你配置的模型。
            </span>
          </div>
        </>
      ) : (
        <>
          <section className="base-control">
            <div className="tag-row">
              <Pill tone={current.enabled ? "green" : "neutral"}>
                <span className="status-dot" />
                {current.enabled ? "正在参与回复" : "尚未参与回复"}
              </Pill>
              {demo && <Pill tone="gold">内置虚构示例</Pill>}
              <span className="muted">
                {current.document_count} 份资料 · {current.chunk_count} 个片段
              </span>
            </div>
            <div className="button-row">
              <button
                className="button button-secondary"
                disabled={busy || !editable}
                onClick={() =>
                  void perform(
                    () =>
                      api(`/knowledge/bases/${current.id}`, "PATCH", {
                        enabled: !current.enabled,
                      }),
                    current.enabled
                      ? "知识库已停用，后续回复不再采用这些资料。"
                      : "知识库已启用，后续回复会按需采用这些资料。",
                  )
                }
              >
                {current.enabled ? "停用知识库" : "启用知识库"}
              </button>
              <button
                className="icon-button"
                title="编辑知识库信息"
                aria-label="编辑知识库信息"
                disabled={busy || !editable}
                onClick={() => openEditor(current)}
              >
                <Icon name="edit" />
              </button>
              {current.id !== "personal" && (
                <button
                  className="icon-button danger-text"
                  title="删除知识库"
                  aria-label="删除知识库"
                  disabled={busy || !editable}
                  onClick={() => setDeleting({ base: current })}
                >
                  <Icon name="trash" />
                </button>
              )}
            </div>
          </section>
          {demo && (
            <div className="callout callout-gold">
              <Icon name="spark" />
              <p>
                推荐在设置中选择「小北 ·
                跨境产品助理」预设，再用右侧问题验证回复。内部参数全部为模拟数据，可向绑定的测试好友解答。
              </p>
              <button
                className="text-link"
                onClick={() => navigate("settings")}
              >
                设置回复风格
                <Icon name="arrow" size={15} />
              </button>
            </div>
          )}
          <div className="knowledge-detail-grid">
            <section className="panel document-panel">
              <div className="section-heading">
                <div>
                  <h2>知识资料</h2>
                  <p>支持 UTF-8 TXT、Markdown，单份最多48 KB。</p>
                </div>
                <Pill>{current.document_count} 份</Pill>
              </div>
              <label
                className={
                  "dropzone " +
                  (dragging ? "is-dragging" : "") +
                  (!editable ? " is-disabled" : "")
                }
                onDragOver={(e) => {
                  e.preventDefault();
                  if (editable && !busy) setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  void importFiles(Array.from(e.dataTransfer.files));
                }}
              >
                <input
                  type="file"
                  multiple
                  className="file-input"
                  accept=".txt,.md,.markdown"
                  disabled={busy || !editable}
                  onChange={(e) => {
                    void importFiles(Array.from(e.target.files || []));
                    e.target.value = "";
                  }}
                />
                <span className="upload-symbol">
                  <Icon name="upload" size={22} />
                </span>
                <strong>
                  {busy ? "正在处理，请稍候…" : "拖入资料，或点击选择文件"}
                </strong>
                <span>一次最多10份 · 共用200份 / 8 MB容量</span>
              </label>
              {importResults.length > 0 && (
                <div className="import-results" role="status">
                  {importResults.map((r, i) => (
                    <div key={i}>
                      <Icon name={r.ok ? "check" : "info"} size={15} />
                      <span>
                        {r.name}
                        <small className={r.ok ? "" : "danger-text"}>
                          {r.message}
                        </small>
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {!documents ? (
                <Skeleton />
              ) : !documents.length ? (
                <Empty icon="book" title="还没有资料">
                  导入产品手册、常见问题或服务政策，让助理有依据可答。
                </Empty>
              ) : (
                <div className="document-list">
                  {documents.map((doc) => (
                    <div className="document-row" key={doc.id}>
                      <span className="document-icon">
                        <Icon name="file" size={20} />
                      </span>
                      <button
                        className="document-name"
                        onClick={() => showDocument(doc)}
                      >
                        <strong>{doc.name}</strong>
                        <small>
                          {sizeText(doc.byte_size)} · {doc.chunk_count} 个片段
                        </small>
                      </button>
                      <button
                        className="icon-button"
                        aria-label={`查看${doc.name}`}
                        title="查看资料"
                        onClick={() => showDocument(doc)}
                      >
                        <Icon name="eye" size={17} />
                      </button>
                      <button
                        className="icon-button"
                        aria-label={`删除${doc.name}`}
                        title="从此知识库移除"
                        disabled={busy || !editable}
                        onClick={() => setDeleting({ doc })}
                      >
                        <Icon name="trash" size={17} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="pagination">
                <button
                  className="quiet-button"
                  disabled={!offset}
                  onClick={() => setOffset(Math.max(0, offset - 30))}
                >
                  上一页
                </button>
                <span>第 {offset / 30 + 1} 页</span>
                <button
                  className="quiet-button"
                  disabled={(documents?.length || 0) < 30}
                  onClick={() => setOffset(offset + 30)}
                >
                  下一页
                </button>
              </div>
            </section>
            <section className="panel playground">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">TRY IT BEFORE YOU SEND</span>
                  <h2>测试一下，助理怎么答</h2>
                </div>
                <span className="playground-symbol">
                  <Icon name="spark" size={21} />
                </span>
              </div>
              <p>
                仅使用当前知识库与已保存的回复设置。这里的模拟回复不会发到微信，也不写入真实会话记录。
              </p>
              {!current.enabled && (
                <div className="inline-warning">
                  请先启用这个知识库，再验证检索或回复。
                </div>
              )}
              {examples.length > 0 && (
                <div className="example-questions">
                  <span className="field-label">从一个问题开始</span>
                  {examples.slice(0, 4).map((q) => (
                    <button
                      key={q.id}
                      onClick={() => setQuestion(q.question)}
                      disabled={busy}
                    >
                      <span>{q.question}</span>
                      <Icon name="arrow" size={14} />
                    </button>
                  ))}
                  <details>
                    <summary>更多测试问题</summary>
                    {examples.slice(4).map((q) => (
                      <button
                        key={q.id}
                        onClick={() => setQuestion(q.question)}
                        disabled={busy}
                      >
                        {q.question}
                      </button>
                    ))}
                  </details>
                </div>
              )}
              <label className="field">
                试问一个具体问题
                <textarea
                  rows={3}
                  maxLength={2000}
                  placeholder="例如：T7 冬季密封圈的内部编号是什么？"
                  value={question}
                  disabled={busy}
                  onChange={(e) => setQuestion(e.target.value)}
                />
              </label>
              <div className="button-row">
                <button
                  className="button"
                  disabled={
                    busy ||
                    !editable ||
                    !current.enabled ||
                    !question.trim() ||
                    !settings?.values.llm_api_key_configured
                  }
                  onClick={() => void preview()}
                >
                  <Icon name="spark" size={16} />
                  {busy ? "请稍候…" : "生成模拟回复"}
                </button>
                <button
                  className="button button-secondary"
                  disabled={busy || !current.enabled || !question.trim()}
                  onClick={() => void retrieve()}
                >
                  <Icon name="search" size={16} />
                  仅查资料
                </button>
              </div>
              {!settings?.values.llm_api_key_configured ? (
                <button
                  className="text-link"
                  onClick={() => navigate("settings")}
                >
                  先连接模型，即可生成回复
                  <Icon name="arrow" size={14} />
                </button>
              ) : (
                <p className="field-hint">
                  生成回复会调用你的模型服务；仅查资料不调用模型。
                </p>
              )}
              {expected && (
                <details className="expected-answer">
                  <summary>核对这题的预期要点</summary>
                  <p>{expected}</p>
                </details>
              )}
              <div className="segmented" role="group" aria-label="测试结果视图">
                <button
                  className={tab === "reply" ? "is-active" : ""}
                  aria-pressed={tab === "reply"}
                  onClick={() => setTab("reply")}
                >
                  模拟对话 {turns.length > 0 && `· ${turns.length}`}
                </button>
                <button
                  className={tab === "sources" ? "is-active" : ""}
                  aria-pressed={tab === "sources"}
                  onClick={() => setTab("sources")}
                >
                  命中资料
                </button>
              </div>
              {tab === "reply" ? (
                <div className="preview-thread" ref={scroll}>
                  {!turns.length ? (
                    <Empty icon="spark" title="让真实资料，变成自然回答">
                      点击问题或自己输入，再生成一条模拟回复。
                    </Empty>
                  ) : (
                    <>
                      {turns.map((turn, index) => (
                        <div className="preview-turn" key={index}>
                          <p className="preview-user preserve">
                            {turn.question}
                          </p>
                          <div className="preview-agent">
                            <span className="eyebrow">AGENT · 仅模拟</span>
                            <p className="preserve">{turn.result.reply_text}</p>
                            <div className="row-between">
                              <span className="muted">
                                {knowledgeText(turn.result.knowledge_status)}
                              </span>
                              <CopyButton
                                value={turn.result.reply_text || ""}
                              />
                            </div>
                            {turn.result.sources.length > 0 && (
                              <details>
                                <summary>查看本轮采用的资料</summary>
                                {turn.result.sources.map((s) => (
                                  <small
                                    className="source-line"
                                    key={s.source_ref}
                                  >
                                    {s.name} · 片段{s.ordinal}
                                  </small>
                                ))}
                              </details>
                            )}
                          </div>
                        </div>
                      ))}
                      <button
                        className="quiet-button"
                        disabled={busy}
                        onClick={() => setTurns([])}
                      >
                        清空模拟对话
                      </button>
                    </>
                  )}
                </div>
              ) : (
                <div className="retrieval-results">
                  {hits === undefined ? (
                    <Empty icon="search" title="先查一条资料">
                      这里会显示实际命中的原文片段。
                    </Empty>
                  ) : !hits.length ? (
                    <Empty icon="search" title="暂无匹配资料">
                      换一个更具体的问题，或检查知识库是否已启用。
                    </Empty>
                  ) : (
                    hits.map((hit) => (
                      <article key={hit.source_ref}>
                        <span className="source-heading">
                          <Icon name="file" size={15} />
                          {hit.name} · #{hit.ordinal}
                        </span>
                        <p className="preserve">{hit.content}</p>
                      </article>
                    ))
                  )}
                </div>
              )}
            </section>
          </div>
        </>
      )}
      {editor && (
        <Modal
          title={editor === "new" ? "新建知识库" : "编辑知识库"}
          description="按一个业务、一类产品或一个服务场景组织资料。"
          busy={busy}
          onClose={() => setEditor(undefined)}
        >
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const ok = await perform(
                () =>
                  api(
                    editor === "new"
                      ? "/knowledge/bases"
                      : `/knowledge/bases/${editor.id}`,
                    editor === "new" ? "POST" : "PATCH",
                    { name, description },
                  ),
                "知识库信息已保存。",
              );
              if (ok) setEditor(undefined);
            }}
          >
            <div className="modal-content">
              <label className="field">
                知识库名称
                <input
                  autoFocus
                  required
                  maxLength={60}
                  placeholder="例如：便携咖啡器具产品手册"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <label className="field">
                描述<span className="optional">选填</span>
                <textarea
                  rows={3}
                  maxLength={300}
                  placeholder="说明这份知识用于什么场景…"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </label>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="button button-secondary"
                disabled={busy}
                onClick={() => setEditor(undefined)}
              >
                取消
              </button>
              <button className="button" disabled={busy || !name.trim()}>
                保存知识库
              </button>
            </div>
          </form>
        </Modal>
      )}
      {deleting && (
        <Modal
          title={
            deleting.base ? "删除这个知识库？" : "从知识库中移除这份资料？"
          }
          description="移除后，后续回复不再召回相应资料；旧的短期上下文也会清除。"
          busy={busy}
          onClose={() => setDeleting(undefined)}
        >
          <div className="modal-content">
            <div className="quote-block">
              {deleting.base?.name || deleting.doc?.name}
            </div>
            {deleting.base?.kind === "demo" && (
              <p className="muted">
                这是内置虚构示例，之后可以从示例入口重新恢复。
              </p>
            )}
          </div>
          <div className="modal-footer">
            <button
              className="button button-secondary"
              disabled={busy}
              onClick={() => setDeleting(undefined)}
            >
              取消
            </button>
            <button
              className="button button-danger"
              disabled={busy || !editable}
              onClick={async () => {
                const ok = await perform(async () => {
                  await api(
                    deleting.base
                      ? `/knowledge/bases/${deleting.base.id}`
                      : `/knowledge/documents/${deleting.doc!.id}?${new URLSearchParams({ base_id: current!.id })}`,
                    "DELETE",
                    {},
                  );
                  if (!deleting.base) await reloadDocuments();
                }, "已删除，后续回复不再召回这些资料。");
                if (ok) {
                  if (deleting.base) select(undefined);
                  setDeleting(undefined);
                  setHits(undefined);
                  setTurns([]);
                }
              }}
            >
              确认删除
            </button>
          </div>
        </Modal>
      )}
      {document && (
        <Modal
          title={document.name}
          description={`${sizeText(document.byte_size)} · ${document.chunk_count} 个片段 · 本地资料原文`}
          wide
          onClose={() => showDocument(undefined)}
        >
          <div className="modal-content">
            {docError ? (
              <p role="alert">{docError}</p>
            ) : document.content === undefined ? (
              <Skeleton />
            ) : (
              <pre className="document-content">{document.content}</pre>
            )}
          </div>
        </Modal>
      )}
    </>
  );
}
