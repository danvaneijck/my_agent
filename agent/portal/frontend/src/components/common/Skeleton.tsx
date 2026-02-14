interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = "" }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded bg-surface-lighter/60 ${className}`}
    />
  );
}

// ---------------------------------------------------------------------------
// Pre-composed skeletons for specific pages
// ---------------------------------------------------------------------------

export function RepoCardSkeleton() {
  return (
    <div className="bg-surface-light border border-border rounded-xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-4 w-8" />
      </div>
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-3/4" />
      <div className="flex items-center gap-3 pt-1">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-14" />
        <Skeleton className="h-3 w-20" />
      </div>
    </div>
  );
}

export function ReposGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
      {Array.from({ length: count }).map((_, i) => (
        <RepoCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function PullRequestRowSkeleton() {
  return (
    <div className="w-full flex items-center justify-between px-4 py-3">
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-4 rounded-full" />
          <Skeleton className="h-4 w-64" />
          <Skeleton className="h-4 w-8" />
        </div>
        <div className="flex items-center gap-2 ml-6">
          <Skeleton className="h-4 w-28 rounded" />
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-3 w-4" />
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-3 w-16" />
        </div>
      </div>
    </div>
  );
}

export function PullRequestsListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="bg-surface-light border border-border rounded-xl overflow-hidden divide-y divide-border/50">
      {Array.from({ length: count }).map((_, i) => (
        <PullRequestRowSkeleton key={i} />
      ))}
    </div>
  );
}

export function UsageBudgetSkeleton() {
  return (
    <div className="bg-surface-light border border-border rounded-xl p-6 space-y-4">
      <Skeleton className="h-4 w-32" />
      <div>
        <div className="flex items-baseline justify-between mb-1.5">
          <Skeleton className="h-7 w-24" />
          <Skeleton className="h-4 w-36" />
        </div>
        <Skeleton className="h-2 w-full rounded-full" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2 border-t border-border">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-1">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-4 w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function UsageModelSkeleton() {
  return (
    <div className="bg-surface-light border border-border rounded-xl p-6 space-y-4">
      <Skeleton className="h-4 w-56" />
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="space-y-1">
            <div className="flex items-center justify-between">
              <Skeleton className="h-3 w-40" />
              <Skeleton className="h-3 w-48" />
            </div>
            <Skeleton className="h-1.5 w-full rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function UsageDailyTableSkeleton() {
  return (
    <div className="bg-surface-light border border-border rounded-xl overflow-hidden">
      <div className="p-4 border-b border-border">
        <Skeleton className="h-4 w-48" />
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
            {Array.from({ length: 7 }).map((_, i) => (
              <tr key={i}>
                <td className="px-4 py-2">
                  <Skeleton className="h-3 w-16" />
                </td>
                <td className="px-4 py-2 text-right">
                  <Skeleton className="h-3 w-12 ml-auto" />
                </td>
                <td className="px-4 py-2 text-right">
                  <Skeleton className="h-3 w-12 ml-auto" />
                </td>
                <td className="px-4 py-2 text-right">
                  <Skeleton className="h-3 w-14 ml-auto" />
                </td>
                <td className="px-4 py-2 text-right">
                  <Skeleton className="h-3 w-14 ml-auto" />
                </td>
                <td className="px-4 py-2 text-right">
                  <Skeleton className="h-3 w-8 ml-auto" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function UsageAnthropicSkeleton() {
  return (
    <div className="bg-surface-light border border-border rounded-xl p-6 space-y-5">
      <Skeleton className="h-4 w-36" />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <div className="flex items-baseline justify-between">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-5 w-10" />
            </div>
            <Skeleton className="h-3 w-full rounded-full" />
            <Skeleton className="h-3 w-28" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function UsagePageSkeleton() {
  return (
    <div className="space-y-4">
      <UsageBudgetSkeleton />
      <UsageAnthropicSkeleton />
      <UsageModelSkeleton />
      <UsageDailyTableSkeleton />
    </div>
  );
}
