# Fix Light Mode — Implementation Plan

## Project Overview

**Branch:** `project/fix-light-mode`
**Goal:** Audit every component in the portal frontend and ensure light mode is fully implemented. Currently, many components use dark-only color classes (`bg-surface`, `bg-surface-light`, `bg-surface-lighter`, `border-border`, `text-white`, `text-gray-200/300/400`) without corresponding `dark:` prefixes, making them invisible or illegible on the white light-mode background.

---

## Architecture & Root Cause

### Tech Stack
- **React 19 + TypeScript** with **Vite 6**
- **Tailwind CSS v3** with `darkMode: "class"` strategy
- Theme class (`light` or `dark`) applied to `<html>` by `ThemeContext.tsx`

### The Core Problem

The custom Tailwind color aliases are **dark-by-default**:

| Tailwind Class | Hex Value | Issue |
|---|---|---|
| `bg-surface` | `#1a1b23` | Dark background — invisible on light page |
| `bg-surface-light` | `#22232d` | Dark background — invisible on light page |
| `bg-surface-lighter` | `#2a2b37` | Dark background — invisible on light page |
| `border-border` | `#33344a` | Dark border — invisible on light page |
| `text-white` | `#ffffff` | White text — invisible on white background |
| `text-gray-200/300/400` | Light grays | Poor contrast on white background |

### The Correct Pattern
Components that are already fixed follow this pattern:
```tsx
// Background
bg-white dark:bg-surface-light

// Text (primary)
text-gray-900 dark:text-white

// Text (secondary)
text-gray-600 dark:text-gray-400

// Text (muted)
text-gray-500 dark:text-gray-500

// Border
border-light-border dark:border-border

// Interactive hover
hover:bg-gray-100 dark:hover:bg-surface-lighter

// Input background
bg-white dark:bg-surface border-light-border dark:border-border text-gray-900 dark:text-white
```

### Available Light-Mode Color Tokens

| Token | Value | Use Case |
|---|---|---|
| `light-surface.DEFAULT` | `#ffffff` | Card/panel backgrounds |
| `light-surface.secondary` | `#f9fafb` | Subtle secondary backgrounds |
| `light-surface.tertiary` | `#f3f4f6` | Tertiary / code blocks |
| `light-border.DEFAULT` | `#e5e7eb` | Standard borders |
| `light-border.light` | `#d1d5db` | Subtle borders |

---

## File Inventory

### Layout & Infrastructure (already mostly correct)
- `src/components/layout/Layout.tsx` — Toast notifications ✅ already uses `dark:` variants
- `src/components/layout/Header.tsx` — ✅ already uses `dark:` variants
- `src/components/layout/Sidebar.tsx` — ✅ already uses `dark:` variants
- `src/App.tsx` — Auth callback error state needs fixes
- `src/index.css` — Code highlight theme needs light-mode override
- `src/contexts/ThemeContext.tsx` — ✅ no visual changes needed

### Common Components (priority fixes)
- `src/components/common/Button.tsx` — Secondary/ghost/danger variants dark-only
- `src/components/common/Card.tsx` — Needs audit
- `src/components/common/ConfirmDialog.tsx` — Fully dark, no `dark:` variants at all
- `src/components/common/EmptyState.tsx` — Needs audit
- `src/components/common/EnvironmentBadge.tsx` — Needs audit
- `src/components/common/ErrorBoundary.tsx` — Button is dark-only
- `src/components/common/LoadingScreen.tsx` — Needs audit
- `src/components/common/Modal.tsx` — Needs audit
- `src/components/common/ProgressBar.tsx` — Needs audit
- `src/components/common/RepoLabel.tsx` — Needs audit
- `src/components/common/Skeleton.tsx` — Needs audit
- `src/components/common/SkipToContent.tsx` — Needs audit
- `src/components/common/Spinner.tsx` — Needs audit
- `src/components/common/StatusBadge.tsx` — Needs audit
- `src/components/common/ThemeToggle.tsx` — Dropdown is fully dark-only

