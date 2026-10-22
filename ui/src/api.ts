const explanations: Record<string, string> = {
  route_not_found:
    "当前运行的服务版本尚未包含新接口。请在终端 Ctrl+C 停止旧服务，重新启动后刷新页面。",
  request_too_large: "本次提交内容较多，请拆分资料或清空部分模拟对话后重试。",
  model_output_incomplete:
    "模型回复未完成，已停止本轮处理。可以在高级设置中适当增加输出预算。",
  model_output_invalid:
    "模型返回了不支持的格式，请检查所选模型是否兼容文字对话接口。",
  model_key_missing: "还没有填写模型密钥，请先到设置完成模型连接。",
  model_http_401: "模型密钥未通过验证，请检查密钥是否正确、是否仍有效。",
  model_http_402: "模型账户额度不足，请在服务商后台检查余额。",
  model_http_403: "模型服务拒绝了访问，请检查密钥权限和服务地址。",
  model_http_404: "模型地址或模型名称没有找到，请检查两项设置。",
  model_http_429: "模型请求暂时过于频繁或额度已用尽，请稍后再试。",
  model_timeout: "模型响应超时，可以稍后重试或适当增加等待时间。",
  model_request_failed: "暂时无法连接模型服务，请检查网络和模型地址。",
  nonempty_allowlist_required: "请先在设置中选择一个已绑定的测试好友。",
  stop_before_content_change: "请先暂停或停止助理，等待当前处理结束后再修改。",
  stop_before_settings: "请先暂停或停止助理，再保存设置。",
  stop_before_diagnostic: "请先暂停或停止助理，再进行环境检查。",
  history_unresolved_outbox:
    "仍有回复需要核对。请先在待处理回复中标记已发送或作废，再清除记录。",
  history_confirmation_required: "请输入“清除”以确认删除所选本地记录。",
  history_selection_invalid: "会话选择已失效，请刷新后重新选择。",
  knowledge_capacity_reached:
    "知识容量已满，请删除不用的资料后再导入（最多200份、8 MB）。",
  knowledge_base_capacity_reached: "知识库数量已达上限，最多可创建20个。",
  knowledge_document_too_large: "单份资料最多48 KB，请拆分文件后再导入。",
  knowledge_document_invalid: "请选择有内容的 UTF-8 TXT 或 Markdown 文本文件。",
  knowledge_document_not_found: "这份资料已被删除，请刷新列表。",
  knowledge_base_not_found: "这个知识库已被删除，请返回知识库列表。",
  default_knowledge_base_required:
    "默认知识库需要保留，可以删除其中的资料或停用它。",
  memory_capacity_reached: "该联系人的偏好已达20条，请先忘记不再需要的偏好。",
  memory_fact_invalid:
    "偏好名称请使用40字以内的文字、字母或数字，内容最多200字。",
  memory_contact_not_found:
    "联系人记录尚未建立，请先完成一次连接，或选择其他已有联系人。",
  request_invalid: "有一项填写格式或范围不正确，请检查后再保存。",
  settings_field_not_editable: "这项接入配置需要停止服务后在本机修改。",
  settings_field_not_applicable: "这项配置不适用于当前系统。",
  application_database_replaced:
    "应用数据文件发生变化，请停止并重启服务后核对。",
  poll_minimum_10_seconds: "读取消息的间隔请设置为10秒以上。",
  worker_still_stopping: "当前处理还在结束中，请稍等片刻。",
  runtime_transition_invalid: "运行状态已发生变化，请刷新后再操作。",
  attachment_not_found: "这条附件记录已清除，请刷新会话。",
  attachment_not_available:
    "还没有获取到本地内容，请等待微信下载和下一轮读取。",
  attachment_file_missing: "本地副本已被移走或删除，助理运行后会重新尝试获取。",
  attachment_location_rejected: "附件位置已失效，请重新获取本地内容。",
  attachment_reveal_failed: "暂时无法打开文件管理器，请稍后重试。",
  attachment_reveal_unsupported: "当前系统暂不支持打开附件位置。",
};
export class ApiError extends Error {
  constructor(
    public code: string,
    public trace?: string,
  ) {
    super(
      explanations[code] || "这次操作没有完成，请刷新状态、检查设置后重试。",
    );
  }
}
export const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "操作未完成，请稍后重试。";
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api" + path, {
      method,
      signal,
      headers: { "Content-Type": "application/json", "X-WeChat-Agent": "1" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new Error(
      "无法连接本机服务。请确认启动命令仍在运行，然后点击右上角刷新。",
    );
  }
  const result = await response.json().catch(() => {
    throw new Error("服务返回了无法读取的结果，请确认已重启最新版本的服务。");
  });
  if (!response.ok)
    throw new ApiError(result.code || "request_failed", result.trace_id);
  return result;
}
export const statusText = (value: string): string =>
  (
    ({
      stopped: "已停止",
      starting: "正在连接",
      running: "运行中",
      paused: "已暂停",
      stopping: "正在停止",
      degraded: "需要处理",
      verified_sent: "本地已确认",
      not_sent: "未发送",
      unknown: "待核对",
      ready: "回复已生成",
      error: "处理未完成",
      cancelled: "已取消",
      filtered: "已过滤",
      baseline: "连接前的消息",
      pending: "等待处理",
      processed: "已处理",
      failed: "处理失败",
      incoming: "好友消息",
      outgoing: "本人消息",
      system: "系统消息",
    }) as Record<string, string>
  )[value] || "待检查";
