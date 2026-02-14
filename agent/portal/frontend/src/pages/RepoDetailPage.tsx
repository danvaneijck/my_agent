import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  GitBranch,
  GitPullRequest,
  CircleDot,
  Play,
  RefreshCw,
  ExternalLink,
  Shield,
} from "lucide-react";
import { api } from "@/api/client";
import { useRepoDetail } from "@/hooks/useRepoDetail";
import NewTaskModal from "@/components/tasks/NewTaskModal";
import type { GitRepo } from "@/types";

type Tab = "branches" | "pulls" | "issues";

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function RepoDetailPage() {
  const { owner = "", repo = "" } = useParams<{ owner: string; repo: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("branches");
  const [repoMeta, setRepoMeta] = useState<GitRepo | null>(null);
  const { branches, issues, pullRequests, loading, error, refetch } =
    useRepoDetail(owner, repo);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [modalRepoUrl, setModalRepoUrl] = useState("");
  const [modalBranch, setModalBranch] = useState("");
  const [modalPrompt, setModalPrompt] = useState("");

  // Fetch repo metadata
  useEffect(() => {
    if (!owner || !repo) return;
    api<GitRepo>(`/api/repos/${owner}/${repo}`)
      .then(setRepoMeta)
      .catch(() => {});
  }, [owner, repo]);

  const cloneUrl = repoMeta?.clone_url || `https://github.com/${owner}/${repo}.git`;

  const openNewTask = useCallback(
    (branch?: string, prompt?: string) => {
      setModalRepoUrl(cloneUrl);
      setModalBranch(branch || "");
      setModalPrompt(prompt || "");
      setModalOpen(true);
    },
    [cloneUrl]
  );

  const tabs: { key: Tab; label: string; icon: typeof GitBranch; count: number }[] = [
    { key: "branches", label: "Branches", icon: GitBranch, count: branches.length },
    { key: "pulls", label: "Pull Requests", icon: GitPullRequest, count: pullRequests.length },
    { key: "issues", label: "Issues", icon: CircleDot, count: issues.length },
  ];

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/repos")}
            className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200 transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <h2 className="text-lg font-semibold text-white">
              {owner}/{repo}
            </h2>
            {repoMeta?.description && (
              <p className="text-sm text-gray-400 mt-0.5">{repoMeta.description}</p>
            )}
          </div>
          <button
            onClick={refetch}
            className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
          {loading && (
            <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          )}
        </div>
        <div className="flex items-center gap-2">
          {repoMeta?.url && (
            <a
              href={repoMeta.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-gray-300 hover:text-white bg-surface-lighter hover:bg-border transition-colors"
            >
              <ExternalLink size={14} />
              GitHub
            </a>
          )}
          <button
            onClick={() => openNewTask(repoMeta?.default_branch)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            <Play size={16} />
            New Task
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {tabs.map(({ key, label, icon: Icon, count }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === key
                ? "border-accent text-accent-hover"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <Icon size={16} />
            {label}
            <span
              className={`text-xs px-1.5 py-0.5 rounded-full ${
                tab === key
                  ? "bg-accent/15 text-accent"
                  : "bg-surface-lighter text-gray-500"
              }`}
            >
              {count}
            </span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="bg-surface-light border border-border rounded-xl overflow-hidden">
        {loading && branches.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {/* Branches */}
            {tab === "branches" && (
              <div className="divide-y divide-border/50">
                {branches.length === 0 ? (
                  <div className="text-center py-12 text-gray-500 text-sm">
                    No branches found
                  </div>
                ) : (
                  branches.map((branch) => (
                    <div
                      key={branch.name}
                      className="flex items-center justify-between px-4 py-3 hover:bg-surface-lighter/50 transition-colors"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <GitBranch size={16} className="text-gray-500 shrink-0" />
                        <div className="min-w-0">
                          <span className="text-sm text-gray-200 font-mono">
                            {branch.name}
                          </span>
                          <span className="text-xs text-gray-500 ml-2 font-mono">
                            {branch.sha}
                          </span>
                        </div>
                        {branch.protected && (
                          <Shield size={14} className="text-yellow-500 shrink-0" />
                        )}
                      </div>
                      <button
                        onClick={() => openNewTask(branch.name)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors shrink-0"
                      >
                        <Play size={12} />
                        New Task
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Pull Requests */}
            {tab === "pulls" && (
              <div className="divide-y divide-border/50">
                {pullRequests.length === 0 ? (
                  <div className="text-center py-12 text-gray-500 text-sm">
                    No open pull requests
                  </div>
                ) : (
                  pullRequests.map((pr) => (
                    <div
                      key={pr.number}
                      className="flex items-center justify-between px-4 py-3 hover:bg-surface-lighter/50 transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <GitPullRequest
                            size={16}
                            className={`shrink-0 ${
                              pr.draft ? "text-gray-500" : "text-green-400"
                            }`}
                          />
                          <span className="text-sm text-gray-200 truncate">
                            {pr.title}
                          </span>
                          <span className="text-xs text-gray-500 shrink-0">
                            #{pr.number}
                          </span>
                          {pr.draft && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-500/20 text-gray-400 shrink-0">
                              Draft
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-gray-500 ml-6">
                          <span className="font-mono">{pr.head}</span>
                          <span>&rarr;</span>
                          <span className="font-mono">{pr.base}</span>
                          {pr.author && <span>by {pr.author}</span>}
                          {pr.created_at && (
                            <span>{formatDate(pr.created_at)}</span>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          openNewTask(
                            pr.head,
                            `Review/continue PR #${pr.number}: ${pr.title}`
                          )
                        }
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors shrink-0 ml-3"
                      >
                        <Play size={12} />
                        New Task
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Issues */}
            {tab === "issues" && (
              <div className="divide-y divide-border/50">
                {issues.length === 0 ? (
                  <div className="text-center py-12 text-gray-500 text-sm">
                    No open issues
                  </div>
                ) : (
                  issues.map((issue) => (
                    <div
                      key={issue.number}
                      className="flex items-center justify-between px-4 py-3 hover:bg-surface-lighter/50 transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <CircleDot size={16} className="text-green-400 shrink-0" />
                          <span className="text-sm text-gray-200 truncate">
                            {issue.title}
                          </span>
                          <span className="text-xs text-gray-500 shrink-0">
                            #{issue.number}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-gray-500 ml-6">
                          {issue.labels.map((label) => (
                            <span
                              key={label}
                              className="px-1.5 py-0.5 rounded bg-surface-lighter text-gray-400"
                            >
                              {label}
                            </span>
                          ))}
                          {issue.author && <span>by {issue.author}</span>}
                          {issue.created_at && (
                            <span>{formatDate(issue.created_at)}</span>
                          )}
                          {issue.comments > 0 && (
                            <span>{issue.comments} comments</span>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          openNewTask(
                            repoMeta?.default_branch,
                            `Fix issue #${issue.number}: ${issue.title}`
                          )
                        }
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors shrink-0 ml-3"
                      >
                        <Play size={12} />
                        New Task
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* New Task Modal */}
      <NewTaskModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        defaultRepoUrl={modalRepoUrl}
        defaultBranch={modalBranch}
        defaultPrompt={modalPrompt}
      />
    </div>
  );
}
