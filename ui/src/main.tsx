import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import * as Tabs from "@radix-ui/react-tabs";
import {
  api,
  ApiError,
  errorText,
  knowledgeText,
  modeText,
  statusText,
} from "./api";
import { CopyButton, Icon, Modal, Pill } from "./components";
import { Overview } from "./views/Overview";
import { Conversations } from "./views/Conversations";
import { Knowledge } from "./views/Knowledge";
import { Memories } from "./views/Memories";
import { SettingsPage } from "./views/Settings";
import { WorkspaceContext } from "./workspace";
import type {
  Bases,
  Conversation,
  Dashboard,
  Nav,
  Outbox,
  Page,
  Preset,
  Run,
  Runtime,
  Settings,
  Setup,
  Values,
} from "./types";
import "./style.css";
const navigation: { id: Nav; title: string; icon: string }[] = [
  { id: "overview", title: "工作概览", icon: "home" },
  { id: "conversations", title: "会话与记录", icon: "chat" },
  { id: "knowledge", title: "知识库", icon: "book" },
  { id: "memories", title: "联系人记忆", icon: "memory" },
  { id: "settings", title: "设置", icon: "settings" },
];
function App() {
  const [nav, navigate] = useState<Nav>("overview");
  const [runtime, setRuntime] = useState<Runtime>();
  const [settings, setSettings] = useState<Settings>();
  const [setup, setSetup] = useState<Setup>();
  const [dashboard, setDashboard] = useState<Dashboard>();
  const [bases, setBases] = useState<Bases>();
  const [presets, setPresets] = useState<Preset[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [outbox, setOutbox] = useState<Outbox[]>([]);
  const [draft, setDraft] = useState<Values>({});
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [error, setError] = useState<{
    message: string;
    code?: string;
    trace?: string;
    polling?: boolean;
  }>();
  const [notice, setNotice] = useState("");
  const [help, setHelp] = useState(false);
  const [clearTarget, setClearTarget] = useState<Conversation | "all">();
  const [confirmation, setConfirmation] = useState("");
  const [forget, setForget] = useState(false);
  const [resolution, setResolution] = useState<{
    row: Outbox;
    value: "sent" | "discarded";
  }>();
  const [verified, setVerified] = useState(false);
  const [run, showRun] = useState<Run>();
  const editable =
    !!runtime && ["stopped", "paused", "degraded"].includes(runtime.state);
  const handleError = useCallback(
    (e: unknown, polling = false) =>
      setError({
        message: errorText(e),
        code: e instanceof ApiError ? e.code : undefined,
        trace: e instanceof ApiError ? e.trace : undefined,
        polling,
      }),
    [],
  );
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const [r, d, a, o, s, guide, k, p] = await Promise.all([
      api<Runtime>("/runtime", "GET", undefined, signal),
      api<Dashboard>("/dashboard", "GET", undefined, signal),
      api<Page<Run>>("/runs?limit=8", "GET", undefined, signal),
      api<Page<Outbox>>("/outbox?limit=50", "GET", undefined, signal),
      api<Settings>("/settings", "GET", undefined, signal),
      api<Setup>("/setup", "GET", undefined, signal),
      api<Bases>("/knowledge/bases", "GET", undefined, signal),
      api<Page<Preset>>("/agent/presets", "GET", undefined, signal),
    ]);
    if (signal?.aborted) return;
    setRuntime(r);
    setDashboard(d);
    setRuns(a.items);
    setOutbox(o.items);
    setSettings(s);
    setSetup(guide);
    setBases(k);
    setPresets(p.items);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let initialized = false;
    const poll = async () => {
      try {
        if (!initialized) {
          await refresh(controller.signal);
          initialized = true;
        } else {
          const [r, d, a, o] = await Promise.all([
            api<Runtime>("/runtime", "GET", undefined, controller.signal),
            api<Dashboard>("/dashboard", "GET", undefined, controller.signal),
            api<Page<Run>>(
              "/runs?limit=8",
              "GET",
              undefined,
              controller.signal,
            ),
            api<Page<Outbox>>(
              "/outbox?limit=50",
              "GET",
              undefined,
              controller.signal,
            ),
          ]);
          if (!controller.signal.aborted) {
            setRuntime(r);
            setDashboard(d);
            setRuns(a.items);
            setOutbox(o.items);
          }
        }
        if (!controller.signal.aborted)
          setError((old) => (old?.polling ? undefined : old));
      } catch (e) {
        if (!controller.signal.aborted) {
          setRuntime(undefined);
          handleError(e, true);
        }
      }
      if (!controller.signal.aborted)
        timer = setTimeout(() => void poll(), 3500);
    };
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [refresh, handleError]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(timer);
  }, [notice]);
  async function perform(task: () => Promise<unknown>, success = "") {
    if (lock.current) return false;
    lock.current = true;
    setBusy(true);
    setError(undefined);
    setNotice("");
    try {
      await task();
      try {
        await refresh();
        setNotice(success);
      } catch {
        handleError(
          new Error(
            "操作已执行，但状态刷新没有完成。请点击右上角刷新，核对最新结果。",
          ),
        );
      }
      return true;
    } catch (e) {
      handleError(e);
      return false;
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function runtimeAction(action: string) {
    await perform(
      () => api(`/runtime/${action}`, "POST", {}),
      (
        {
          start: "开始请求已提交，请留意连接状态。",
          resume: "恢复请求已提交，只处理恢复后的新消息。",
          pause: "助理已暂停。",
          stop: "助理已停止。",
        } as Record<string, string>
      )[action],
    );
  }
  async function saveSettings() {
    const saved = await perform(async () => {
      const updated = await api<Settings>("/settings", "PATCH", draft);
      setSettings(updated);
    }, "设置已保存，下次开始或恢复时生效。");
    if (saved) setDraft({});
  }
  function openClear(conversation?: Conversation) {
    setConfirmation("");
    setForget(false);
    setClearTarget(conversation || "all");
  }
  const pending = outbox.filter(
    (o) => ["unknown", "paused"].includes(o.state) && !o.resolution,
  );
  return (
    <WorkspaceContext.Provider
      value={{
        runtime,
        settings,
        setup,
        dashboard,
        bases,
        presets,
        runs,
        outbox,
        busy,
        editable,
        nav,
        navigate,
        perform,
        refresh,
        draft,
        setDraft,
        saveSettings,
        runtimeAction,
        openClear,
        openResolve: (row, value) => {
          setVerified(false);
          setResolution({ row, value });
        },
        showRun,
        errorMessage: error?.message,
      }}
    >
      <Tabs.Root
        className="app-shell"
        value={nav}
        onValueChange={(value) => navigate(value as Nav)}
        orientation="vertical"
      >
        <a className="skip-link" href="#workspace-main">
          跳到主要内容
        </a>
        <aside className="sidebar">
          <div className="brand">
            <span className="brand-symbol">
              <Icon name="chat" size={23} />
            </span>
            <div>
              <strong>
                Reply Studio<span className="brand-dot">.</span>
              </strong>
              <small>微信回复工作台</small>
            </div>
          </div>
          <div className="workspace-switch">
            <span className="workspace-avatar">W</span>
            <span>
              我的工作空间<small>本机 · 个人测试</small>
            </span>
            <Icon name="shield" size={14} />
          </div>
          <span className="nav-caption">WORKSPACE</span>
          <Tabs.List className="navigation" aria-label="工作台导航">
            {navigation.map((item) => (
              <Tabs.Trigger value={item.id} key={item.id}>
                <Icon name={item.icon} />
                <span>{item.title}</span>
                {item.id === "conversations" && !!dashboard?.unresolved && (
                  <span className="nav-count">{dashboard.unresolved}</span>
                )}
                {item.id === "settings" && Object.keys(draft).length > 0 && (
                  <span className="draft-dot" title="有未保存的修改" />
                )}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          <div className="sidebar-bottom">
            <button className="sidebar-help" onClick={() => setHelp(true)}>
              <Icon name="help" />
              <span>使用指南</span>
              <Icon name="arrow" size={15} />
            </button>
            <div className="sidebar-foot">
              <span className="status-dot" />
              <span>
                本机服务<span className="sidebar-version"> v0.1</span>
              </span>
              <Icon name="shield" size={14} />
            </div>
          </div>
        </aside>
        <div className="workspace-body">
          <header className="topbar">
            <div className="breadcrumbs">
              <span>工作空间</span>
              <span>/</span>
              <strong>{navigation.find((n) => n.id === nav)?.title}</strong>
            </div>
            <div className="topbar-actions">
              <span className="platform-tag">
                <Icon name="globe" size={14} />
                {runtime?.platform || settings?.platform || "本机"}
              </span>
              <span className="topbar-status">
                <span
                  className={
                    "status-dot " +
                    (runtime?.state === "running"
                      ? "is-green"
                      : runtime?.state === "degraded"
                        ? "is-amber"
                        : "is-muted")
                  }
                />
                {runtime ? statusText(runtime.state) : "连接服务中"}
              </span>
              <button
                className="icon-button"
                title="刷新状态"
                aria-label="刷新工作台状态"
                disabled={busy}
                onClick={() => void perform(async () => {}, "状态已刷新。")}
              >
                <Icon name="refresh" className={busy ? "spin" : ""} />
              </button>
              <button
                className="icon-button"
                aria-label="使用指南"
                title="使用指南"
                onClick={() => setHelp(true)}
              >
                <Icon name="help" />
              </button>
              <span className="user-avatar" aria-label="本机用户">
                我
              </span>
            </div>
          </header>
          <main id="workspace-main" className="page-content">
            {error && (
              <div className="feedback feedback-error" role="alert">
                <Icon name="info" />
                <div>
                  <strong>{error.message}</strong>
                  {error.code && (
                    <details>
                      <summary>查看技术信息</summary>
                      <code>
                        {error.code}
                        {error.trace ? ` · ${error.trace}` : ""}
                      </code>
                    </details>
                  )}
                </div>
                <button
                  className="icon-button"
                  aria-label="关闭错误提示"
                  onClick={() => setError(undefined)}
                >
                  <Icon name="close" />
                </button>
              </div>
            )}
            {notice && (
              <div className="toast" role="status">
                <Icon name="check" />
                <span>{notice}</span>
                <button
                  className="icon-button"
                  aria-label="关闭提示"
                  onClick={() => setNotice("")}
                >
                  <Icon name="close" size={16} />
                </button>
              </div>
            )}
            {!!dashboard?.unresolved && nav !== "overview" && (
              <button
                className="pending-banner"
                onClick={() => navigate("overview")}
              >
                <Icon name="info" />
                <span>
                  {dashboard.unresolved}{" "}
                  条回复待核对，处理后可继续运行或清除记录
                </span>
                <Icon name="arrow" />
              </button>
            )}
            <Tabs.Content value="overview">
              <Overview pending={pending} />
            </Tabs.Content>
            <Tabs.Content value="conversations">
              <Conversations />
            </Tabs.Content>
            <Tabs.Content value="knowledge">
              <Knowledge />
            </Tabs.Content>
            <Tabs.Content value="memories">
              <Memories />
            </Tabs.Content>
            <Tabs.Content value="settings">
              <SettingsPage />
            </Tabs.Content>
            <footer className="page-footer">
              <Icon name="shield" size={13} />
              <span>仅处理已绑定的测试好友 · 生成内容会按你的模型配置处理</span>
              <span>Reply Studio</span>
            </footer>
          </main>
        </div>
      </Tabs.Root>
      {clearTarget && (
        <Modal
          title={
            clearTarget === "all"
              ? "清除全部本地记录"
              : `清除「${clearTarget.alias || "当前会话"}」的记录`
          }
          description={
            clearTarget === "all"
              ? "范围：本机全部会话与运行模式。此操作无法从工作台撤销。"
              : `范围：${modeText(clearTarget.scope.split(":").at(-1) || "")} · 当前会话。此操作无法撤销。`
          }
          busy={busy}
          onClose={() => setClearTarget(undefined)}
        >
          <div className="modal-content">
            <div className="callout">
              <Icon name="trash" />
              <p>
                清除消息正文、助理回复、执行记录及短期对话上下文。知识库、微信中的消息和登录配置不受影响。
              </p>
            </div>
            <label className="check-row">
              <input
                type="checkbox"
                checked={forget}
                onChange={(e) => setForget(e.target.checked)}
              />
              同时忘记{clearTarget === "all" ? "所有联系人" : "该会话范围"}
              的长期偏好
            </label>
            <p className="field-hint">
              必要的防重复发送标识仍会保留。待核对的回复需先处理，不能通过清除记录跳过。
            </p>
            <label className="field">
              输入“清除”以确认
              <input
                autoComplete="off"
                value={confirmation}
                onChange={(e) => setConfirmation(e.target.value)}
                placeholder="清除"
              />
            </label>
          </div>
          <div className="modal-footer">
            <button
              className="button button-secondary"
              disabled={busy}
              onClick={() => setClearTarget(undefined)}
            >
              取消
            </button>
            <button
              className="button button-danger"
              disabled={busy || !editable || confirmation !== "清除"}
              onClick={async () => {
                const ok = await perform(
                  () =>
                    api("/history/clear", "POST", {
                      confirmation,
                      forget_memories: forget,
                      ...(clearTarget === "all"
                        ? {}
                        : {
                            scope: clearTarget.scope,
                            conversation: clearTarget.id,
                          }),
                    }),
                  "本地记录已清除，后续新消息会正常记录。",
                );
                if (ok) setClearTarget(undefined);
              }}
            >
              {busy ? "正在清除…" : "确认清除"}
            </button>
          </div>
        </Modal>
      )}
      {resolution && (
        <Modal
          title={
            resolution.value === "sent"
              ? "确认这条回复已经发送"
              : "将这条回复标记为作废"
          }
          description="请先在微信及对端核对。本操作只记录你的结论，不会再次发送。"
          busy={busy}
          onClose={() => setResolution(undefined)}
        >
          <div className="modal-content">
            <div className="quote-block">{resolution.row.reply_text}</div>
            <label className="check-row">
              <input
                type="checkbox"
                checked={verified}
                onChange={(e) => setVerified(e.target.checked)}
              />
              我已核对实际情况，确认
              {resolution.value === "sent"
                ? "这条回复已发送"
                : "将这条回复作废"}
            </label>
          </div>
          <div className="modal-footer">
            <button
              className="button button-secondary"
              disabled={busy}
              onClick={() => setResolution(undefined)}
            >
              取消
            </button>
            <button
              className="button"
              disabled={busy || !verified || !editable}
              onClick={async () => {
                const ok = await perform(
                  () =>
                    api(`/outbox/${resolution.row.id}/resolve`, "POST", {
                      resolution: resolution.value,
                    }),
                  "核对结论已记录，不会重新发送。",
                );
                if (ok) setResolution(undefined);
              }}
            >
              保存核对结论
            </button>
          </div>
        </Modal>
      )}
      {run && (
        <Modal
          title="回复处理详情"
          description={`执行记录 #${run.trace_id} · ${modeText(run.scope.split(":").at(-1) || "")}`}
          wide
          onClose={() => showRun(undefined)}
        >
          <div className="modal-content">
            <div className="row-between">
              <Pill tone={run.status === "ready" ? "green" : "amber"}>
                {statusText(run.status)}
              </Pill>
              <span className="muted">
                {knowledgeText(run.knowledge_status)}
              </span>
            </div>
            <div className="quote-block">
              {run.reply_text || "本轮没有生成可用回复。"}
            </div>
            <div className="detail-metrics">
              <span>
                读取 <strong>{Math.round(run.poll_ms)} ms</strong>
              </span>
              <span>
                模型 <strong>{Math.round(run.model_ms)} ms</strong>
              </span>
              <span>
                发送{" "}
                <strong>
                  {run.send_ms === null
                    ? "未执行"
                    : Math.round(run.send_ms) + " ms"}
                </strong>
              </span>
            </div>
            <h3>本轮采用的知识来源</h3>
            {run.sources.length ? (
              run.sources.map((source) => (
                <div className="source-item" key={source.source_ref}>
                  <Icon name="file" />
                  <span>
                    {source.name}
                    <small>片段 {source.ordinal}</small>
                  </span>
                </div>
              ))
            ) : (
              <p className="muted">本轮没有采用本地知识片段。</p>
            )}
            <details className="technical">
              <summary>技术记录</summary>
              <p>结果：{run.reason}</p>
              <p className="mono">输入引用：{run.input_refs.join(" / ")}</p>
            </details>
          </div>
        </Modal>
      )}
      {help && (
        <Modal
          title="从这里开始，三步上手"
          description="先看资料和模拟回复，再连接微信验证。"
          wide
          onClose={() => setHelp(false)}
        >
          <div className="modal-content guide-content">
            <div>
              <span className="step-number">01</span>
              <h3>连接你自己的模型</h3>
              <p>
                在设置里填写模型地址、名称和密钥。可以先测试连接，保存后才会用于新回复。密钥只保存在本机后端。
              </p>
            </div>
            <div>
              <span className="step-number">02</span>
              <h3>给助理准备可靠的资料</h3>
              <p>
                知识库内置了虚构的北线咖啡示例。启用后可直接用测试问题查资料、生成模拟回复。也可以新建自己的知识库，导入
                TXT / Markdown。
              </p>
            </div>
            <div>
              <span className="step-number">03</span>
              <h3>先仅生成，再微信发送</h3>
              <p>
                选择已绑定好友，从“仅生成回复”开始。确认回答正确后，再明确切换为“微信发送”。每次最多回复3条，至少间隔30秒。
              </p>
            </div>
            <div className="callout">
              <Icon name="info" />
              <p>
                {runtime?.platform === "macOS"
                  ? "Mac 请保持绑定的独立聊天窗打开、输入框为空，桌面解锁。当前已授权的降级接入需要你人工核对窗口和收件。"
                  : "Windows 请保持微信已登录、桌面解锁，完成本机账号与测试好友绑定。环境检查不会主动初始化微信。"}
              </p>
            </div>
            <details className="technical">
              <summary>启动命令与接入说明</summary>
              <div className="code-row">
                <code>./.local/tooling/bin/uv run wechat-agent serve</code>
                <CopyButton value="./.local/tooling/bin/uv run wechat-agent serve" />
              </div>
              <p>
                如果终端已经安装 uv，也可以用 uv run wechat-agent
                serve。更新代码后，先在旧终端按
                Ctrl+C，再重新启动。首次账号绑定和权限准备请参考项目中的
                docs/mac-probe.md 或 docs/windows-probe.md。
              </p>
            </details>
          </div>
          <div className="modal-footer">
            <button
              className="button"
              onClick={() => {
                setHelp(false);
                navigate("settings");
              }}
            >
              去完成设置
              <Icon name="arrow" size={16} />
            </button>
          </div>
        </Modal>
      )}
    </WorkspaceContext.Provider>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
