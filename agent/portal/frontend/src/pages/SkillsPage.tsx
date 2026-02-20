import { useState } from "react";
import { motion } from "framer-motion";
import { pageVariants, listContainerVariants, listItemVariants } from "@/utils/animations";
import { useNavigate } from "react-router-dom";
import { Lightbulb, RefreshCw, Plus, Search, Filter } from "lucide-react";
import { useSkills } from "@/hooks/useSkills";
import { usePageTitle } from "@/hooks/usePageTitle";
import SkillCard from "@/components/skills/SkillCard";
import NewSkillModal from "@/components/skills/NewSkillModal";
import EmptyState from "@/components/common/EmptyState";

const CATEGORIES = ["code", "config", "procedure", "template", "reference"];

export default function SkillsPage() {
  usePageTitle("Skills");
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [showNewSkill, setShowNewSkill] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const { skills, loading, error, refetch } = useSkills(
    categoryFilter || undefined,
    tagFilter || undefined,
    searchQuery || undefined
  );
  const navigate = useNavigate();

  const handleSkillCreated = (skillId: string) => {
    refetch();
    navigate(`/skills/${skillId}`);
  };

  const clearFilters = () => {
    setSearchQuery("");
    setCategoryFilter("");
    setTagFilter("");
  };

  const hasActiveFilters = searchQuery || categoryFilter || tagFilter;

  return (
    <>
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
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Lightbulb size={20} className="text-accent" />
              Skills
            </h2>
            <button
              onClick={refetch}
              className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
              title="Refresh"
            >
              <RefreshCw size={16} />
            </button>
          </div>

          <button
            onClick={() => setShowNewSkill(true)}
            className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded transition-colors"
          >
            <Plus size={16} />
            New Skill
          </button>
        </div>

        {/* Search and Filters */}
        <div className="space-y-3">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search skills by name or description..."
                className="w-full pl-10 pr-3 py-2 bg-white dark:bg-surface-lighter border border-light-border dark:border-border rounded text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`px-4 py-2 rounded border transition-colors flex items-center gap-2 ${
                showFilters || hasActiveFilters
                  ? "bg-accent/10 border-accent text-accent"
                  : "bg-gray-100 dark:bg-surface-lighter border-light-border dark:border-border text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
              }`}
            >
              <Filter size={16} />
              Filters
            </button>
          </div>

          {/* Filter Panel */}
          {showFilters && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="bg-gray-50 dark:bg-surface-lighter border border-light-border dark:border-border rounded p-4 space-y-3"
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Category
                  </label>
                  <select
                    value={categoryFilter}
                    onChange={(e) => setCategoryFilter(e.target.value)}
                    className="w-full px-3 py-2 bg-white dark:bg-surface border border-light-border dark:border-border rounded text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-accent"
                  >
                    <option value="">All categories</option>
                    {CATEGORIES.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Tag
                  </label>
                  <input
                    type="text"
                    value={tagFilter}
                    onChange={(e) => setTagFilter(e.target.value)}
                    placeholder="Filter by tag..."
                    className="w-full px-3 py-2 bg-white dark:bg-surface border border-light-border dark:border-border rounded text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent"
                  />
                </div>
              </div>

              {hasActiveFilters && (
                <div className="flex justify-end">
                  <button
                    onClick={clearFilters}
                    className="text-sm text-gray-400 hover:text-white"
                  >
                    Clear filters
                  </button>
                </div>
              )}
            </motion.div>
          )}
        </div>

        {/* Error State */}
        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/20 rounded text-red-400">
            {error}
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent"></div>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && skills.length === 0 && (
          <EmptyState
            icon={Lightbulb}
            title={hasActiveFilters ? "No skills found" : "No skills yet"}
            description={
              hasActiveFilters
                ? "Try adjusting your filters"
                : "Create your first skill to get started"
            }
            action={
              !hasActiveFilters
                ? {
                    label: "New Skill",
                    onClick: () => setShowNewSkill(true),
                  }
                : undefined
            }
          />
        )}

        {/* Skills Grid */}
        {!loading && !error && skills.length > 0 && (
          <motion.div
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
            variants={listContainerVariants}
            initial="hidden"
            animate="visible"
          >
            {skills.map((skill) => (
              <motion.div key={skill.skill_id} variants={listItemVariants}>
                <SkillCard
                  skill={skill}
                  onClick={() => navigate(`/skills/${skill.skill_id}`)}
                />
              </motion.div>
            ))}
          </motion.div>
        )}

        {/* Skills Count */}
        {!loading && !error && skills.length > 0 && (
          <div className="text-sm text-gray-400 text-center">
            {skills.length} skill{skills.length !== 1 ? "s" : ""}
            {hasActiveFilters && " (filtered)"}
          </div>
        )}
      </motion.div>

      {/* New Skill Modal */}
      <NewSkillModal
        open={showNewSkill}
        onClose={() => setShowNewSkill(false)}
        onCreated={handleSkillCreated}
      />
    </>
  );
}