### Chat Components
- `src/components/chat/ChatInput.tsx` — Fully dark (input, textarea, border)
- `src/components/chat/ChatView.tsx` — "Thinking" bubble dark-only
- `src/components/chat/MessageBubble.tsx` — Needs audit
- `src/components/chat/ToolCallsDisplay.tsx` — Needs audit

### Code Components
- `src/components/code/TerminalPanel.tsx` — Needs audit
- `src/components/code/TerminalView.tsx` — Status bar hardcoded `bg-gray-800`

### File Components
- `src/components/files/FileList.tsx` — Needs audit
- `src/components/files/FilePreview.tsx` — Needs audit
- `src/components/files/FileUpload.tsx` — Needs audit

### Project Components
- `src/components/projects/MultiStateProgressBar.tsx` — Needs audit
- `src/components/projects/NewProjectModal.tsx` — Needs audit
- `src/components/projects/PlanningTaskPanel.tsx` — Needs audit
- `src/components/projects/ProjectExecutionPanel.tsx` — Needs audit

### Settings Components
- `src/components/settings/ConnectedAccounts.tsx` — Needs audit
- `src/components/settings/CredentialCard.tsx` — Needs audit
- `src/components/settings/LlmSettingsCard.tsx` — Needs audit

### Skills Components
- `src/components/skills/NewSkillModal.tsx` — Needs audit
- `src/components/skills/SkillCard.tsx` — Needs audit
- `src/components/skills/SkillPicker.tsx` — Needs audit

### Task Components
- `src/components/tasks/ContinueTaskForm.tsx` — Needs audit
- `src/components/tasks/NewTaskForm.tsx` — Needs audit
- `src/components/tasks/NewTaskModal.tsx` — Needs audit
- `src/components/tasks/PlanReviewPanel.tsx` — Needs audit
- `src/components/tasks/TaskChainViewer.tsx` — Needs audit
- `src/components/tasks/TaskList.tsx` — Mobile cards and table rows dark-only
- `src/components/tasks/TaskLogViewer.tsx` — Needs audit
- `src/components/tasks/TaskOutputViewer.tsx` — Needs audit
- `src/components/tasks/WorkspaceBrowser.tsx` — Needs audit

### Pages
- `src/pages/ChatPage.tsx` — Needs audit
- `src/pages/CodePage.tsx` — Needs audit
- `src/pages/DeploymentsPage.tsx` — Needs audit
- `src/pages/FilesPage.tsx` — Search input dark-only (`bg-surface text-white`)
- `src/pages/HomePage.tsx` — `text-white` headings and stat values
- `src/pages/NotFoundPage.tsx` — Needs audit
- `src/pages/PhaseDetailPage.tsx` — Needs audit
- `src/pages/ProjectDetailPage.tsx` — Inputs and buttons dark-only
- `src/pages/ProjectTaskDetailPage.tsx` — Needs audit
- `src/pages/ProjectsPage.tsx` — Needs audit
- `src/pages/PullRequestDetailPage.tsx` — Comment input and action buttons dark-only
- `src/pages/PullRequestsPage.tsx` — Needs audit
- `src/pages/RepoDetailPage.tsx` — Needs audit
- `src/pages/ReposPage.tsx` — Needs audit
- `src/pages/SchedulePage.tsx` — Needs audit
- `src/pages/SettingsPage.tsx` — Needs audit
- `src/pages/ShowcasePage.tsx` — Needs audit
- `src/pages/SkillDetailPage.tsx` — Tags, code preview, modal dark-only
- `src/pages/SkillsPage.tsx` — Needs audit
- `src/pages/TaskDetailPage.tsx` — Needs audit
- `src/pages/TasksPage.tsx` — Needs audit
- `src/pages/UsagePage.tsx` — Hardcoded `text-white` on stat values

---

## Implementation Phases

---

### Phase 1: Foundation & Infrastructure
**Scope:** Global CSS, shared config, and the most-reused common components. Fixing these propagates improvements everywhere.

