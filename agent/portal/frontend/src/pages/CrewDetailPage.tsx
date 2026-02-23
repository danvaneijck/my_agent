import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { pageVariants } from "@/utils/animations";
import {
  ArrowLeft,
  RefreshCw,
  Play,
  Pause,
  XCircle,
  RotateCcw,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useCrewSession } from "@/hooks/useCrewSession";
import { useCrewEvents } from "@/hooks/useCrewEvents";
import {
  startCrewSession,
  pauseCrewSession,
  resumeCrewSession,
  cancelCrewSession,
  postCrewContext,
} from "@/hooks/useCrews";
import { usePageTitle } from "@/hooks/usePageTitle";
import AgentTimeline from "@/components/crews/AgentTimeline";
import ContextBoard from "@/components/crews/ContextBoard";
import MemberPanel from "@/components/crews/MemberPanel";
import DependencyGraph from "@/components/crews/DependencyGraph";
import WaveProgress from "@/components/crews/WaveProgress";
import type { CrewMember, CrewEvent } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  configuring: "bg-blue-500/20 text-blue-400",
  running: "bg-green-500/20 text-green-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-gray-500/20 text-gray-400",
  failed: "bg-red-500/20 text-red-400",
};

type TabId = "context" | "graph" | "events";

export default function CrewDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { session, loading, error, refetch } = useCrewSession(sessionId);
  const { events, connected } = useCrewEvents(sessionId);
  const [selectedMember, setSelectedMember] = useState<CrewMember | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("context");
  const [actionLoading, setActionLoading] = useState(false);

  usePageTitle(session ? `Crew: ${session.name}` : "Crew");

  const handleAction = async (action: () => Promise<void>) => {
    setActionLoading(true);
    try {
      await action();
      refetch();
    } catch {
      // Errors handled via refetch
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-4 md:p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 dark:bg-surface-lighter/60 rounded w-1/3" />
          <div className="h-64 bg-gray-200 dark:bg-surface-lighter/60 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="p-4 md:p-6">
        <button
          onClick={() => navigate("/crews")}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 mb-4"
        >
          <ArrowLeft size={16} />
          Back to Crews
        </button>
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
          {error || "Crew session not found"}
        </div>
      </div>
    );
  }

  const summary = session.summary;
  const tabs: { id: TabId; label: string }[] = [
    { id: "context", label: "Context Board" },
    { id: "graph", label: "Dependencies" },
    { id: "events", label: `Events (${events.length})` },
  ];

  return (
    <motion.div
      className="p-4 md:p-6 space-y-4"
      initial="initial"
      animate="animate"
      exit="exit"
      variants={pageVariants}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <button
            onClick={() => navigate("/crews")}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 mb-2"
          >
            <ArrowLeft size={16} />
            Crews
          </button>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              {session.name}
            </h2>
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[session.status] || STATUS_COLORS.configuring}`}
            >
              {session.status}
            </span>
            {connected ? (
              <Wifi size={14} className="text-green-400" />
            ) : (
              <WifiOff size={14} className="text-gray-400" />
            )}
            <button
              onClick={refetch}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-500"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {session.status === "configuring" && (
            <button
              onClick={() => handleAction(() => startCrewSession(session.session_id))}
              disabled={actionLoading}
              className="px-3 py-1.5 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 transition-colors disabled:opacity-50 flex items-center gap-1.5"
            >
              <Play size={14} />
              Start
            </button>
          )}
          {session.status === "running" && (
            <button
              onClick={() => handleAction(() => pauseCrewSession(session.session_id))}
              disabled={actionLoading}
              className="px-3 py-1.5 rounded-lg text-sm font-medium bg-yellow-600 text-white hover:bg-yellow-700 transition-colors disabled:opacity-50 flex items-center gap-1.5"
            >
              <Pause size={14} />
              Pause
            </button>
          )}
          {session.status === "paused" && (
            <button
              onClick={() => handleAction(() => resumeCrewSession(session.session_id))}
              disabled={actionLoading}
              className="px-3 py-1.5 rounded-lg text-sm font-medium bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50 flex items-center gap-1.5"
            >
              <RotateCcw size={14} />
              Resume
            </button>
          )}
          {["running", "paused", "configuring"].includes(session.status) && (
            <button
              onClick={() => handleAction(() => cancelCrewSession(session.session_id))}
              disabled={actionLoading}
              className="px-3 py-1.5 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center gap-1.5"
            >
              <XCircle size={14} />
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Summary bar */}
      <div className="flex flex-wrap items-center gap-4 bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl px-4 py-3">
        <WaveProgress
          currentWave={session.current_wave}
          totalWaves={session.total_waves}
        />
        <div className="h-6 w-px bg-gray-200 dark:bg-surface-lighter" />
        {summary && (
          <>
            <div className="text-sm">
              <span className="text-gray-500 dark:text-gray-400">Tasks: </span>
              <span className="text-gray-900 dark:text-white font-medium">
                {summary.completed_tasks}/{summary.total_tasks}
              </span>
            </div>
            <div className="text-sm">
              <span className="text-gray-500 dark:text-gray-400">Active: </span>
              <span className="text-blue-400 font-medium">
                {summary.active_agents}
              </span>
            </div>
            {summary.failed_tasks > 0 && (
              <div className="text-sm">
                <span className="text-gray-500 dark:text-gray-400">Failed: </span>
                <span className="text-red-400 font-medium">
                  {summary.failed_tasks}
                </span>
              </div>
            )}
          </>
        )}
        <div className="text-sm">
          <span className="text-gray-500 dark:text-gray-400">Agents: </span>
          <span className="text-gray-900 dark:text-white font-medium">
            {session.members.length}/{session.max_agents}
          </span>
        </div>
      </div>

      {/* Main content — 2 column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Left: Agent Timeline (60%) */}
        <div className="lg:col-span-3 space-y-3">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Agent Timeline
          </h3>
          <AgentTimeline
            members={session.members}
            currentWave={session.current_wave}
            onMemberClick={(m) => setSelectedMember(m)}
          />

          {/* Selected member panel */}
          {selectedMember && (
            <MemberPanel
              member={selectedMember}
              onClose={() => setSelectedMember(null)}
            />
          )}
        </div>

        {/* Right: Tabbed panel (40%) */}
        <div className="lg:col-span-2">
          {/* Tabs */}
          <div className="flex border-b border-light-border dark:border-border mb-3">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? "border-accent text-accent"
                    : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 min-h-[300px] max-h-[600px] overflow-y-auto">
            {activeTab === "context" && (
              <ContextBoard
                entries={session.context_entries}
                onPost={async (entry) => {
                  await postCrewContext(session.session_id, entry);
                  refetch();
                }}
              />
            )}
            {activeTab === "graph" && (
              <DependencyGraph
                members={session.members}
                totalWaves={session.total_waves}
                currentWave={session.current_wave}
              />
            )}
            {activeTab === "events" && (
              <EventsFeed events={events} />
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function EventsFeed({ events }: { events: CrewEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
        No events received yet. Events stream in real-time when the crew is running.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {[...events].reverse().map((event, i) => {
        const time = new Date(event.timestamp).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });

        return (
          <div
            key={i}
            className="flex gap-2 text-xs border-b border-light-border dark:border-border pb-2 last:border-0"
          >
            <span className="text-gray-500 dark:text-gray-400 shrink-0 font-mono">
              {time}
            </span>
            <div className="min-w-0">
              <span className="font-medium text-gray-900 dark:text-white">
                {event.event.replace(/_/g, " ")}
              </span>
              {event.task_title && (
                <span className="text-gray-500 dark:text-gray-400">
                  {" "}&mdash; {event.task_title}
                </span>
              )}
              {event.role && (
                <span className="text-gray-500 dark:text-gray-400 capitalize">
                  {" "}({event.role})
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