export const modeText = (mode: string) =>
  mode === "live" ? "微信发送" : "仅生成回复";
export const knowledgeText = (status: string): string =>
  (
    ({
      matched: "已使用知识",
      no_hits: "暂无匹配资料",
      budget_omitted: "输入预算不足，请在设置应用推荐预设",
      disabled: "未使用知识",
    }) as Record<string, string>
  )[status] || "未使用知识";
export const reasonText = (value: string): string =>
  (
    ({
      reply_limit: "本次已完成3条回复，点击开始可继续下一轮。",
      baseline_recorded:
        "已连接，可在“会话”查看已有消息；正在等待好友的新消息。",
      start_required: "设置完成后，即可开始处理新消息。",
      running: "正在处理好友的新消息。",
      stopped: "助理已停止，历史记录和设置已保存。",
      paused: "助理已暂停，恢复后只处理新的消息。",
      connect_requested: "正在检查绑定并连接微信，请稍等。",
      unresolved_outbox_stop_required:
        "有回复结果需要人工核对，请先处理下方待办。",
      input_budget_exceeded: "输入内容超过预算，请在设置中使用推荐的输入预算。",
      output_rejected: "本次回复未通过格式或长度检查，已停止发送。",
      output_unsupported_by_adapter:
        "回复格式超出了当前微信接入支持的范围，已停止发送。",
      native_database_replaced:
        "微信数据发生变化，请停止服务并核对绑定后重启。",
      account_or_database_binding_changed:
        "微信账号或数据库发生变化，请重新核对本机绑定。",
      mac_matching_degraded_acceptance_required:
        "当前 Mac 微信绑定、版本或数据库与已验收记录不一致，请核对本机接入记录。环境检测通过仍需完成此项校验。",
      mac_g1_matching_report_required:
        "缺少与当前 Mac 微信绑定匹配的读取验收记录，请先完成接入验收。",
      mac_g2_matching_report_required:
        "缺少与当前 Mac 微信绑定匹配的发送验收记录，请先完成接入验收。",
      windows_matching_acceptance_required:
        "当前 Windows 微信绑定或版本与已验收记录不一致，请核对本机接入记录。",
      mac_account_security_stop_active:
        "微信接入已暂停，请先核对微信登录状态并处理本机接入暂停记录。",
      mac_client_version_changed:
        "微信版本或构建发生变化，请重新核对本机接入。",
      mac_key_or_database_validation_failed:
        "微信本地数据库未通过读取校验，请核对账号绑定和读取密钥。",
      unresolved_native_operation_stop_required:
        "有一次微信发送结果尚未核对，请先确认已发送或作废。",
      desktop_resume_reconnect_required:
        "电脑从睡眠或中断中恢复，请确认微信窗口后重新开始。",
      model_timeout: "模型响应超时，确认网络后可重新开始。",
      model_request_failed: "模型暂时无法连接，请先在设置中测试连接。",
    }) as Record<string, string>
  )[value] ||
  explanations[value] ||
  "启动或运行未完成，请检查本机接入状态后重试。";
export const sizeText = (bytes: number) =>
  bytes < 1000 ? `${bytes} B` : `${(bytes / 1000).toFixed(1)} KB`;
export const timeText = (value: string | number) =>
  new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(typeof value === "number" ? value * 1000 : value));
