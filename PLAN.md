# Implementation Plan: Secondary "Ideal Pace" Indicator on Claude Code Usage Bars

## Goal

On both the Home dashboard (`HomePage.tsx`) and the Usage page (`UsagePage.tsx`), add a secondary visual indicator on the Claude Code usage progress bars (5-hour and 7-day windows) that shows where usage **should** be if it were perfectly evenly distributed throughout the time window. This lets users quickly see whether they are ahead of pace (burning through quota faster than expected) or behind pace (using less than expected).

---

## Mathematical Foundation

### Inputs available per usage window
| Field | Source | Description |
|---|---|---|
| `utilization_percent` | API | Current actual usage as % of the quota (0–100) |
| `reset_timestamp` | API | Unix timestamp (ms) when the current window resets |

### Deriving the "ideal" position

For each window we know:
- **Window duration** — fixed constants: `5 * 60 * 60 * 1000` ms (5 hours) and `7 * 24 * 60 * 60 * 1000` ms (7 days)
- **Window start** = `reset_timestamp - windowDurationMs`
- **Time elapsed** = `Date.now() - windowStart`
- **Ideal utilization** = `(elapsed / windowDurationMs) * 100`, clamped to [0, 100]

If `elapsed < 0` (clock skew / just after reset) → ideal = 0.
If `elapsed > windowDurationMs` (past the reset timestamp) → ideal = 100.

```ts
function computeIdealPct(resetTimestamp: number, windowDurationMs: number): number {
  const windowStart = resetTimestamp - windowDurationMs;
  const elapsed = Date.now() - windowStart;
  return Math.min(100, Math.max(0, (elapsed / windowDurationMs) * 100));
}
```

---

## Visual Design

### Chosen approach: Vertical "pace marker" line

A thin (2 px) vertical line positioned absolutely inside the progress bar container at `left: ${idealPct}%`. This is the clearest, least intrusive way to show the target without cluttering the existing color-coded bar.

```
┌────────────────────────────────────────────────────────┐
│  ████████████████████  ┊                               │
│  ████████ actual ████  ┊ ← ideal pace marker           │
└────────────────────────────────────────────────────────┘
        Actual: 38%     ↑ Ideal: 45%   (behind pace)
```

```
┌────────────────────────────────────────────────────────┐
│  ██████████████████████████████████  ┊                 │
│  ████████ actual ██████████████████  ┊ ← ideal marker  │
└────────────────────────────────────────────────────────┘
           Actual: 70%                ↑ Ideal: 55%  (ahead of pace)
```

### Marker styling
- **Color**: `bg-white` with slight opacity (`opacity-90`) — readable over any bar color and against the gray background
- **Width**: `w-0.5` (2 px)
- **Height**: `h-full` — spans the full height of the bar track
- **z-index**: sits above the progress fill (`z-10`)
- The marker is **always rendered** regardless of whether actual usage is above or below ideal

### Secondary label (optional, on UsagePage only)
On the full Usage page (`UsagePage.tsx`), a small label below the bar showing the ideal percentage provides extra context since there is more space:

```
Resets in 2h 14m   •   Ideal pace: 55%
```

On the compact Home dashboard card, space is tight — only the marker line is shown (no label).

---

## Files to Modify

### 1. `agent/portal/frontend/src/pages/UsagePage.tsx`

#### a) Add `computeIdealPct` helper (after existing `utilizationColor` on line 83)

```ts
const FIVE_HOUR_MS = 5 * 60 * 60 * 1000;
const SEVEN_DAY_MS = 7 * 24 * 60 * 60 * 1000;

function computeIdealPct(resetTimestamp: number, windowDurationMs: number): number {
  const windowStart = resetTimestamp - windowDurationMs;
  const elapsed = Date.now() - windowStart;
  return Math.min(100, Math.max(0, (elapsed / windowDurationMs) * 100));
}
```

#### b) Update `UsageBar` component props (line 314)

Add `windowDurationMs` prop:

```ts
function UsageBar({
  label,
  pct,
  resetTimestamp,
  windowDurationMs,
}: {
  label: string;
  pct: number;
  resetTimestamp: number;
  windowDurationMs: number;
}) {
```

#### c) Compute idealPct inside `UsageBar` (after `resetLabel` computation)

```ts
const idealPct = computeIdealPct(resetTimestamp, windowDurationMs);
```

#### d) Update the progress bar `div` to add `relative` positioning and the marker

Change the bar container from:
```tsx
<div className="w-full bg-gray-200 dark:bg-surface rounded-full h-3">
  <div
    className={`h-3 rounded-full transition-all ${utilizationColor(pct)}`}
    style={{ width: `${Math.min(100, pct)}%` }}
  />
</div>
```

To:
```tsx
<div className="relative w-full bg-gray-200 dark:bg-surface rounded-full h-3 overflow-hidden">
  <div
    className={`h-3 rounded-full transition-all ${utilizationColor(pct)}`}
    style={{ width: `${Math.min(100, pct)}%` }}
  />
  <div
    className="absolute top-0 h-full w-0.5 bg-white opacity-90 z-10"
    style={{ left: `${idealPct}%` }}
    title={`Ideal pace: ${Math.round(idealPct)}%`}
  />
</div>
```

**Note**: `overflow-hidden` on the container keeps the marker clipped at the rounded edges. The marker renders regardless of position.

#### e) Add ideal pace label below the reset label

Change:
```tsx
<p className="text-xs text-gray-500">{resetLabel}</p>
```

To:
```tsx
<p className="text-xs text-gray-500">
  {resetLabel}
  <span className="ml-2 text-gray-400">· Ideal pace: {Math.round(idealPct)}%</span>
</p>
```

#### f) Update call sites in `AnthropicUsageSection` (lines 288-301)