#### Task 1.1 — `src/index.css`: Light-mode code highlight theme
**Description:** The file imports `github-dark-dimmed.css` as a global code highlight theme. In light mode, code blocks will have dark backgrounds. Add a conditional import or CSS override for the `github` (light) highlight theme under `.light` scope.

**Approach:** Use a `@layer` override so that `.light .hljs` overrides the dark theme variables with the light github theme colors.

**Acceptance Criteria:**
- Code blocks in `<pre>` / `highlight.js` styled elements have a light background and dark text when `html.light` is active
- Code blocks retain the dark theme when `html.dark` is active
- No visual regression in dark mode

**Files:** `src/index.css`

---

#### Task 1.2 — `src/components/common/Button.tsx`: Fix all variants
**Description:** The `secondary`, `ghost`, and `danger` variants use dark-only colors. Every variant must have explicit light-mode and `dark:` dark-mode classes.

**Pattern to apply:**

| Variant | Current | Fixed |
|---|---|---|
| `secondary` | `bg-surface-lighter text-gray-200 border-border` | `bg-white dark:bg-surface-lighter text-gray-700 dark:text-gray-200 border-light-border dark:border-border hover:bg-gray-100 dark:hover:bg-surface-light` |
| `ghost` | `bg-transparent hover:bg-surface-lighter text-gray-400` | `bg-transparent hover:bg-gray-100 dark:hover:bg-surface-lighter text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200` |
| `danger` | Needs audit | `bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-200 dark:border-red-800/50` |

**Acceptance Criteria:**
- All button variants are visible in light mode
- All button variants are visible in dark mode
- Hover states work correctly in both modes
- `primary` variant (brand color) unchanged

**Files:** `src/components/common/Button.tsx`

---

#### Task 1.3 — `src/components/common/ConfirmDialog.tsx`: Full light-mode pass
**Description:** The entire dialog uses dark-only classes with no `dark:` variants. This is one of the most broken components in light mode.

**Fixes needed:**
- Dialog container: `bg-surface-light border-border` → `bg-white dark:bg-surface-light border-light-border dark:border-border`
- Title: `text-white` → `text-gray-900 dark:text-white`
- Message: `text-gray-400` → `text-gray-600 dark:text-gray-400`
- Cancel button: `bg-surface-lighter text-gray-300 border-border hover:bg-surface-light` → apply Button secondary pattern
- Confirm button: review and apply correct variant
- Backdrop/overlay: ensure it works in both modes

**Acceptance Criteria:**
- ConfirmDialog is fully readable in light mode
- All text has sufficient contrast in both modes
- Buttons are visible and styled correctly in both modes

**Files:** `src/components/common/ConfirmDialog.tsx`

---

#### Task 1.4 — `src/components/common/Modal.tsx`: Full light-mode pass
**Description:** Modals are used widely. Audit and fix all classes.

**Fixes needed:**
- Modal overlay/backdrop: ensure background overlay works in both modes
- Modal container: `bg-surface-light border-border` → `bg-white dark:bg-surface-light border-light-border dark:border-border`
- Modal title/headings: `text-white` → `text-gray-900 dark:text-white`
- Modal body text: `text-gray-400` → `text-gray-600 dark:text-gray-400`
- Close/action buttons: apply correct variant pattern

**Acceptance Criteria:**
- Modal is readable and well-styled in light mode
- Modal retains dark appearance in dark mode

**Files:** `src/components/common/Modal.tsx`

---

#### Task 1.5 — `src/components/common/ThemeToggle.tsx`: Fix dropdown
**Description:** The dropdown menu uses dark-only classes (`bg-surface-light border-border text-gray-300 hover:bg-surface-lighter`).

**Fixes needed:**
- Dropdown container: `bg-surface-light border-border` → `bg-white dark:bg-surface-light border-light-border dark:border-border shadow-lg`
- Option text: `text-gray-300` → `text-gray-700 dark:text-gray-300`
- Option hover: `hover:bg-surface-lighter` → `hover:bg-gray-100 dark:hover:bg-surface-lighter`
- Active/selected state: review contrast in both modes

