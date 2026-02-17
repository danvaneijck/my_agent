# Implementation Plan: Project Planner UI Improvements

## Overview
This plan addresses two specific issues with the project planner module portal UI:
1. **Multi-colored progress bars**: Progress bars should show different task states (todo, doing, in_review, done) with different colors and proportional widths
2. **Phase ordering consistency**: Phases should always be rendered in correct order (by `order_index`), starting with phase 1 at the top

## Current Issues Analysis

### Issue 1: Progress Bars
**Location**: `ProjectsPage.tsx` and `ProjectDetailPage.tsx`

**Current behavior**:
- ProjectsPage (lines 47-58): Shows a single-color progress bar based only on done/total tasks
- ProjectDetailPage PhaseRow (lines 66-74): Shows a single-color progress bar based only on done/total tasks for each phase

**Problem**: The progress bars don't visualize the different task states (todo, doing, in_review, done, failed) with different colors and proportional segments.

### Issue 2: Phase Ordering
**Location**: `ProjectDetailPage.tsx` (lines 450-466)

**Current behavior**: Phases are rendered in the order they come from the backend API.

**Root cause investigation**:
- Backend query in `tools.py:252-256` uses `.order_by(ProjectPhase.order_index)` ✓ Correct
- The data is properly ordered when sent from backend
- Frontend doesn't re-sort or modify the order
- **Likely cause**: The issue may be intermittent due to async operations or state updates, but adding explicit sorting on the frontend will ensure consistency

## Implementation Plan

### Task 1: Create Multi-Segment Progress Bar Component

**File**: `agent/portal/frontend/src/components/projects/MultiStateProgressBar.tsx` (NEW)

**Purpose**: Create a reusable component that displays a segmented progress bar showing different task states with different colors.

**Implementation details**:
- Accept `task_counts` object with optional properties: `todo`, `doing`, `in_review`, `done`, `failed`
- Calculate total and percentages for each state
- Render segments horizontally with widths proportional to their count
- Use color scheme:
  - `todo`: gray (`bg-gray-500`)
  - `doing`: yellow (`bg-yellow-500`)
  - `in_review`: blue (`bg-blue-500`)
  - `done`: green (`bg-green-500`)
  - `failed`: red (`bg-red-500`)
- Handle edge cases: empty counts, zero total
- Add tooltips showing exact counts on hover

**Props interface**:
```typescript
interface MultiStateProgressBarProps {
  task_counts: {
    todo?: number;
    doing?: number;
    in_review?: number;
    done?: number;
    failed?: number;
  };
  height?: string; // Tailwind class, default "h-1.5"
  showLabels?: boolean; // Show text labels below
}
```

### Task 2: Update ProjectsPage to Use Multi-State Progress Bar

**File**: `agent/portal/frontend/src/pages/ProjectsPage.tsx`

**Changes**:
1. Import the new `MultiStateProgressBar` component
2. Replace the `ProjectCard` progress bar section (lines 47-71)
3. Pass `project.task_counts` to the new component
4. Keep the text summary of tasks (done/total and state counts) but move the single-color bar to multi-state bar
5. Maintain the existing layout and styling

**Modified section**: Lines 47-71 in the `ProjectCard` component

### Task 3: Update ProjectDetailPage Phase Progress Bars

**File**: `agent/portal/frontend/src/pages/ProjectDetailPage.tsx`

**Changes**:
1. Import the new `MultiStateProgressBar` component
2. Replace the `PhaseRow` progress bar section (lines 66-95)
3. Pass `phase.task_counts` to the new component
4. Keep the text summary showing counts by state
5. Maintain existing layout and styling

**Modified section**: Lines 66-95 in the `PhaseRow` component

**Additionally**: Update the overall progress bar (lines 357-366) to use multi-state visualization

### Task 4: Ensure Phase Ordering Consistency

**File**: `agent/portal/frontend/src/pages/ProjectDetailPage.tsx`

**Changes**:
1. Add explicit sorting when rendering phases (line 451)
2. Sort by `order_index` before mapping to ensure consistent ordering
3. Add defensive check to handle missing `order_index`

**Modified section**:
```typescript
// Before (line 451):
{project.phases.map((phase) => (

// After:
{[...project.phases]
  .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
  .map((phase) => (
```

**Note**: The spread operator `[...]` creates a shallow copy to avoid mutating the original array.

### Task 5: Update TypeScript Types (if needed)

**File**: `agent/portal/frontend/src/types/index.ts`

**Verification**: Check that `ProjectTaskCounts` interface (lines 266-272) includes all needed properties. Current interface looks complete:
- `todo?: number`
- `doing?: number`
- `in_review?: number`
- `done?: number`
- `failed?: number`

No changes needed to types.

### Task 6: Test Multi-State Progress Bar Edge Cases

**Testing scenarios**:
1. Project with all tasks in one state (e.g., all "todo")
2. Project with no tasks (empty counts)
3. Project with tasks distributed across all states
4. Very small counts (e.g., 1 task) to ensure visibility
5. Large counts to ensure proper percentage calculations
6. Undefined or null task_counts

### Task 7: Verify Phase Ordering

**Testing scenarios**:
1. Create a project with 5+ phases
2. Verify phases render in correct order (1, 2, 3, 4, 5...)
3. Refresh page multiple times to check consistency
4. Check ordering after phase status updates
5. Check ordering after task status updates

## File Summary

### Files to Create
1. `agent/portal/frontend/src/components/projects/MultiStateProgressBar.tsx` - New reusable progress bar component

### Files to Modify
1. `agent/portal/frontend/src/pages/ProjectsPage.tsx` - Update ProjectCard to use multi-state progress bars
2. `agent/portal/frontend/src/pages/ProjectDetailPage.tsx` - Update PhaseRow and overall progress to use multi-state bars, add phase sorting

### Files to Read (no changes)
1. `agent/portal/frontend/src/types/index.ts` - Verify types are adequate (they are)

## Implementation Order

1. **First**: Create `MultiStateProgressBar.tsx` component with full functionality and styling
2. **Second**: Update `ProjectsPage.tsx` to integrate the new component
3. **Third**: Update `ProjectDetailPage.tsx` to integrate the new component and add phase sorting
4. **Fourth**: Manual testing of all scenarios

## Color Scheme Reference

Based on existing code patterns in the UI:

```typescript
todo: "bg-gray-500"      // Gray for pending/not started
doing: "bg-yellow-500"   // Yellow for in progress (already used in UI)
in_review: "bg-blue-500" // Blue for in review (already used in UI)
done: "bg-green-500"     // Green for completed (already used in UI)
failed: "bg-red-500"     // Red for failed (already used in UI)
```

These colors match the existing badge colors used throughout the project planner UI for consistency.

## Success Criteria

1. ✅ Progress bars show segmented visualization with different colors for each task state
2. ✅ Segment widths are proportional to the number of tasks in each state
3. ✅ Progress bars work correctly on both ProjectsPage (project cards) and ProjectDetailPage (phase rows and overall progress)
4. ✅ Phases are always rendered in correct order by `order_index`
5. ✅ Phase ordering remains consistent across page refreshes and state updates
6. ✅ All edge cases are handled gracefully (no tasks, undefined counts, etc.)
7. ✅ UI maintains existing layout and styling consistency

## Notes

- The backend already correctly orders phases by `order_index`, but adding frontend sorting provides an additional layer of safety
- The multi-state progress bar component is designed to be reusable across the application
- Colors chosen match the existing UI design system used in the project planner module
- The implementation maintains backward compatibility with existing data structures
