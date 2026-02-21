# Mobile Support Review — Task Detail & Navigation

## Problem Statement

Two related mobile UX issues to fix:

1. **Task Detail Page — TaskChainViewer dominates the header**: When a task chain has multiple tasks, `TaskChainViewer` renders inline in the fixed header area (`shrink-0`). On narrow screens this consumes most of the vertical space, leaving little room for the output/logs content area below.

2. **Tasks nav in the sidebar is not mobile-friendly**: The sidebar navigation (`Sidebar.tsx`) works as a slide-in overlay on mobile, but the nav items are numerous (13 links) and take up significant vertical space. There is no bottom-anchored mobile tab bar, no way to quickly reach Tasks without opening the full menu, and the hamburger-menu workflow adds friction.

---

## Files to Modify

| File | Change |
|---|---|
| `agent/portal/frontend/src/components/tasks/TaskChainViewer.tsx` | Make chain collapsible on mobile; show compact horizontal pill list by default |
| `agent/portal/frontend/src/pages/TaskDetailPage.tsx` | Move `TaskChainViewer` out of the non-scrollable header area; give the header a `max-h` cap with internal scroll on mobile |
| `agent/portal/frontend/src/components/layout/Sidebar.tsx` | Add a mobile bottom tab bar for the most important nav items (Home, Tasks, Chat, Settings) |
| `agent/portal/frontend/src/components/layout/Layout.tsx` | Add bottom padding to `<main>` on mobile so content is not hidden behind the tab bar |

---

## Detailed Approach

### 1. `TaskChainViewer.tsx` — Compact mobile chain display

**Current behaviour**: Full vertical list of chain tasks, each row is ~40 px tall. With 4–6 tasks this is 160–240 px gone from the header.

**Fix**:
- On mobile (`md:hidden`), replace the vertical list with a **horizontal scrollable row of status pills**. Each pill shows the short task ID (8 chars) and a `StatusBadge`. A single tap navigates to that task; the current task is highlighted.
- On desktop (`hidden md:block`), keep the existing vertical list unchanged.
- Add a `ChevronDown/Up` toggle button (mobile only) that expands the chain to the current full vertical view if the user wants to see prompt text. Default state is **collapsed** (pills only).
- This reduces chain display from ~160–240 px down to ~36 px on mobile.

Implementation sketch:
```tsx
// Mobile: horizontal pill row
<div className="md:hidden">
  <div className="flex items-center gap-1 overflow-x-auto pb-1">
    {chain.map((t) => (
      <button
        key={t.id}
        onClick={() => navigate(`/tasks/${t.id}`)}
        className={`shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs border ${
          t.id === currentTaskId ? "border-accent bg-accent/10 text-accent" : "border-border text-gray-500"
        }`}
      >
        <StatusBadge status={t.status} />
        <span className="font-mono">{t.id.slice(0, 8)}</span>
      </button>
    ))}
  </div>
</div>

// Desktop: keep existing vertical list (wrapped in hidden md:block)
<div className="hidden md:block">
  {/* existing space-y-1 list */}
</div>
```

### 2. `TaskDetailPage.tsx` — Constrain header height on mobile

**Current behaviour**: The header `<div>` has `shrink-0` and no max-height, so it expands as large as its content (prompt text + metadata + chain viewer + optional forms).

**Fix**:
- Add `max-h-[45vh] overflow-y-auto` on mobile only to the header's inner scrollable area, keeping `shrink-0` intact on the outer container.
- Specifically: wrap the "below the first row" content (prompt, metadata, error, plan/resume forms, chain viewer) in a new `<div className="overflow-y-auto max-h-[40vh] md:max-h-none space-y-3">`. The first row (back button + status badge + action buttons) stays always visible.
- This ensures the content area below the tabs always gets meaningful space even on a phone with a 667 px viewport.

