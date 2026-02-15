import { useNavigate } from "react-router-dom";
import {
  Sparkles,
  Code,
  MessageSquare,
  FolderKanban,
  GitPullRequest,
  Rocket,
  FileText,
  Zap,
  Shield,
  Globe,
  ArrowRight,
  Check,
} from "lucide-react";
import { Logo } from "@/components/brand/Logo";

interface AuthProvider {
  name: string;
  label: string;
}

interface LandingPageProps {
  providers: AuthProvider[];
  onLogin: (provider: string) => void;
  loading: boolean;
}

export default function LandingPage({ providers, onLogin, loading }: LandingPageProps) {
  const features = [
    {
      icon: Code,
      title: "Code Execution",
      description: "Run Python, shell commands, and automated coding tasks in a sandboxed environment",
      color: "text-accent",
      bgColor: "bg-accent/10",
    },
    {
      icon: MessageSquare,
      title: "Natural Language",
      description: "Interact with your AI agent using natural language across multiple platforms",
      color: "text-secondary",
      bgColor: "bg-secondary/10",
    },
    {
      icon: FolderKanban,
      title: "Project Planning",
      description: "Plan and execute multi-phase projects with autonomous task execution",
      color: "text-accent",
      bgColor: "bg-accent/10",
    },
    {
      icon: GitPullRequest,
      title: "Git Integration",
      description: "Seamless GitHub and Bitbucket integration for repos, PRs, and CI/CD",
      color: "text-secondary",
      bgColor: "bg-secondary/10",
    },
    {
      icon: Rocket,
      title: "One-Click Deploy",
      description: "Deploy and host your projects with a single command",
      color: "text-accent",
      bgColor: "bg-accent/10",
    },
    {
      icon: FileText,
      title: "Document Processing",
      description: "Store, retrieve, and intelligently process documents and files",
      color: "text-secondary",
      bgColor: "bg-secondary/10",
    },
  ];

  const modules = [
    "Research & Web Search",
    "Knowledge Management",
    "Atlassian Integration",
    "Health & Fitness Tracking",
    "Location Services",
    "Blockchain Trading",
    "Custom Module Support",
  ];

  const benefits = [
    "Multiple LLM providers (Anthropic, OpenAI, Google)",
    "Automatic fallback chains for reliability",
    "Per-user permissions and token budgets",
    "Real-time notifications via WebSocket",
    "Modular architecture for easy extension",
    "Multi-platform support (Discord, Telegram, Slack)",
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface via-surface-light to-surface">
      {/* Hero Section */}
      <div className="max-w-7xl mx-auto px-4 py-16 md:py-24">
        <div className="text-center mb-16">
          <div className="flex justify-center mb-8">
            <Logo size="xl" variant="full" />
          </div>
          <h1 className="text-4xl md:text-6xl font-bold text-white mb-6">
            Your Modular AI Agent Framework
          </h1>
          <p className="text-xl text-gray-400 mb-8 max-w-3xl mx-auto">
            Build, deploy, and manage powerful AI agents with a modular architecture.
            Connect multiple LLM providers, integrate with your tools, and automate your workflows.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            {providers.length > 0 && (
              <>
                {providers.map((p) => (
                  <button
                    key={p.name}
                    onClick={() => onLogin(p.name)}
                    disabled={loading}
                    className={`px-8 py-4 rounded-lg font-semibold text-lg transition-all disabled:opacity-50 flex items-center gap-3 shadow-lg hover:shadow-xl ${
                      p.name === "discord"
                        ? "bg-[#5865F2] hover:bg-[#4752C4] text-white"
                        : p.name === "google"
                        ? "bg-white text-gray-800 hover:bg-gray-100 border-2 border-gray-300"
                        : "bg-accent hover:bg-accent-hover text-white"
                    }`}
                  >
                    <Sparkles size={20} />
                    {loading ? "Redirecting..." : `Get Started with ${p.label}`}
                  </button>
                ))}
              </>
            )}
          </div>
        </div>

        {/* Features Grid */}
        <div className="mb-16">
          <h2 className="text-3xl font-bold text-white text-center mb-12">
            Powerful Features
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="bg-surface-light border border-border rounded-xl p-6 hover:border-accent/50 transition-all shadow-lg hover:shadow-xl"
              >
                <div className={`w-12 h-12 ${feature.bgColor} rounded-lg flex items-center justify-center mb-4`}>
                  <feature.icon className={feature.color} size={24} />
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">{feature.title}</h3>
                <p className="text-gray-400 text-sm">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Modules Section */}
        <div className="mb-16 bg-surface-light border border-border rounded-2xl p-8 md:p-12">
          <div className="grid md:grid-cols-2 gap-8 items-center">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Zap className="text-secondary" size={32} />
                <h2 className="text-3xl font-bold text-white">Extensible Modules</h2>
              </div>
              <p className="text-gray-400 mb-6">
                ModuFlow comes with a rich ecosystem of pre-built modules and supports
                custom module development for your specific needs.
              </p>
              <div className="space-y-3">
                {modules.map((module) => (
                  <div key={module} className="flex items-center gap-3">
                    <div className="w-5 h-5 rounded-full bg-accent/20 flex items-center justify-center">
                      <Check className="text-accent" size={14} />
                    </div>
                    <span className="text-gray-300">{module}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-surface border border-border rounded-xl p-6">
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-3 bg-accent/10 border border-accent/30 rounded-lg">
                  <Shield className="text-accent" size={20} />
                  <span className="text-white font-medium">Enterprise-grade Security</span>
                </div>
                <div className="flex items-center gap-3 p-3 bg-secondary/10 border border-secondary/30 rounded-lg">
                  <Globe className="text-secondary" size={20} />
                  <span className="text-white font-medium">Multi-platform Support</span>
                </div>
                <div className="flex items-center gap-3 p-3 bg-accent/10 border border-accent/30 rounded-lg">
                  <Code className="text-accent" size={20} />
                  <span className="text-white font-medium">Open Architecture</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Benefits Section */}
        <div className="mb-16">
          <h2 className="text-3xl font-bold text-white text-center mb-12">
            Why ModuFlow?
          </h2>
          <div className="bg-gradient-to-r from-accent/10 to-secondary/10 border border-accent/20 rounded-2xl p-8 md:p-12">
            <div className="grid md:grid-cols-2 gap-4">
              {benefits.map((benefit) => (
                <div key={benefit} className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-accent flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Check className="text-white" size={14} />
                  </div>
                  <span className="text-gray-200">{benefit}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* CTA Section */}
        <div className="text-center bg-surface-light border border-border rounded-2xl p-8 md:p-12 shadow-2xl">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to Get Started?
          </h2>
          <p className="text-gray-400 mb-8 max-w-2xl mx-auto">
            Join the modular AI revolution. Sign in now to access your personalized
            AI agent framework.
          </p>
          {providers.length > 0 && (
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              {providers.map((p) => (
                <button
                  key={p.name}
                  onClick={() => onLogin(p.name)}
                  disabled={loading}
                  className={`px-8 py-4 rounded-lg font-semibold transition-all disabled:opacity-50 flex items-center justify-center gap-2 shadow-lg hover:shadow-xl ${
                    p.name === "discord"
                      ? "bg-[#5865F2] hover:bg-[#4752C4] text-white"
                      : p.name === "google"
                      ? "bg-white text-gray-800 hover:bg-gray-100 border-2 border-gray-300"
                      : "bg-accent hover:bg-accent-hover text-white"
                  }`}
                >
                  {loading ? "Redirecting..." : `Sign in with ${p.label}`}
                  <ArrowRight size={20} />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-border">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-2">
              <Logo size="sm" variant="icon" />
              <span className="text-gray-400 text-sm">© 2026 ModuFlow. All rights reserved.</span>
            </div>
            <div className="text-gray-500 text-xs">
              Built with FastAPI, React, and Claude
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
