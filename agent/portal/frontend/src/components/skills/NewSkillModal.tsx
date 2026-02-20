import { useState, useEffect, useRef } from "react";
import { X, Code, Tag as TagIcon } from "lucide-react";
import { createSkill, updateSkill } from "@/hooks/useSkills";
import type { Skill, CreateSkillPayload } from "@/hooks/useSkills";

interface NewSkillModalProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (skillId: string) => void;
  editSkill?: Skill | null;
}

const CATEGORIES = ["code", "config", "procedure", "template", "reference"];
const LANGUAGES = ["python", "javascript", "typescript", "bash", "sql", "markdown", "yaml", "json"];

export default function NewSkillModal({ open, onClose, onCreated, editSkill }: NewSkillModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("code");
  const [content, setContent] = useState("");
  const [language, setLanguage] = useState("python");
  const [tagInput, setTagInput] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [isTemplate, setIsTemplate] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const nameRef = useRef<HTMLInputElement>(null);

  // Populate form when editing
  useEffect(() => {
    if (open && editSkill) {
      setName(editSkill.name);
      setDescription(editSkill.description || "");
      setCategory(editSkill.category || "code");
      setContent(editSkill.content);
      setLanguage(editSkill.language || "python");
      setTags(editSkill.tags || []);
      setIsTemplate(editSkill.is_template);
    } else if (open) {
      setName("");
      setDescription("");
      setCategory("code");
      setContent("");
      setLanguage("python");
      setTags([]);
      setIsTemplate(false);
      setTagInput("");
      setError("");
      setTimeout(() => nameRef.current?.focus(), 50);
    }
  }, [open, editSkill]);

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

  const handleAddTag = () => {
    const trimmed = tagInput.trim();
    if (trimmed && !tags.includes(trimmed)) {
      setTags([...tags, trimmed]);
      setTagInput("");
    }
  };

  const handleRemoveTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  };

  const handleTagKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddTag();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !content.trim()) {
      setError("Name and content are required");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      const payload: CreateSkillPayload = {
        name: name.trim(),
        content: content.trim(),
        description: description.trim() || undefined,
        category: category || undefined,
        language: language || undefined,
        tags: tags.length > 0 ? tags : undefined,
        is_template: isTemplate,
      };

      if (editSkill) {
        await updateSkill(editSkill.skill_id, payload);
        onCreated?.(editSkill.skill_id);
      } else {
        const created = await createSkill(payload);
        onCreated?.(created.skill_id);
      }

      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to save skill";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white dark:bg-surface border border-light-border dark:border-border rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white dark:bg-surface border-b border-light-border dark:border-border p-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Code size={20} className="text-accent" />
            {editSkill ? "Edit Skill" : "New Skill"}
          </h2>
          <button
            onClick={onClose}
            disabled={submitting}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 disabled:opacity-50"
          >
            <X size={20} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Name <span className="text-red-400">*</span>
            </label>
            <input
              ref={nameRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my_skill"
              disabled={submitting}
              className="w-full px-3 py-2 bg-gray-100 dark:bg-surface-lighter border border-light-border dark:border-border rounded text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this skill do?"
              rows={2}
              disabled={submitting}
              className="w-full px-3 py-2 bg-gray-100 dark:bg-surface-lighter border border-light-border dark:border-border rounded text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50 resize-none"
            />
          </div>

          {/* Category and Language */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Category
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={submitting}
                className="w-full px-3 py-2 bg-gray-100 dark:bg-surface-lighter border border-light-border dark:border-border rounded text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Language
              </label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                disabled={submitting}
                className="w-full px-3 py-2 bg-gray-100 dark:bg-surface-lighter border border-light-border dark:border-border rounded text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50"
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Content */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Content <span className="text-red-400">*</span>
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Enter your code, configuration, or procedure here..."
              rows={12}
              disabled={submitting}
              className="w-full px-3 py-2 bg-gray-100 dark:bg-surface-lighter border border-light-border dark:border-border rounded text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50 font-mono text-sm resize-none"
            />
          </div>

          {/* Tags */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Tags
            </label>
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={handleTagKeyDown}
                placeholder="Add a tag..."
                disabled={submitting}
                className="flex-1 px-3 py-2 bg-gray-100 dark:bg-surface-lighter border border-light-border dark:border-border rounded text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50"
              />
              <button
                type="button"
                onClick={handleAddTag}
                disabled={submitting || !tagInput.trim()}
                className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Add
              </button>
            </div>
            {tags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 dark:bg-surface-lighter border border-light-border dark:border-border rounded text-sm text-gray-700 dark:text-gray-300"
                  >
                    <TagIcon size={12} />
                    {tag}
                    <button
                      type="button"
                      onClick={() => handleRemoveTag(tag)}
                      disabled={submitting}
                      className="ml-1 text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white disabled:opacity-50"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Template Toggle */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is-template"
              checked={isTemplate}
              onChange={(e) => setIsTemplate(e.target.checked)}
              disabled={submitting}
              className="w-4 h-4 rounded bg-gray-100 dark:bg-surface-lighter border-gray-300 dark:border-border text-accent focus:ring-2 focus:ring-accent disabled:opacity-50"
            />
            <label htmlFor="is-template" className="text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
              This is a template (supports Jinja2 variables like <code className="text-accent">{"{{ variable }}"}</code>)
            </label>
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 bg-gray-100 dark:bg-surface-lighter hover:bg-gray-200 dark:hover:bg-surface-light text-gray-700 dark:text-gray-300 rounded disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !name.trim() || !content.trim()}
              className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? (editSkill ? "Updating..." : "Creating...") : (editSkill ? "Update" : "Create")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
