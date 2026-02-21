import { useState, useEffect, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { X, GitBranch, Upload, Search, Plus, Shield, BookOpen, ChevronDown, Check } from "lucide-react";
import { api } from "@/api/client";
import { useRepos } from "@/hooks/useRepos";
import { useBranches } from "@/hooks/useBranches";
import { useSkills } from "@/hooks/useSkills";
import type { GitRepo, GitBranch as GitBranchType } from "@/types";

interface NewTaskModalProps {
  open: boolean;
  onClose: () => void;
  onCreated?: () => void;
  defaultRepoUrl?: string;
  defaultBranch?: string;
  defaultPrompt?: string;
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
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function NewTaskModal({
  open,
  onClose,
  onCreated,
  defaultRepoUrl = "",
  defaultBranch = "",
  defaultPrompt = "",
}: NewTaskModalProps) {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [repoUrl, setRepoUrl] = useState(defaultRepoUrl);
  const [branch, setBranch] = useState(defaultBranch);
  const [newBranch, setNewBranch] = useState("");
  const [mode, setMode] = useState<"execute" | "plan">("execute");
  const [autoPush, setAutoPush] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const promptRef = useRef<HTMLTextAreaElement>(null);

  // Skills state
  const [selectedSkillIds, setSelectedSkillIds] = useState<string[]>([]);
  const [skillsExpanded, setSkillsExpanded] = useState(false);
  const [skillSearch, setSkillSearch] = useState("");

  // Repository selection state
  const [selectedRepo, setSelectedRepo] = useState<GitRepo | null>(null);
  const [repoSearch, setRepoSearch] = useState("");

  // Branch selection state
  const [selectedBranch, setSelectedBranch] = useState<GitBranchType | null>(null);
  const [branchSearch, setBranchSearch] = useState("");
  const [creatingNewBranch, setCreatingNewBranch] = useState(false);

  // Fetch repos (only when no defaultRepoUrl)
  const { repos, loading: reposLoading } = useRepos();

  // Fetch branches when repo is selected
  const { branches, loading: branchesLoading } = useBranches(
    selectedRepo?.owner || "",
    selectedRepo?.repo || "",
    !!selectedRepo // only fetch when repo is selected
  );

  // Fetch user skills for the skills selector
  const { skills, loading: skillsLoading } = useSkills();

  // Filter repos by search
  const filteredRepos = useMemo(() => {
    if (!repoSearch.trim()) return [];
    const q = repoSearch.toLowerCase();
    return repos.filter(
      (r) =>
        r.full_name.toLowerCase().includes(q) ||
        (r.description || "").toLowerCase().includes(q)
    );
  }, [repos, repoSearch]);

  // Filter branches by search
  const filteredBranches = useMemo(() => {
    if (!branchSearch.trim()) return [];
    const q = branchSearch.toLowerCase();
    return branches.filter((b) => b.name.toLowerCase().includes(q));
  }, [branches, branchSearch]);

  // Filter skills by search
  const filteredSkills = useMemo(() => {
    if (!skillSearch.trim()) return skills;
    const q = skillSearch.toLowerCase();
    return skills.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        (s.description || "").toLowerCase().includes(q) ||
        (s.category || "").toLowerCase().includes(q)
    );
  }, [skills, skillSearch]);

  // The branch actually sent to the API: new branch overrides source branch
  const effectiveBranch = newBranch.trim() || branch.trim();

  // Sync defaults when props change (e.g. opened from different repo/branch)
  useEffect(() => {
    if (open) {
      setRepoUrl(defaultRepoUrl);
      setBranch(defaultBranch);
      setNewBranch("");
      setPrompt(defaultPrompt);
      setMode("execute");
      setAutoPush(false);
      setError("");
      setRepoSearch("");
      setBranchSearch("");
      setCreatingNewBranch(false);
      setSelectedSkillIds([]);
      setSkillsExpanded(false);
      setSkillSearch("");

      // If defaultRepoUrl is provided, parse it to populate selectedRepo
      if (defaultRepoUrl) {
        // Parse git URL to extract owner/repo
        // e.g., "https://github.com/owner/repo.git" -> owner="owner", repo="repo"
        const match = defaultRepoUrl.match(/github\.com\/([^\/]+)\/([^\/\.]+)/);
        if (match) {
          setSelectedRepo({
            owner: match[1],
            repo: match[2],
            full_name: `${match[1]}/${match[2]}`,
            clone_url: defaultRepoUrl,
            description: null,
            url: defaultRepoUrl,
            default_branch: defaultBranch || "main",
            language: null,
            private: false,
            stars: 0,
            updated_at: "",
          });
        }
      } else {
        setSelectedRepo(null);
      }

      setSelectedBranch(null);
      setTimeout(() => promptRef.current?.focus(), 50);
    }
  }, [open, defaultRepoUrl, defaultBranch, defaultPrompt]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  const toggleSkill = (skillId: string) => {
    setSelectedSkillIds((prev) =>
      prev.includes(skillId) ? prev.filter((id) => id !== skillId) : [...prev, skillId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setSubmitting(true);
    setError("");

    try {
      const body: Record<string, string | boolean> = { prompt: prompt.trim(), mode };

      // Determine repo_url
      if (selectedRepo) {
        body.repo_url = selectedRepo.clone_url;
      } else if (repoUrl.trim()) {
        body.repo_url = repoUrl.trim();
      }

      // Determine branch and source_branch
      if (creatingNewBranch && newBranch.trim()) {
        body.branch = newBranch.trim();
        // Source branch is either selected branch or the default/provided branch
        const sourceBranchName = selectedBranch?.name || branch.trim();
        if (sourceBranchName) {
          body.source_branch = sourceBranchName;
        }
      } else if (selectedBranch) {
        body.branch = selectedBranch.name;
      } else if (branch.trim()) {
        body.branch = branch.trim();
      }

      if (autoPush) body.auto_push = true;
      if (selectedSkillIds.length > 0) {
        (body as Record<string, unknown>).skill_ids = selectedSkillIds;
      }

      const result = await api<{ task_id: string }>("/api/tasks", {
        method: "POST",
        body: JSON.stringify(body),
      });

      onClose();
      onCreated?.();

      if (result.task_id) {
        navigate(`/tasks/${result.task_id}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create task");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl w-full max-w-lg shadow-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-light-border dark:border-border shrink-0">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">New Task</h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4 overflow-y-auto flex-1">
          <div>
            <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1.5">Task description</label>
            <textarea
              ref={promptRef}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe what you want Claude Code to do..."
              rows={4}
              className="w-full px-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent resize-none"
            />
          </div>

          {/* Repository selection dropdown (when not pre-filled) */}
          {!defaultRepoUrl && (
            <div className="space-y-3">
              <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1.5">
                Repository <span className="text-gray-400 dark:text-gray-600">(optional)</span>
              </label>

              {/* Search input */}
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  value={repoSearch}
                  onChange={(e) => setRepoSearch(e.target.value)}
                  placeholder="Search repositories..."
                  className="w-full pl-9 pr-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent"
                />
              </div>

              {/* Repo list dropdown */}
              {repoSearch && (
                <div className="max-h-52 overflow-y-auto border border-light-border dark:border-border rounded-lg divide-y divide-light-border dark:divide-border bg-white dark:bg-surface">
                  {reposLoading ? (
                    <div className="px-3 py-4 text-sm text-gray-500 text-center">Loading repos...</div>
                  ) : filteredRepos.length === 0 ? (
                    <div className="px-3 py-4 text-sm text-gray-500 text-center">
                      No matching repos
                    </div>
                  ) : (
                    filteredRepos.map((repo) => (
                      <button
                        key={repo.full_name}
                        type="button"
                        onClick={() => {
                          setSelectedRepo(repo);
                          setRepoUrl(repo.clone_url);
                          setRepoSearch("");
                          setSelectedBranch(null);
                          setBranch(repo.default_branch);
                          setCreatingNewBranch(false);
                        }}
                        className="w-full text-left px-3 py-2.5 hover:bg-gray-100 dark:hover:bg-surface-lighter transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-gray-900 dark:text-white font-mono">{repo.full_name}</span>
                          {repo.private && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                              private
                            </span>
                          )}
                        </div>
                        {repo.description && (
                          <p className="text-xs text-gray-500 mt-0.5 truncate">{repo.description}</p>
                        )}
                      </button>
                    ))
                  )}
                </div>
              )}

              {/* Selected repo indicator */}
              {selectedRepo && (
                <div className="bg-accent/10 border border-accent/20 rounded-lg px-3 py-2 flex items-center justify-between">
                  <span className="text-sm text-accent font-mono">{selectedRepo.full_name}</span>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedRepo(null);
                      setRepoUrl("");
                      setSelectedBranch(null);
                      setBranch("");
                      setCreatingNewBranch(false);
                    }}
                    className="p-1 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Repository info (if pre-filled) */}
          {defaultRepoUrl && (
            <div className="bg-gray-50 dark:bg-surface/50 border border-light-border dark:border-border rounded-lg px-3 py-2">
              <span className="text-xs text-gray-500 block mb-0.5">Repository</span>
              <span className="text-sm text-gray-700 dark:text-gray-300 font-mono">{selectedRepo?.full_name || repoUrl}</span>
            </div>
          )}

          {/* Branch selection dropdown (shown when repo is selected or pre-filled) */}
          {(selectedRepo || defaultRepoUrl) && (
            <div className="space-y-3">
              <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1.5">
                <GitBranch size={14} className="inline mr-1 -mt-0.5" />
                Branch
              </label>

              {/* "Create new branch" option */}
              <button
                type="button"
                onClick={() => {
                  setCreatingNewBranch(!creatingNewBranch);
                  if (!creatingNewBranch) {
                    setSelectedBranch(null);
                    setNewBranch("");
                  }
                }}
                className={`w-full text-left px-3 py-2 rounded-lg border transition-colors ${
                  creatingNewBranch
                    ? "bg-accent/10 border-accent/30 text-accent"
                    : "bg-white dark:bg-surface border-light-border dark:border-border text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-surface-lighter"
                }`}
              >
                <Plus size={14} className="inline mr-2 -mt-0.5" />
                Create new branch
              </button>

              {/* New branch name input (shown when creating new branch) */}
              {creatingNewBranch && (
                <div>
                  <input
                    value={newBranch}
                    onChange={(e) => setNewBranch(e.target.value)}
                    placeholder="feature/my-new-feature"
                    className="w-full px-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent font-mono"
                  />
                  {newBranch.trim() && (
                    <p className="text-xs text-gray-500 mt-1">
                      Will create <span className="text-accent font-mono">{newBranch.trim()}</span> from{" "}
                      <span className="font-mono">{selectedBranch?.name || branch || "default branch"}</span>
                    </p>
                  )}
                </div>
              )}

              {/* Existing branch selection */}
              {!creatingNewBranch && (
                <>
                  {/* Search input */}
                  <div className="relative">
                    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                    <input
                      value={branchSearch}
                      onChange={(e) => setBranchSearch(e.target.value)}
                      placeholder="Search branches..."
                      className="w-full pl-9 pr-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent"
                    />
                  </div>

                  {/* Branch list dropdown */}
                  {branchSearch && (
                    <div className="max-h-52 overflow-y-auto border border-light-border dark:border-border rounded-lg divide-y divide-light-border dark:divide-border bg-white dark:bg-surface">
                      {branchesLoading ? (
                        <div className="px-3 py-4 text-sm text-gray-500 text-center">Loading branches...</div>
                      ) : filteredBranches.length === 0 ? (
                        <div className="px-3 py-4 text-sm text-gray-500 text-center">
                          No matching branches
                        </div>
                      ) : (
                        filteredBranches.map((branchItem) => (
                          <button
                            key={branchItem.name}
                            type="button"
                            onClick={() => {
                              setSelectedBranch(branchItem);
                              setBranch(branchItem.name);
                              setBranchSearch("");
                            }}
                            className="w-full text-left px-3 py-2.5 hover:bg-gray-100 dark:hover:bg-surface-lighter transition-colors"
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-sm text-gray-900 dark:text-white font-mono">{branchItem.name}</span>
                              {branchItem.protected && (
                                <Shield size={12} className="text-yellow-400" />
                              )}
                            </div>
                            {branchItem.updated_at && (
                              <p className="text-xs text-gray-500 mt-0.5">
                                Updated {formatRelativeDate(branchItem.updated_at)}
                              </p>
                            )}
                          </button>
                        ))
                      )}
                    </div>
                  )}

                  {/* Selected branch indicator */}
                  {selectedBranch && (
                    <div className="bg-accent/10 border border-accent/20 rounded-lg px-3 py-2 flex items-center justify-between">
                      <span className="text-sm text-accent font-mono">{selectedBranch.name}</span>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedBranch(null);
                          setBranch("");
                        }}
                        className="p-1 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  )}

                  {/* Show default branch if nothing selected */}
                  {!selectedBranch && branch && (
                    <div className="bg-gray-50 dark:bg-surface/50 border border-light-border dark:border-border rounded-lg px-3 py-2">
                      <span className="text-xs text-gray-500 block mb-0.5">Default branch</span>
                      <span className="text-sm text-gray-700 dark:text-gray-300 font-mono">{branch}</span>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Mode */}
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-600 dark:text-gray-400">Mode:</label>
            <button
              type="button"
              onClick={() => setMode(mode === "execute" ? "plan" : "execute")}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                mode === "plan"
                  ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                  : "bg-gray-100 dark:bg-surface-lighter text-gray-700 dark:text-gray-300 border border-light-border dark:border-border"
              }`}
            >
              {mode === "plan" ? "Plan First" : "Execute Directly"}
            </button>
            {mode === "plan" && (
              <span className="text-xs text-gray-500">
                Claude will create a plan for your review before implementing
              </span>
            )}
          </div>

          {/* Skills selector */}
          <div>
            <button
              type="button"
              onClick={() => setSkillsExpanded(!skillsExpanded)}
              className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors w-full"
            >
              <BookOpen size={14} />
              <span>Include Skills</span>
              {selectedSkillIds.length > 0 && (
                <span className="px-1.5 py-0.5 rounded-full bg-accent/20 text-accent text-xs font-medium">
                  {selectedSkillIds.length}
                </span>
              )}
              <ChevronDown
                size={14}
                className={`ml-auto transition-transform ${skillsExpanded ? "rotate-180" : ""}`}
              />
            </button>

            {skillsExpanded && (
              <div className="mt-2 space-y-2">
                {/* Skill search */}
                <div className="relative">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                  <input
                    value={skillSearch}
                    onChange={(e) => setSkillSearch(e.target.value)}
                    placeholder="Search skills..."
                    className="w-full pl-9 pr-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent"
                  />
                </div>

                {/* Skill list */}
                <div className="max-h-48 overflow-y-auto border border-light-border dark:border-border rounded-lg divide-y divide-light-border dark:divide-border bg-white dark:bg-surface">
                  {skillsLoading ? (
                    <div className="px-3 py-4 text-sm text-center text-gray-500">Loading skills...</div>
                  ) : filteredSkills.length === 0 ? (
                    <div className="px-3 py-4 text-sm text-center text-gray-500">
                      {skills.length === 0 ? "No skills saved yet." : "No matching skills."}
                    </div>
                  ) : (
                    filteredSkills.map((skill) => {
                      const selected = selectedSkillIds.includes(skill.skill_id);
                      return (
                        <button
                          key={skill.skill_id}
                          type="button"
                          onClick={() => toggleSkill(skill.skill_id)}
                          className={`w-full text-left px-3 py-2.5 transition-colors ${
                            selected
                              ? "bg-accent/10"
                              : "hover:bg-gray-100 dark:hover:bg-surface-lighter"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-gray-900 dark:text-white">
                              {skill.name}
                            </span>
                            <div className="flex items-center gap-2 shrink-0">
                              {skill.category && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-surface-lighter text-gray-500 dark:text-gray-400">
                                  {skill.category}
                                </span>
                              )}
                              {selected && <Check size={14} className="text-accent" />}
                            </div>
                          </div>
                          {skill.description && (
                            <p className="text-xs text-gray-500 mt-0.5 truncate">{skill.description}</p>
                          )}
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Auto-push (only shown when a repo + branch is configured) */}
          {(repoUrl.trim() || defaultRepoUrl) && effectiveBranch && (
            <div className="flex items-center gap-3">
              <label className="text-sm text-gray-600 dark:text-gray-400">Auto-push:</label>
              <button
                type="button"
                onClick={() => setAutoPush(!autoPush)}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors flex items-center gap-1.5 ${
                  autoPush
                    ? "bg-green-500/20 text-green-400 border border-green-500/30"
                    : "bg-gray-100 dark:bg-surface-lighter text-gray-700 dark:text-gray-300 border border-light-border dark:border-border"
                }`}
              >
                <Upload size={14} />
                {autoPush ? "Enabled" : "Disabled"}
              </button>
              {autoPush && (
                <span className="text-xs text-gray-500">
                  Will push to <span className="font-mono text-accent">{effectiveBranch}</span> on completion
                </span>
              )}
            </div>
          )}

          {error && <p className="text-sm text-red-400">{error}</p>}
        </form>

        {/* Footer - Actions */}
        <div className="flex justify-end gap-2 px-5 py-4 border-t border-light-border dark:border-border shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg bg-gray-100 dark:bg-surface-lighter text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-border transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={submitting || !prompt.trim()}
            className="px-4 py-2 text-sm rounded-lg bg-accent text-white font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
          >
            {submitting
              ? "Starting..."
              : mode === "plan"
              ? "Start Planning"
              : "Start Task"}
          </button>
        </div>
      </div>
    </div>
  );
}
