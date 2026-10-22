import React, { useEffect, useState } from "react";
import { api, errorText, modeText, timeText } from "../api";
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
import type { Contact, Fact, Page } from "../types";
export function Memories() {
  const { busy, editable, perform, dashboard, navigate } = useWorkspace();
  const [contacts, setContacts] = useState<Contact[]>();
  const [selected, setSelected] = useState("");
  const [facts, setFacts] = useState<Fact[]>();
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Fact | "new">();
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [forgetting, setForgetting] = useState<Fact>();
  const contact = contacts?.find(
    (c) => JSON.stringify([c.scope, c.contact]) === selected,
  );
  const params = contact
    ? new URLSearchParams({ scope: contact.scope, contact: contact.contact })
    : undefined;
  useEffect(() => {
    const controller = new AbortController();
    void api<Page<Contact>>(
      "/memories/contacts",
      "GET",
      undefined,
      controller.signal,
    )
      .then((p) => {
        setContacts(p.items);
        setSelected((old) =>
          p.items.some((c) => JSON.stringify([c.scope, c.contact]) === old)
            ? old
            : p.items[0]
              ? JSON.stringify([p.items[0].scope, p.items[0].contact])
              : "",
        );
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorText(e));
      });
    return () => controller.abort();
  }, [dashboard?.memories]);
  const reload = async () => {
    if (params) setFacts((await api<Page<Fact>>(`/memories?${params}`)).items);
  };
  useEffect(() => {
    setFacts(undefined);
    if (!params) return;
    const controller = new AbortController();
    void api<Page<Fact>>(
      `/memories?${params}`,
      "GET",
      undefined,
      controller.signal,
    )
      .then((p) => {
        setFacts(p.items);
        setError("");
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorText(e));
      });
    return () => controller.abort();
  }, [selected, dashboard?.memories]);
  return (
    <>
      <PageHeading
        eyebrow="MEMORY, WITH PERMISSION"
        title="记住偏好，也尊重边界。"
        description="长期记忆与短期对话分开保存。每个联系人、每种运行模式，各有自己的记忆。"
        action={
          <button
            className="button"
            disabled={busy || !editable || !contact}
            onClick={() => {
              setKey("");
              setValue("");
              setEditing("new");
            }}
          >
            <Icon name="plus" size={16} />
            添加偏好
          </button>
        }
      />
      {!editable && (
        <div className="callout">
          <Icon name="info" />
          <p>助理运行中可查看记忆；暂停或停止后，可以更正或忘记。</p>
        </div>
      )}
      {error && (
        <div className="feedback feedback-error" role="alert">
          {error}
        </div>
      )}
      <div className="memory-layout">
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>联系人偏好</h2>
              <p>只为选中的联系人使用，不会跨联系人混用。</p>
            </div>
            <Icon name="memory" />
          </div>
          <label className="field">
            查看谁的记忆
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              disabled={!contacts?.length || busy}
            >
              {!contacts?.length && <option>暂无已连接的联系人</option>}
              {contacts?.map((c) => (
                <option
                  key={c.scope + c.contact}
                  value={JSON.stringify([c.scope, c.contact])}
                >
                  {c.alias} · {modeText(c.scope.split(":").at(-1) || "")}
                </option>
              ))}
            </select>
          </label>
          {!contacts ? (
            <Skeleton />
          ) : !contact ? (
            <Empty
              icon="memory"
              title="从第一次连接开始"
              action={
                <button
                  className="button button-secondary"
                  onClick={() => navigate("overview")}
                >
                  去连接微信
                  <Icon name="arrow" size={16} />
                </button>
              }
            >
              正式运行建立绑定后，联系人会出现在这里。单纯的知识库模拟回复不会建立联系人记忆。
            </Empty>
          ) : !facts ? (
            <Skeleton />
          ) : !facts.length ? (
            <Empty icon="memory" title="还没有长期偏好">
              可以手动添加，也可以让好友发送右侧的明确记忆指令。
            </Empty>
          ) : (
            <div className="memory-facts">
              {facts.map((fact) => (
                <article className="memory-fact" key={fact.key}>
                  <div className="row-between">
                    <span className="field-label">{fact.key}</span>
                    <div className="button-row">
                      <button
                        className="icon-button"
                        aria-label={`更正${fact.key}`}
                        title="更正偏好"
                        disabled={busy || !editable}
                        onClick={() => {
                          setKey(fact.key);
                          setValue(fact.value);
                          setEditing(fact);
                        }}
                      >
                        <Icon name="edit" size={16} />
                      </button>
                      <button
                        className="icon-button"
                        aria-label={`忘记${fact.key}`}
                        title="忘记偏好"
                        disabled={busy || !editable}
                        onClick={() => setForgetting(fact)}
                      >
                        <Icon name="trash" size={16} />
                      </button>
                    </div>
                  </div>
                  <p>{fact.value}</p>
                  <div className="row-between">
                    <Pill>
                      {fact.source === "explicit_chat"
                        ? "好友明确指令"
                        : "工作台添加"}
                    </Pill>
                    <time className="muted">{timeText(fact.updated)}</time>
                  </div>
                </article>
              ))}
            </div>
          )}
          {contact && (
            <div className="micro-note">
              <Icon name="shield" size={14} />
              <span>
                当前为{modeText(contact.scope.split(":").at(-1) || "")}
                范围，每位联系人最多20条。更正或忘记时会清除这个会话的旧上下文。
              </span>
            </div>
          )}
        </section>
        <div className="memory-guide">
          <section className="panel">
            <span className="eyebrow">SMALL DETAILS. BETTER REPLIES.</span>
            <h2>怎样让助理记住你？</h2>
            <p>
              不会从普通聊天中擅自推断长期事实。需要好友发出一条明确指令，或由你在这里添加。
            </p>
            {[
              "记住我的偏好：饮品=乌龙茶",
              "更正我的偏好：饮品=白茶",
              "忘记我的偏好：饮品",
            ].map((command, index) => (
              <div className="memory-command" key={command}>
                <span className="field-label">
                  {["记住一件事", "更新旧偏好", "不再保留"][index]}
                </span>
                <div>
                  <code>{command}</code>
                  <CopyButton value={command} />
                </div>
              </div>
            ))}
          </section>
          <div className="callout">
            <Icon name="info" />
            <p>
              偏好在成功生成本轮回复后保存；模型失败或暂停后被取消的回复不会写入。发送结果不确定时，已经保存的偏好仍保留。
            </p>
          </div>
        </div>
      </div>
      {editing && contact && (
        <Modal
          title={editing === "new" ? "添加一条偏好" : "更正这条偏好"}
          description={`仅用于 ${contact.alias} · ${modeText(contact.scope.split(":").at(-1) || "")}`}
          busy={busy}
          onClose={() => setEditing(undefined)}
        >
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const ok = await perform(async () => {
                await api("/memories", "PUT", {
                  scope: contact.scope,
                  contact: contact.contact,
                  key: key.trim(),
                  value: value.trim(),
                });
                await reload();
              }, "偏好已保存，旧的短期上下文已清除。");
              if (ok) setEditing(undefined);
            }}
          >
            <div className="modal-content">
              <label className="field">
                偏好名称
                <input
                  required
                  maxLength={40}
                  readOnly={editing !== "new"}
                  value={key}
                  placeholder="例如：口味、预算、收货地区"
                  onChange={(e) => setKey(e.target.value)}
                />
              </label>
              <label className="field">
                偏好内容
                <textarea
                  autoFocus
                  required
                  rows={3}
                  maxLength={200}
                  value={value}
                  placeholder="例如：更喜欢中浅烘，不喜欢太苦的咖啡"
                  onChange={(e) => setValue(e.target.value)}
                />
              </label>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="button button-secondary"
                disabled={busy}
                onClick={() => setEditing(undefined)}
              >
                取消
              </button>
              <button
                className="button"
                disabled={busy || !key.trim() || !value.trim()}
              >
                保存偏好
              </button>
            </div>
          </form>
        </Modal>
      )}
      {forgetting && contact && (
        <Modal
          title={`忘记「${forgetting.key}」？`}
          description="删除这条长期偏好，并清除该会话的旧上下文。"
          busy={busy}
          onClose={() => setForgetting(undefined)}
        >
          <div className="modal-content">
            <div className="quote-block">{forgetting.value}</div>
            <p className="muted">其他联系人、知识库及历史收发记录不受影响。</p>
          </div>
          <div className="modal-footer">
            <button
              className="button button-secondary"
              disabled={busy}
              onClick={() => setForgetting(undefined)}
            >
              取消
            </button>
            <button
              className="button button-danger"
              disabled={busy || !editable}
              onClick={async () => {
                const ok = await perform(async () => {
                  await api(
                    `/memories?${params}&${new URLSearchParams({ key: forgetting.key })}`,
                    "DELETE",
                    {},
                  );
                  await reload();
                }, "已忘记这条偏好。");
                if (ok) setForgetting(undefined);
              }}
            >
              确认忘记
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