**Acceptance Criteria:**
- ThemeToggle dropdown is clearly readable in both modes
- The active theme option is visually distinguishable in both modes

**Files:** `src/components/common/ThemeToggle.tsx`

---

#### Task 1.6 — Remaining common components: Audit and fix
**Description:** Systematically audit and fix each remaining common component.

**Files to process (one by one):**
- `src/components/common/Card.tsx`
- `src/components/common/EmptyState.tsx`
- `src/components/common/EnvironmentBadge.tsx`
- `src/components/common/ErrorBoundary.tsx` (button is dark-only)
- `src/components/common/LoadingScreen.tsx`
- `src/components/common/ProgressBar.tsx`
- `src/components/common/RepoLabel.tsx`
- `src/components/common/Skeleton.tsx`
- `src/components/common/SkipToContent.tsx`
- `src/components/common/Spinner.tsx`
- `src/components/common/StatusBadge.tsx`

**For each file, apply the pattern:**
- Replace bare `bg-surface*` → `bg-white dark:bg-surface*` or `bg-light-surface* dark:bg-surface*`
- Replace bare `border-border` → `border-light-border dark:border-border`
- Replace bare `text-white` → `text-gray-900 dark:text-white`
- Replace bare `text-gray-200/300` → `text-gray-600/700 dark:text-gray-200/300`

**Acceptance Criteria:**
- Each component is visually correct in both light and dark mode
- No white-on-white or invisible elements remain

---

#### Task 1.7 — `src/App.tsx`: Fix auth callback error state
**Description:** The `AuthCallback` component's error state uses dark-only classes.

**Fixes needed:**
- Container: `bg-surface-light border-border` → `bg-white dark:bg-surface-light border-light-border dark:border-border`
- Error heading: `text-red-400` → `text-red-600 dark:text-red-400`
- Body text: `text-gray-400` → `text-gray-600 dark:text-gray-400`

**Acceptance Criteria:**
- Auth error state is readable in light mode

**Files:** `src/App.tsx`

---

### Phase 2: Chat & Task Components
**Scope:** Chat interface and task-related components — heavily used interactive surfaces.

#### Task 2.1 — `src/components/chat/ChatInput.tsx`: Full light-mode pass
**Description:** The entire chat input bar uses dark-only colors.

**Fixes needed:**
- Form container: `bg-surface-light border-border` → `bg-white dark:bg-surface-light border-t border-light-border dark:border-border`
- Textarea: `bg-surface border-border text-white placeholder:text-gray-500` → `bg-white dark:bg-surface border-light-border dark:border-border text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500`
- Attachment/action buttons: apply hover pattern
- File attachment chips/badges: ensure light-mode visibility
- Any icon colors: `text-gray-400/500` → `text-gray-500 dark:text-gray-400`

**Acceptance Criteria:**
- Chat input is fully usable and readable in light mode
- Text typed in the textarea is visible (dark text on white background)
- All action buttons are visible

**Files:** `src/components/chat/ChatInput.tsx`

---

#### Task 2.2 — `src/components/chat/ChatView.tsx`: Fix thinking bubble and message containers
**Description:** "Thinking..." bubble uses dark-only classes. Audit the full file for other issues.

**Fixes needed:**
- Thinking bubble: `bg-surface-lighter text-gray-500` → `bg-gray-100 dark:bg-surface-lighter text-gray-500 dark:text-gray-500`
- Any conversation area backgrounds
- Any timestamp or metadata text

**Acceptance Criteria:**
- "Thinking..." indicator is visible in light mode
- Conversation area background is appropriate in light mode

**Files:** `src/components/chat/ChatView.tsx`

---

#### Task 2.3 — `src/components/chat/MessageBubble.tsx`: Full audit
**Description:** Message bubbles for user and assistant must be readable in both modes.

