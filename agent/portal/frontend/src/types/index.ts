// Task types (from claude_code module)
export interface ContextTracking {
  peak_context_tokens: number;
  latest_context_tokens: number;
  num_compactions: number;
  num_turns: number;
  num_continuations: number;
  context_model: string | null;
}

export interface Task {
  id: string;
  prompt: string;
  repo_url: string | null;
  branch: string | null;
  source_branch: string | null;
  workspace: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | "awaiting_input" | "timed_out";
  mode: "execute" | "plan";
  auto_push: boolean;
  parent_task_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  heartbeat: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  log_file: string;
  elapsed_seconds: number | null;
  context_tracking?: ContextTracking;
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
export interface ToolCallSummary {
  name: string;
  success: boolean;
  tool_use_id: string;
}

export interface ToolCallsMetadata {
  total_count: number;
  unique_tools: number;
  tools_sequence: ToolCallSummary[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  model_used?: string | null;
  created_at: string | null;
  files?: FileRef[];
  tool_calls_metadata?: ToolCallsMetadata | null;
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
  tool_calls_metadata?: ToolCallsMetadata | null;
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
  updated_at: string | null;
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

export interface PRComment {
  author: string;
  body: string;
  path: string | null;
  created_at: string;
}

export interface PRFile {
  filename: string;
  status: string;
  additions: number;
  deletions: number;
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
  // Cross-repo list fields
  owner?: string;
  repo?: string;
  // Detail fields (from get_pull_request)
  body?: string;
  mergeable?: boolean | null;
  additions?: number;
  deletions?: number;
  changed_files?: number;
  review_comments?: PRComment[];
  files?: PRFile[];
  merged_at?: string | null;
  updated_at?: string;
}

export interface GitWorkflowRun {
  id: number;
  name: string;
  display_title: string;
  status: "queued" | "in_progress" | "completed";
  conclusion: "success" | "failure" | "cancelled" | "skipped" | "timed_out" | "neutral" | null;
  event: string;
  branch: string | null;
  sha: string;
  created_at: string;
  updated_at: string;
  url: string;
  // Cross-repo fields (added by dashboard endpoint)
  owner?: string;
  repo?: string;
}

// Deployment types (from deployer module)
export interface ServicePort {
  host: number;
  container: number;
  protocol: string;
  service?: string;
}

export interface DeploymentService {
  name: string;
  container_id: string | null;
  container_name: string;
  status: string;
  ports: ServicePort[];
  image: string;
}

export interface Deployment {
  deploy_id: string;
  project_name: string;
  project_type: "react" | "nextjs" | "static" | "node" | "docker" | "compose";
  port: number;
  container_id: string | null;
  url: string;
  status: "building" | "running" | "failed" | "stopped";
  created_at: string;
  services: DeploymentService[];
  all_ports: ServicePort[];
  env_var_count: number;
}

// Project planner types
export interface ProjectTaskCounts {
  todo?: number;
  doing?: number;
  in_review?: number;
  done?: number;
  failed?: number;
}

export interface ProjectPhase {
  phase_id: string;
  project_id: string;
  name: string;
  description: string | null;
  order_index: number;
  status: "planned" | "in_progress" | "completed";
  branch_name: string | null;
  pr_number: number | null;
  created_at: string;
  task_counts?: ProjectTaskCounts;
}

export interface ProjectSummary {
  project_id: string;
  name: string;
  description: string | null;
  repo_owner: string | null;
  repo_name: string | null;
  status: string;
  auto_merge: boolean;
  planning_task_id: string | null;
  total_tasks: number;
  done_tasks: number;
  task_counts: ProjectTaskCounts;
  updated_at: string;
}

export interface ProjectDetail {
  project_id: string;
  name: string;
  description: string | null;
  design_document: string | null;
  repo_owner: string | null;
  repo_name: string | null;
  default_branch: string;
  auto_merge: boolean;
  planning_task_id: string | null;
  status: string;
  plan_apply_status: "idle" | "applying" | "applied" | "failed";
  plan_apply_error: string | null;
  created_at: string;
  updated_at: string;
  phases: ProjectPhase[];
}

export interface ProjectTask {
  task_id: string;
  phase_id: string;
  project_id: string;
  title: string;
  description: string | null;
  acceptance_criteria: string | null;
  order_index: number;
  status: "todo" | "doing" | "in_review" | "done" | "failed";
  branch_name: string | null;
  pr_number: number | null;
  issue_number: number | null;
  claude_task_id: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

// Knowledge / memory types
export interface Memory {
  memory_id: string;
  content: string;
  conversation_id: string | null;
  created_at: string;
}

export interface MemoryListResponse {
  memories: Memory[];
  count: number;
}

export interface RecallResponse {
  memories: Memory[];
  count: number;
}

// Module health
export interface ModuleHealth {
  module: string;
  status: "ok" | "error" | "unknown";
  error?: string;
}

// New project creation flow
export interface CreateProjectPayload {
  name: string;
  description?: string;
  repo_owner?: string;
  repo_name?: string;
  default_branch?: string;
  auto_merge?: boolean;
}

export interface CreateRepoPayload {
  name: string;
  description?: string;
  private?: boolean;
}

export interface CreateRepoResult {
  owner: string;
  repo: string;
  full_name: string;
  clone_url: string;
  default_branch: string;
  private: boolean;
}

export interface KickoffResult {
  project_id: string;
  claude_task_id: string;
  mode: string;
  workspace: string;
}
