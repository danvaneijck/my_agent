# Light Mode Styling Fix Plan

## Scope

Full review of `agent/dashboard/static/index.html` (Dashboard) and `agent/dashboard/static/admin.html` (Admin Portal) to identify and fix every place where light mode is not properly implemented.

Both pages use CSS custom properties defined in `:root` (dark mode defaults) and `html.light { ... }` overrides. The theme is toggled by adding/removing the `light` class on `<html>` via JavaScript.

---

## Issues Found

### Issue 1 — Tag badge backgrounds invisible in light mode (CRITICAL)

**Files:** Both `index.html` and `admin.html`

**Problem:** All `.tag-*` badge background colors use 8-digit hex with `22` alpha suffix (e.g. `#6c8cff22`), which means ~13% opacity. In dark mode these sit on dark `--surface` (`#1a1d27`) producing subtle dark tints. In light mode `--surface` is `#ffffff`, so the same tints become near-invisible against white.

**Affected selectors (identical in both files):**
- `.tag-owner` — `background: #6c8cff22`
- `.tag-admin` — `background: #fbbf2422`
- `.tag-user` — `background: #4ade8022`
- `.tag-guest` — `background: #8b90a022`
- `.tag-discord` — `background: #5865f222`
- `.tag-telegram` — `background: #229ed922`
- `.tag-slack` — `background: #4a154b22`
- `.tag-web` — `background: #6c8cff22`
- `.tag-google` — `background: #4285f422`

**index.html only:**
- `.tag-healthy` — `background: #4ade8022`
- `.tag-unhealthy` — `background: #f8717122`
- `.tag-unreachable` — `background: #8b90a022`

**Fix:** Add `html.light` overrides for each tag background using RGBA with higher alpha (0.15) and color values tuned to the light-mode palette. Use the light-mode `--green`, `--yellow`, `--red`, `--accent` values as base colors:

```css
html.light .tag-owner    { background: rgba(99,102,241,0.12); }
html.light .tag-admin    { background: rgba(234,179,8,0.12); }
html.light .tag-user     { background: rgba(34,197,94,0.12); }
html.light .tag-guest    { background: rgba(107,114,128,0.12); }
html.light .tag-discord  { background: rgba(88,101,242,0.12); }
html.light .tag-telegram { background: rgba(34,158,217,0.12); }
html.light .tag-slack    { background: rgba(224,30,90,0.12); }
html.light .tag-web      { background: rgba(108,140,255,0.12); }
html.light .tag-google   { background: rgba(66,133,244,0.12); }
/* index.html only: */
html.light .tag-healthy    { background: rgba(34,197,94,0.12); }
html.light .tag-unhealthy  { background: rgba(239,68,68,0.12); }
html.light .tag-unreachable{ background: rgba(107,114,128,0.12); }
```

---

### Issue 2 — Platform tag text colors fail contrast on white (HIGH)

**Files:** Both `index.html` and `admin.html`

**Problem:** The platform-specific tag text colors are hardcoded absolute hex values that are not overridden for light mode. Against a near-white background (light mode), several fail WCAG AA contrast (4.5:1 for small text):
- `.tag-discord` — `color: #7289da` — ~3.0:1 contrast on white (FAIL)
- `.tag-telegram` — `color: #29b6f6` — ~2.5:1 contrast on white (FAIL)
- `.tag-web` — `color: #6c8cff` — ~3.1:1 contrast on white (FAIL)
- `.tag-google` — `color: #4285f4` — ~3.3:1 contrast on white (FAIL)
- `.tag-slack` — `color: #e01e5a` — ~4.6:1 on white (PASS, but dark tone preferred)

**Fix:** Add `html.light` color overrides with darkened equivalents:
```css
html.light .tag-discord  { color: #4752c4; }
html.light .tag-telegram { color: #0277bd; }
html.light .tag-web      { color: #4338ca; }
html.light .tag-google   { color: #1557b0; }
html.light .tag-slack    { color: #b5103c; }
```

---

### Issue 3 — Toast notifications use hardcoded dark backgrounds (CRITICAL)

**File:** `admin.html` only

**Problem:**
```css
.toast-success { background: #065f46; color: var(--green); border: 1px solid var(--green); }
.toast-error   { background: #7f1d1d; color: var(--red);   border: 1px solid var(--red);   }
```
`#065f46` (dark forest green) and `#7f1d1d` (dark crimson) are explicitly dark-mode colors. In light mode, toasts appear as jarring dark floating boxes on a light page.

**Fix:** Add `html.light` overrides:
```css
html.light .toast-success {
  background: #f0fdf4;
  color: #15803d;
  border-color: #86efac;
}
html.light .toast-error {
  background: #fef2f2;
  color: #b91c1c;
  border-color: #fca5a5;
}
```

