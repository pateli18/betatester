export type ScrapeStatus = "running" | "completed" | "failed" | "stopped";

export type ModelChatType = "system" | "user" | "assistant";

export type ModelChatContentType = "type" | "image_url";

export type ModelChatContentImageDetail = "low" | "auto" | "high";

export interface ModelChatContentImage {
  url: string;
  detail: ModelChatContentImageDetail;
}

export interface ModelChatContent {
  type: ModelChatContentType;
  text?: string;
  image_url?: ModelChatContentImage;
}

export interface ModelChat {
  role: ModelChatType;
  content: string | ModelChatContent[];
}

export type ActionType = "click" | "fill" | "select" | "check";

export interface ActionElement {
  role: string | null;
  name: string | null;
  selector: string | null;
}

export interface Action {
  element: ActionElement;
  action_type: ActionType;
  action_value: string | null;
}

export interface RunStep {
  step_id: string;
  next_step: string;
  status: ScrapeStatus;
  debug_next_step_chat: ModelChat[] | null;
  debug_choose_action_chat: ModelChat[] | null;
  action: Action | null;
  action_count: number | null;
  timestamp: string;
  start_timestamp: string;
}

export interface RunEventMetadata {
  id: string;
  url: string;
  high_level_goal: string;
  status: ScrapeStatus;
  start_timestamp: string;
  timestamp: string;
  page_views: number;
  action_count: number;
  fail_reason: string | null;
  max_page_views: number;
  max_total_actions: number;
}

export interface RunMessage extends RunEventMetadata {
  steps: RunStep[];
}

export interface FileInfo {
  name: string;
  b64_content: string;
  mimeType: string;
}
