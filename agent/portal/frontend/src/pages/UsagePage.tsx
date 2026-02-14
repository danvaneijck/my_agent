import { useState, useEffect, useCallback } from "react";
import { BarChart3, RefreshCw } from "lucide-react";
import { api } from "@/api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UsageSummary {
  token_budget_monthly: number | null;
  tokens_used_this_month: number;
  budget_reset_at: string | null;
  all_time: TokenStats;
  this_month: TokenStats;
}

interface TokenStats {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  requests: number;
}

interface DailyUsage {
  date: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  requests: number;
}

interface ModelUsage {
  model: string;
  total_tokens: number;
  total_cost: number;
  requests: number;
}

interface UsageHistory {
  daily: DailyUsage[];
  by_model: ModelUsage[];
}

interface AnthropicUsageWindow {
  utilization_percent: number;
  reset_timestamp: number;
}

interface AnthropicUsageData {
  available: boolean;
  five_hour: AnthropicUsageWindow | null;
  seven_day: AnthropicUsageWindow | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function formatCost(n: number): string {
  return `$${n.toFixed(4)}`;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function utilizationColor(pct: number): string {
  if (pct > 90) return "bg-red-500";
  if (pct > 70) return "bg-yellow-500";
  return "bg-accent";
}

function budgetColor(pct: number): string {
  if (pct > 90) return "bg-red-500";
  if (pct > 70) return "bg-yellow-500";
  return "bg-green-500";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-sm font-semibold text-white mt-0.5">{value}</p>
    </div>
  );
}

function BudgetCard({ summary }: { summary: UsageSummary }) {
  const hasBudget = summary.token_budget_monthly !== null;
  const usagePct = hasBudget
    ? Math.min(
      100,
      (summary.tokens_used_this_month / summary.token_budget_monthly!) * 100
    )
    : 0;

  return (
    <div className="bg-surface-light border border-border rounded-xl p-6 space-y-4">
      <h3 className="text-sm font-semibold text-white uppercase tracking-wider">
        Monthly Budget
      </h3>

      <div>
        <div className="flex items-baseline justify-between mb-1.5">
          <span className="text-2xl font-bold text-white">
            {formatNumber(summary.tokens_used_this_month)}
          </span>
          <span className="text-sm text-gray-400">
            {hasBudget
              ? `/ ${formatNumber(summary.token_budget_monthly!)} tokens`
              : "Unlimited"}
          </span>
        </div>
        {hasBudget && (
          <div className="w-full bg-surface rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all ${budgetColor(usagePct)}`}
              style={{ width: `${usagePct}%` }}
            />
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2 border-t border-border">
        <Stat
          label="This Month Cost"
          value={formatCost(summary.this_month.cost)}
        />
        <Stat
          label="This Month Requests"
          value={summary.this_month.requests.toLocaleString()}
        />
        <Stat
          label="All-Time Tokens"
          value={formatNumber(summary.all_time.total_tokens)}
        />
        <Stat label="All-Time Cost" value={formatCost(summary.all_time.cost)} />
      </div>
    </div>
  );
}

function ModelBreakdown({ models }: { models: ModelUsage[] }) {
  if (models.length === 0) return null;

  const maxTokens = Math.max(...models.map((m) => m.total_tokens), 1);

  return (
    <div className="bg-surface-light border border-border rounded-xl p-6">
      <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-4">
        API Usage by Model (Last 30 Days)
      </h3>
      <div className="space-y-3">
        {models.map((m) => (
          <div key={m.model}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-gray-300 font-mono">{m.model}</span>
              <span className="text-gray-400">
                {formatNumber(m.total_tokens)} tokens &middot;{" "}
                {formatCost(m.total_cost)} &middot; {m.requests} req
              </span>
            </div>
            <div className="w-full bg-surface rounded-full h-1.5">
              <div
                className="h-1.5 rounded-full bg-accent"
                style={{
                  width: `${(m.total_tokens / maxTokens) * 100}%`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DailyHistory({ daily }: { daily: DailyUsage[] }) {
  if (daily.length === 0) {
    return (
      <div className="bg-surface-light border border-border rounded-xl p-6 text-center text-gray-500 text-sm">
        No usage data for the last 30 days.
      </div>
    );
  }

  const reversed = [...daily].reverse();

  return (
    <div className="bg-surface-light border border-border rounded-xl overflow-hidden">
      <div className="p-4 border-b border-border">
        <h3 className="text-sm font-semibold text-white uppercase tracking-wider">
          Daily History (Last 30 Days)
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-gray-500 text-xs uppercase tracking-wider">
              <th className="text-left px-4 py-2.5 font-medium">Date</th>
              <th className="text-right px-4 py-2.5 font-medium">Input</th>
              <th className="text-right px-4 py-2.5 font-medium">Output</th>
              <th className="text-right px-4 py-2.5 font-medium">Total</th>
              <th className="text-right px-4 py-2.5 font-medium">Cost</th>
              <th className="text-right px-4 py-2.5 font-medium">Requests</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {reversed.map((d) => (
              <tr
                key={d.date}
                className="hover:bg-surface-lighter/50 transition-colors"
              >
                <td className="px-4 py-2 text-gray-300">
                  {formatDate(d.date)}
                </td>
                <td className="px-4 py-2 text-right text-gray-400 font-mono text-xs">
                  {formatNumber(d.input_tokens)}
                </td>
                <td className="px-4 py-2 text-right text-gray-400 font-mono text-xs">
                  {formatNumber(d.output_tokens)}
                </td>
                <td className="px-4 py-2 text-right text-gray-200 font-mono text-xs">
                  {formatNumber(d.input_tokens + d.output_tokens)}
                </td>
                <td className="px-4 py-2 text-right text-gray-400 font-mono text-xs">
                  {formatCost(d.cost)}
                </td>
                <td className="px-4 py-2 text-right text-gray-400 font-mono text-xs">
                  {d.requests}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AnthropicUsageSection({ data }: { data: AnthropicUsageData }) {
  if (!data.available) {
    return (
      <div className="bg-surface-light border border-border rounded-xl p-6">
        <h3 className="text-sm font-semibold text-white uppercase tracking-wider mb-3">
          Claude Code Usage
        </h3>
        <p className="text-sm text-gray-500">
          Configure your Claude Code credentials in{" "}
          <a href="/settings" className="text-accent hover:underline">
            Settings
          </a>{" "}
          to view API usage limits.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-surface-light border border-border rounded-xl p-6 space-y-5">
      <h3 className="text-sm font-semibold text-white uppercase tracking-wider">
        Claude Code Usage
      </h3>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {data.five_hour && (
          <UsageBar
            label="5 Hour Usage"
            pct={data.five_hour.utilization_percent}
            resetTimestamp={data.five_hour.reset_timestamp}
          />
        )}
        {data.seven_day && (
          <UsageBar
            label="Weekly Usage"
            pct={data.seven_day.utilization_percent}
            resetTimestamp={data.seven_day.reset_timestamp}
          />
        )}
      </div>

      {!data.five_hour && !data.seven_day && (
        <p className="text-sm text-gray-500">
          Credentials configured but no usage data returned. The token may need
          the <code className="text-gray-400">user:profile</code> scope.
        </p>
      )}
    </div>
  );
}

function UsageBar({
  label,
  pct,
  resetTimestamp,
}: {
  label: string;
  pct: number;
  resetTimestamp: number;
}) {
  const resetDate = new Date(resetTimestamp);
  const now = new Date();
  const diffMs = resetDate.getTime() - now.getTime();
  const diffMins = Math.max(0, Math.round(diffMs / 60_000));
  const hours = Math.floor(diffMins / 60);
  const mins = diffMins % 60;
  const resetLabel =
    diffMs > 0
      ? `Resets in ${hours > 0 ? `${hours}h ` : ""}${mins}m`
      : "Reset time passed";

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-gray-300">{label}</span>
        <span className="text-lg font-bold text-white">{Math.round(pct)}%</span>
      </div>
      <div className="w-full bg-surface rounded-full h-3">
        <div
          className={`h-3 rounded-full transition-all ${utilizationColor(pct)}`}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
      <p className="text-xs text-gray-500">{resetLabel}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function UsagePage() {
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [history, setHistory] = useState<UsageHistory | null>(null);
  const [anthropic, setAnthropic] = useState<AnthropicUsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    const [summaryResult, historyResult, anthropicResult] =
      await Promise.allSettled([
        api<UsageSummary>("/api/usage/summary"),
        api<UsageHistory>("/api/usage/history"),
        api<AnthropicUsageData>("/api/usage/anthropic"),
      ]);

    if (summaryResult.status === "fulfilled") {
      setSummary(summaryResult.value);
    } else {
      setError("Failed to load usage summary.");
    }

    if (historyResult.status === "fulfilled") {
      setHistory(historyResult.value);
    }

    if (anthropicResult.status === "fulfilled") {
      setAnthropic(anthropicResult.value);
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="p-4 md:p-6 space-y-4 max-w-5xl mx-auto">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <BarChart3 size={20} className="text-accent" />
          Usage
        </h2>
        <button
          onClick={() => fetchData()}
          className="p-1.5 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200 transition-colors"
          title="Refresh"
        >
          <RefreshCw size={16} />
        </button>
        {loading && (
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        )}
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading && !summary ? (
        <div className="flex items-center justify-center py-12">
          <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          {summary && <BudgetCard summary={summary} />}
          {anthropic && <AnthropicUsageSection data={anthropic} />}
          {history && <ModelBreakdown models={history.by_model} />}
          {history && <DailyHistory daily={history.daily} />}
        </>
      )}
    </div>
  );
}
