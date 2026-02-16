import { useState, useEffect } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import { getToken, setToken, setUser, clearAuth, api } from "@/api/client";
import Layout from "@/components/layout/Layout";
import TasksPage from "@/pages/TasksPage";
import ChatPage from "@/pages/ChatPage";
import FilesPage from "@/pages/FilesPage";
import CodePage from "@/pages/CodePage";
import SchedulePage from "@/pages/SchedulePage";
import DeploymentsPage from "@/pages/DeploymentsPage";
import TaskDetailPage from "@/pages/TaskDetailPage";
import ReposPage from "@/pages/ReposPage";
import RepoDetailPage from "@/pages/RepoDetailPage";
import PullRequestsPage from "@/pages/PullRequestsPage";
import PullRequestDetailPage from "@/pages/PullRequestDetailPage";
import SettingsPage from "@/pages/SettingsPage";
import UsagePage from "@/pages/UsagePage";
import ProjectsPage from "@/pages/ProjectsPage";
import ProjectDetailPage from "@/pages/ProjectDetailPage";
import PhaseDetailPage from "@/pages/PhaseDetailPage";
import ProjectTaskDetailPage from "@/pages/ProjectTaskDetailPage";
import HomePage from "@/pages/HomePage";

interface AuthProvider {
  name: string;
  label: string;
}

function LoginScreen() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [providers, setProviders] = useState<AuthProvider[]>([]);
  const [discovering, setDiscovering] = useState(true);

  useEffect(() => {
    fetch("/api/auth/providers")
      .then((r) => r.json())
      .then((data) => setProviders(data.providers || []))
      .catch(() => {})
      .finally(() => setDiscovering(false));
  }, []);

  const handleLogin = async (provider: string) => {
    setLoading(true);
    setError("");
    try {
      const resp = await fetch(`/api/auth/${provider}/url`);
      if (!resp.ok) throw new Error("Failed to get login URL");
      const data = await resp.json();
      window.location.href = data.url;
    } catch {
      setError("Failed to initiate login");
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex items-center justify-center p-4 bg-gradient-to-br from-gray-50 via-white to-gray-100 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
      <motion.div
        className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-2xl shadow-xl dark:shadow-2xl p-8 w-full max-w-md space-y-6"
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.0, 0.0, 0.2, 1] }}
      >
        {/* Logo and Branding */}
        <motion.div
          className="text-center space-y-3"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <div className="flex justify-center mb-4">
            <img
              src="/logo-icon.svg"
              alt="Nexus"
              className="h-16 w-16"
            />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Nexus</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Your AI orchestration platform
          </p>
        </motion.div>

        {error && (
          <motion.div
            className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-lg p-3"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <p className="text-sm text-red-600 dark:text-red-400 text-center">{error}</p>
          </motion.div>
        )}

        {discovering ? (
          <div className="flex justify-center py-8">
            <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
        ) : providers.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
            No authentication providers configured.
          </p>
        ) : (
          <motion.div
            className="space-y-3"
            initial="initial"
            animate="animate"
            variants={{
              initial: {},
              animate: {
                transition: {
                  staggerChildren: 0.1,
                  delayChildren: 0.2,
                },
              },
            }}
          >
            {providers.map((p) => (
              <motion.button
                key={p.name}
                onClick={() => handleLogin(p.name)}
                disabled={loading}
                variants={{
                  initial: { opacity: 0, y: 10 },
                  animate: { opacity: 1, y: 0 },
                }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={`w-full py-3 rounded-lg font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-sm hover:shadow-md ${
                  p.name === "discord"
                    ? "bg-[#5865F2] hover:bg-[#4752C4] text-white"
                    : p.name === "google"
                    ? "bg-white text-gray-800 hover:bg-gray-50 border border-gray-300"
                    : "bg-accent hover:bg-accent-hover text-white"
                }`}
              >
                {p.name === "discord" && (
                  <svg width="20" height="15" viewBox="0 0 71 55" fill="currentColor">
                    <path d="M60.1 4.9A58.5 58.5 0 0045.4.2a.2.2 0 00-.2.1 40.8 40.8 0 00-1.8 3.7 54 54 0 00-16.2 0A37.4 37.4 0 0025.4.3a.2.2 0 00-.2-.1A58.4 58.4 0 0010.5 5a.2.2 0 00-.1 0A60 60 0 00.3 45.3a.3.3 0 000 .2 58.7 58.7 0 0017.7 9 .2.2 0 00.3-.1 42 42 0 003.6-5.9.2.2 0 00-.1-.3 38.7 38.7 0 01-5.5-2.6.2.2 0 01 0-.4l1.1-.9a.2.2 0 01.2 0 41.9 41.9 0 0035.6 0 .2.2 0 01.2 0l1.1.9a.2.2 0 010 .3 36.3 36.3 0 01-5.5 2.7.2.2 0 00-.1.3 47.2 47.2 0 003.6 5.9.2.2 0 00.3 0A58.5 58.5 0 0070.3 45.5a.2.2 0 000-.2A59.7 59.7 0 0060.1 5a.2.2 0 000 0zM23.7 37.3c-3.5 0-6.4-3.2-6.4-7.1s2.8-7.1 6.4-7.1 6.5 3.2 6.4 7.1c0 3.9-2.8 7.1-6.4 7.1zm23.6 0c-3.5 0-6.4-3.2-6.4-7.1s2.8-7.1 6.4-7.1 6.5 3.2 6.4 7.1c0 3.9-2.8 7.1-6.4 7.1z" />
                  </svg>
                )}
                {p.name === "google" && (
                  <svg width="18" height="18" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                  </svg>
                )}
                {loading ? "Redirecting..." : `Sign in with ${p.label}`}
              </motion.button>
            ))}
          </motion.div>
        )}

        {/* Footer */}
        <motion.p
          className="text-xs text-center text-gray-500 dark:text-gray-400 pt-4 border-t border-light-border dark:border-border"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          Secure authentication powered by OAuth 2.0
        </motion.p>
      </motion.div>
    </div>
  );
}

