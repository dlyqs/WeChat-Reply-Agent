import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import * as Tabs from "@radix-ui/react-tabs";
import "./style.css";

type Runtime = {
  state: string;
  reason: string;
  connected: boolean;
  mode: string;
  generation: number;
  sent_this_run: number;
  max_replies: number;
  initialization: Record<string, string>;
  platform: string;
  foundation: string;
  capabilities: {
    ui_checks_degraded?: boolean;
    max_text_characters?: number;
    supports_newlines?: boolean;
    target_navigation?: string;
  };
};
type Conversation = {
  id: string;
  scope: string;
  alias: string | null;
  message_count: number;
};
type Message = {
  id: string;
  text: string | null;
  direction: string;
  status: string;
  observed_at: string;
};
type Run = {
  trace_id: string;
  scope: string;
  status: string;
  reason: string;
  reply_text: string;
  poll_ms: number;
  model_ms: number;
  send_ms: number | null;
  input_refs: string[];
};
type Outbox = {
  id: string;
  state: string;
  resolution: string | null;
  reply_text: string;
  mode: string;
  scope: string;
  basis: string | null;
};
type Values = Record<string, string | number | boolean | string[] | null>;
type Settings = {
  values: Values;
  sources: Record<string, string>;
  readonly: string[];
  inactive: string[];
  platform: string;
};
type Page<T> = { items: T[] };
const labels: Record<string, string> = {
  stopped: "已停止",
  starting: "正在连接",
  running: "运行中",
  paused: "已暂停",
  degraded: "已降级 · 停发",
  stopping: "正在停止",
  unknown: "待人工核实",
  cancelled: "已丢弃",
  run_generation_expired: "暂停或停止后返回的结果已作废",
  verified_sent: "本地新记录已确认",
  not_sent: "未发送",
  baseline: "启动基线",
  filtered: "已过滤",
  pending: "排队中",
  processed: "已处理",
  failed: "处理失败",
  incoming: "好友来信",
  outgoing: "本人发出",
  system: "系统消息",
};
const fieldLabels: Record<string, string> = {
  wechat_profile: "绑定文件",
  wechat_account_ref: "账号引用",
  wechat_allowlist: "白名单（JSON 数组）",
  wechat_db_root: "数据库根目录",
  wechat_ocr_enabled: "启用 OCR",
  wechat_uia_gate_enabled: "启用 UIA 热激活",
  send_mode: "发送模式",
  poll_interval_seconds: "轮询间隔（秒）",
  llm_base_url: "模型地址",
  llm_model: "模型名称",
  llm_timeout_seconds: "模型超时（秒）",
  llm_max_input_tokens: "输入预算",
  llm_max_output_tokens: "输出预算",
  llm_max_calls_per_turn: "调用预算",
  agent_persona: "回复人设",
  max_reply_characters: "回复字数上限",
  coalesce_window_ms: "消息合并窗口（毫秒）",
  queue_max_size: "队列上限",
  min_send_interval_seconds: "发送间隔（秒）",
  max_sends_per_minute: "每分钟发送上限",
  retention_days: "基座缓存保留天数",
  mac_bridge_path: "Mac 原生桥路径",
  mac_verify_timeout_seconds: "Mac 发送回读超时（秒）",
};
const text = (value: string) => labels[value] || value;
async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json", "X-WeChat-Agent": "1" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      `${result.code || "request_failed"} · ${result.trace_id || ""}`,
    );
  return result;
}
function App() {
  const [runtime, setRuntime] = useState<Runtime>();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Conversation>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [outbox, setOutbox] = useState<Outbox[]>([]);
  const [settings, setSettings] = useState<Settings>();
  const [draft, setDraft] = useState<Values>({});
  const [key, setKey] = useState("");
  const [clearKey, setClearKey] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [diagnostic, setDiagnostic] = useState("");
  const [offset, setOffset] = useState(0);
  const [conversationOffset, setConversationOffset] = useState(0);
  const editable =
    runtime && ["stopped", "paused", "degraded"].includes(runtime.state);
  async function refresh() {
    const [r, c, a, o] = await Promise.all([
      api<Runtime>("/runtime"),
      api<Page<Conversation>>(
        `/conversations?limit=30&offset=${conversationOffset}`,
      ),
      api<Page<Run>>("/runs?limit=50"),
      api<Page<Outbox>>("/outbox?limit=50"),
    ]);
    setRuntime(r);
    setConversations(c.items);
    setRuns(a.items);
    setOutbox(o.items);
  }
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        if (alive) await refresh();
      } catch (e) {
        if (alive) setError(String(e));
      }
    };
    void load();
    const timer = setInterval(() => void load(), 3000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [conversationOffset]);
  useEffect(() => {
    api<Settings>("/settings")
      .then(setSettings)
      .catch((e) => setError(String(e)));
  }, []);
  useEffect(() => {
    if (!selected) return;
    let alive = true;
    const load = () =>
      api<Page<Message>>(
        `/conversations/${encodeURIComponent(selected.id)}/messages?scope=${encodeURIComponent(selected.scope)}&limit=30&offset=${offset}`,
      )
        .then((p) => {
          if (alive) setMessages(p.items);
        })
        .catch((e) => {
          if (alive) setError(String(e));
        });
    void load();
    const timer = setInterval(() => void load(), 3000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [selected, offset]);
  async function action(fn: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await refresh();
      setNotice(success);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    const body: Record<string, unknown> = { ...draft };
    if (typeof body.wechat_allowlist === "string")
      body.wechat_allowlist = JSON.parse(body.wechat_allowlist);
    if (key) body.llm_api_key = key;
    if (clearKey) body.clear_llm_api_key = true;
    const updated = await api<Settings>("/settings", "PATCH", body);
    setSettings(updated);
    setDraft({});
    setKey("");
    setClearKey(false);
  }
  const unknown = outbox.filter(
    (o) => ["unknown", "paused"].includes(o.state) && !o.resolution,
  );
  return (
    <Tabs.Root defaultValue="overview" className="shell">
      <aside>
        <div className="brand">
          <span className="brand-mark">微</span>
          <div>
            微信回复<small>本地 Agent 工作台</small>
          </div>
        </div>
        <Tabs.List aria-label="主导航">
          <Tabs.Trigger value="overview">概览</Tabs.Trigger>
          <Tabs.Trigger value="conversations">会话</Tabs.Trigger>
          <Tabs.Trigger value="settings">设置</Tabs.Trigger>
        </Tabs.List>
        <div className="aside-note">
          个人测试环境
          <br />
          仅处理已绑定白名单单聊
          <br />
          每次启动最多回复 3 条
        </div>
      </aside>
      <main>
        <header>
          <div>
            <small>WECHAT REPLY AGENT</small>
            <h1>让每次回复都有记录</h1>
          </div>
          <span
            className={"badge " + (runtime?.state === "running" ? "good" : "")}
          >
            {runtime ? text(runtime.state) : "连接本地服务中"}
          </span>
        </header>
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
        {unknown.length > 0 && (
          <div className="alert">
            有 {unknown.length}{" "}
            条回复需要人工处理。请核对微信及对端收件，在下方标记已发或作废后重新开始。
          </div>
        )}
        <Tabs.Content value="overview">
          <section>
            <h2>
              {runtime?.platform || settings?.platform || "本机"} · 微信连接方式
            </h2>
            <p>
              {runtime?.foundation === "mac_db"
                ? "本地数据库读取与确认 · 独立聊天窗发送"
                : "Windows Replica"}
            </p>
            {runtime?.capabilities.ui_checks_degraded && (
              <p className="notice">
                当前为已选择的降级模式：未核验空草稿、输入全文及窗口遮挡。请保持绑定聊天窗打开、输入框为空；发送结果按本地新增记录确认。
              </p>
            )}
            {runtime?.capabilities.max_text_characters && (
              <p>
                文字能力上限 {runtime.capabilities.max_text_characters} 字 ·{" "}
                {runtime.capabilities.supports_newlines ? "支持换行" : "仅单行"}
              </p>
            )}
          </section>
          <section className="cards">
            <article>
              <small>发送模式</small>
              <h2>
                {runtime?.mode === "live"
                  ? "LIVE · 真实发送"
                  : "DRY-RUN · 只生成"}
              </h2>
              <p>
                {runtime?.mode === "live"
                  ? "仅向已绑定白名单发送文字"
                  : "不执行输入或发送按键"}
              </p>
            </article>
            <article>
              <small>微信连接</small>
              <h2>{runtime?.connected ? "已连接" : "未连接"}</h2>
              <p>{runtime?.reason || "等待本地服务"}</p>
            </article>
            <article>
              <small>本次回复</small>
              <h2>
                {runtime?.sent_this_run || 0}
                <em> / 3</em>
              </h2>
              <p>运行代数 {runtime?.generation || 0} · 暂停后旧队列作废</p>
            </article>
          </section>
          <section>
            <div className="section-heading">
              <div>
                <h2>运行控制</h2>
                <p>
                  {runtime?.foundation === "mac_db"
                    ? "开始会校验已有密钥与绑定，不重新取钥；发送前自动切回已打开的绑定聊天窗。"
                    : "开始会初始化基座、读取密钥缓存并按配置校准或热激活。"}
                  启动前历史不自动回复。
                </p>
              </div>
              <div className="actions">
                <button
                  disabled={busy || !editable || runtime?.state === "paused"}
                  onClick={() =>
                    void action(
                      () => api("/runtime/start", "POST", {}),
                      "开始请求已提交，请查看连接状态。",
                    )
                  }
                >
                  开始
                </button>
                <button
                  disabled={
                    busy ||
                    !["running", "starting"].includes(runtime?.state || "")
                  }
                  onClick={() =>
                    void action(
                      () => api("/runtime/pause", "POST", {}),
                      "已暂停，旧队列不再发送。",
                    )
                  }
                >
                  暂停
                </button>
                <button
                  disabled={busy || runtime?.state !== "paused"}
                  onClick={() =>
                    void action(
                      () => api("/runtime/resume", "POST", {}),
                      "恢复请求已提交，将重新建立基线。",
                    )
                  }
                >
                  恢复
                </button>
                <button
                  className="secondary"
                  disabled={busy || !runtime || runtime.state === "stopped"}
                  onClick={() =>
                    void action(
                      () => api("/runtime/stop", "POST", {}),
                      "工作线程已停止。",
                    )
                  }
                >
                  停止
                </button>
              </div>
            </div>
            {busy && <p role="status">正在处理，请等待当前调用结束…</p>}
            {runtime && Object.keys(runtime.initialization).length > 0 && (
              <p>
                初始化结果：
                {Object.entries(runtime.initialization)
                  .map(([step, status]) => `${step}: ${status}`)
                  .join(" · ")}
              </p>
            )}
          </section>
          <section>
            <h2>发送记录</h2>
            <p>
              本地数据库确认不等于对端送达；不确定的发送不会自动重试。显示最近
              50 条。
            </p>
            {outbox.length === 0 ? (
              <div className="empty">
                还没有回复记录。配置白名单后，先用 dry-run 开始测试。
              </div>
            ) : (
              outbox.map((o) => (
                <article className="record" key={o.id}>
                  <div>
                    <span
                      className={
                        "badge " + (o.state === "unknown" ? "warn" : "")
                      }
                    >
                      {text(o.state)}
                    </span>
                    <small>
                      {o.mode} · {o.id}
                    </small>
                  </div>
                  <p className="content">{o.reply_text}</p>
                  <small>
                    {o.basis || "尚未执行"}{" "}
                    {o.resolution &&
                      `· 人工结果：${o.resolution === "sent" ? "已发" : "作废"}`}
                  </small>
                  {["unknown", "paused"].includes(o.state) && !o.resolution && (
                    <div className="actions">
                      <button
                        disabled={busy || !editable}
                        onClick={() =>
                          void action(
                            () =>
                              api(`/outbox/${o.id}/resolve`, "POST", {
                                resolution: "sent",
                              }),
                            "人工核对已记录。",
                          )
                        }
                      >
                        已核实发送
                      </button>
                      <button
                        className="secondary"
                        disabled={busy || !editable}
                        onClick={() =>
                          void action(
                            () =>
                              api(`/outbox/${o.id}/resolve`, "POST", {
                                resolution: "discarded",
                              }),
                            "已作废，不会重发。",
                          )
                        }
                      >
                        作废
                      </button>
                    </div>
                  )}
                </article>
              ))
            )}
          </section>
          <section>
            <h2>Agent 执行时间线</h2>
            <p>显示最近 50 次执行，仅包含输入引用、回复结果与耗时。</p>
            {runs.length === 0 ? (
              <div className="empty">等待新消息触发 Agent。</div>
            ) : (
              runs.map((r) => (
                <details key={r.trace_id}>
                  <summary>
                    #{r.trace_id} · {text(r.status)} · 模型{" "}
                    {Math.round(r.model_ms)} ms · {r.reason}
                  </summary>
                  <p className="content">
                    {r.reply_text || "本轮没有可发送回复"}
                  </p>
                  <small>
                    读取 {Math.round(r.poll_ms)} ms / 发送{" "}
                    {r.send_ms === null
                      ? "未执行"
                      : `${Math.round(r.send_ms)} ms`}
                  </small>
                  <p className="refs">输入：{r.input_refs.join(" / ")}</p>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() =>
                      void action(async () => {
                        const detail = await api<Run>(`/runs/${r.trace_id}`);
                        setRuns((old) =>
                          old.map((item) =>
                            item.trace_id === detail.trace_id ? detail : item,
                          ),
                        );
                      }, "执行记录已刷新。")
                    }
                  >
                    刷新详情
                  </button>
                </details>
              ))
            )}
          </section>
        </Tabs.Content>
        <Tabs.Content value="conversations">
          <section className="conversation-layout">
            <div>
              <h2>会话记录</h2>
              {conversations.length === 0 && (
                <div className="empty">
                  尚无会话。启动后的基线与新消息会记录在这里。
                </div>
              )}
              {conversations.map((c) => (
                <button
                  className={
                    "conversation " +
                    (selected?.id === c.id && selected?.scope === c.scope
                      ? "selected"
                      : "")
                  }
                  key={c.scope + c.id}
                  onClick={() => {
                    setSelected(c);
                    setOffset(0);
                    setMessages([]);
                  }}
                >
                  <strong>{c.alias || c.id}</strong>
                  <small>
                    {c.scope} · {c.message_count} 条
                  </small>
                </button>
              ))}
              <div className="actions">
                <button
                  className="secondary"
                  disabled={!conversationOffset}
                  onClick={() =>
                    setConversationOffset(Math.max(0, conversationOffset - 30))
                  }
                >
                  上一页
                </button>
                <button
                  className="secondary"
                  disabled={conversations.length < 30}
                  onClick={() => setConversationOffset(conversationOffset + 30)}
                >
                  下一页
                </button>
              </div>
            </div>
            <div className="messages">
              <h2>{selected?.alias || selected?.id || "选择一个会话"}</h2>
              {selected && messages.length === 0 && (
                <div className="empty">这一页没有消息。</div>
              )}
              {messages.map((m) => (
                <article className="message" key={m.id}>
                  <small>
                    {text(m.direction)} ·{" "}
                    {new Date(m.observed_at).toLocaleString()} ·{" "}
                    {text(m.status)}
                  </small>
                  <p className="content">{m.text || "非文本消息"}</p>
                  {m.status === "filtered" && (
                    <small>
                      方向、消息类型、身份或白名单不符合自动回复条件。
                    </small>
                  )}
                </article>
              ))}
              {selected && (
                <div className="actions">
                  <button
                    className="secondary"
                    disabled={!offset}
                    onClick={() => setOffset(Math.max(0, offset - 30))}
                  >
                    较新消息
                  </button>
                  <button
                    className="secondary"
                    disabled={messages.length < 30}
                    onClick={() => setOffset(offset + 30)}
                  >
                    较早消息
                  </button>
                </div>
              )}
            </div>
          </section>
        </Tabs.Content>
        <Tabs.Content value="settings">
          <section>
            <div className="section-heading">
              <div>
                <h2>连接与回复配置</h2>
                <p>
                  停止后保存，下次开始生效。环境变量优先于本地文件；密钥留空会保留已有值。
                </p>
              </div>
              <button
                disabled={busy || !editable || !settings}
                onClick={() =>
                  void action(save, "配置已原子保存。请核对有效值与来源。")
                }
              >
                保存配置
              </button>
            </div>
            {settings ? (
              <div className="form">
                {Object.entries(settings.values)
                  .filter(([name]) => name !== "llm_api_key_configured")
                  .map(([name, value]) => (
                    <label key={name}>
                      {fieldLabels[name] || name}
                      <small>
                        {settings.sources[name]}
                        {settings.readonly.includes(name)
                          ? " · 启动参数只读"
                          : ""}
                        {settings.inactive.includes(name)
                          ? " · 当前平台不适用"
                          : ""}
                      </small>
                      {typeof value === "boolean" ? (
                        <input
                          type="checkbox"
                          disabled={
                            !editable ||
                            settings.readonly.includes(name) ||
                            settings.inactive.includes(name)
                          }
                          checked={Boolean(draft[name] ?? value)}
                          onChange={(e) =>
                            setDraft({ ...draft, [name]: e.target.checked })
                          }
                        />
                      ) : name === "send_mode" ? (
                        <select
                          disabled={!editable}
                          value={String(draft[name] ?? value)}
                          onChange={(e) =>
                            setDraft({ ...draft, [name]: e.target.value })
                          }
                        >
                          <option value="dry-run">dry-run · 只生成</option>
                          <option value="live">live · 真实发送</option>
                        </select>
                      ) : (
                        <textarea
                          rows={name === "agent_persona" ? 4 : 1}
                          disabled={
                            !editable ||
                            settings.readonly.includes(name) ||
                            settings.inactive.includes(name)
                          }
                          value={String(
                            draft[name] ??
                              (Array.isArray(value)
                                ? JSON.stringify(value)
                                : (value ?? "")),
                          )}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              [name]:
                                typeof value === "number"
                                  ? Number(e.target.value)
                                  : [
                                        "wechat_db_root",
                                        "mac_bridge_path",
                                      ].includes(name) && !e.target.value
                                    ? null
                                    : e.target.value,
                            })
                          }
                        />
                      )}
                    </label>
                  ))}
                <label>
                  模型 API 密钥
                  <small>
                    {settings.values.llm_api_key_configured
                      ? "已配置 · 值不返回浏览器"
                      : "未配置"}
                  </small>
                  <input
                    type="password"
                    autoComplete="new-password"
                    value={key}
                    disabled={!editable}
                    onChange={(e) => setKey(e.target.value)}
                  />
                </label>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={clearKey}
                    disabled={!editable}
                    onChange={(e) => setClearKey(e.target.checked)}
                  />
                  显式清除已保存密钥（环境变量仍优先）
                </label>
              </div>
            ) : (
              <div className="empty">正在读取配置…</div>
            )}
          </section>
          <section>
            <div className="section-heading">
              <div>
                <h2>环境诊断</h2>
                <p>只读检查，不取钥、不热激活。真实连接状态以概览为准。</p>
              </div>
              <button
                disabled={busy || !editable}
                className="secondary"
                onClick={() =>
                  void action(async () => {
                    const d = await api<{
                      healthy: boolean;
                      reason: string;
                      capabilities: { send_confirmation: string };
                      permissions: Record<string, boolean>;
                    }>("/diagnostics", "POST", {});
                    setDiagnostic(
                      `${d.healthy ? "环境可用，仍需显式开始连接" : "环境尚未就绪"} · ${d.reason}\n${d.capabilities.send_confirmation}\n${Object.entries(
                        d.permissions,
                      )
                        .map(
                          ([name, enabled]) =>
                            `${({ accessibility: "辅助功能", screen_recording: "屏幕录制权限", screen_locked: "桌面锁定", account_security_stop: "账号安全停发" } as Record<string, string>)[name] || name}：${enabled ? "是" : "否"}`,
                        )
                        .join(" · ")}`,
                    );
                  }, "诊断完成。")
                }
              >
                运行诊断
              </button>
            </div>
            {diagnostic && <p className="content">{diagnostic}</p>}
          </section>
        </Tabs.Content>
        <footer>
          所有数据保存在本机 · 支持范围与人工验收见项目文档 · 知识 /
          长期记忆尚未接入（Phase 7）
        </footer>
      </main>
    </Tabs.Root>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