**Common fixes:**
- User message bubble: ensure correct text color
- Assistant message bubble: ensure correct background and text
- Code blocks within messages: ensure light-mode code styling
- Any action buttons (copy, etc.): ensure light-mode visibility

**Acceptance Criteria:**
- Both user and assistant messages are fully readable in light mode
- Code in messages has appropriate light-mode styling

**Files:** `src/components/chat/MessageBubble.tsx`

---

#### Task 2.4 — `src/components/chat/ToolCallsDisplay.tsx`: Full audit
**Description:** Tool call display (showing what tools the agent invoked) needs light-mode support.

**Acceptance Criteria:**
- Tool calls are readable in light mode
- Tool name, arguments, and results are visible

**Files:** `src/components/chat/ToolCallsDisplay.tsx`

---

#### Task 2.5 — Task components: Full audit and fix
**Description:** Systematically audit and fix each task component.

**Files with known issues:**
- `src/components/tasks/TaskList.tsx` — Mobile card view (`bg-surface-light`) and table rows (`hover:bg-surface-lighter`) dark-only; `text-gray-200` hardcoded
- `src/components/tasks/TaskLogViewer.tsx` — Log viewer container likely dark-only
- `src/components/tasks/TaskOutputViewer.tsx` — Output container likely dark-only
- `src/components/tasks/WorkspaceBrowser.tsx` — File browser likely dark-only

**Files to audit (may be already correct or need minor fixes):**
- `src/components/tasks/ContinueTaskForm.tsx`
- `src/components/tasks/NewTaskForm.tsx`
- `src/components/tasks/NewTaskModal.tsx`
- `src/components/tasks/PlanReviewPanel.tsx`
- `src/components/tasks/TaskChainViewer.tsx`

**For each file:**
- Replace bare `bg-surface*` with proper `bg-white dark:bg-surface*`
- Replace bare `text-gray-200/300` with `text-gray-600/700 dark:text-gray-200/300`
- Replace bare `border-border` with `border-light-border dark:border-border`
- Replace bare `text-white` with `text-gray-900 dark:text-white`

**Acceptance Criteria:**
- TaskList renders correctly in both modes (mobile cards and table)
- Task log viewer is readable in both modes
- All form inputs are visible and usable in light mode

---

### Phase 3: Pages — Home, Usage, Chat, Files
**Scope:** High-traffic pages with confirmed critical issues.

#### Task 3.1 — `src/pages/HomePage.tsx`: Fix dashboard headings and stat values
**Description:** The dashboard heading and stat values use bare `text-white`, invisible in light mode.

**Known issues:**
- `<h2>` "Dashboard" heading: `text-white` → `text-gray-900 dark:text-white`
- `StatRow` component values: `text-white` fallback color → `text-gray-900 dark:text-white`
- Any section titles or labels using bare `text-gray-*` without light counterpart
- Card backgrounds for stats, workflow runs, etc.

**Acceptance Criteria:**
- Dashboard page title is readable in light mode
- All stat values are visible in light mode
- All card headers and sub-labels are readable

**Files:** `src/pages/HomePage.tsx`

---

#### Task 3.2 — `src/pages/UsagePage.tsx`: Fix stat value text
**Description:** Stat values use bare `text-white` (line ~772).

**Known issues:**
- `<span className="text-lg font-bold text-white">` → `text-gray-900 dark:text-white`
- Any chart labels or axis text using hardcoded colors
- Table rows and headers in usage tables

**Acceptance Criteria:**
- All usage statistics are readable in light mode
- Chart labels (if any) are visible in light mode

**Files:** `src/pages/UsagePage.tsx`

---

#### Task 3.3 — `src/pages/FilesPage.tsx`: Fix search input
**Description:** Search input uses `bg-surface border-border text-white`.

**Fixes needed:**
- Search input: `bg-surface border-border text-white placeholder:text-gray-500` → `bg-white dark:bg-surface border-light-border dark:border-border text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500`
- Any filter dropdowns or action buttons

**Acceptance Criteria:**
- File search input is visible and usable in light mode
- Text typed in the search field is visible

