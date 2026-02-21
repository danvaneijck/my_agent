import { useState, useEffect, useRef } from "react";
import { X, Rocket, Search, ChevronDown, AlertTriangle } from "lucide-react";
import { api } from "@/api/client";
import { mapTask } from "@/types";
import type { Task } from "@/types";

interface NewDeploymentModalProps {
  open: boolean;
  onClose: () => void;
  onCreated?: () => void;
}

interface FormErrors {
  project_name?: string;
  project_path?: string;
  container_port?: string;
}

const PROJECT_TYPES = [
  { value: "", label: "Auto-detect" },
  { value: "react", label: "React" },
  { value: "nextjs", label: "Next.js" },
  { value: "static", label: "Static" },
  { value: "node", label: "Node.js" },
  { value: "docker", label: "Docker" },
  { value: "compose", label: "Compose" },
];

function validate(
  projectName: string,
  projectPath: string,
  containerPort: string
): FormErrors {
  const errors: FormErrors = {};

  if (!projectName.trim()) {
    errors.project_name = "Project name is required.";
  }

  if (!projectPath.trim()) {
    errors.project_path = "Project path is required.";
  }

  if (containerPort.trim() !== "") {
    const parsed = parseInt(containerPort, 10);
    if (isNaN(parsed) || !Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
      errors.container_port = "Port must be an integer between 1 and 65535.";
    }
  }

  return errors;
}

