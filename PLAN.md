# Implementation Plan: Mobile Sidebar Scrollability & Deployment Banner Fix

## Problem Analysis

### Issue 1 — Sidebar nav items not scrollable on mobile

**Root cause:** `Sidebar.tsx`'s `<aside>` element is not a flex container, so the
`<motion.nav>` inside it has no mechanism to take the remaining height and
overflow-scroll. With 15 nav items (~44 px each ≈ 660 px of content), this overflows
on most phones (e.g. iPhone 8 only has ~611 px below the sidebar header).

### Issue 2 — Deployment banner broken on mobile

Two distinct sub-problems:

**2a — Sidebar overlay doesn't cover BottomNav.**
`BottomNav` has `z-30` (same as the sidebar backdrop overlay). DOM order makes the
BottomNav appear *above* the dark overlay when the sidebar is open, because it is
rendered later in the DOM. The bottom nav remains visible and tappable when the
sidebar overlay is active — confusing UX that makes the banner interaction feel broken
(two navigation surfaces visible at once).

**2b — Desktop sidebar is partially hidden behind the banner.**
The outer layout `<div className="h-full flex">` has no top offset when the banner is
visible. Only the *content column* gets `pt-9`. The `<aside>` on desktop is
`md:static` (in normal flow), so its `top-9` Tailwind class has **no effect** on a
statically-positioned element — the sidebar starts at y=0 and the first 36 px of its
logo header is covered by the fixed banner. On mobile the sidebar is `position: fixed`
so `top-9` works correctly; on desktop it does not. Moving `pt-9` to the outer wrapper
fixes the desktop case and keeps mobile correct (fixed elements are viewport-relative
and unaffected by their parent's padding).

---

## Files to Modify

| File | Change |
|---|---|
| `agent/portal/frontend/src/components/layout/Sidebar.tsx` | Add `flex flex-col` to `<aside>`; add `flex-1 overflow-y-auto` to `<motion.nav>` |
| `agent/portal/frontend/src/components/layout/Layout.tsx` | Move `pt-9` from the content column div to the outer `div.h-full.flex` |
| `agent/portal/frontend/src/components/layout/BottomNav.tsx` | Change `z-30` → `z-20` so the sidebar overlay properly dims it |

---

## Step-by-Step Changes

### Step 1 — `Sidebar.tsx`: make nav scrollable

**Current `<aside>` className** (line 93):
```
fixed left-0 z-40 w-56 bg-white dark:bg-surface-light border-r
border-light-border dark:border-border md:static{bannerVisible ? " top-9 bottom-0" : " inset-y-0"}
```

**Change:** append `flex flex-col` to the `<aside>` className.

No explicit `h-full` is needed:
- On **mobile** (`fixed`), the `top` / `bottom` constraints (`top-9 bottom-0` or
  `inset-y-0`) already give the aside a definite height.
- On **desktop** (`md:static`), the aside is a flex item inside `div.h-full.flex`
  whose `align-items` defaults to `stretch`, so it already fills the container height.

**Current `<motion.nav>` className** (line 120):
```
p-3 space-y-1
```

**Change:** add `flex-1 overflow-y-auto`:
```
p-3 space-y-1 flex-1 overflow-y-auto
```

`flex-1` causes the nav to occupy all remaining height inside the flex-column aside
(below the fixed `h-14` logo header). `overflow-y-auto` enables scrolling when the 15
nav items exceed the available height.

**Height math on a 667 px iPhone 8 with banner visible:**
- Sidebar height = 667 − 36 (banner) = 631 px
- Logo header = 56 px (`h-14`)
- Nav scroll area = 631 − 56 = **575 px** for 660 px of content → scrollable ✓

---

### Step 2 — `Layout.tsx`: move banner offset to the outer wrapper

**Current outer div** (line 188):
```jsx
<div className="h-full flex">
```

**Change to:**
```jsx
<div className={`h-full flex${showDeployBanner ? " pt-9" : ""}`}>
```

**Current content column** (line 206):
```jsx
<div className={`flex-1 flex flex-col min-w-0${showDeployBanner ? " pt-9" : ""}`}>
```

**Change to:**
```jsx
<div className="flex-1 flex min-w-0 flex-col">
```

**Why this is safe on both breakpoints:**

- *Mobile*: The `<aside>` is `position: fixed` (viewport-relative). The outer div's
  `pt-9` does not affect it. The sidebar's own `top-9` when `bannerVisible` still
  positions it correctly below the banner. The content column (in-flow child of the
  outer div) is offset 36 px from the top — same effective result as before.
- *Desktop*: The `<aside>` is `md:static` and is a flex item. It now starts 36 px
  below the outer div's top edge (matching the banner height) instead of being
  partially covered by the banner.
- The `top-9 bottom-0` on the sidebar when `bannerVisible` remains correct and
  harmless on desktop (CSS `top`/`bottom` have no effect on statically-positioned
  elements).

---

### Step 3 — `BottomNav.tsx`: fix z-index so sidebar overlay covers it

**Current nav className** (line 19):
```
fixed bottom-0 inset-x-0 z-30 md:hidden ...
```

**Change:** `z-30` → `z-20`:
```
fixed bottom-0 inset-x-0 z-20 md:hidden ...
```

**Why:** The sidebar backdrop overlay is `z-30`. With BottomNav also at `z-30`, the
BottomNav (rendered later in the DOM) appears *above* the overlay. Setting BottomNav
to `z-20` means the overlay correctly covers it when the sidebar is open.

Z-index stack after this change:

| Layer | z-index |
|---|---|
| Regular content | 0–10 |
| BottomNav | **z-20** (was z-30) |
| Sidebar overlay (backdrop) | z-30 — now covers BottomNav ✓ |
| Sidebar panel | z-40 |
| Deployment banner | z-40 |
| Notification toasts | z-50 |

The BottomNav does not need to sit above the sidebar or banner (it is at the bottom of
the screen, spatially separated from both), so `z-20` is safe.

---

## No New Files, No New Dependencies

All changes are pure className/CSS adjustments in three existing components. No new
components, hooks, packages, migrations, or Docker changes are required.