---

### Issue 4 — `.btn-danger:hover` uses dark-mode red alpha (HIGH)

**File:** `admin.html` only

**Problem:**
```css
.btn-danger:hover { background: #f8717122; }
```
`#f87171` is the dark-mode value of `--red`. At 13% alpha on a white background this is nearly invisible. In light mode `--red` is `#ef4444`, so the hover effect should use that base.

**Fix:** Change to use a proper rgba that works in both modes, or add an `html.light` override:
```css
/* Change base rule to use a neutral approach */
.btn-danger:hover { background: rgba(248,113,113,0.13); }
/* Add light mode override */
html.light .btn-danger:hover { background: rgba(239,68,68,0.12); }
```

---

### Issue 5 — Bar fill inner text hardcoded to dark background color (MEDIUM)

**File:** `index.html` only

**Problem:** In `loadToolUsage()` JavaScript, the tool count text on the green bar fill uses:
```js
'<span style="color:#0f1117;opacity:0.8;font-size:10px">' + info.tools.length + ' tools</span>'
```
`#0f1117` is the dark-mode `--bg` (page background). On a dark page this looks intentional — dark text on bright green fill. In light mode, the light page background `--bg` becomes `#f9fafb`, but this text stays `#0f1117` (dark). While the contrast is technically acceptable on the green bar (`#4ade80`/`#22c55e`), the value is semantically wrong — it should not reference the dark background color directly.

**Fix:** Change `color:#0f1117` to `color:#111827` (an always-dark neutral) which provides correct contrast on the green bar in both modes, without coupling to the dark-mode background value.

---

### Issue 6 — Modal overlay scrim slightly heavy in light mode (LOW)

**File:** `admin.html` only

**Problem:**
```css
.modal-overlay { background: rgba(0,0,0,0.6); }
```
A 60% black overlay is appropriate on a dark page. On a light page it appears heavier than expected. This is a minor aesthetic issue — not a color correctness bug.

**Fix (optional):** Add light mode reduction:
```css
html.light .modal-overlay { background: rgba(0,0,0,0.4); }
```

---

### Issue 7 — Logo SVG not theme-aware (LOW, informational)

**File:** `agent/dashboard/static/logo-icon.svg`, used in both pages via `<img>` tag

**Status:** Not a blocking bug. The logo uses `fill="#6366f1"` throughout, which matches `--accent` (identical in both modes: `#6366f1`). The SVG is loaded via `<img>` so CSS variables cannot reach it anyway. Since the accent color doesn't change between themes, this is acceptable as-is.

**No change needed.**

---

## Files to Modify

| File | Changes |
|---|---|
| `agent/dashboard/static/index.html` | Add light mode overrides for tag backgrounds, tag text colors (platform tags), fix bar fill text color in JS |
| `agent/dashboard/static/admin.html` | Add light mode overrides for tag backgrounds, tag text colors (platform tags), toast colors, btn-danger hover, modal overlay |

---

## Implementation Steps

### Step 1: Fix `index.html`

1. In the `<style>` block, after the existing `html.light { ... }` section, add:
   - Light mode tag background overrides (Issues 1 for `index.html` tags)
   - Light mode platform tag text color overrides (Issue 2)

2. In the `loadToolUsage()` JavaScript function (around line 461), change the inline `color:#0f1117` to `color:#111827` (Issue 5)

### Step 2: Fix `admin.html`

1. In the `<style>` block, after the existing `html.light { ... }` section, add:
   - Light mode tag background overrides (Issue 1 for `admin.html` tags)
   - Light mode platform tag text color overrides (Issue 2)
   - Light mode toast overrides (Issue 3)
   - Light mode btn-danger hover (Issue 4)
   - Light mode modal overlay (Issue 6, optional)

---

## Testing Checklist

After applying fixes, verify in both dark and light modes:

- [ ] All permission level tags (owner/admin/user/guest) display visible colored badges
- [ ] All platform tags (discord/telegram/slack/web/google) show readable colored badges with sufficient contrast
- [ ] Status tags (healthy/unhealthy/unreachable) are visible and color-coded
- [ ] Toast success/error notifications match the light theme (light surface, dark text)
- [ ] Delete button danger hover state is visible in light mode
- [ ] Modal overlay scrim is proportionate
- [ ] All table text, headers, borders are properly themed (already working via CSS vars)
- [ ] Form inputs, selects, textareas are properly themed (already working via CSS vars)
- [ ] Buttons render correctly in both modes
- [ ] Bar charts show appropriate contrast for text-on-fill
