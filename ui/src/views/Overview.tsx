import React from "react";
import { Empty, Icon, PageHeading, Pill, Skeleton } from "../components";
import {
  knowledgeText,
  modeText,
  reasonText,
  statusText,
  timeText,
} from "../api";
import { useWorkspace } from "../workspace";
import type { Outbox } from "../types";
export function Overview({ pending }: { pending: Outbox[] }) {
  const {
    runtime,
    dashboard,
    settings,
    setup,
    bases,
    runs,
    outbox,
    busy,
    editable,
    navigate,
    runtimeAction,
    openResolve,
    showRun,
  } = useWorkspace();
  const active =
    bases?.items.filter((b) => b.enabled && b.document_count > 0) || [];
  const steps = [
    {
      title: "连接回复模型",
      text: "填写密钥，测试连接并保存",
      ready: !!setup?.model_ready,
      target: "settings" as const,
    },
    {
      title: "准备知识与回复风格",
      text: "启用示例知识库，或导入自己的资料",
      ready: active.length > 0,
      target: "knowledge" as const,
    },
    {
      title: "选择测试好友",
      text: "在设置中选中已绑定的单聊好友",
      ready: !!setup?.allowlist_ready && !!setup?.profile_ready,
      target: "settings" as const,
    },
  ];
  const ready = steps.filter((s) => s.ready).length;
  return (
    <>
      <PageHeading
        eyebrow="YOUR REPLY WORKSPACE"
        title="让每次回复，都更从容。"
        description="把资料、会话与回复连在一起，让助理有依据地回答。"
        action={
          <Pill tone={runtime?.mode === "live" ? "amber" : "green"}>
            <span className="status-dot" />
            {modeText(runtime?.mode || "")}
          </Pill>
        }
      />
      <section className="hero-panel">
        <div className="hero-copy">
          <span className="eyebrow">LESS REPETITION. MORE CONVERSATION.</span>
          <h2>
            好好说话，
            <br />
            也有据可答。
          </h2>
          <p>
            {runtime?.state === "running"
              ? "助理正在留意好友的新消息。你可以在这里查看每条回复的状态和资料来源。"
              : "先配置模型与知识，再让助理接住重复的问题。你始终掌握何时开始、暂停和发送。"}
          </p>
          <div className="button-row">
            {runtime?.state === "running" || runtime?.state === "starting" ? (
              <button
                className="button"
                disabled={busy}
                onClick={() => void runtimeAction("pause")}
              >
                <Icon name="pause" size={16} />
                暂停助理
              </button>
            ) : (
              <button
                className="button"
                disabled={
                  busy ||
                  !editable ||
                  !setup?.model_ready ||
                  !setup?.allowlist_ready ||
                  !setup?.profile_ready ||
                  !!dashboard?.unresolved
                }
                onClick={() =>
                  void runtimeAction(
                    runtime?.state === "paused" ? "resume" : "start",
                  )
                }
              >
                <Icon name="play" size={16} />
                {runtime?.state === "paused" ? "恢复助理" : "开始运行"}
              </button>
            )}
            <button
              className="button button-secondary"
              onClick={() => navigate("knowledge")}
            >
              试试示例知识库
              <Icon name="arrow" size={16} />
            </button>
            {runtime && runtime.state !== "stopped" && (
              <button
                className="quiet-button"
                disabled={busy}
                onClick={() => void runtimeAction("stop")}
              >
                <Icon name="stop" size={15} />
                停止
              </button>
            )}
          </div>
          <div className="hero-status">
            <span
              className={
                "status-dot " + (runtime?.connected ? "is-green" : "is-muted")
              }
            />
            <span>
              {runtime ? reasonText(runtime.reason) : "正在连接本机服务…"}
            </span>
          </div>
        </div>
        <div
          className="hero-visual"
          aria-label="工作方式：读取新消息，结合知识，生成回复"
        >
          <div className="visual-kicker">
            <span className="mini-line" />
            THE REPLY FLOW
          </div>
          <div className="flow-item">
            <span className="flow-icon">
              <Icon name="chat" />
            </span>
            <div>
              一条新消息<small>只处理已绑定好友</small>
            </div>
            <span className="flow-index">01</span>
          </div>
          <div className="flow-connector" />
          <div className="flow-item highlighted">
            <span className="flow-icon">
              <Icon name="book" />
            </span>
            <div>
              结合知识与偏好<small>让回答有自己的依据</small>
            </div>
            <span className="flow-index">02</span>
          </div>
          <div className="flow-connector" />
          <div className="flow-item">
            <span className="flow-icon">
              <Icon name="spark" />
            </span>
            <div>
              自然、合适的回复<small>按你选择的模式生成或发送</small>
            </div>
            <span className="flow-index">03</span>
          </div>
        </div>
      </section>
      <div className="metric-grid">
        <article className="metric-card">
          <div>
            <span>消息记录</span>
            <Icon name="chat" />
          </div>
          <strong>
            {dashboard?.messages ?? "—"}
            <small>条</small>
          </strong>
          <p>当前工作台中的可见消息</p>
        </article>
        <article className="metric-card">
          <div>
            <span>助理回复</span>
            <Icon name="spark" />
          </div>
          <strong>
            {dashboard?.replies ?? "—"}
            <small>条</small>
          </strong>
          <p>
            本次已处理 {runtime?.sent_this_run ?? "—"} /{" "}
            {runtime?.max_replies ?? 3} 条
          </p>
        </article>
        <article className="metric-card">
          <div>
            <span>已启用知识库</span>
            <Icon name="book" />
          </div>
          <strong>
            {bases ? active.length : "—"}
            <small>个</small>
          </strong>
          <p>
            {active.reduce((sum, b) => sum + b.document_count, 0)}{" "}
            份资料参与回复
          </p>
        </article>
      </div>
      <section className="panel setup-panel">
        <div className="section-heading">
          <div>
            <h2>开始之前，完成这几步</h2>
            <p>首次使用推荐先生成模拟回复，确认后再连接微信。</p>
          </div>
          <span className="muted">{ready} / 3 已准备</span>
        </div>
        <div className="setup-steps">
          {steps.map((step, index) => (
            <button
              key={step.title}
              className={"setup-step " + (step.ready ? "is-complete" : "")}
              onClick={() => navigate(step.target)}
            >
              <span className="step-number">
                {step.ready ? <Icon name="check" size={17} /> : `0${index + 1}`}
              </span>
              <span>
                <strong>{step.title}</strong>
                <small>{step.text}</small>
              </span>
              <Icon name="chevron" size={15} />
            </button>
          ))}
        </div>
      </section>
      {runtime?.capabilities.ui_checks_degraded && (
        <div className="callout callout-amber">
          <Icon name="info" />
          <p>
            当前 Mac
            接入需要人工配合：保持绑定聊天窗打开、输入框为空，并核对实际收件。应用暂时无法自动检查草稿、粘贴全文和遮挡。
          </p>
        </div>
      )}
      {pending.length > 0 && (
        <section className="panel attention-panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">NEEDS YOUR ATTENTION</span>
              <h2>这些回复，需要你确认一下</h2>
              <p>先在微信及对端核对，再记录结论。应用不会自动重发。</p>
            </div>
            <Pill tone="amber">{dashboard?.unresolved} 条待处理</Pill>
          </div>
          {pending.map((row) => (
            <div className="pending-row" key={row.id}>
              <p className="preserve">{row.reply_text}</p>
              <div className="button-row">
                <button
                  className="button button-secondary"
                  disabled={busy || !editable}
                  onClick={() => openResolve(row, "sent")}
                >
                  已核实发送
                </button>
                <button
                  className="quiet-button"
                  disabled={busy || !editable}
                  onClick={() => openResolve(row, "discarded")}
                >
                  标记作废
                </button>
              </div>
            </div>
          ))}
        </section>
      )}
      <div className="overview-grid">
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>最近的回复处理</h2>
              <p>结果、耗时与知识来源，随时可追溯。</p>
            </div>
            <button
              className="text-link"
              onClick={() => navigate("conversations")}
            >
              查看会话
              <Icon name="arrow" size={15} />
            </button>
          </div>
          {!runtime ? (
            <Skeleton />
          ) : !runs.length ? (
            <Empty
              title="等待第一条新消息"
              action={
                <button
                  className="button button-secondary"
                  onClick={() => navigate("knowledge")}
                >
                  先生成一条模拟回复
                </button>
              }
            >
              也可以在知识库中直接试问，无需发送微信。
            </Empty>
          ) : (
            <div className="activity-list">
              {runs.slice(0, 5).map((r) => (
                <button
                  key={r.trace_id}
                  className="activity-row"
                  onClick={() => showRun(r)}
                >
                  <span
                    className={
                      "activity-symbol " +
                      (r.status === "ready" ? "is-success" : "")
                    }
                  >
                    <Icon
                      name={r.status === "ready" ? "check" : "info"}
                      size={16}
                    />
                  </span>
                  <span className="activity-main">
                    <strong>{r.reply_text || statusText(r.status)}</strong>
                    <small>
                      #{r.trace_id} · {knowledgeText(r.knowledge_status)} · 模型{" "}
                      {(r.model_ms / 1000).toFixed(1)}s
                    </small>
                  </span>
                  <Icon name="chevron" size={15} />
                </button>
              ))}
            </div>
          )}
        </section>
        <section className="panel compact-panel">
          <span className="eyebrow">CONNECTED TO YOUR WORK</span>
          <h2>当前运行配置</h2>
          <dl className="definition-list">
            <div>
              <dt>回复模式</dt>
              <dd>{modeText(runtime?.mode || "")}</dd>
            </div>
            <div>
              <dt>测试好友</dt>
              <dd>
                {(
                  settings?.values.wechat_allowlist as string[] | undefined
                )?.join("、") || "尚未选择"}
              </dd>
            </div>
            <div>
              <dt>微信连接</dt>
              <dd>
                <span
                  className={
                    "status-dot " +
                    (runtime?.connected ? "is-green" : "is-muted")
                  }
                />
                {runtime?.connected ? "已连接" : "开始后连接"}
              </dd>
            </div>
            <div>
              <dt>发送节奏</dt>
              <dd>
                至少间隔 {settings?.values.min_send_interval_seconds ?? 30} 秒
              </dd>
            </div>
          </dl>
          <button
            className="button button-secondary full-width"
            onClick={() => navigate("settings")}
          >
            <Icon name="settings" size={16} />
            调整设置
          </button>
          <div className="micro-note">
            <Icon name="shield" size={14} />
            <span>每次启动最多3条回复。停止或暂停后，不会自动补发旧队列。</span>
          </div>
        </section>
      </div>
      {outbox.length > 0 && (
        <div className="latest-caption">
          最近一条回复记录于 {timeText(outbox[0].created)} ·
          本地记录确认不等于对端已收件
        </div>
      )}
    </>
  );
}
