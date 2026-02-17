import { useState, useEffect, useMemo } from "react";
import { X, Search, Plus, Check } from "lucide-react";
import { useSkills } from "@/hooks/useSkills";
import type { SkillSummary } from "@/hooks/useSkills";

const CATEGORIES = ["code", "config", "procedure", "template", "reference"];

interface SkillPickerProps {
  open: boolean;
  onClose: () => void;
  onAttach: (skillId: string) => Promise<void>;
  attachedSkillIds: string[];
  title?: string;
}

export default function SkillPicker({
  open,
  onClose,
  onAttach,
  attachedSkillIds,
  title = "Attach Skill",
}: SkillPickerProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [attaching, setAttaching] = useState<string | null>(null);
  const [error, setError] = useState("");

  const { skills, loading } = useSkills(
    categoryFilter || undefined,
    undefined,
    searchQuery || undefined
  );

  // Filter out already attached skills
  const availableSkills = useMemo(() => {
    return skills.filter((skill) => !attachedSkillIds.includes(skill.skill_id));
  }, [skills, attachedSkillIds]);

  // Reset state when modal opens
  useEffect(() => {
    if (open) {
      setSearchQuery("");
      setCategoryFilter("");
      setError("");
      setAttaching(null);
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !attaching) onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose, attaching]);

  if (!open) return null;

  const handleAttach = async (skillId: string) => {
    setAttaching(skillId);
    setError("");
    try {
      await onAttach(skillId);
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to attach skill";
      setError(msg);
    } finally {
      setAttaching(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-surface border border-border rounded-xl max-w-2xl w-full max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="sticky top-0 bg-surface border-b border-border p-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Plus size={20} className="text-accent" />
            {title}
          </h2>
          <button
            onClick={onClose}
            disabled={!!attaching}
            className="p-1 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200 disabled:opacity-50"
          >
            <X size={20} />
          </button>
        </div>

        {/* Search and Filter */}
        <div className="p-4 space-y-3 border-b border-border">
          <div className="relative">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search skills..."
              disabled={!!attaching}
              className="w-full pl-10 pr-3 py-2 bg-surface-lighter border border-border rounded text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50"
            />
          </div>

          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            disabled={!!attaching}
            className="w-full px-3 py-2 bg-surface-lighter border border-border rounded text-white focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50"
          >
            <option value="">All categories</option>
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        {/* Error */}
        {error && (
          <div className="mx-4 mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Skills List */}
        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-accent"></div>
            </div>
          )}

          {!loading && availableSkills.length === 0 && (
            <div className="text-center py-8 text-gray-400">
              {skills.length === 0
                ? "No skills found"
                : "All available skills are already attached"}
            </div>
          )}

          {!loading && availableSkills.length > 0 && (
            <div className="space-y-2">
              {availableSkills.map((skill) => (
                <button
                  key={skill.skill_id}
                  onClick={() => handleAttach(skill.skill_id)}
                  disabled={!!attaching}
                  className="w-full bg-surface-lighter border border-border rounded-lg p-3 text-left hover:border-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium text-white truncate">
                          {skill.name}
                        </h3>
                        {skill.category && (
                          <span className="text-xs px-2 py-0.5 bg-surface rounded text-gray-400">
                            {skill.category}
                          </span>
                        )}
                      </div>
                      {skill.description && (
                        <p className="text-sm text-gray-400 line-clamp-2">
                          {skill.description}
                        </p>
                      )}
                      {skill.language && (
                        <span className="text-xs text-gray-500 mt-1 inline-block">
                          {skill.language}
                        </span>
                      )}
                    </div>
                    {attaching === skill.skill_id ? (
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-accent flex-shrink-0"></div>
                    ) : (
                      <Plus size={18} className="text-accent flex-shrink-0" />
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-border p-4">
          <div className="flex justify-between items-center text-sm text-gray-400">
            <span>
              {availableSkills.length} skill{availableSkills.length !== 1 ? "s" : ""}{" "}
              available
            </span>
            <button
              onClick={onClose}
              disabled={!!attaching}
              className="px-4 py-2 bg-surface-lighter hover:bg-surface-light text-gray-300 rounded disabled:opacity-50"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