function AuthCallback() {
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    if (!code) {
      setError("No authorization code received");
      return;
    }

    // Detect provider from URL path: /auth/callback/discord or /auth/callback/google
    // Fall back to "discord" for legacy /auth/callback URLs
    const pathParts = window.location.pathname.split("/");
    const lastPart = pathParts[pathParts.length - 1];
    const provider = ["discord", "google"].includes(lastPart)
      ? lastPart
      : "discord";

    fetch(`/api/auth/${provider}/callback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    })
      .then(async (resp) => {
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({ detail: "Login failed" }));
          throw new Error(data.detail || "Login failed");
        }
        return resp.json();
      })
      .then((data) => {
        setToken(data.token);
        setUser({
          user_id: data.user_id,
          username: data.username,
          permission_level: data.permission_level,
        });
        window.location.href = "/";
      })
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return (
      <div className="h-full flex items-center justify-center p-4">
        <div className="bg-surface-light border border-border rounded-xl p-8 w-full max-w-sm space-y-4 text-center">
          <h2 className="text-lg font-bold text-red-400">Login Failed</h2>
          <p className="text-sm text-gray-400">{error}</p>
          <a href="/" className="text-accent hover:underline text-sm">
            Try again
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex items-center justify-center">
      <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const location = useLocation();

  useEffect(() => {
    // Let the callback routes handle themselves
    if (window.location.pathname.startsWith("/auth/callback")) {
      setAuthenticated(false);
      return;
    }

    const token = getToken();
    if (!token) {
      setAuthenticated(false);
      return;
    }
    // Verify token is still valid
    api("/api/auth/me")
      .then(() => setAuthenticated(true))
      .catch(() => {
        clearAuth();
        setAuthenticated(false);
      });
  }, []);

  // Show callback route regardless of auth state
  if (window.location.pathname.startsWith("/auth/callback")) {
    return (
      <Routes>
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/auth/callback/:provider" element={<AuthCallback />} />
      </Routes>
    );
  }

  if (authenticated === null) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!authenticated) {
    return <LoginScreen />;
  }

  return (
    <Layout>
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<HomePage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chat/:conversationId" element={<ChatPage />} />
          <Route path="/files" element={<FilesPage />} />
          <Route path="/repos" element={<ReposPage />} />
          <Route path="/repos/:owner/:repo" element={<RepoDetailPage />} />
          <Route path="/pulls" element={<PullRequestsPage />} />
          <Route path="/pulls/:owner/:repo/:number" element={<PullRequestDetailPage />} />
          <Route path="/code" element={<CodePage />} />
          <Route path="/schedule" element={<SchedulePage />} />
          <Route path="/deployments" element={<DeploymentsPage />} />
          <Route path="/usage" element={<UsagePage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/projects/:projectId/phases/:phaseId" element={<PhaseDetailPage />} />
          <Route path="/projects/:projectId/tasks/:taskId" element={<ProjectTaskDetailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </AnimatePresence>
    </Layout>
  );
}
