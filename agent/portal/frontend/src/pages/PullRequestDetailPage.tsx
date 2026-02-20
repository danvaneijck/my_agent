import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  GitPullRequest,
  GitMerge,
  MessageSquare,
  FileText,
  RefreshCw,
  ExternalLink,
  Send,
  ChevronDown,
  Check,
  Plus,
  Minus,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/api/client";
import { usePageTitle } from "@/hooks/usePageTitle";
import ConfirmDialog from "@/components/common/ConfirmDialog";
import type { GitPullRequest as PRType } from "@/types";

type MergeMethod = "squash" | "merge" | "rebase";

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function PullRequestDetailPage() {
  const { owner = "", repo = "", number = "" } = useParams<{
    owner: string;
    repo: string;
    number: string;
  }>();
  usePageTitle(`PR #${number} - ${owner}/${repo}`);
  const navigate = useNavigate();
  const prNumber = parseInt(number, 10);

  const [pr, setPr] = useState<PRType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Comment state
  const [comment, setComment] = useState("");
  const [commenting, setCommenting] = useState(false);

  // Merge state
  const [mergeMethod, setMergeMethod] = useState<MergeMethod>("squash");
  const [showMergeDropdown, setShowMergeDropdown] = useState(false);
  const [confirmMerge, setConfirmMerge] = useState(false);
  const [merging, setMerging] = useState(false);
  const [mergeResult, setMergeResult] = useState<string | null>(null);

  const fetchPr = useCallback(async () => {
    if (!owner || !repo || isNaN(prNumber)) return;
    setLoading(true);
    try {
      const data = await api<PRType>(
        `/api/repos/${owner}/${repo}/pulls/${prNumber}`
      );
      setPr(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch PR");
    } finally {
      setLoading(false);
    }
  }, [owner, repo, prNumber]);

  useEffect(() => {
    fetchPr();
  }, [fetchPr]);

  const handleComment = async () => {
    if (!comment.trim()) return;
    setCommenting(true);
    try {
      await api(`/api/repos/${owner}/${repo}/pulls/${prNumber}/comment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: comment }),
      });
      setComment("");
      fetchPr();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to post comment");
    } finally {
      setCommenting(false);
    }
  };

  const handleMerge = async () => {
    setConfirmMerge(false);
    setMerging(true);
    try {
      const result = await api<{ merged: boolean; message: string }>(
        `/api/repos/${owner}/${repo}/pulls/${prNumber}/merge`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ merge_method: mergeMethod }),
        }
      );
      setMergeResult(result.message || "Pull request merged successfully");
      window.dispatchEvent(new CustomEvent("pr-count-update"));
      fetchPr();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Merge failed");
    } finally {
      setMerging(false);
    }
  };

  const canMerge = pr && pr.state === "open" && !pr.draft && pr.mergeable !== false;

  const MERGE_LABELS: Record<MergeMethod, string> = {
    squash: "Squash and merge",
    merge: "Create a merge commit",
    rebase: "Rebase and merge",
  };

  if (loading && !pr) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-4 max-w-4xl">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button
          onClick={() => navigate("/pulls")}
          className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors mt-0.5"
        >
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              {pr?.title || `PR #${prNumber}`}
            </h2>
            <span className="text-sm text-gray-500">#{prNumber}</span>
          </div>
          <div className="flex items-center gap-2 mt-1 text-sm text-gray-400">
            <span className="text-xs text-gray-500">
              {owner}/{repo}
            </span>
            {pr?.state && (
              <span
                className={`text-xs px-1.5 py-0.5 rounded-full ${pr.state === "open"
                    ? "bg-green-500/20 text-green-400"
                    : pr.merged_at
                      ? "bg-purple-500/20 text-purple-400"
                      : "bg-red-500/20 text-red-400"
                  }`}
              >
                {pr.merged_at ? "Merged" : pr.state}
              </span>
            )}
            {pr?.draft && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-gray-500/20 text-gray-400">
                Draft
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 flex-wrap">
            {pr?.author && <span>by {pr.author}</span>}
            <span className="font-mono">{pr?.head}</span>
            <span>&rarr;</span>
            <span className="font-mono">{pr?.base}</span>
            {pr?.created_at && <span>opened {formatDate(pr.created_at)}</span>}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={fetchPr}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={16} />
          </button>
          {pr?.url && (
            <a
              href={pr.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white bg-gray-100 dark:bg-surface-lighter hover:bg-gray-200 dark:hover:bg-border transition-colors"
            >
              <ExternalLink size={14} />
              GitHub
            </a>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Merge result */}
      {mergeResult && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg px-4 py-3 text-sm text-green-400">
          {mergeResult}
        </div>
      )}

      {pr && (
        <>
          {/* Stats bar */}
          <div className="flex items-center gap-4 text-sm flex-wrap">
            {(pr.additions !== undefined || pr.deletions !== undefined) && (
              <div className="flex items-center gap-2">
                <span className="text-green-400 flex items-center gap-0.5">
                  <Plus size={14} />
                  {pr.additions ?? 0}
                </span>
                <span className="text-red-400 flex items-center gap-0.5">
                  <Minus size={14} />
                  {pr.deletions ?? 0}
                </span>
              </div>
            )}
            {pr.changed_files !== undefined && (
              <span className="text-gray-400 flex items-center gap-1">
                <FileText size={14} />
                {pr.changed_files} files changed
              </span>
            )}
            {pr.mergeable !== undefined && pr.mergeable !== null && (
              <span
                className={`flex items-center gap-1 ${pr.mergeable ? "text-green-400" : "text-red-400"
                  }`}
              >
                <GitMerge size={14} />
                {pr.mergeable ? "Mergeable" : "Conflicts"}
              </span>
            )}
          </div>

          {/* Description */}
          {pr.body && (
            <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4">
              <div className="prose dark:prose-invert prose-sm max-w-none prose-p:my-2 prose-pre:bg-black/30 dark:prose-pre:bg-black/30 prose-code:text-accent-hover">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {pr.body}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {/* Changed files */}
          {pr.files && pr.files.length > 0 && (
            <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden">
              <div className="px-4 py-2.5 border-b border-light-border dark:border-border flex items-center gap-2">
                <FileText size={16} className="text-gray-400" />
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                  Changed files
                </span>
                <span className="text-xs px-1.5 py-0.5 rounded-full bg-gray-200 dark:bg-surface-lighter text-gray-500">
                  {pr.files.length}
                </span>
              </div>
              <div className="divide-y divide-light-border dark:divide-border/50">
                {pr.files.map((file) => (
                  <div
                    key={file.filename}
                    className="flex items-center justify-between px-4 py-2.5 hover:bg-gray-50 dark:hover:bg-surface-lighter/50 transition-colors"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0 ${file.status === "added"
                            ? "bg-green-500/20 text-green-400"
                            : file.status === "deleted" || file.status === "removed"
                              ? "bg-red-500/20 text-red-400"
                              : "bg-yellow-500/20 text-yellow-400"
                          }`}
                      >
                        {file.status === "added"
                          ? "A"
                          : file.status === "deleted" || file.status === "removed"
                            ? "D"
                            : "M"}
                      </span>
                      <span className="text-sm text-gray-700 dark:text-gray-300 font-mono truncate">
                        {file.filename}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs shrink-0 ml-3">
                      {file.additions > 0 && (
                        <span className="text-green-400">+{file.additions}</span>
                      )}
                      {file.deletions > 0 && (
                        <span className="text-red-400">-{file.deletions}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Comments */}
          {pr.review_comments && pr.review_comments.length > 0 && (
            <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden">
              <div className="px-4 py-2.5 border-b border-light-border dark:border-border flex items-center gap-2">
                <MessageSquare size={16} className="text-gray-400" />
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                  Review comments
                </span>
                <span className="text-xs px-1.5 py-0.5 rounded-full bg-gray-200 dark:bg-surface-lighter text-gray-500">
                  {pr.review_comments.length}
                </span>
              </div>
              <div className="divide-y divide-light-border dark:divide-border/50">
                {pr.review_comments.map((c, i) => (
                  <div key={i} className="px-4 py-3">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
                        {c.author}
                      </span>
                      {c.path && (
                        <span className="text-xs text-gray-500 font-mono">
                          {c.path}
                        </span>
                      )}
                      <span className="text-xs text-gray-500">
                        {formatDate(c.created_at)}
                      </span>
                    </div>
                    <div className="prose dark:prose-invert prose-sm max-w-none prose-p:my-1 prose-pre:bg-black/30 dark:prose-pre:bg-black/30 prose-code:text-accent-hover">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {c.body}
                      </ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Add comment */}
          {pr.state === "open" && (
            <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 space-y-3">
              <div className="flex items-center gap-2">
                <MessageSquare size={16} className="text-gray-400" />
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                  Add a comment
                </span>
              </div>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Leave a comment... (Markdown supported)"
                rows={3}
                className="w-full px-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent resize-y"
              />
              <div className="flex justify-end">
                <button
                  onClick={handleComment}
                  disabled={!comment.trim() || commenting}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send size={14} />
                  {commenting ? "Posting..." : "Comment"}
                </button>
              </div>
            </div>
          )}

          {/* Merge section */}
          {pr.state === "open" && (
            <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm">
                  <GitMerge size={16} className="text-gray-400" />
                  <span className="text-gray-800 dark:text-gray-200 font-medium">Merge pull request</span>
                  {pr.mergeable === false && (
                    <span className="text-xs text-red-400">
                      (has conflicts)
                    </span>
                  )}
                  {pr.draft && (
                    <span className="text-xs text-gray-500">
                      (draft — cannot merge)
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setConfirmMerge(true)}
                    disabled={!canMerge || merging}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-l-lg bg-green-600 text-white text-sm font-medium hover:bg-green-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {merging ? (
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <Check size={14} />
                    )}
                    {MERGE_LABELS[mergeMethod]}
                  </button>
                  <div className="relative">
                    <button
                      onClick={() => setShowMergeDropdown(!showMergeDropdown)}
                      disabled={!canMerge || merging}
                      className="px-2 py-2 rounded-r-lg bg-green-600 text-white hover:bg-green-500 transition-colors border-l border-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ChevronDown size={14} />
                    </button>
                    {showMergeDropdown && (
                      <div className="absolute right-0 top-full mt-1 w-56 bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-lg shadow-xl z-10 py-1">
                        {(["squash", "merge", "rebase"] as MergeMethod[]).map(
                          (method) => (
                            <button
                              key={method}
                              onClick={() => {
                                setMergeMethod(method);
                                setShowMergeDropdown(false);
                              }}
                              className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-surface-lighter transition-colors flex items-center gap-2 ${mergeMethod === method
                                  ? "text-accent"
                                  : "text-gray-700 dark:text-gray-300"
                                }`}
                            >
                              {mergeMethod === method && (
                                <Check size={14} />
                              )}
                              <span className={mergeMethod === method ? "" : "ml-[22px]"}>
                                {MERGE_LABELS[method]}
                              </span>
                            </button>
                          )
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Merge confirmation dialog */}
      <ConfirmDialog
        open={confirmMerge}
        title="Merge pull request"
        message={`Are you sure you want to ${mergeMethod} and merge PR #${prNumber} into ${pr?.base || "base"}?`}
        confirmLabel="Merge"
        onConfirm={handleMerge}
        onCancel={() => setConfirmMerge(false)}
      />
    </div>
  );
}
