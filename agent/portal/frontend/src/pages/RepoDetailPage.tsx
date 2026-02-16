import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  GitBranch,
  GitPullRequest,
  CircleDot,
  Play,
  RefreshCw,
  ExternalLink,
  Shield,
  Trash2,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  X,
} from "lucide-react";
import { api } from "@/api/client";
import { useRepoDetail } from "@/hooks/useRepoDetail";
import { usePageTitle } from "@/hooks/usePageTitle";
import NewTaskModal from "@/components/tasks/NewTaskModal";
import { pageVariants } from "@/utils/animations";
import ConfirmDialog from "@/components/common/ConfirmDialog";
import type { GitRepo } from "@/types";

type Tab = "branches" | "pulls" | "issues";
type SortField = "name" | "updated_at";
type SortDir = "asc" | "desc";

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatRelativeDate(dateStr: string | null): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return formatDate(dateStr);
}

export default function RepoDetailPage() {
  const { owner = "", repo = "" } = useParams<{ owner: string; repo: string }>();
  usePageTitle(`${owner}/${repo}`);
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

  // Delete branch state
  const [deleteBranch, setDeleteBranch] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Branch sorting state
  const [sortField, setSortField] = useState<SortField>("updated_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // Create PR modal state
  const [createPROpen, setCreatePROpen] = useState(false);
  const [prHead, setPrHead] = useState("");
  const [prBase, setPrBase] = useState("");
  const [prTitle, setPrTitle] = useState("");
  const [prBody, setPrBody] = useState("");
  const [prDraft, setPrDraft] = useState(false);
  const [creatingPR, setCreatingPR] = useState(false);

  const handleDeleteBranch = useCallback(async () => {
    if (!deleteBranch) return;
    setDeleting(true);
    try {
      await api(`/api/repos/${owner}/${repo}/branches/${encodeURIComponent(deleteBranch)}`, {
        method: "DELETE",
      });
      setDeleteBranch(null);
      refetch();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to delete branch";
      // Try to extract a user-friendly error from the JSON response
      const jsonMatch = msg.match(/\d+:\s*(\{.*\})/);
      if (jsonMatch) {
        try {
          const parsed = JSON.parse(jsonMatch[1]);
          alert(parsed.error || msg);
        } catch {
          alert(msg);
        }
      } else {
        alert(msg);
      }
    } finally {
      setDeleting(false);
    }
  }, [deleteBranch, owner, repo, refetch]);

  // Fetch repo metadata
  useEffect(() => {
    if (!owner || !repo) return;
    api<GitRepo>(`/api/repos/${owner}/${repo}`)
      .then(setRepoMeta)
      .catch(() => { });
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

  // Sort branches
  const sortedBranches = useMemo(() => {
    const sorted = [...branches].sort((a, b) => {
      if (sortField === "name") {
        return a.name.localeCompare(b.name);
      }
      const aDate = a.updated_at || "";
      const bDate = b.updated_at || "";
      return aDate.localeCompare(bDate);
    });
    return sortDir === "desc" ? sorted.reverse() : sorted;
  }, [branches, sortField, sortDir]);

  const toggleSort = useCallback((field: SortField) => {
    setSortField((prev) => {
      if (prev === field) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        return prev;
      }
      setSortDir(field === "updated_at" ? "desc" : "asc");
      return field;
    });
  }, []);

  // Create PR handlers
  const openCreatePR = useCallback(
    (headBranch: string) => {
      setPrHead(headBranch);
      setPrBase(repoMeta?.default_branch || "main");
      setPrTitle("");
      setPrBody("");
      setPrDraft(false);
      setCreatePROpen(true);
    },
    [repoMeta]
  );

  const handleCreatePR = useCallback(async () => {
    if (!prTitle.trim() || !prHead || !prBase) return;
    setCreatingPR(true);
    try {
      await api(`/api/repos/${owner}/${repo}/pulls`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: prTitle,
          head: prHead,
          base: prBase,
          body: prBody || null,
          draft: prDraft,
        }),
      });
      setCreatePROpen(false);
      refetch();
      setTab("pulls");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to create pull request";
      const jsonMatch = msg.match(/\d+:\s*(\{.*\})/);
      if (jsonMatch) {
        try {
          const parsed = JSON.parse(jsonMatch[1]);
          alert(parsed.error || msg);
        } catch {
          alert(msg);
        }
      } else {
        alert(msg);
      }
    } finally {
      setCreatingPR(false);
    }
  }, [prTitle, prHead, prBase, prBody, prDraft, owner, repo, refetch]);

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown size={12} className="text-gray-600" />;
    return sortDir === "asc" ? (
      <ArrowUp size={12} className="text-accent" />
    ) : (
      <ArrowDown size={12} className="text-accent" />
    );
  };

  const tabs: { key: Tab; label: string; icon: typeof GitBranch; count: number }[] = [
    { key: "branches", label: "Branches", icon: GitBranch, count: branches.length },
    { key: "pulls", label: "Pull Requests", icon: GitPullRequest, count: pullRequests.length },
    { key: "issues", label: "Issues", icon: CircleDot, count: issues.length },
  ];

  return (
    <motion.div
      className="p-4 md:p-6 space-y-4"
      initial="initial"
      animate="animate"
      exit="exit"
      variants={pageVariants}
    >
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
      <div className="flex gap-1 border-b border-light-border dark:border-border">
        {tabs.map(({ key, label, icon: Icon, count }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${tab === key
              ? "border-accent text-accent-hover"
              : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
          >
            <Icon size={16} />
            {label}
            <span
              className={`text-xs px-1.5 py-0.5 rounded-full ${tab === key
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
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden">
        {loading && branches.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {/* Branches */}
            {tab === "branches" && (
              <div>
                {branches.length === 0 ? (
                  <div className="text-center py-12 text-gray-500 text-sm">
                    No branches found
                  </div>
                ) : (
                  <>
                    {/* Sort header */}
                    <div className="flex items-center justify-between px-4 py-2 border-b border-light-border dark:border-border bg-surface-lighter/30">
                      <button
                        onClick={() => toggleSort("name")}
                        className="flex items-center gap-1.5 text-xs font-medium text-gray-400 hover:text-gray-200 uppercase tracking-wider transition-colors"
                      >
                        Branch
                        <SortIcon field="name" />
                      </button>
                      <div className="flex items-center gap-8">
                        <button
                          onClick={() => toggleSort("updated_at")}
                          className="flex items-center gap-1.5 text-xs font-medium text-gray-400 hover:text-gray-200 uppercase tracking-wider transition-colors"
                        >
                          Last Updated
                          <SortIcon field="updated_at" />
                        </button>
                        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider w-48 text-right">
                          Actions
                        </span>
                      </div>
                    </div>
                    {/* Branch rows */}
                    <div className="divide-y divide-light-border dark:divide-border/50">
                      {sortedBranches.map((branch) => (
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
                          <div className="flex items-center gap-4 shrink-0">
                            {branch.updated_at && (
                              <span
                                className="text-xs text-gray-500 w-20 text-right"
                                title={new Date(branch.updated_at).toLocaleString()}
                              >
                                {formatRelativeDate(branch.updated_at)}
                              </span>
                            )}
                            <div className="flex items-center gap-2">
                              {!branch.protected && branch.name !== repoMeta?.default_branch && (
                                <button
                                  onClick={() => openCreatePR(branch.name)}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-green-500/10 text-green-400 hover:bg-green-500/20 transition-colors"
                                >
                                  <GitPullRequest size={12} />
                                  Open PR
                                </button>
                              )}
                              <button
                                onClick={() => openNewTask(branch.name)}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
                              >
                                <Play size={12} />
                                New Task
                              </button>
                              {!branch.protected && branch.name !== repoMeta?.default_branch && (
                                <button
                                  onClick={() => setDeleteBranch(branch.name)}
                                  className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                                  title={`Delete branch ${branch.name}`}
                                >
                                  <Trash2 size={14} />
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Pull Requests */}
            {tab === "pulls" && (
              <div className="divide-y divide-light-border dark:divide-border/50">
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
                            className={`shrink-0 ${pr.draft ? "text-gray-500" : "text-green-400"
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
              <div className="divide-y divide-light-border dark:divide-border/50">
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

      {/* Delete Branch Confirmation */}
      <ConfirmDialog
        open={!!deleteBranch}
        title="Delete branch"
        message={`Are you sure you want to delete the branch "${deleteBranch}"? This action cannot be undone.`}
        confirmLabel={deleting ? "Deleting\u2026" : "Delete"}
        onConfirm={handleDeleteBranch}
        onCancel={() => setDeleteBranch(null)}
      />

      {/* Create PR Modal */}
      {createPROpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-6 max-w-md w-full space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">Open Pull Request</h3>
              <button
                onClick={() => setCreatePROpen(false)}
                className="p-1 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Head branch */}
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">
                From branch (head)
              </label>
              <select
                value={prHead}
                onChange={(e) => setPrHead(e.target.value)}
                className="w-full bg-surface-lighter border border-border rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-accent"
              >
                {branches.map((b) => (
                  <option key={b.name} value={b.name}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Base branch */}
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">
                Into branch (base)
              </label>
              <select
                value={prBase}
                onChange={(e) => setPrBase(e.target.value)}
                className="w-full bg-surface-lighter border border-border rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-accent"
              >
                {branches
                  .filter((b) => b.name !== prHead)
                  .map((b) => (
                    <option key={b.name} value={b.name}>
                      {b.name}
                    </option>
                  ))}
              </select>
            </div>

            {/* Title */}
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">
                Title
              </label>
              <input
                type="text"
                value={prTitle}
                onChange={(e) => setPrTitle(e.target.value)}
                placeholder="Pull request title"
                className="w-full bg-surface-lighter border border-border rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-accent"
              />
            </div>

            {/* Body */}
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">
                Description (optional)
              </label>
              <textarea
                value={prBody}
                onChange={(e) => setPrBody(e.target.value)}
                placeholder="Describe the changes..."
                rows={3}
                className="w-full bg-surface-lighter border border-border rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-accent resize-none"
              />
            </div>

            {/* Draft toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={prDraft}
                onChange={(e) => setPrDraft(e.target.checked)}
                className="w-4 h-4 rounded border-border bg-surface-lighter text-accent focus:ring-accent"
              />
              <span className="text-sm text-gray-300">Create as draft</span>
            </label>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setCreatePROpen(false)}
                className="px-4 py-2 text-sm rounded-lg bg-surface-lighter text-gray-300 hover:bg-border transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreatePR}
                disabled={!prTitle.trim() || !prHead || !prBase || creatingPR}
                className="px-4 py-2 text-sm rounded-lg bg-green-600 text-white hover:bg-green-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {creatingPR ? "Creating\u2026" : "Create Pull Request"}
              </button>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
}