export default function NewDeploymentModal({
  open,
  onClose,
  onCreated,
}: NewDeploymentModalProps) {
  const [projectName, setProjectName] = useState("");
  const [projectPath, setProjectPath] = useState("");
  const [projectType, setProjectType] = useState("");
  const [containerPort, setContainerPort] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  // Task picker state
  const [tasks, setTasks] = useState<Task[]>([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [tasksError, setTasksError] = useState(false);
  const [taskSearch, setTaskSearch] = useState("");
  const [taskPickerOpen, setTaskPickerOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [pathMode, setPathMode] = useState<"task" | "manual">("task");

  const firstInputRef = useRef<HTMLInputElement>(null);
  const taskPickerRef = useRef<HTMLDivElement>(null);

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setProjectName("");
      setProjectPath("");
      setProjectType("");
      setContainerPort("");
      setErrors({});
      setTouched({});
      setSubmitting(false);
      setSubmitError("");
      setSelectedTask(null);
      setTaskSearch("");
      setTaskPickerOpen(false);
      setTasksError(false);
      setPathMode("task");
      setTimeout(() => firstInputRef.current?.focus(), 50);
    }
  }, [open]);

  // Fetch tasks for path picker; fall back to manual mode on error
  useEffect(() => {
    if (!open) return;
    setTasksLoading(true);
    setTasksError(false);
    api<{ tasks: Record<string, unknown>[] }>("/api/tasks")
      .then((data) => setTasks((data.tasks || []).map(mapTask)))
      .catch(() => {
        setTasksError(true);
        setPathMode("manual");
      })
      .finally(() => setTasksLoading(false));
  }, [open]);

  // Close task picker on outside click
  useEffect(() => {
    if (!taskPickerOpen) return;
    const handler = (e: MouseEvent) => {
      if (
        taskPickerRef.current &&
        !taskPickerRef.current.contains(e.target as Node)
      ) {
        setTaskPickerOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [taskPickerOpen]);

  // Escape key closes modal (but not while submitting)
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose, submitting]);

  const filteredTasks = tasks.filter(
    (t) =>
      t.status === "completed" &&
      (taskSearch === "" ||
        t.prompt.toLowerCase().includes(taskSearch.toLowerCase()) ||
        t.id.toLowerCase().includes(taskSearch.toLowerCase()))
  );

  const handleSelectTask = (task: Task) => {
    setSelectedTask(task);
    setProjectPath(task.workspace);
    setTaskPickerOpen(false);
    setTaskSearch("");
    if (touched.project_path) {
      setErrors((prev) => ({ ...prev, project_path: undefined }));
    }
  };

  const handlePathModeSwitch = (mode: "task" | "manual") => {
    setPathMode(mode);
    setSelectedTask(null);
    setProjectPath("");
    setErrors((prev) => ({ ...prev, project_path: undefined }));
  };

  const handleBlur = (field: string) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
    const newErrors = validate(projectName, projectPath, containerPort);
    setErrors(newErrors);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Block submission if tasks are still loading (race condition guard)
    if (tasksLoading) return;

    setTouched({ project_name: true, project_path: true, container_port: true });
    const newErrors = validate(projectName, projectPath, containerPort);
    setErrors(newErrors);
    if (Object.keys(newErrors).length > 0) return;

    setSubmitting(true);
    setSubmitError("");
    try {
      const body: Record<string, unknown> = {
        project_name: projectName.trim(),
        project_path: projectPath.trim(),
      };
      if (projectType) body.project_type = projectType;
      if (containerPort.trim() !== "") {
        body.container_port = parseInt(containerPort, 10);
      }
      await api("/api/deployments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      onCreated?.();
      onClose();
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Failed to start deployment."
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  const hasErrors = Object.keys(validate(projectName, projectPath, containerPort)).length > 0;
  // Button is disabled while submitting, tasks are loading, or there are visible validation errors
  const submitDisabled =
    submitting ||
    tasksLoading ||
    (Object.keys(touched).length > 0 && hasErrors);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl w-full max-w-lg flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-light-border dark:border-border">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Rocket size={16} className="text-accent" />
            New Deployment
          </h3>
          <button
            onClick={onClose}
            disabled={submitting}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <X size={16} />
          </button>
        </div>

        {/* Tasks-load-failed notice */}
        {tasksError && (
          <div className="mx-5 mt-4 flex items-start gap-2 bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2.5 text-xs text-yellow-600 dark:text-yellow-400">
            <AlertTriangle size={13} className="shrink-0 mt-0.5" />
            <span>
              Could not load task workspaces. Enter the project path manually below.
            </span>
          </div>
        )}

        {/* Body */}
        <form id="new-deployment-form" onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Project name */}
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              Project Name <span className="text-red-400">*</span>
            </label>
            <input
              ref={firstInputRef}
              type="text"
              value={projectName}
              onChange={(e) => {
                setProjectName(e.target.value);
                if (touched.project_name) {
                  const newErrors = validate(e.target.value, projectPath, containerPort);
                  setErrors((prev) => ({ ...prev, project_name: newErrors.project_name }));
                }
              }}
              onBlur={() => handleBlur("project_name")}
              placeholder="my-app"
              className={`w-full bg-white dark:bg-surface border rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none transition-colors ${
                errors.project_name
                  ? "border-red-400 focus:border-red-400"
                  : "border-light-border dark:border-border focus:border-accent"
              }`}
            />
            {errors.project_name && (
              <p className="mt-1 text-xs text-red-400">{errors.project_name}</p>
            )}
          </div>

          {/* Project path */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-medium text-gray-700 dark:text-gray-300">
                Project Path <span className="text-red-400">*</span>
              </label>
              {/* Only show mode toggle when task fetch didn't error */}
              {!tasksError && (
                <div className="flex gap-1 text-xs">
                  <button
                    type="button"
                    disabled={tasksLoading}
                    onClick={() => handlePathModeSwitch("task")}
                    className={`px-2 py-0.5 rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                      pathMode === "task"
                        ? "bg-accent/15 text-accent-hover"
                        : "text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                    }`}
                  >
                    From task
                  </button>
                  <button
                    type="button"
                    disabled={tasksLoading}
                    onClick={() => handlePathModeSwitch("manual")}
                    className={`px-2 py-0.5 rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                      pathMode === "manual"
                        ? "bg-accent/15 text-accent-hover"
                        : "text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                    }`}
                  >
                    Manual
                  </button>
                </div>
              )}
            </div>

            {pathMode === "task" ? (
              <div ref={taskPickerRef} className="relative">
                <button
                  type="button"
                  disabled={tasksLoading}
                  onClick={() => !tasksLoading && setTaskPickerOpen((v) => !v)}
                  onBlur={() => handleBlur("project_path")}
                  className={`w-full flex items-center justify-between bg-white dark:bg-surface border rounded-lg px-3 py-2 text-sm text-left transition-colors focus:outline-none disabled:cursor-not-allowed disabled:opacity-60 ${
                    errors.project_path
                      ? "border-red-400"
                      : "border-light-border dark:border-border focus:border-accent"
                  }`}
                >
                  {selectedTask ? (
                    <span className="text-gray-900 dark:text-gray-200 truncate">
                      {selectedTask.prompt.slice(0, 60)}
                      {selectedTask.prompt.length > 60 ? "…" : ""}
                    </span>
                  ) : (
                    <span className="text-gray-400 dark:text-gray-600">
                      {tasksLoading ? "Loading workspaces…" : "Select a completed task"}
                    </span>
                  )}
                  {tasksLoading ? (
                    <div className="ml-2 shrink-0 w-3.5 h-3.5 border-2 border-gray-300 dark:border-gray-600 border-t-accent rounded-full animate-spin" />
                  ) : (
                    <ChevronDown
                      size={14}
                      className={`ml-2 shrink-0 text-gray-400 transition-transform ${taskPickerOpen ? "rotate-180" : ""}`}
                    />
                  )}
                </button>

                {taskPickerOpen && !tasksLoading && (
                  <div className="absolute z-10 mt-1 w-full bg-white dark:bg-surface border border-light-border dark:border-border rounded-lg shadow-lg overflow-hidden">
                    <div className="p-2 border-b border-light-border dark:border-border">
                      <div className="flex items-center gap-2 bg-gray-100 dark:bg-surface-lighter rounded px-2 py-1.5">
                        <Search size={12} className="text-gray-400 shrink-0" />
                        <input
                          autoFocus
                          type="text"
                          value={taskSearch}
                          onChange={(e) => setTaskSearch(e.target.value)}
                          placeholder="Search tasks…"
                          className="flex-1 bg-transparent text-xs text-gray-900 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none"
                        />
                      </div>
                    </div>
                    <div className="max-h-48 overflow-y-auto">
                      {filteredTasks.length === 0 ? (
                        <div className="px-3 py-4 text-xs text-gray-400 text-center">
                          No completed tasks found
                        </div>
                      ) : (
                        filteredTasks.map((task) => (
                          <button
                            key={task.id}
                            type="button"
                            onClick={() => handleSelectTask(task)}
                            className="w-full text-left px-3 py-2.5 hover:bg-gray-50 dark:hover:bg-surface-lighter text-xs border-b border-light-border dark:border-border/50 last:border-0"
                          >
                            <div className="text-gray-800 dark:text-gray-200 truncate">
                              {task.prompt.slice(0, 80)}
                              {task.prompt.length > 80 ? "…" : ""}
                            </div>
                            <div className="text-gray-400 font-mono mt-0.5 truncate">
                              {task.workspace}
                            </div>
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                )}

                {selectedTask && (
                  <div className="mt-1 text-xs text-gray-400 font-mono truncate">
                    {selectedTask.workspace}
                  </div>
                )}
              </div>
            ) : (
              <input
                type="text"
                value={projectPath}
                onChange={(e) => {
                  setProjectPath(e.target.value);
                  if (touched.project_path) {
                    const newErrors = validate(projectName, e.target.value, containerPort);
                    setErrors((prev) => ({ ...prev, project_path: newErrors.project_path }));
                  }
                }}
                onBlur={() => handleBlur("project_path")}
                placeholder="/tmp/claude_tasks/abc123/"
                className={`w-full bg-white dark:bg-surface border rounded-lg px-3 py-2 text-sm font-mono text-gray-900 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none transition-colors ${
                  errors.project_path
                    ? "border-red-400 focus:border-red-400"
                    : "border-light-border dark:border-border focus:border-accent"
                }`}
              />
            )}

            {errors.project_path && (
              <p className="mt-1 text-xs text-red-400">{errors.project_path}</p>
            )}
          </div>

          {/* Project type */}
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              Project Type
            </label>
            <select
              value={projectType}
              onChange={(e) => setProjectType(e.target.value)}
              className="w-full bg-white dark:bg-surface border border-light-border dark:border-border rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-gray-200 focus:outline-none focus:border-accent transition-colors"
            >
              {PROJECT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          {/* Container port */}
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              Container Port
              <span className="ml-1 text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="text"
              inputMode="numeric"
              value={containerPort}
              onChange={(e) => {
                setContainerPort(e.target.value);
                if (touched.container_port) {
                  const newErrors = validate(projectName, projectPath, e.target.value);
                  setErrors((prev) => ({ ...prev, container_port: newErrors.container_port }));
                }
              }}
              onBlur={() => handleBlur("container_port")}
              placeholder="Auto-detected (e.g. 3000)"
              className={`w-full bg-white dark:bg-surface border rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none transition-colors ${
                errors.container_port
                  ? "border-red-400 focus:border-red-400"
                  : "border-light-border dark:border-border focus:border-accent"
              }`}
            />
            {errors.container_port && (
              <p className="mt-1 text-xs text-red-400">{errors.container_port}</p>
            )}
          </div>

          {submitError && (
            <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2">
              {submitError}
            </p>
          )}
        </form>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-light-border dark:border-border">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="px-3 py-1.5 rounded-lg text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-surface-lighter transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="new-deployment-form"
            disabled={submitDisabled}
            title={tasksLoading ? "Waiting for workspaces to load…" : undefined}
            className="px-4 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
          >
            {submitting ? (
              <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <Rocket size={12} />
            )}
            {submitting ? "Deploying…" : "Deploy"}
          </button>
        </div>
      </div>
    </div>
  );
}
