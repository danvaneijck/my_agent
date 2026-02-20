import { useState } from "react";
import { motion } from "framer-motion";
import { pageVariants } from "@/utils/animations";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Edit,
  Trash2,
  FileCode,
  Tag as TagIcon,
  Calendar,
  AlertCircle,
} from "lucide-react";
import { useSkill } from "@/hooks/useSkill";
import { deleteSkill } from "@/hooks/useSkills";
import { usePageTitle } from "@/hooks/usePageTitle";
import NewSkillModal from "@/components/skills/NewSkillModal";

const CATEGORY_COLORS: Record<string, string> = {
  code: "bg-blue-500/20 text-blue-400",
  config: "bg-purple-500/20 text-purple-400",
  procedure: "bg-green-500/20 text-green-400",
  template: "bg-yellow-500/20 text-yellow-400",
  reference: "bg-gray-500/20 text-gray-400",
};

export default function SkillDetailPage() {
  const { skillId } = useParams<{ skillId: string }>();
  const navigate = useNavigate();
  const { skill, loading, error, refetch } = useSkill(skillId);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  usePageTitle(skill?.name || "Skill");

  const handleEdit = () => {
    setShowEditModal(true);
  };

  const handleDelete = async () => {
    if (!skillId) return;

    setDeleting(true);
    setDeleteError("");

    try {
      await deleteSkill(skillId);
      navigate("/skills");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete skill";
      setDeleteError(msg);
    } finally {
      setDeleting(false);
    }
  };

  const handleSkillUpdated = () => {
    setShowEditModal(false);
    refetch();
  };

  if (loading) {
    return (
      <div className="p-4 md:p-6 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
      </div>
    );
  }

  if (error || !skill) {
    return (
      <div className="p-4 md:p-6">
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded text-red-400">
          {error || "Skill not found"}
        </div>
        <button
          onClick={() => navigate("/skills")}
          className="mt-4 text-accent hover:text-accent-hover flex items-center gap-2"
        >
          <ArrowLeft size={16} />
          Back to Skills
        </button>
      </div>
    );
  }

  const categoryColor = skill.category
    ? CATEGORY_COLORS[skill.category] || CATEGORY_COLORS.code
    : "bg-gray-500/20 text-gray-400";

  return (
    <>
      <motion.div
        className="p-4 md:p-6 space-y-4"
        initial="initial"
        animate="animate"
        exit="exit"
        variants={pageVariants}
      >
        {/* Back Button */}
        <button
          onClick={() => navigate("/skills")}
          className="text-accent hover:text-accent-hover flex items-center gap-2 text-sm"
        >
          <ArrowLeft size={16} />
          Back to Skills
        </button>

        {/* Header */}
        <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-6">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <FileCode size={24} className="text-accent flex-shrink-0" />
              <div className="min-w-0">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white truncate">
                  {skill.name}
                </h1>
                {skill.description && (
                  <p className="text-gray-400 mt-1">{skill.description}</p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                onClick={handleEdit}
                className="p-2 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
                title="Edit"
              >
                <Edit size={18} />
              </button>
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="p-2 rounded hover:bg-red-500/10 text-gray-400 hover:text-red-400 transition-colors"
                title="Delete"
              >
                <Trash2 size={18} />
              </button>
            </div>
          </div>

          {/* Metadata */}
          <div className="flex flex-wrap items-center gap-3">
            {skill.category && (
              <span className={`text-sm px-3 py-1 rounded-full ${categoryColor}`}>
                {skill.category}
              </span>
            )}
            {skill.language && (
              <span className="text-sm px-3 py-1 bg-gray-100 dark:bg-surface-lighter rounded text-gray-600 dark:text-gray-400">
                {skill.language}
              </span>
            )}
            {skill.is_template && (
              <span className="text-sm px-3 py-1 bg-yellow-500/10 text-yellow-400 rounded">
                Template
              </span>
            )}
            <span className="text-sm text-gray-500 flex items-center gap-1">
              <Calendar size={14} />
              Created {new Date(skill.created_at).toLocaleDateString()}
            </span>
          </div>

          {/* Tags */}
          {skill.tags && skill.tags.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-light-border dark:border-border">
              {skill.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-sm px-3 py-1 bg-gray-100 dark:bg-surface-lighter rounded text-gray-600 dark:text-gray-400 flex items-center gap-1"
                >
                  <TagIcon size={12} />
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Content */}
        <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
            <FileCode size={18} className="text-accent" />
            Content
          </h2>
          <div className="bg-gray-50 dark:bg-surface-lighter border border-light-border dark:border-border rounded p-4 overflow-x-auto">
            <pre className="text-sm text-gray-700 dark:text-gray-300 font-mono whitespace-pre-wrap break-words">
              {skill.content}
            </pre>
          </div>
          {skill.is_template && (
            <div className="mt-3 p-3 bg-yellow-500/5 border border-yellow-500/20 rounded text-sm text-yellow-400 flex items-start gap-2">
              <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
              <div>
                <strong>Template Skill:</strong> This skill supports Jinja2 variable
                substitution. Use the render endpoint to populate variables like{" "}
                <code className="bg-yellow-500/10 px-1 rounded">{"{{ variable }}"}</code>
              </div>
            </div>
          )}
        </div>

        {/* TODO: Show projects/tasks using this skill */}
        {/* This will be implemented in Phase 8 */}
      </motion.div>

      {/* Edit Modal */}
      <NewSkillModal
        open={showEditModal}
        onClose={() => setShowEditModal(false)}
        onCreated={handleSkillUpdated}
        editSkill={skill}
      />

      {/* Delete Confirmation */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white dark:bg-surface border border-light-border dark:border-border rounded-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Delete Skill</h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Are you sure you want to delete <strong>{skill.name}</strong>? This
              action cannot be undone.
            </p>

            {deleteError && (
              <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded text-red-400 text-sm">
                {deleteError}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setDeleteError("");
                }}
                disabled={deleting}
                className="px-4 py-2 bg-gray-100 dark:bg-surface-lighter hover:bg-gray-200 dark:hover:bg-surface-light text-gray-700 dark:text-gray-300 rounded disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded disabled:opacity-50"
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
