import { useState, useEffect, useRef, useMemo } from "react";
import { X, Search, Plus, GitBranch, Upload, Sparkles, Play } from "lucide-react";
import { useRepos } from "@/hooks/useRepos";
import { createRepo } from "@/hooks/useRepos";
import { createProject, kickoffProject } from "@/hooks/useProjects";
import type { GitRepo } from "@/types";

type RepoChoice = "existing" | "new" | "none";
type StepId = "details" | "repo" | "options";

interface NewProjectModalProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (projectId: string, claudeTaskId?: string) => void;
}

const STEPS: StepId[] = ["details", "repo", "options"];

export default function NewProjectModal({ open, onClose, onCreated }: NewProjectModalProps) {
  // Step state
  const [step, setStep] = useState<StepId>("details");
  const stepIndex = STEPS.indexOf(step);

  // Details
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  // Repo selection
  const [repoChoice, setRepoChoice] = useState<RepoChoice>("existing");
  const [repoSearch, setRepoSearch] = useState("");
  const [selectedRepo, setSelectedRepo] = useState<GitRepo | null>(null);
  const [newRepoName, setNewRepoName] = useState("");
  const [newRepoPrivate, setNewRepoPrivate] = useState(true);

  // Options
  const [mode, setMode] = useState<"plan" | "execute">("plan");
  const [autoPush, setAutoPush] = useState(true);

  // UI state
  const [submitting, setSubmitting] = useState(false);
  const [submitStep, setSubmitStep] = useState("");
  const [error, setError] = useState("");
  const nameRef = useRef<HTMLInputElement>(null);

  // Fetch repos
  const { repos, loading: reposLoading } = useRepos();

  // Filter repos by search
  const filteredRepos = useMemo(() => {
    if (!repoSearch.trim()) return repos;
    const q = repoSearch.toLowerCase();
    return repos.filter(
      (r) =>
        r.full_name.toLowerCase().includes(q) ||
        (r.description || "").toLowerCase().includes(q),
    );
  }, [repos, repoSearch]);

  // Reset on open
  useEffect(() => {
    if (open) {
      setStep("details");
      setName("");
      setDescription("");
      setRepoChoice("existing");
      setRepoSearch("");
      setSelectedRepo(null);
      setNewRepoName("");
      setNewRepoPrivate(true);
      setMode("plan");
      setAutoPush(true);
      setError("");
      setSubmitting(false);
      setSubmitStep("");
      setTimeout(() => nameRef.current?.focus(), 50);
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose, submitting]);

  if (!open) return null;

  const canNext = () => {
    if (step === "details") return name.trim().length > 0;
    if (step === "repo") {
      if (repoChoice === "existing") return selectedRepo !== null;
      if (repoChoice === "new") return newRepoName.trim().length > 0;
      return true; // "none"
    }
    return true;
  };

  const goNext = () => {
    if (stepIndex < STEPS.length - 1) setStep(STEPS[stepIndex + 1]);
  };
  const goBack = () => {
    if (stepIndex > 0) setStep(STEPS[stepIndex - 1]);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError("");

    try {
      let repoOwner: string | undefined;
      let repoName: string | undefined;
      let defaultBranch = "main";

      // 1. Create repo if needed
      if (repoChoice === "new" && newRepoName.trim()) {
        setSubmitStep("Creating repository...");
        const created = await createRepo({
          name: newRepoName.trim(),
          private: newRepoPrivate,
        });
        repoOwner = created.owner;
        repoName = created.repo;
        defaultBranch = created.default_branch || "main";
      } else if (repoChoice === "existing" && selectedRepo) {
        repoOwner = selectedRepo.owner;
        repoName = selectedRepo.repo;
        defaultBranch = selectedRepo.default_branch || "main";
      }

      // 2. Create project
      setSubmitStep("Creating project...");
      const project = await createProject({
        name: name.trim(),
        description: description.trim() || undefined,
        repo_owner: repoOwner,
        repo_name: repoName,
        default_branch: defaultBranch,
      });
      const projectId = project.project_id;

      // 3. Kick off claude task
      setSubmitStep("Starting Claude task...");
      const kickoff = await kickoffProject(projectId, {
        mode,
        auto_push: autoPush,
        description: description.trim() || undefined,
      });

      onCreated?.(projectId, kickoff.claude_task_id);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to create project";
      // Try to extract error from JSON response body
      const jsonMatch = msg.match(/\d+:\s*(\{.*\})/);
      if (jsonMatch) {
        try {
          const parsed = JSON.parse(jsonMatch[1]);
          setError(parsed.error || parsed.detail || msg);
        } catch {
          setError(msg);
        }
      } else {
        setError(msg);
      }
    } finally {
      setSubmitting(false);
      setSubmitStep("");
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onClose();
      }}
    >
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl w-full max-w-lg shadow-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-light-border dark:border-border shrink-0">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">New Project</h3>
          <button
            onClick={onClose}
            disabled={submitting}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-2 px-5 py-3 border-b border-light-border dark:border-border shrink-0">
          {STEPS.map((s, i) => {
            const labels = { details: "Details", repo: "Repository", options: "Options" };
            const active = i === stepIndex;
            const done = i < stepIndex;
            return (
              <div key={s} className="flex items-center gap-2">
                {i > 0 && <div className="w-6 h-px bg-border" />}
                <div
                  className={`flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full ${
                    active
                      ? "bg-accent/20 text-accent"
                      : done
                        ? "bg-green-500/20 text-green-400"
                        : "text-gray-500"
                  }`}
                >
                  <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${
                    active
                      ? "bg-accent text-white"
                      : done
                        ? "bg-green-500 text-white"
                        : "bg-surface-lighter text-gray-500"
                  }`}>
                    {done ? "\u2713" : i + 1}
                  </span>
                  {labels[s]}
                </div>
              </div>
            );
          })}
        </div>

        {/* Content */}
        <div className="p-5 space-y-4 overflow-y-auto flex-1">
          {/* Step 1: Details */}
          {step === "details" && (
            <>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1.5">
                  Project name <span className="text-red-400">*</span>
                </label>
                <input
                  ref={nameRef}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My New Project"
                  className="w-full px-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && canNext()) goNext();
                  }}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1.5">
                  Description
                  <span className="text-gray-400 dark:text-gray-600 ml-1">(used as the project goal for Claude)</span>
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe what this project should do, the tech stack, key features..."
                  rows={4}
                  className="w-full px-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent resize-none"
                />
              </div>
            </>
          )}

          {/* Step 2: Repository */}
          {step === "repo" && (
            <>
              {/* Choice tabs */}
              <div className="flex gap-2">
                {([
                  { id: "existing" as const, label: "Existing Repo", icon: GitBranch },
                  { id: "new" as const, label: "Create New", icon: Plus },
                  { id: "none" as const, label: "No Repo", icon: X },
                ]).map(({ id, label, icon: Icon }) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setRepoChoice(id)}
                    className={`flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg transition-colors ${
                      repoChoice === id
                        ? "bg-accent/20 text-accent border border-accent/30"
                        : "bg-gray-100 dark:bg-surface-lighter text-gray-500 dark:text-gray-400 border border-light-border dark:border-border hover:text-gray-700 dark:hover:text-gray-300"
                    }`}
                  >
                    <Icon size={14} />
                    {label}
                  </button>
                ))}
              </div>

              {/* Existing repo picker */}
              {repoChoice === "existing" && (
                <div className="space-y-3">
                  <div className="relative">
                    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                    <input
                      value={repoSearch}
                      onChange={(e) => setRepoSearch(e.target.value)}
                      placeholder="Search repositories..."
                      className="w-full pl-9 pr-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent"
                    />
                  </div>
                  <div className="max-h-52 overflow-y-auto border border-light-border dark:border-border rounded-lg divide-y divide-light-border dark:divide-border bg-white dark:bg-surface">
                    {reposLoading ? (
                      <div className="px-3 py-4 text-sm text-gray-500 text-center">Loading repos...</div>
                    ) : filteredRepos.length === 0 ? (
                      <div className="px-3 py-4 text-sm text-gray-500 text-center">
                        {repoSearch ? "No matching repos" : "No repos found"}
                      </div>
                    ) : (
                      filteredRepos.map((repo) => (
                        <button
                          key={repo.full_name}
                          type="button"
                          onClick={() => setSelectedRepo(repo)}
                          className={`w-full text-left px-3 py-2.5 hover:bg-gray-100 dark:hover:bg-surface-lighter transition-colors ${
                            selectedRepo?.full_name === repo.full_name ? "bg-accent/10" : ""
                          }`}
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
                          <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                            {repo.language && <span>{repo.language}</span>}
                            <span>{repo.default_branch}</span>
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                  {selectedRepo && (
                    <div className="bg-accent/10 border border-accent/20 rounded-lg px-3 py-2">
                      <span className="text-xs text-gray-400">Selected: </span>
                      <span className="text-sm text-accent font-mono">{selectedRepo.full_name}</span>
                    </div>
                  )}
                </div>
              )}

              {/* New repo form */}
              {repoChoice === "new" && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1.5">
                      Repository name <span className="text-red-400">*</span>
                    </label>
                    <input
                      value={newRepoName}
                      onChange={(e) => setNewRepoName(e.target.value)}
                      placeholder="my-new-project"
                      className="w-full px-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent font-mono"
                    />
                  </div>
                  <div className="flex items-center gap-3">
                    <label className="text-sm text-gray-600 dark:text-gray-400">Visibility:</label>
                    <button
                      type="button"
                      onClick={() => setNewRepoPrivate(!newRepoPrivate)}
                      className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                        newRepoPrivate
                          ? "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30"
                          : "bg-surface-lighter text-gray-300 border border-border"
                      }`}
                    >
                      {newRepoPrivate ? "Private" : "Public"}
                    </button>
                  </div>
                </div>
              )}

              {/* No repo info */}
              {repoChoice === "none" && (
                <div className="bg-gray-50 dark:bg-surface/50 border border-light-border dark:border-border rounded-lg px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                  The project will be created without a linked repository. Claude will plan the project
                  but won&apos;t clone or push to any repo.
                </div>
              )}
            </>
          )}

          {/* Step 3: Options */}
          {step === "options" && (
            <>
              {/* Summary */}
              <div className="bg-gray-50 dark:bg-surface/50 border border-light-border dark:border-border rounded-lg px-4 py-3 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">Project</span>
                  <span className="text-sm text-gray-900 dark:text-white font-medium">{name}</span>
                </div>
                {(repoChoice === "existing" && selectedRepo) && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Repository</span>
                    <span className="text-sm text-accent font-mono">{selectedRepo.full_name}</span>
                  </div>
                )}
                {(repoChoice === "new" && newRepoName) && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">New Repository</span>
                    <span className="text-sm text-accent font-mono">{newRepoName}</span>
                  </div>
                )}
                {repoChoice === "none" && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Repository</span>
                    <span className="text-sm text-gray-500">None</span>
                  </div>
                )}
              </div>

              {/* Mode */}
              <div className="space-y-2">
                <label className="block text-sm text-gray-600 dark:text-gray-400">Execution mode</label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setMode("plan")}
                    className={`flex-1 flex items-center gap-2 px-3 py-2.5 text-sm rounded-lg transition-colors ${
                      mode === "plan"
                        ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                        : "bg-gray-100 dark:bg-surface-lighter text-gray-500 dark:text-gray-400 border border-light-border dark:border-border hover:text-gray-700 dark:hover:text-gray-300"
                    }`}
                  >
                    <Sparkles size={14} />
                    <div className="text-left">
                      <div className="font-medium">Plan first</div>
                      <div className="text-xs opacity-70">Claude creates a plan for your review</div>
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("execute")}
                    className={`flex-1 flex items-center gap-2 px-3 py-2.5 text-sm rounded-lg transition-colors ${
                      mode === "execute"
                        ? "bg-green-500/20 text-green-400 border border-green-500/30"
                        : "bg-gray-100 dark:bg-surface-lighter text-gray-500 dark:text-gray-400 border border-light-border dark:border-border hover:text-gray-700 dark:hover:text-gray-300"
                    }`}
                  >
                    <Play size={14} />
                    <div className="text-left">
                      <div className="font-medium">Execute</div>
                      <div className="text-xs opacity-70">Claude starts implementing right away</div>
                    </div>
                  </button>
                </div>
              </div>

              {/* Auto-push */}
              {repoChoice !== "none" && (
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm text-gray-600 dark:text-gray-400 flex items-center gap-1.5">
                      <Upload size={14} />
                      Auto-push on completion
                    </label>
                    <p className="text-xs text-gray-500 mt-0.5">Push branch to remote after task finishes</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setAutoPush(!autoPush)}
                    className={`relative w-10 h-5 rounded-full transition-colors ${
                      autoPush ? "bg-accent" : "bg-surface-lighter"
                    }`}
                  >
                    <div
                      className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                        autoPush ? "translate-x-5" : "translate-x-0.5"
                      }`}
                    />
                  </button>
                </div>
              )}
            </>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-sm text-red-400">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-light-border dark:border-border shrink-0">
          <button
            type="button"
            onClick={stepIndex === 0 ? onClose : goBack}
            disabled={submitting}
            className="px-4 py-2 text-sm rounded-lg bg-gray-100 dark:bg-surface-lighter text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-border transition-colors disabled:opacity-50"
          >
            {stepIndex === 0 ? "Cancel" : "Back"}
          </button>

          {step === "options" ? (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting}
              className="px-4 py-2 text-sm rounded-lg bg-accent text-white font-medium hover:bg-accent-hover transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {submitting ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  {submitStep}
                </>
              ) : mode === "plan" ? (
                <>
                  <Sparkles size={14} />
                  Create & Plan
                </>
              ) : (
                <>
                  <Play size={14} />
                  Create & Execute
                </>
              )}
            </button>
          ) : (
            <button
              type="button"
              onClick={goNext}
              disabled={!canNext()}
              className="px-4 py-2 text-sm rounded-lg bg-accent text-white font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              Next
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