Implementation sketch (within the header `<div>`):
```tsx
{/* Always-visible first row */}
<div className="flex items-center gap-3"> ... </div>

{/* Scrollable header details (mobile: max 40vh, desktop: uncapped) */}
<div className="overflow-y-auto max-h-[40vh] md:max-h-none space-y-3">
  <p className="text-sm ...">{task.prompt}</p>
  <div className="flex flex-wrap ..."> {/* metadata */} </div>
  {task.error && <div>...</div>}
  {/* plan/resume/retry/continue forms */}
  <TaskChainViewer ... />
</div>
```

### 3. `Sidebar.tsx` — Mobile bottom tab bar

**Current behaviour**: On mobile the sidebar is a full-height slide-in drawer triggered by the hamburger button in the header. There is no persistent bottom navigation.

**Fix**: Add a **fixed bottom tab bar** visible only on mobile (`md:hidden`). It shows the 4 most-used nav destinations: **Home, Tasks, Chat, Settings** (and a "More" button that opens the existing full sidebar). This way the most common actions are one tap away without opening the full menu.

- The bottom bar is `fixed bottom-0 left-0 right-0 z-30` with a solid background and border-top.
- Each tab shows its icon + short label.
- Active tab is highlighted with `text-accent`.
- The "More" / hamburger icon opens the existing sidebar overlay.
- The bottom bar is rendered **at the end of the Sidebar component** (or could be a new `BottomNav.tsx` component called from `Layout.tsx`).

Implementation sketch (new component `BottomNav.tsx` called from `Layout.tsx`):
```tsx
// agent/portal/frontend/src/components/layout/BottomNav.tsx
const BOTTOM_TABS = [
  { to: "/", icon: Home, label: "Home", end: true },
  { to: "/tasks", icon: LayoutDashboard, label: "Tasks" },
  { to: "/chat", icon: MessageSquare, label: "Chat" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function BottomNav({ onMenuOpen }: { onMenuOpen: () => void }) {
  return (
    <nav className="fixed bottom-0 inset-x-0 z-30 md:hidden bg-white dark:bg-surface-light border-t border-light-border dark:border-border flex items-stretch">
      {BOTTOM_TABS.map(({ to, icon: Icon, label, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `flex-1 flex flex-col items-center justify-center py-2 text-[10px] font-medium gap-0.5 ${
              isActive ? "text-accent" : "text-gray-500"
            }`
          }
        >
          <Icon size={20} />
          {label}
        </NavLink>
      ))}
      {/* "More" button opens the full sidebar */}
      <button
        onClick={onMenuOpen}
        className="flex-1 flex flex-col items-center justify-center py-2 text-[10px] font-medium gap-0.5 text-gray-500"
      >
        <Menu size={20} />
        More
      </button>
    </nav>
  );
}
```

### 4. `Layout.tsx` — Bottom padding for main content on mobile

When the bottom tab bar is present, the last content in `<main>` is obscured behind it (height ≈ 56 px on iOS Safari with safe-area).

**Fix**: Add `pb-16 md:pb-0` (plus `pb-safe` via env() if needed) to the `<main>` element.

```tsx
<main
  id="main-content"
  className="flex-1 overflow-auto pb-16 md:pb-0"
  tabIndex={-1}
>
  {children}
</main>
```

And render `<BottomNav onMenuOpen={() => setSidebarOpen(true)} />` inside the Layout return, sibling to the Sidebar.

---

## Step-by-Step Implementation Order

1. **Create `BottomNav.tsx`** — new file with 4 tabs + More button.
2. **Update `Layout.tsx`** — import and render `<BottomNav>`, add `pb-16 md:pb-0` to `<main>`.
3. **Update `TaskChainViewer.tsx`** — add mobile horizontal pill row, wrap existing list in `hidden md:block`.
4. **Update `TaskDetailPage.tsx`** — wrap scrollable header details in a height-capped inner div.

---

## What Is NOT Changed

- Desktop layout is entirely unaffected (all changes gated behind `md:hidden` / `hidden md:block`).
- The existing sidebar behaviour (slide-in on mobile) is preserved — the bottom nav's "More" button still opens it.
- No changes to routing, API calls, or business logic.
- No dependency additions required (all components use existing Tailwind + lucide-react + react-router).
