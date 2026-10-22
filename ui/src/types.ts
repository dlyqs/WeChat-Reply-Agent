export type Runtime = {
  state: string;
  reason: string;
  connected: boolean;
  mode: string;
  generation: number;
  sent_this_run: number;
  max_replies: number;
  platform: string;
  foundation: string;
  initialization: Record<string, string>;
  capabilities: {
    ui_checks_degraded?: boolean;
    max_text_characters?: number;
    supports_newlines?: boolean;
  };
};
export type Values = Record<
  string,
  string | number | boolean | string[] | null
>;
export type Settings = {
  values: Values;
  sources: Record<string, string>;
  readonly: string[];
  inactive: string[];
  platform: string;
};
export type Setup = {
  profile_ready: boolean;
  contact_aliases: string[];
  model_ready: boolean;
  allowlist_ready: boolean;
};
export type Dashboard = {
  messages: number;
  replies: number;
  runs: number;
  memories: number;
  unresolved: number;
  model_ms: number | null;
};
export type Conversation = {
  id: string;
  scope: string;
  alias: string | null;
  message_count: number;
};
export type Message = {
  id: string;
  text: string | null;
  direction: string;
  status: string;
  observed_at: string;
  source_created_at?: number | null;
  type: string;
  attachment?: {
    kind: "file" | "voice";
    status: "pending" | "available" | "missing" | "error";
    name: string | null;
    byte_size: number | null;
    format: string | null;
    reason: string | null;
  } | null;
};
export type Source = { source_ref: string; name: string; ordinal: number };
export type Run = {
  trace_id: string;
  scope: string;
  status: string;
  reason: string;
  reply_text: string | null;
  sources: Source[];
  knowledge_status: string;
  model_ms: number;
  poll_ms: number;
  send_ms: number | null;
  input_refs: string[];
};
export type Outbox = {
  id: string;
  scope: string;
  conversation_id: string;
  state: string;
  resolution: string | null;
  reply_text: string;
  mode: string;
  created: number;
  basis: string | null;
};
export type KnowledgeBase = {
  id: string;
  name: string;
  description: string;
  enabled: number;
  kind: string;
  document_count: number;
  chunk_count: number;
  byte_size: number;
};
export type Document = {
  id: string;
  name: string;
  byte_size: number;
  chunk_count: number;
  content?: string;
};
export type Question = {
  id: string;
  question: string;
  expected: string;
  category: string;
};
export type Catalog = {
  id: string;
  name: string;
  description: string;
  fictional: boolean;
  questions: Question[];
};
export type Bases = { items: KnowledgeBase[]; demo: Catalog };
export type Preset = {
  id: string;
  name: string;
  description: string;
  prompt: string;
  input_budget: number;
  output_budget: number;
};
export type Contact = { scope: string; alias: string; contact: string };
export type Fact = {
  key: string;
  value: string;
  source: string;
  updated: number;
};
export type Page<T> = { items: T[] };
export type Perform = (
  task: () => Promise<unknown>,
  success?: string,
) => Promise<boolean>;
export type Nav =
  "overview" | "conversations" | "knowledge" | "memories" | "settings";