Pass the new `windowDurationMs` prop when rendering each `UsageBar`:

```tsx
{data.five_hour && (
  <UsageBar
    label="5 Hour Usage"
    pct={data.five_hour.utilization_percent}
    resetTimestamp={data.five_hour.reset_timestamp}
    windowDurationMs={FIVE_HOUR_MS}
  />
)}
{data.seven_day && (
  <UsageBar
    label="Weekly Usage"
    pct={data.seven_day.utilization_percent}
    resetTimestamp={data.seven_day.reset_timestamp}
    windowDurationMs={SEVEN_DAY_MS}
  />
)}
```

---

### 2. `agent/portal/frontend/src/pages/HomePage.tsx`

#### a) Add `computeIdealPct` helper (after existing `utilizationTextColor` on line 837)

```ts
const FIVE_HOUR_MS = 5 * 60 * 60 * 1000;
const SEVEN_DAY_MS = 7 * 24 * 60 * 60 * 1000;

function computeIdealPct(resetTimestamp: number, windowDurationMs: number): number {
  const windowStart = resetTimestamp - windowDurationMs;
  const elapsed = Date.now() - windowStart;
  return Math.min(100, Math.max(0, (elapsed / windowDurationMs) * 100));
}
```

#### b) Compute ideal percentages inside `ClaudeCodeUsageCard` (before the return)

Inside the `ClaudeCodeUsageCard` function body (after `const navigate = useNavigate()`), add:

```ts
const fiveHourIdealPct = data?.five_hour
  ? computeIdealPct(data.five_hour.reset_timestamp, FIVE_HOUR_MS)
  : 0;
const sevenDayIdealPct = data?.seven_day
  ? computeIdealPct(data.seven_day.reset_timestamp, SEVEN_DAY_MS)
  : 0;
```

#### c) Update the 5-hour bar (lines 898-903)

Change:
```tsx
<div className="w-full bg-gray-200 dark:bg-surface rounded-full h-2.5">
  <div
    className={`h-2.5 rounded-full transition-all ${utilizationColor(data.five_hour.utilization_percent)}`}
    style={{ width: `${Math.min(100, data.five_hour.utilization_percent)}%` }}
  />
</div>
```

To:
```tsx
<div className="relative w-full bg-gray-200 dark:bg-surface rounded-full h-2.5 overflow-hidden">
  <div
    className={`h-2.5 rounded-full transition-all ${utilizationColor(data.five_hour.utilization_percent)}`}
    style={{ width: `${Math.min(100, data.five_hour.utilization_percent)}%` }}
  />
  <div
    className="absolute top-0 h-full w-0.5 bg-white opacity-90 z-10"
    style={{ left: `${fiveHourIdealPct}%` }}
    title={`Ideal pace: ${Math.round(fiveHourIdealPct)}%`}
  />
</div>
```

#### d) Update the 7-day bar (lines 917-922)

Change:
```tsx
<div className="w-full bg-gray-200 dark:bg-surface rounded-full h-2.5">
  <div
    className={`h-2.5 rounded-full transition-all ${utilizationColor(data.seven_day.utilization_percent)}`}
    style={{ width: `${Math.min(100, data.seven_day.utilization_percent)}%` }}
  />
</div>
```

To:
```tsx
<div className="relative w-full bg-gray-200 dark:bg-surface rounded-full h-2.5 overflow-hidden">
  <div
    className={`h-2.5 rounded-full transition-all ${utilizationColor(data.seven_day.utilization_percent)}`}
    style={{ width: `${Math.min(100, data.seven_day.utilization_percent)}%` }}
  />
  <div
    className="absolute top-0 h-full w-0.5 bg-white opacity-90 z-10"
    style={{ left: `${sevenDayIdealPct}%` }}
    title={`Ideal pace: ${Math.round(sevenDayIdealPct)}%`}
  />
</div>
```

---

## Edge Cases

| Scenario | Behaviour |
|---|---|
| Window has just reset (elapsed ≈ 0) | Ideal = 0% — marker at far left of bar |
| Window is about to expire (elapsed ≈ duration) | Ideal ≈ 100% — marker at far right |
| Clock skew (elapsed < 0) | `Math.max(0, ...)` clamps to 0 |
| elapsed > windowDuration (past reset) | `Math.min(100, ...)` clamps to 100 |
| `data.five_hour` is null | Ideal computed only when data is present; guards already in JSX |
| Usage > ideal (ahead of pace) | Actual bar extends past marker — marker visible on bar fill |
| Usage < ideal (behind pace) | Actual bar ends before marker — marker visible on gray background |
| Usage = 0% | Actual bar invisible; marker at current ideal position on gray |

---

## Step-by-Step Implementation Order

1. **Edit `UsagePage.tsx`**
   - Add `computeIdealPct` helper + constants after line 83
   - Add `windowDurationMs` to `UsageBar` props interface
   - Compute `idealPct` inside `UsageBar`
   - Update bar container to `relative` + `overflow-hidden` and add marker `div`
   - Add ideal pace text to the reset label line
   - Pass `windowDurationMs` at both `UsageBar` call sites in `AnthropicUsageSection`

2. **Edit `HomePage.tsx`**
   - Add `computeIdealPct` helper + constants after line 837
   - Compute `fiveHourIdealPct` and `sevenDayIdealPct` inside `ClaudeCodeUsageCard`
   - Update the 5-hour bar container + add marker `div`
   - Update the 7-day bar container + add marker `div`

3. **Verify TypeScript** — no new dependencies needed; all changes are pure TSX/math

4. **Commit and push**

---

## No Backend Changes Required

The existing `reset_timestamp` field already provides everything needed to calculate ideal pace. No API changes, no new endpoints, no new data fetching.
