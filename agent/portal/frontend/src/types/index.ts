// Task types (from claude_code module)
export interface Task {
  id: string;
  prompt: string;
  repo_url: string | null;
  branch: string | null;
  source_branch: string | null;
  workspace: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | "awaiting_input" | "timed_out";
  mode: "execute" | "plan";
  parent_task_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  heartbeat: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  log_file: string;
  elapsed_seconds: number | null;
}

/** Map backend task response (task_id) to frontend Task (id). */
export function mapTask(raw: Record<string, unknown>): Task {
  return { ...raw, id: (raw.task_id as string) || (raw.id as string) } as Task;
}

// Workspace browser types
export interface WorkspaceEntry {
  name: string;
  type: "file" | "directory";
  size: number | null;
  modified: string;
}

export interface WorkspaceFileContent {
  task_id: string;
  path: string;
  size: number;
  binary: boolean;
  content: string | null;
  truncated?: boolean;
  message?: string;
}

export interface TaskLogData {
  lines: string[];
  total_lines: number;
  showing_from: number;
  status: string;
}

// Chat types
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  model_used?: string | null;
  created_at: string | null;
  files?: FileRef[];
}

export interface Conversation {
  id: string;
  platform_channel_id: string;
  title: string | null;
  started_at: string | null;
  last_active_at: string | null;
  last_read_at: string | null;
  unread_count: number;
}

// File types
export interface FileInfo {
  file_id: string;
  filename: string;
  mime_type: string | null;
  size_bytes: number | null;
  public_url: string;
  created_at: string;
}

export interface FileRef {
  filename: string;
  url: string;
}

// WebSocket message types
export interface WsLogLines {
  type: "log_lines";
  lines: string[];
  total_lines: number;
  offset: number;
  status: string;
}

export interface WsStatusChange {
  type: "status_change";
  status: string;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface WsHeartbeat {
  type: "heartbeat";
}

export interface WsError {
  type: "error";
  message: string;
}

export type WsTaskMessage =
  | WsLogLines
  | WsStatusChange
  | WsHeartbeat
  | WsError;

export interface WsChatResponse {
  type: "response";
  conversation_id: string;
  content: string;
  files: FileRef[];
  error: string | null;
}

export type WsChatMessage = WsChatResponse | WsHeartbeat | WsError;

export interface WsNotification {
  type: "notification";
  content: string;
  conversation_id: string | null;
  job_id: string | null;
  platform_channel_id: string;
}

// Git platform types
export interface GitRepo {
  owner: string;
  repo: string;
  full_name: string;
  description: string | null;
  url: string;
  clone_url: string;
  default_branch: string;
  language: string | null;
  private: boolean;
  stars: number;
  updated_at: string;
}

export interface GitBranch {
  name: string;
  sha: string;
  protected: boolean;
}

export interface GitIssue {
  number: number;
  title: string;
  state: string;
  author: string | null;
  assignee: string | null;
  labels: string[];
  comments: number;
  created_at: string;
  url: string;
}

export interface GitPullRequest {
  number: number;
  title: string;
  state: string;
  author: string | null;
  head: string;
  base: string;
  draft: boolean;
  created_at: string;
  url: string;
}

// Deployment types (from deployer module)
export interface Deployment {
  deploy_id: string;
  project_name: string;
  project_type: "react" | "nextjs" | "static" | "node" | "docker";
  port: number;
  container_id: string | null;
  url: string;
  status: "building" | "running" | "failed" | "stopped";
  created_at: string;
}

// Module health
export interface ModuleHealth {
  module: string;
  status: "ok" | "error" | "unknown";
  error?: string;
}
