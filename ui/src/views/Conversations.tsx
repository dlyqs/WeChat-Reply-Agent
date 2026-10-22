import React, { useEffect, useState } from "react";
import { api, errorText, modeText, statusText, timeText } from "../api";
import {
  CopyButton,
  Empty,
  Icon,
  PageHeading,
  Pill,
  Skeleton,
} from "../components";
import { useWorkspace } from "../workspace";
import type { Conversation, Message, Outbox, Page } from "../types";
const messageTime = (message: Message) =>
  message.source_created_at ?? new Date(message.observed_at).getTime() / 1000;

export function Conversations() {
  const {
    dashboard,
    busy,
    editable,
    navigate,
    openClear,
    openResolve,
    perform,
  } = useWorkspace();
  const [items, setItems] = useState<Conversation[]>();
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Conversation>();
  const [messageOffset, setMessageOffset] = useState(0);
  const [messages, setMessages] = useState<Message[]>();
  const [replies, setReplies] = useState<Outbox[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    void api<Page<Conversation>>(
      `/conversations?limit=30&offset=${offset}`,
      "GET",
      undefined,
      controller.signal,
    )
      .then((data) => {
        setItems(data.items);
        setSelected((old) =>
          data.items.find((c) => c.id === old?.id && c.scope === old?.scope),
        );
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorText(e));
      });
    return () => controller.abort();
  }, [offset, dashboard?.messages, dashboard?.replies]);
  useEffect(() => {
    setMessageOffset(0);
    setMessages(undefined);
    setReplies([]);
  }, [selected?.id, selected?.scope]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      const params = new URLSearchParams({
        scope: selected.scope,
        limit: "30",
        offset: String(messageOffset),
      });
      try {
        const [m, o] = await Promise.all([
          api<Page<Message>>(
            `/conversations/${encodeURIComponent(selected.id)}/messages?${params}`,
            "GET",
            undefined,
            controller.signal,
          ),
          api<Page<Outbox>>(
            `/outbox?${params}&${new URLSearchParams({ conversation: selected.id })}`,
            "GET",
            undefined,
            controller.signal,
          ),
        ]);
        if (!controller.signal.aborted) {
          setMessages(m.items);
          setReplies(o.items);
          setError("");
        }
      } catch (e) {
        if (!controller.signal.aborted) setError(errorText(e));
      }
      if (!controller.signal.aborted)
        timer = setTimeout(() => void load(), 3500);
    };
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [
    selected?.id,
    selected?.scope,
    messageOffset,
    dashboard?.messages,
    dashboard?.replies,
  ]);
  const timeline = [
    ...(messages || [])
      .filter(
        (m) =>
          m.direction !== "outgoing" ||
          !replies.some(
            (o) =>
              o.state === "verified_sent" &&
              o.reply_text === m.text &&
              Math.abs(o.created - messageTime(m)) < 90,
          ),
      )
      .map((m) => ({
        id: "m-" + m.id,
        text: m.text,
        time: messageTime(m),
        author:
          m.direction === "incoming"
            ? "好友"
            : m.direction === "outgoing"
              ? "本人"
              : "系统",
        status: statusText(m.status),
        reply: undefined as Outbox | undefined,
        messageId: m.id,
        attachment: m.attachment,
      })),
    ...replies.map((o) => ({
      id: "o-" + o.id,
      text: o.reply_text,
      time: o.created,
      author: "助理",
      status: o.mode === "dry-run" ? "仅生成 · 未发送" : statusText(o.state),
      reply: o,
      messageId: undefined,
      attachment: undefined,
    })),
  ].sort((a, b) => a.time - b.time);
  return (
    <>
      <PageHeading
        eyebrow="CONVERSATIONS"
        title="每段对话，清楚留痕。"
        description="查看好友消息、助理回复与发送状态，也可以清除本地旧记录。"
        action={
          <button
            className="button button-secondary"
            disabled={
              busy || !editable || (!dashboard?.messages && !dashboard?.replies)
            }
            onClick={() => openClear()}
          >
            <Icon name="trash" size={16} />
            清除全部记录
          </button>
        }
      />
      {error && (
        <div className="feedback feedback-error" role="alert">
          {error}
        </div>
      )}
      {!editable && (
        <div className="callout">
          <Icon name="info" />
          <p>助理运行中仍可浏览记录；暂停或停止后，可清除本地历史。</p>
        </div>
      )}
      <section className="conversation-workspace">
        <div className="conversation-sidebar">
          <div className="conversation-tools">
            <h2>
              会话<span className="muted">{items?.length ?? "—"}</span>
            </h2>
            <label className="search-field">
              <Icon name="search" size={16} />
              <input
                aria-label="筛选当前页会话"
                placeholder="筛选当前页会话…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
            </label>
          </div>
          {!items ? (
            <Skeleton />
          ) : !items.length ? (
            <Empty title="还没有会话">
              连接微信后，新读取到的消息会出现在这里。
            </Empty>
          ) : (
            <div className="conversation-list">
              {items
                .filter((c) =>
                  (c.alias || c.id)
                    .toLowerCase()
                    .includes(filter.toLowerCase()),
                )
                .map((c) => (
                  <button
                    key={c.scope + c.id}
                    className={
                      "conversation-item " +
                      (selected?.id === c.id && selected.scope === c.scope
                        ? "is-selected"
                        : "")
                    }
                    onClick={() => setSelected(c)}
                  >
                    <span className="contact-avatar">
                      {(c.alias || "友").slice(0, 1).toUpperCase()}
                    </span>
                    <span>
                      <strong>{c.alias || "已绑定会话"}</strong>
                      <small>
                        {modeText(c.scope.split(":").at(-1) || "")} ·{" "}
                        {c.message_count} 条消息
                      </small>
                    </span>
                    <Icon name="chevron" size={14} />
                  </button>
                ))}
            </div>
          )}
          {items && (
            <div className="pagination">
              <button
                className="icon-button"
                aria-label="上一页会话"
                disabled={!offset || busy}
                onClick={() => {
                  setSelected(undefined);
                  setOffset(Math.max(0, offset - 30));
                }}
              >
                <span className="rotate">
                  <Icon name="chevron" size={16} />
                </span>
              </button>
              <span>第 {offset / 30 + 1} 页</span>
              <button
                className="icon-button"
                aria-label="下一页会话"
                disabled={items.length < 30 || busy}
                onClick={() => {
                  setSelected(undefined);
                  setOffset(offset + 30);
                }}
              >
                <Icon name="chevron" size={16} />
              </button>
            </div>
          )}
        </div>
        <div className="conversation-detail">
          {!selected ? (
            <Empty
              title={items?.length ? "选择一段会话" : "新的对话，从这里开始"}
              action={
                <button
                  className="button button-secondary"
                  onClick={() => navigate("overview")}
                >
                  返回工作概览
                  <Icon name="arrow" size={16} />
                </button>
              }
            >
              左侧选择好友，查看消息与回复。本地清记录不会删除微信里的聊天。
            </Empty>
          ) : (
            <>
              <div className="chat-heading">
                <div>
                  <h2>{selected.alias || "已绑定会话"}</h2>
                  <span className="muted">
                    {modeText(selected.scope.split(":").at(-1) || "")} ·
                    独立保存的会话范围
                  </span>
                </div>
                <button
                  className="icon-button"
                  title="清除此会话"
                  aria-label="清除当前会话记录"
                  disabled={busy || !editable}
                  onClick={() => openClear(selected)}
                >
                  <Icon name="trash" />
                </button>
              </div>
              <div className="chat-timeline">
                {!messages ? (
                  <Skeleton />
                ) : !timeline.length ? (
                  <Empty title="这一页没有消息" />
                ) : (
                  timeline.map((m) => (
                    <article
                      key={m.id}
                      className={
                        "chat-message " +
                        (m.author === "助理" ? "from-agent" : "")
                      }
                    >
                      <div className="chat-author">
                        <span>{m.author}</span>
                        <time>{timeText(m.time)}</time>
                      </div>
                      <div className="chat-bubble">
                        {m.attachment ? (
                          <div className="chat-attachment">
                            <strong>
                              {m.attachment.kind === "voice" ? "语音" : "文件"}
                              {m.attachment.name
                                ? ` · ${m.attachment.name}`
                                : ""}
                            </strong>
                            <span className="muted">
                              {m.attachment.status === "available"
                                ? `已获取到本地${m.attachment.byte_size != null ? ` · ${(m.attachment.byte_size / 1024).toFixed(1)} KB` : ""}`
                                : m.attachment.status === "pending"
                                  ? "等待查找本地内容"
                                  : m.attachment.reason === "ambiguous_file"
                                    ? "存在多个同名文件，暂时无法确定对应文件"
                                    : m.attachment.status === "error"
                                      ? "本地内容获取失败，运行时会自动重试"
                                      : "未找到本地内容，下载后将在运行时重试"}
                            </span>
                            <small className="muted">
                              仅保存本地内容，不参与自动回复
                            </small>
                            <button
                              className="button button-secondary"
                              disabled={
                                busy || m.attachment.status !== "available"
                              }
                              title={
                                m.attachment.status === "available"
                                  ? "在系统文件管理器中选中本地副本，双击即可打开"
                                  : "获取到本地内容后即可打开所在位置"
                              }
                              onClick={() =>
                                void perform(
                                  () =>
                                    api(
                                      `/attachments/${encodeURIComponent(m.messageId!)}/reveal`,
                                      "POST",
                                      {},
                                    ),
                                  "已打开所在位置",
                                )
                              }
                            >
                              打开所在位置
                            </button>
                          </div>
                        ) : (
                          <p className="preserve">{m.text || "非文本消息"}</p>
                        )}
                      </div>
                      <div className="chat-meta">
                        <Pill
                          tone={
                            m.reply?.state === "unknown"
                              ? "amber"
                              : m.author === "助理"
                                ? "green"
                                : "neutral"
                          }
                        >
                          {m.status}
                        </Pill>
                        {m.text && <CopyButton value={m.text} />}
                      </div>
                      {m.reply &&
                        ["unknown", "paused"].includes(m.reply.state) &&
                        !m.reply.resolution && (
                          <div className="button-row">
                            <button
                              className="button button-secondary"
                              disabled={busy || !editable}
                              onClick={() => openResolve(m.reply!, "sent")}
                            >
                              已核实发送
                            </button>
                            <button
                              className="quiet-button"
                              disabled={busy || !editable}
                              onClick={() => openResolve(m.reply!, "discarded")}
                            >
                              标记作废
                            </button>
                          </div>
                        )}
                    </article>
                  ))
                )}
              </div>
              <div className="chat-bottom">
                <span>本地确认不等于对端已收件</span>
                <div className="pagination">
                  <button
                    className="quiet-button"
                    disabled={!messageOffset}
                    onClick={() =>
                      setMessageOffset(Math.max(0, messageOffset - 30))
                    }
                  >
                    较新记录
                  </button>
                  <button
                    className="quiet-button"
                    disabled={
                      (messages?.length || 0) < 30 && replies.length < 30
                    }
                    onClick={() => setMessageOffset(messageOffset + 30)}
                  >
                    更早记录
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </section>
    </>
  );
}
