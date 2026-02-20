import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { pageVariants, listContainerVariants, listItemVariants } from "@/utils/animations";
import { GitPullRequest, RefreshCw } from "lucide-react";
import { usePullRequests } from "@/hooks/usePullRequests";
import { usePageTitle } from "@/hooks/usePageTitle";
import { PullRequestsListSkeleton } from "@/components/common/Skeleton";
import EmptyState from "@/components/common/EmptyState";

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return `${Math.floor(diffDays / 30)}mo ago`;
}

export default function PullRequestsPage() {
  usePageTitle("Pull Requests");
  const { pullRequests, loading, error, refetch } = usePullRequests();
  const navigate = useNavigate();

  return (
    <motion.div
      className="p-4 md:p-6 space-y-4"
      initial="initial"
      animate="animate"
      exit="exit"
      variants={pageVariants}
    >
      {/* Header */}
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <GitPullRequest size={20} className="text-accent" />
          Pull Requests
        </h2>
        <button
          onClick={refetch}
          className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
          title="Refresh"
        >
          <RefreshCw size={16} />
        </button>
        {loading && (
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* PR list */}
      {loading && pullRequests.length === 0 ? (
        <PullRequestsListSkeleton />
      ) : pullRequests.length === 0 ? (
        <EmptyState
          icon={GitPullRequest}
          title="No open pull requests"
          description="There are no open pull requests across your repositories. Pull requests will appear here when created."
        />
      ) : (
        <motion.div
          className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl overflow-hidden divide-y divide-light-border dark:divide-border/50"
          initial="initial"
          animate="animate"
          variants={listContainerVariants}
        >
          {pullRequests.map((pr) => (
            <motion.button
              key={`${pr.owner}/${pr.repo}#${pr.number}`}
              variants={listItemVariants}
              layout
              onClick={() => navigate(`/pulls/${pr.owner}/${pr.repo}/${pr.number}`)}
              className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 dark:hover:bg-surface-lighter/50 transition-colors text-left"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <GitPullRequest
                    size={16}
                    className={`shrink-0 ${pr.draft ? "text-gray-500" : "text-green-400"}`}
                  />
                  <span className="text-sm text-gray-800 dark:text-gray-200 truncate">
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
                <div className="flex items-center gap-2 text-xs text-gray-500 ml-6 flex-wrap">
                  <span
                    className="px-1.5 py-0.5 rounded bg-accent/10 text-accent cursor-pointer hover:bg-accent/20"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/repos/${pr.owner}/${pr.repo}`);
                    }}
                  >
                    {pr.owner}/{pr.repo}
                  </span>
                  <span className="font-mono">{pr.head}</span>
                  <span>&rarr;</span>
                  <span className="font-mono">{pr.base}</span>
                  {pr.author && <span>by {pr.author}</span>}
                  {pr.created_at && <span>{timeAgo(pr.created_at)}</span>}
                </div>
              </div>
            </motion.button>
          ))}
        </motion.div>
      )}
    </motion.div>
  );
}
