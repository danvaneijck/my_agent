import { useState } from "react";
import { motion } from "framer-motion";
import { pageVariants, listContainerVariants, listItemVariants } from "@/utils/animations";
import { useNavigate } from "react-router-dom";
import { Users, RefreshCw, Plus } from "lucide-react";
import { useCrews } from "@/hooks/useCrews";
import { usePageTitle } from "@/hooks/usePageTitle";
import CrewCard from "@/components/crews/CrewCard";
import NewCrewModal from "@/components/crews/NewCrewModal";
import EmptyState from "@/components/common/EmptyState";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "configuring", label: "Configuring" },
  { value: "running", label: "Running" },
  { value: "paused", label: "Paused" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
];

export default function CrewsPage() {
  usePageTitle("Crews");
  const [statusFilter, setStatusFilter] = useState("");
  const [showNewCrew, setShowNewCrew] = useState(false);
  const { crews, loading, error, refetch } = useCrews(statusFilter || undefined);
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Users size={20} className="text-accent" />
            Agent Crews
          </h2>
          <button
            onClick={refetch}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-lg px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 focus:outline-none focus:border-accent"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            onClick={() => setShowNewCrew(true)}
            className="bg-accent hover:bg-accent-hover text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5"
          >
            <Plus size={16} />
            New Crew
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Content */}
      {loading && crews.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 animate-pulse"
            >
              <div className="h-5 bg-gray-200 dark:bg-surface-lighter/60 rounded w-2/3 mb-3" />
              <div className="h-4 bg-gray-200 dark:bg-surface-lighter/60 rounded w-1/2 mb-3" />
              <div className="h-1.5 bg-gray-200 dark:bg-surface-lighter/60 rounded-full" />
            </div>
          ))}
        </div>
      ) : crews.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No crew sessions yet"
          description="Create your first crew to coordinate multiple AI agents working together on a project."
          action={{
            label: "Create Crew",
            onClick: () => setShowNewCrew(true),
          }}
        />
      ) : (
        <motion.div
          className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3"
          initial="initial"
          animate="animate"
          variants={listContainerVariants}
        >
          {crews.map((crew) => (
            <motion.div key={crew.session_id} variants={listItemVariants} layout>
              <CrewCard
                crew={crew}
                onClick={() => navigate(`/crews/${crew.session_id}`)}
              />
            </motion.div>
          ))}
        </motion.div>
      )}

      <NewCrewModal
        open={showNewCrew}
        onClose={() => setShowNewCrew(false)}
        onCreated={(sessionId) => {
          setShowNewCrew(false);
          refetch();
          navigate(`/crews/${sessionId}`);
        }}
      />
    </motion.div>
  );
}
