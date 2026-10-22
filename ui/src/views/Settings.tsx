import React, { useState } from "react";
import { api, modeText } from "../api";
import { Icon, PageHeading, Pill, Skeleton } from "../components";
import { useWorkspace } from "../workspace";
import type { Values } from "../types";
type Diagnostic = {
  healthy: boolean;
  reason: string;
  platform: string;
  permissions: Record<string, boolean | string | null>;
  connected: boolean;
};
const advanced: [string, string, string, number?, number?][] = [
  [
    "llm_timeout_seconds",
    "模型最长等待时间（秒）",
    "超时后停止本轮处理，不发送替代话术。",
    1,
    120,
  ],
  [
    "llm_max_input_tokens",
    "模型输入预算",
    "包含人设、知识、记忆和对话，推荐8192；按保守字节估算。",
    128,
    16384,
  ],
  [
    "llm_max_output_tokens",
    "模型输出预算",
    "跨境客服建议256，过小可能导致回复不完整。",
    16,
    1000,
  ],
  [
    "max_reply_characters",
    "单条回复字数上限",
    "含所有换行和可选来源，不会静默截断。",
    1,
    1000,
  ],
  [
    "coalesce_window_ms",
    "连续消息合并等待（毫秒）",
    "好友短时间连发时，合并成一轮回复。",
    0,
    10000,
  ],
  [
    "queue_max_size",
    "最多排队消息数",
    "超过上限时停发，避免积压失控。",
    1,
    1000,
  ],
  ["max_sends_per_minute", "每分钟最多发送", "当前测试环境至多2次。", 1, 2],
  [
    "mac_verify_timeout_seconds",
    "Mac 发送确认等待（秒）",
    "发送后等候本地新记录的最长时间，不代表对端收件。",
    1,
    120,
  ],
  [
    "retention_days",
    "诊断缓存保留天数",
    "仅清理过期平台缓存，不清理聊天账本和知识。",
    1,
    365,
  ],
];
export function SettingsPage() {
  const {
    settings,
    setup,
    presets,
    runtime,
    busy,
    editable,
    draft,
    setDraft,
    saveSettings,
    perform,
    openClear,
    dashboard,
  } = useWorkspace();
  const [showKey, setShowKey] = useState(false);
  const [alias, setAlias] = useState("");
  const [testResult, setTestResult] = useState<number>();
  const [diagnostic, setDiagnostic] = useState<Diagnostic>();
  if (!settings)
    return (
      <>
        <PageHeading
          title="把助理，调整成你的样子。"
          description="正在加载当前配置…"
        />
        <Skeleton rows={5} />
      </>
    );
  const value = (key: string) =>
    draft[key] !== undefined ? draft[key] : settings.values[key];
  const change = (key: string, val: Values[string]) =>
    setDraft((old) => {
      const next = { ...old };
      if (JSON.stringify(val) === JSON.stringify(settings.values[key]))
        delete next[key];
      else next[key] = val;
      return next;
    });
  const allowlist = (value("wechat_allowlist") || []) as string[];
  const aliases = Array.from(
    new Set([...(setup?.contact_aliases || []), ...allowlist]),
  );
  const selectedPreset =
    presets.find((p) => p.prompt === value("agent_persona"))?.id || "custom";
  const dirty = Object.keys(draft).length > 0;
  const toggleAlias = (item: string) =>
    change(
      "wechat_allowlist",
      allowlist.includes(item)
        ? allowlist.filter((a) => a !== item)
        : [...allowlist, item],
    );
  const numeric = (
    key: string,
    label: string,
    hint: string,
    min?: number,
    max?: number,
  ) => (
    <label className="field" key={key}>
      {label}
      <input
        type="number"
        min={min}
        max={max}
        step={key === "llm_timeout_seconds" ? "any" : 1}
        value={String(value(key) ?? "")}
        disabled={busy || !editable}
        onChange={(e) =>
          change(key, e.target.value === "" ? "" : Number(e.target.value))
        }
      />
      <small>{hint}</small>
    </label>
  );
  return (
    <>
      <PageHeading
        eyebrow="MAKE IT YOURS"
        title="把助理，调整成你的样子。"
        description="先完成模型、回复风格和测试好友。其余参数保持推荐值，就能开始。"
        action={
          <Pill tone={editable ? "green" : "amber"}>
            {editable ? "可以编辑" : "运行中 · 暂停后编辑"}
          </Pill>
        }
      />
      <nav className="settings-nav" aria-label="设置分组">
        <a href="#model-settings">模型连接</a>
        <a href="#persona-settings">回复风格</a>
        <a href="#wechat-settings">微信接入</a>
        <a href="#behavior-settings">运行方式</a>
        <a href="#privacy-settings">数据与隐私</a>
      </nav>
      <form
        id="settings-form"
        className="settings-form"
        onSubmit={(e) => {
          e.preventDefault();
          void saveSettings();
        }}
      >
        <section className="panel settings-section" id="model-settings">
          <div className="section-heading">
            <div className="section-title">
              <span className="section-icon">
                <Icon name="spark" />
              </span>
              <div>
                <h2>模型连接</h2>
                <p>助理通过你选择的模型理解问题和组织回复。</p>
              </div>
            </div>
            <Pill
              tone={
                settings.values.llm_api_key_configured ? "green" : "neutral"
              }
            >
              {settings.values.llm_api_key_configured
                ? "密钥已配置"
                : "等待配置"}
            </Pill>
          </div>
          <div className="form-grid">
            <label className="field">
              模型服务
              <select
                value={
                  String(value("llm_base_url")).includes("api.deepseek.com")
                    ? "deepseek"
                    : "custom"
                }
                disabled={busy || !editable}
                onChange={(e) => {
                  if (e.target.value === "deepseek") {
                    change("llm_base_url", "https://api.deepseek.com");
                    change("llm_model", "deepseek-flash");
                  } else change("llm_base_url", "");
                  setTestResult(undefined);
                }}
              >
                <option value="deepseek">DeepSeek</option>
                <option value="custom">自定义兼容服务</option>
              </select>
              <small>支持兼容 Chat Completions 的模型接口。</small>
            </label>
            <label className="field">
              模型名称
              <input
                required
                value={String(value("llm_model") || "")}
                placeholder="例如 deepseek-flash"
                disabled={busy || !editable}
                onChange={(e) => {
                  change("llm_model", e.target.value);
                  setTestResult(undefined);
                }}
              />
              <small>填写服务商提供的实际模型名称。</small>
            </label>
            <label className="field span-two">
              服务地址
              <input
                required
                type="url"
                value={String(value("llm_base_url") || "")}
                placeholder="https://api.deepseek.com"
                disabled={busy || !editable}
                onChange={(e) => {
                  change("llm_base_url", e.target.value);
                  setTestResult(undefined);
                }}
              />
              <small>
                填写接口根地址，不要包含密钥、查询参数或 /chat/completions。
              </small>
            </label>
            <label className="field span-two">
              API 密钥
              <div className="input-with-action">
                <input
                  type={showKey ? "text" : "password"}
                  autoComplete="new-password"
                  value={String(draft.llm_api_key || "")}
                  placeholder={
                    settings.values.llm_api_key_configured
                      ? "已安全保存；留空会保留原密钥"
                      : "粘贴模型服务商提供的密钥"
                  }
                  disabled={busy || !editable}
                  onChange={(e) => {
                    change("llm_api_key", e.target.value);
                    setDraft((old) => {
                      const next = { ...old };
                      delete next.clear_llm_api_key;
                      return next;
                    });
                    setTestResult(undefined);
                  }}
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label={showKey ? "隐藏输入的密钥" : "显示输入的密钥"}
                  onClick={() => setShowKey(!showKey)}
                >
                  <Icon name="eye" size={17} />
                </button>
              </div>
              <small>
                后端不会把已保存密钥返回页面。只在本机保存，不会写入前端构建。
              </small>
            </label>
          </div>
          <div className="section-actions">
            <button
              type="button"
              className="button button-secondary"
              disabled={
                busy ||
                !editable ||
                !value("llm_base_url") ||
                !value("llm_model") ||
                (!draft.llm_api_key &&
                  !settings.values.llm_api_key_configured) ||
                !!draft.clear_llm_api_key
              }
              onClick={() =>
                void perform(async () => {
                  const result = await api<{
                    ok: boolean;
                    duration_ms: number;
                  }>("/model/test", "POST", {
                    llm_base_url: value("llm_base_url"),
                    llm_model: value("llm_model"),
                    ...(draft.llm_api_key
                      ? { llm_api_key: draft.llm_api_key }
                      : {}),
                  });
                  setTestResult(result.duration_ms);
                }, "模型连接正常。测试没有自动保存修改。")
              }
            >
              <Icon name="refresh" size={16} />
              测试连接
            </button>
            {testResult !== undefined && (
              <span className="success-text">
                <Icon name="check" size={15} />
                连接成功 · {(testResult / 1000).toFixed(1)}s
              </span>
            )}
            <span className="field-hint">
              会发送一次简短测试请求，按服务商规则计费。
            </span>
          </div>
          {settings.sources.llm_api_key === "environment" && (
            <div className="inline-warning">
              密钥由启动环境提供。如需更换或清除，请同时修改对应环境变量。
            </div>
          )}
        </section>
        <section className="panel settings-section" id="persona-settings">
          <div className="section-heading">
            <div className="section-title">
              <span className="section-icon">
                <Icon name="chat" />
              </span>
              <div>
                <h2>回复风格</h2>
                <p>选一个完整预设，再按需要微调。自然、有分寸，也不编造。</p>
              </div>
            </div>
          </div>
          <div className="persona-grid">
            {presets.map((preset) => (
              <button
                type="button"
                className={
                  "persona-card " +
                  (selectedPreset === preset.id ? "is-selected" : "")
                }
                key={preset.id}
                disabled={busy || !editable}
                onClick={() =>
                  setDraft((old) => ({
                    ...old,
                    agent_persona: preset.prompt,
                    llm_max_input_tokens: preset.input_budget,
                    llm_max_output_tokens: preset.output_budget,
                    reply_show_sources: false,
                  }))
                }
              >
                <div className="row-between">
                  <Icon
                    name={preset.id === "northline" ? "coffee" : "chat"}
                    size={21}
                  />
                  <span className="radio-indicator">
                    {selectedPreset === preset.id && <span />}
                  </span>
                </div>
                <strong>{preset.name}</strong>
                <p>{preset.description}</p>
                <small>
                  {preset.id === "northline"
                    ? "适合内置跨境电商示例"
                    : "适合一般日常对话"}
                </small>
              </button>
            ))}
          </div>
          {selectedPreset === "custom" && (
            <p className="field-hint">
              当前使用自定义提示词，原有内容会保留。选择预设会将完整提示词和推荐预算放入待保存修改。
            </p>
          )}
          <details className="advanced-details">
            <summary>
              <span>
                <Icon name="edit" size={16} />
                查看并编辑完整提示词
              </span>
              <span className="muted">可自定义</span>
            </summary>
            <div className="details-content">
              <label className="field">
                人设与回复规则
                <textarea
                  rows={11}
                  maxLength={12000}
                  value={String(value("agent_persona") || "")}
                  disabled={busy || !editable}
                  onChange={(e) => change("agent_persona", e.target.value)}
                />
                <small>
                  预设覆盖语气、产品依据、追问、资料缺失、售后边界与联系人记忆。不允许聊天或资料改变系统操作规则。
                </small>
              </label>
            </div>
          </details>
          <label className="toggle-row">
            <span>
              <strong>在微信回复末尾显示资料来源</strong>
              <small>
                建议关闭，让聊天更自然。工作台仍会完整保存本轮采用的来源。
              </small>
            </span>
            <input
              type="checkbox"
              className="switch"
              checked={Boolean(value("reply_show_sources"))}
              disabled={busy || !editable}
              onChange={(e) => change("reply_show_sources", e.target.checked)}
            />
          </label>
        </section>
        <section className="panel settings-section" id="wechat-settings">
          <div className="section-heading">
            <div className="section-title">
              <span className="section-icon">
                <Icon name="globe" />
              </span>
              <div>
                <h2>微信接入</h2>
                <p>只处理选中的、已经在本机完成绑定的测试好友。</p>
              </div>
            </div>
            <Pill tone={setup?.profile_ready ? "green" : "amber"}>
              {setup?.profile_ready ? "已有本机绑定" : "需要完成本机绑定"}
            </Pill>
          </div>
          <div className="binding-summary">
            <span className="contact-avatar">
              <Icon name="shield" />
            </span>
            <div>
              <strong>
                {runtime?.platform || settings.platform} · 本机微信
              </strong>
              <p>
                {setup?.profile_ready
                  ? "已读取本机绑定资料，开始运行时会再次核对账号和好友。"
                  : "先登录微信、完成系统授权与账号/好友绑定，再回来选择测试好友。"}
              </p>
            </div>
          </div>
          <span className="field-label">允许回复的测试好友</span>
          {aliases.length ? (
            <div className="contact-options">
              {aliases.map((item) => (
                <label className="contact-option" key={item}>
                  <input
                    type="checkbox"
                    checked={allowlist.includes(item)}
                    disabled={busy || !editable}
                    onChange={() => toggleAlias(item)}
                  />
                  <span className="contact-avatar">
                    {item.slice(0, 1).toUpperCase()}
                  </span>
                  <span>
                    <strong>{item}</strong>
                    <small>
                      {setup?.contact_aliases.includes(item)
                        ? "本机绑定的单聊好友"
                        : "已保存的别名，开始时复核"}
                    </small>
                  </span>
                </label>
              ))}
            </div>
          ) : (
            <div className="inline-warning">
              尚未发现已绑定好友。初次接入需要按下方系统接入指引准备。
            </div>
          )}
          <details className="advanced-details">
            <summary>
              <span>
                <Icon name="help" size={16} />
                初次接入与手动指定好友
              </span>
            </summary>
            <div className="details-content">
              <ol className="guide-list">
                <li>打开微信并登录，确认当前账号与测试好友。</li>
                <li>
                  {settings.platform === "macOS"
                    ? "按项目 docs/mac-probe.md 完成本机账号绑定和首次密钥准备；系统权限由你显式授权，不会在开始时自动重新取钥。"
                    : "按项目 docs/windows-probe.md 完成本机账号和测试好友绑定；初始化在你点击开始后执行。"}
                </li>
                <li>
                  点击环境检查，准备好窗口，再保存名单并开始“仅生成回复”。
                </li>
              </ol>
              <label className="field">
                已有绑定的好友别名
                <div className="input-with-button">
                  <input
                    value={alias}
                    placeholder="例如 test-a；不是昵称或新的微信号"
                    disabled={busy || !editable}
                    onChange={(e) => setAlias(e.target.value)}
                  />
                  <button
                    type="button"
                    className="button button-secondary"
                    disabled={busy || !editable || !alias.trim()}
                    onClick={() => {
                      const item = alias.trim();
                      if (!allowlist.includes(item))
                        change("wechat_allowlist", [...allowlist, item]);
                      setAlias("");
                    }}
                  >
                    添加
                  </button>
                </div>
                <small>
                  只接受已在本机绑定文件中存在的别名。填写陌生昵称不会建立微信绑定。
                </small>
              </label>
            </div>
          </details>
          <div className="section-actions">
            <button
              type="button"
              className="button button-secondary"
              disabled={busy || !editable}
              onClick={() =>
                void perform(
                  async () =>
                    setDiagnostic(
                      await api<Diagnostic>("/diagnostics", "POST", {}),
                    ),
                  "只读环境检查已完成。",
                )
              }
            >
              <Icon name="shield" size={16} />
              检查本机环境
            </button>
            <span className="field-hint">不取钥、不切换窗口、不发送消息。</span>
          </div>
          {diagnostic && (
            <div className="diagnostic-result">
              <div className="row-between">
                <strong>
                  {diagnostic.healthy ? "环境检查可用" : "有接入项目需要处理"}
                </strong>
                <Pill tone={diagnostic.healthy ? "green" : "amber"}>
                  {diagnostic.healthy ? "环境可用" : "请检查权限与依赖"}
                </Pill>
              </div>
              <p>
                此项检查系统权限与依赖；开始运行还会校验账号绑定、数据库和接入验收记录。
              </p>
              {Object.entries(diagnostic.permissions).map(([key, val]) => (
                <div className="diagnostic-line" key={key}>
                  <span>
                    {
                      (
                        {
                          screen_locked: "桌面锁屏",
                          screen_recording: "屏幕录制权限",
                          accessibility: "辅助功能权限",
                          account_security_stop: "账号安全停止",
                        } as Record<string, string>
                      )[key]
                    }
                  </span>
                  <span>
                    {val === null
                      ? "未检测"
                      : key === "screen_locked" ||
                          key === "account_security_stop"
                        ? val
                          ? "需要处理"
                          : "未触发"
                        : val === true ||
                            ["granted", "available", "authorized"].includes(
                              String(val),
                            )
                          ? "可用"
                          : val === false
                            ? "尚未授权"
                            : String(val)}
                  </span>
                </div>
              ))}
              <details className="technical">
                <summary>技术结果</summary>
                <code>{diagnostic.reason}</code>
              </details>
            </div>
          )}
          {runtime?.capabilities.ui_checks_degraded && (
            <div className="callout callout-amber">
              <Icon name="info" />
              <p>
                当前 Mac
                接入需人工清空输入框、保持绑定的独立聊天窗打开，并核对完整收件；无法自动检查草稿和遮挡。
              </p>
            </div>
          )}
        </section>
        <section className="panel settings-section" id="behavior-settings">
          <div className="section-heading">
            <div className="section-title">
              <span className="section-icon">
                <Icon name="clock" />
              </span>
              <div>
                <h2>运行方式</h2>
                <p>先确认回复效果，再决定是否发送到微信。</p>
              </div>
            </div>
          </div>
          <div className="mode-options">
            {["dry-run", "live"].map((mode) => (
              <label
                className={
                  "mode-option " +
                  (value("send_mode") === mode ? "is-selected" : "")
                }
                key={mode}
              >
                <input
                  type="radio"
                  name="send_mode"
                  checked={value("send_mode") === mode}
                  disabled={busy || !editable}
                  onChange={() => change("send_mode", mode)}
                />
                <span>
                  <strong>
                    {modeText(mode)}
                    {mode === "dry-run" && <Pill>推荐先试</Pill>}
                  </strong>
                  <small>
                    {mode === "dry-run"
                      ? "读取新消息并生成回复，不操作微信输入或发送按键。"
                      : "点击开始后，向已选定的测试好友发送真实文字。"}
                  </small>
                </span>
              </label>
            ))}
          </div>
          {value("send_mode") === "live" && (
            <div className="inline-warning">
              保存“微信发送”后仍需点击开始才会发送。每次重新启动服务都会回到“仅生成回复”。
            </div>
          )}
          <div className="form-grid">
            {numeric(
              "max_replies_per_run",
              "每次运行最多回复（条）",
              "默认3条，可设为1–100条；达到上限自动停止。每次开始或恢复时重新计数，仅生成回复也计入。",
              1,
              100,
            )}
            {numeric(
              "poll_interval_seconds",
              "多久读取一次消息（秒）",
              "推荐15秒；首次开始建立基线，不回复旧历史。",
              10,
              60,
            )}
            {numeric(
              "min_send_interval_seconds",
              "两次发送至少间隔（秒）",
              "保持低频，测试时至少30秒。",
              30,
              3600,
            )}
          </div>
          <details className="advanced-details">
            <summary>
              <span>
                <Icon name="settings" size={16} />
                高级模型与运行参数
              </span>
              <span className="muted">通常无需修改</span>
            </summary>
            <div className="details-content form-grid">
              {advanced
                .filter(([key]) => !settings.inactive.includes(key))
                .map(([key, label, hint, min, max]) =>
                  numeric(key, label, hint, min, max),
                )}
            </div>
          </details>
          <details className="advanced-details">
            <summary>
              <span>
                <Icon name="globe" size={16} />
                高级本机接入配置
              </span>
            </summary>
            <div className="details-content form-grid">
              {[
                ["wechat_profile", "本机绑定文件"],
                ["wechat_account_ref", "本机账号引用"],
                ["wechat_db_root", "微信数据库根目录"],
                ["mac_bridge_path", "Mac 原生桥路径"],
              ]
                .filter(([key]) => !settings.inactive.includes(key))
                .map(([key, label]) => (
                  <label className="field" key={key}>
                    {label}
                    <input
                      value={String(value(key) || "")}
                      disabled={
                        busy || !editable || settings.readonly.includes(key)
                      }
                      onChange={(e) => change(key, e.target.value)}
                    />
                    <small>
                      已有绑定时保留当前值；更换账号或路径需要重新核对本机绑定。
                    </small>
                  </label>
                ))}
              {["wechat_uia_gate_enabled", "wechat_ocr_enabled"]
                .filter((key) => !settings.inactive.includes(key))
                .map((key) => (
                  <label className="check-row" key={key}>
                    <input
                      type="checkbox"
                      checked={Boolean(value(key))}
                      disabled={busy || !editable}
                      onChange={(e) => change(key, e.target.checked)}
                    />
                    {key === "wechat_ocr_enabled"
                      ? "允许 Windows OCR 核验"
                      : "允许 Windows UIA 热激活"}
                  </label>
                ))}
              <details className="technical span-two">
                <summary>配置来源与启动参数</summary>
                {Object.entries(settings.sources).map(([key, source]) => (
                  <div className="diagnostic-line" key={key}>
                    <code>{key}</code>
                    <span>
                      {(
                        {
                          default: "默认值",
                          dotenv: "本机配置文件",
                          environment: "环境变量优先",
                          session: "本次启动覆盖",
                        } as Record<string, string>
                      )[source] || source}
                    </span>
                  </div>
                ))}
              </details>
            </div>
          </details>
        </section>
        <section className="panel settings-section" id="privacy-settings">
          <div className="section-heading">
            <div className="section-title">
              <span className="section-icon">
                <Icon name="shield" />
              </span>
              <div>
                <h2>数据与隐私</h2>
                <p>
                  会话、知识和偏好保存在本机；回复所需片段会发给你配置的模型。
                </p>
              </div>
            </div>
          </div>
          <div className="privacy-row">
            <div>
              <strong>清除本地会话与执行记录</strong>
              <p>
                微信中清空聊天不会同步清除工作台记录。可在这里清除全部，也可到会话中单独清除。
              </p>
              <small>
                {dashboard?.messages ?? "—"} 条消息 ·{" "}
                {dashboard?.replies ?? "—"} 条回复 ·{" "}
                {dashboard?.memories ?? "—"} 条长期偏好
              </small>
            </div>
            <button
              type="button"
              className="button button-danger-soft"
              disabled={busy || !editable}
              onClick={() => openClear()}
            >
              <Icon name="trash" size={16} />
              清除记录
            </button>
          </div>
          <label className="toggle-row">
            <span>
              <strong>清除已保存的模型密钥</strong>
              <small>
                勾选并保存后清除本机配置中的密钥。环境变量提供的密钥需在启动环境中移除。
              </small>
            </span>
            <input
              className="switch"
              type="checkbox"
              disabled={busy || !editable}
              checked={Boolean(draft.clear_llm_api_key)}
              onChange={(e) =>
                setDraft((old) => {
                  const next = { ...old };
                  if (e.target.checked) {
                    next.clear_llm_api_key = true;
                    delete next.llm_api_key;
                  } else delete next.clear_llm_api_key;
                  return next;
                })
              }
            />
          </label>
        </section>
      </form>
      <div className={"settings-savebar " + (dirty ? "has-changes" : "")}>
        <div>
          <span className={"status-dot " + (dirty ? "is-amber" : "is-green")} />
          <span>
            {dirty ? "有未保存的修改" : "设置已同步"}
            <small>
              {dirty
                ? "切换页面会保留草稿；保存后在下次开始或恢复时生效。"
                : "模型密钥始终只保存在后端。"}
            </small>
          </span>
        </div>
        <div className="button-row">
          <button
            className="button button-secondary"
            disabled={busy || !dirty}
            onClick={() => setDraft({})}
          >
            放弃修改
          </button>
          <button
            className="button"
            type="submit"
            form="settings-form"
            disabled={busy || !editable || !dirty}
          >
            {busy ? "请稍候…" : "保存设置"}
            <Icon name="check" size={16} />
          </button>
        </div>
      </div>
    </>
  );
}