**Files:** `src/pages/FilesPage.tsx`

---

#### Task 3.4 — `src/pages/ChatPage.tsx`: Full audit
**Description:** Audit the full chat page for dark-only styling.

**Common fixes:**
- Conversation list items: hover states
- Conversation sidebar (if any): background and borders
- Any inline styles or hardcoded color values

**Acceptance Criteria:**
- Chat page conversation list is readable in light mode
- Active conversation highlighting works in both modes

**Files:** `src/pages/ChatPage.tsx`

---

### Phase 4: Pages — Projects, Pull Requests, Skills
**Scope:** Feature-rich pages with complex components and known issues.

#### Task 4.1 — `src/pages/ProjectDetailPage.tsx`: Full light-mode pass
**Description:** Multiple inline styles and component classes are dark-only.

**Known issues:**
- Inline action buttons: `bg-surface-lighter border-border text-gray-300` → apply light pattern
- Textarea/input fields: `bg-surface border-border text-gray-200` → `bg-white dark:bg-surface border-light-border dark:border-border text-gray-900 dark:text-gray-200`
- Section headers and metadata labels
- Progress indicators

**Acceptance Criteria:**
- Entire project detail page readable in light mode
- All inputs and interactive elements usable

**Files:** `src/pages/ProjectDetailPage.tsx`

---

#### Task 4.2 — `src/pages/PullRequestDetailPage.tsx`: Fix inputs and buttons
**Description:** Comment input and action buttons are dark-only.

**Known issues:**
- Comment textarea: `bg-surface border-border text-white` → apply input pattern
- Action/merge buttons: `bg-surface-lighter hover:bg-border text-gray-300` → apply button pattern
- PR diff viewer sections: ensure code diffs readable in light mode
- File change sections and metadata

**Acceptance Criteria:**
- Comment input is usable in light mode
- All PR action buttons are visible and readable
- PR diff (if styled) is readable in light mode

**Files:** `src/pages/PullRequestDetailPage.tsx`

---

#### Task 4.3 — `src/pages/SkillDetailPage.tsx`: Full light-mode pass
**Description:** Multiple dark-only elements confirmed.

**Known issues:**
- Tags: `bg-surface-lighter text-gray-400` → `bg-gray-100 dark:bg-surface-lighter text-gray-600 dark:text-gray-400`
- Code preview: `bg-surface-lighter border-border` → `bg-light-surface-tertiary dark:bg-surface-lighter border-light-border dark:border-border`
- Edit modal: `bg-surface border-border` → `bg-white dark:bg-surface border-light-border dark:border-border`
- Any inline form fields

**Acceptance Criteria:**
- Skill tags are visible in light mode
- Code preview block has proper light-mode background
- Edit modal is fully usable in light mode

**Files:** `src/pages/SkillDetailPage.tsx`

---

#### Task 4.4 — Remaining project/PR/skills pages: Audit and fix
**Files to process:**
- `src/pages/ProjectsPage.tsx`
- `src/pages/ProjectTaskDetailPage.tsx`
- `src/pages/PhaseDetailPage.tsx`
- `src/pages/PullRequestsPage.tsx`
- `src/pages/SkillsPage.tsx`

**Apply the standard pattern to each file.**

**Acceptance Criteria:**
- All list pages (projects, PRs, skills) render without invisible elements in light mode
- Detail pages for tasks and phases are readable

---

### Phase 5: Pages — Repos, Code, Deployments, Settings, Schedule
**Scope:** Remaining pages and specialized components.

#### Task 5.1 — `src/pages/ReposPage.tsx` and `src/pages/RepoDetailPage.tsx`: Full audit
**Description:** Repository browser and detail pages.

**Common issues to look for:**
- Search/filter inputs
- Repo cards
- Branch selectors
- CI/workflow run status indicators

**Acceptance Criteria:**
- Repos list page readable in light mode
- Repo detail page (branches, PRs, workflow runs) readable in light mode

