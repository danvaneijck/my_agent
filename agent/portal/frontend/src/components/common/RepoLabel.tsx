import { GitBranch } from "lucide-react";

/** Extract "owner/repo" from a git URL, or return the URL as-is if unparseable. */
function parseRepoName(url: string): string {
  // Handles https://github.com/owner/repo.git, git@github.com:owner/repo.git, etc.
  const httpsMatch = url.match(/(?:github\.com|bitbucket\.org)[/:]([^/]+\/[^/.]+)/);
  if (httpsMatch) return httpsMatch[1];
  // Fallback: just strip protocol and .git
  return url.replace(/^https?:\/\//, "").replace(/\.git$/, "");
}

interface RepoLabelProps {
  repoUrl: string;
  branch?: string | null;
  /** "sm" = compact inline badge, "md" = slightly larger with more padding */
  size?: "sm" | "md";
  className?: string;
}

export default function RepoLabel({
  repoUrl,
  branch,
  size = "sm",
  className = "",
}: RepoLabelProps) {
  const repoName = parseRepoName(repoUrl);

  if (size === "sm") {
    return (
      <span
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent/10 text-accent text-[10px] font-medium max-w-[200px] ${className}`}
        title={`${repoUrl}${branch ? ` @ ${branch}` : ""}`}
      >
        <GitBranch size={10} className="shrink-0" />
        <span className="truncate">{repoName}</span>
        {branch && (
          <>
            <span className="text-gray-500">@</span>
            <span className="truncate text-accent/70">{branch}</span>
          </>
        )}
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-accent/10 text-accent text-xs font-medium ${className}`}
      title={`${repoUrl}${branch ? ` @ ${branch}` : ""}`}
    >
      <GitBranch size={12} className="shrink-0" />
      <span className="truncate">{repoName}</span>
      {branch && (
        <>
          <span className="text-gray-500">@</span>
          <span className="truncate text-accent/70">{branch}</span>
        </>
      )}
    </span>
  );
}