**Files:** `src/pages/ReposPage.tsx`, `src/pages/RepoDetailPage.tsx`

---

#### Task 5.2 — `src/pages/CodePage.tsx` and terminal components: Full audit
**Description:** Code/terminal page with xterm.js terminal. The terminal itself is inherently dark (xterm.js), but surrounding UI chrome must support light mode.

**Known issues:**
- `src/components/code/TerminalView.tsx`: Status bar uses `bg-gray-800 text-gray-400` (hardcoded dark)
- Tab bar and task selector chrome
- Panel headers and labels

**Note:** The xterm.js terminal canvas itself should remain dark regardless of theme — only the surrounding UI chrome needs light-mode support. Consider adding a light-mode container that contrasts properly with the dark terminal.

**Acceptance Criteria:**
- Code page surrounding chrome (headers, tab bar, labels) is readable in light mode
- Terminal itself retains dark appearance (acceptable for terminal emulators)
- Status bar below terminal uses dark: prefix for its dark styling

**Files:** `src/pages/CodePage.tsx`, `src/components/code/TerminalPanel.tsx`, `src/components/code/TerminalView.tsx`

---

#### Task 5.3 — `src/pages/DeploymentsPage.tsx`: Full audit
**Description:** Deployment list and status indicators.

**Acceptance Criteria:**
- Deployment cards and list items are readable in light mode
- Status badges and action buttons are visible

**Files:** `src/pages/DeploymentsPage.tsx`

---

#### Task 5.4 — `src/pages/SettingsPage.tsx` and settings components: Full audit
**Files to process:**
- `src/pages/SettingsPage.tsx`
- `src/components/settings/ConnectedAccounts.tsx`
- `src/components/settings/CredentialCard.tsx`
- `src/components/settings/LlmSettingsCard.tsx`

**Common issues:**
- Form input fields: apply input light-mode pattern
- Card backgrounds
- Label text
- Toggle/checkbox controls

**Acceptance Criteria:**
- Settings page and all sub-cards fully readable and usable in light mode

---

#### Task 5.5 — `src/pages/SchedulePage.tsx`: Full audit
**Description:** Schedule/jobs list page.

**Acceptance Criteria:**
- Schedule page readable in light mode
- Job cards and status indicators visible

**Files:** `src/pages/SchedulePage.tsx`

---

#### Task 5.6 — `src/pages/TasksPage.tsx` and `src/pages/TaskDetailPage.tsx`: Full audit
**Description:** Task management pages.

**Acceptance Criteria:**
- Tasks list page readable in light mode
- Task detail page (logs, output, workspace browser) readable in light mode

**Files:** `src/pages/TasksPage.tsx`, `src/pages/TaskDetailPage.tsx`

---

#### Task 5.7 — Remaining pages: Audit and fix
**Files:**
- `src/pages/NotFoundPage.tsx`
- `src/pages/ShowcasePage.tsx`

**Acceptance Criteria:**
- 404 page is readable in light mode
- Showcase/demo page is readable in light mode

---

### Phase 6: Projects & Skills Components + Final Audit
**Scope:** Remaining component directories and final end-to-end sweep.

#### Task 6.1 — Project components: Full audit and fix
**Files:**
- `src/components/projects/NewProjectModal.tsx`
- `src/components/projects/PlanningTaskPanel.tsx`
- `src/components/projects/ProjectExecutionPanel.tsx`
- `src/components/projects/MultiStateProgressBar.tsx`

**Acceptance Criteria:**
- All project modals and panels fully usable in light mode
- Progress bars and status indicators visible in both modes

---

#### Task 6.2 — Skills components: Full audit and fix
**Files:**
- `src/components/skills/NewSkillModal.tsx`
- `src/components/skills/SkillCard.tsx`
- `src/components/skills/SkillPicker.tsx`

**Acceptance Criteria:**
- Skill cards render correctly in light mode
- Skill picker dropdown is readable and usable in light mode
- New skill modal is fully usable

---

#### Task 6.3 — File components: Full audit and fix
**Files:**
- `src/components/files/FileList.tsx`
- `src/components/files/FilePreview.tsx`
- `src/components/files/FileUpload.tsx`

**Acceptance Criteria:**
- File list items and upload dropzone visible in light mode
- File preview panel readable in light mode

---

#### Task 6.4 — Final end-to-end sweep
**Description:** Do a final pass of all 58 component/page files to catch any remaining issues. Focus on:

1. Any remaining bare `text-white` (without `dark:`)
2. Any remaining bare `bg-surface*` (without light counterpart)
3. Any remaining bare `border-border` (without `border-light-border` pair)
4. Any remaining bare `text-gray-200` or `text-gray-300` (without `dark:`)
5. Any hardcoded hex colors in className strings
6. Inline `style={{}}` props with hardcoded dark colors

**Search patterns to grep for:**
```
text-white(?!.*dark:)         # text-white without a dark: counterpart
bg-surface(?!.*dark:)         # bare surface bg
border-border(?!.*dark:)      # bare dark border
text-gray-[12]00(?!.*dark:)   # light gray text without dark counterpart
```

**Acceptance Criteria:**
- Running the app with light mode active shows no invisible text or elements on any page
- All interactive elements (buttons, inputs, dropdowns) are usable in light mode
- Dark mode still works correctly (no regression)

---

## Commit Strategy

Each phase should be committed as a unit with a descriptive message:

```
git commit -m "fix(light-mode): Phase 1 - foundation and common components"
git commit -m "fix(light-mode): Phase 2 - chat and task components"
git commit -m "fix(light-mode): Phase 3 - home, usage, files, chat pages"
git commit -m "fix(light-mode): Phase 4 - projects, pull requests, skills pages"
git commit -m "fix(light-mode): Phase 5 - repos, code, deployments, settings pages"
git commit -m "fix(light-mode): Phase 6 - project/skills/file components and final sweep"
```

---

## Quick Reference: Replacement Patterns

### Background Colors
| Dark-only (broken) | Light + Dark (correct) |
|---|---|
| `bg-surface` | `bg-white dark:bg-surface` |
| `bg-surface-light` | `bg-white dark:bg-surface-light` or `bg-light-surface-secondary dark:bg-surface-light` |
| `bg-surface-lighter` | `bg-light-surface-tertiary dark:bg-surface-lighter` |

### Text Colors
| Dark-only (broken) | Light + Dark (correct) |
|---|---|
| `text-white` | `text-gray-900 dark:text-white` |
| `text-gray-200` | `text-gray-700 dark:text-gray-200` |
| `text-gray-300` | `text-gray-600 dark:text-gray-300` |
| `text-gray-400` | `text-gray-500 dark:text-gray-400` |

### Borders
| Dark-only (broken) | Light + Dark (correct) |
|---|---|
| `border-border` | `border-light-border dark:border-border` |
| `border-border/50` | `border-light-border dark:border-border/50` |

### Interactive / Hover
| Dark-only (broken) | Light + Dark (correct) |
|---|---|
| `hover:bg-surface-lighter` | `hover:bg-gray-100 dark:hover:bg-surface-lighter` |
| `hover:bg-surface-light` | `hover:bg-gray-50 dark:hover:bg-surface-light` |
| `hover:text-gray-200` | `hover:text-gray-900 dark:hover:text-gray-200` |

### Inputs
| Dark-only (broken) | Light + Dark (correct) |
|---|---|
| `bg-surface border-border text-white` | `bg-white dark:bg-surface border-light-border dark:border-border text-gray-900 dark:text-white` |
| `placeholder:text-gray-500` | `placeholder:text-gray-400 dark:placeholder:text-gray-500` |

---

## Total File Count

- **Pages:** 22 files
- **Components:** 36 files
- **CSS:** 1 file (`index.css`)
- **Context/App:** 2 files (`App.tsx`, `ThemeContext.tsx`)

**Total: ~61 files to audit/fix across 6 phases**
