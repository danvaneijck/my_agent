# Nexus Design System

> Comprehensive design system documentation for the Nexus AI orchestration platform

## Overview

The Nexus design system provides a cohesive visual language and component library for building consistent, accessible, and beautiful user interfaces. This system supports both light and dark themes with carefully crafted design tokens.

## Brand Identity

### Brand Name: Nexus

**Tag line**: "Your AI orchestration platform"

**Brand Values**:
- Connected: Integrates multiple AI services seamlessly
- Intelligent: Powered by advanced AI capabilities
- Orchestrated: Coordinates complex workflows effortlessly
- Modular: Flexible architecture for diverse use cases
- Accessible: Powerful yet easy to use

**Visual Identity**: Modern, clean design with network/node imagery representing connections and orchestration.

---

## Color System

### Brand Colors

The primary brand color palette is based on indigo, suggesting intelligence, technology, and trust.

```css
brand-50:  #eef2ff  /* Lightest tint */
brand-100: #e0e7ff
brand-200: #c7d2fe
brand-300: #a5b4fc
brand-400: #818cf8
brand-500: #6366f1  /* Primary brand color */
brand-600: #4f46e5
brand-700: #4338ca
brand-800: #3730a3
brand-900: #312e81
brand-950: #1e1b4b  /* Darkest shade */
```

**Usage**:
- Primary actions: `brand-500`
- Hover states: `brand-600` (light mode), `brand-400` (dark mode)
- Focus rings: `brand-500`
- Brand elements: `brand-500` to `brand-700`

### Surface Colors

#### Dark Theme (Default)
```css
surface-DEFAULT: #1a1b23  /* Main background */
surface-light:   #22232d  /* Card/panel backgrounds */
surface-lighter: #2a2b37  /* Elevated surfaces, hover states */
```

#### Light Theme
```css
light-surface-DEFAULT:   #ffffff  /* Main background (white) */
light-surface-secondary: #f9fafb  /* Card/panel backgrounds */
light-surface-tertiary:  #f3f4f6  /* Elevated surfaces, hover states */
```

**Usage**:
- Use `bg-surface` for main backgrounds (auto-adapts to theme)
- Use `bg-surface-light` for card backgrounds
- Use `bg-surface-lighter` for hover states and elevated components

### Border Colors

#### Dark Theme
```css
border-DEFAULT: #33344a  /* Default borders */
border-light:   #44456a  /* Lighter borders for emphasis */
```

#### Light Theme
```css
light-border-DEFAULT: #e5e7eb  /* Default borders */
light-border-light:   #d1d5db  /* Darker borders for emphasis */
```

**Usage**:
- Use `border-border` class for theme-aware borders
- Apply `dark:border-light` for emphasis in dark mode

### Accent Colors

Interactive elements and calls to action.

```css
accent-DEFAULT: #6366f1  /* Primary interactive color */
accent-hover:   #818cf8  /* Hover state */
accent-light:   #a5b4fc  /* Light variant */
accent-dark:    #4f46e5  /* Dark variant */
```

**Usage**:
- Buttons: `bg-accent hover:bg-accent-hover`
- Links: `text-accent hover:text-accent-hover`
- Active states: `bg-accent/15 text-accent`

### Semantic Colors

Status indicators and feedback.

#### Success (Green)
```css
success-DEFAULT: #4ade80
success-light:   #86efac
success-dark:    #22c55e
success-bg:      #dcfce7  /* Background for alerts */
```

#### Warning (Yellow)
```css
warning-DEFAULT: #fbbf24
warning-light:   #fcd34d
warning-dark:    #f59e0b
warning-bg:      #fef3c7
```

#### Error (Red)
```css
error-DEFAULT: #f87171
error-light:   #fca5a5
error-dark:    #ef4444
error-bg:      #fee2e2
```

#### Info (Blue)
```css
info-DEFAULT: #60a5fa
info-light:   #93c5fd
info-dark:    #3b82f6
info-bg:      #dbeafe
```

**Usage**:
- Status badges: `bg-success/20 text-success` (semi-transparent pattern)
- Alerts: `bg-error-bg border border-error text-error-dark`
- Icons: `text-warning`, `text-success`, etc.

---

## Typography

### Font Families

**Sans-serif (UI Text)**:
```css
font-sans: Inter, system-ui, -apple-system, BlinkMacSystemFont,
           "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif
```

**Monospace (Code & Logs)**:
```css
font-mono: "JetBrains Mono", "Fira Code", "Cascadia Code",
           Consolas, Monaco, "Courier New", monospace
```

### Font Size Scale

| Class | Size | Line Height | Usage |
|-------|------|-------------|-------|
| `text-2xs` | 10px | 14px | Tiny labels, metadata |
| `text-xs` | 12px | 16px | Small text, captions |
| `text-sm` | 14px | 20px | Secondary text, table cells |
| `text-base` | 16px | 24px | Body text (default) |
| `text-lg` | 18px | 28px | Emphasized body text |
| `text-xl` | 20px | 28px | Small headings |
| `text-2xl` | 24px | 32px | Section headings |
| `text-3xl` | 30px | 36px | Page headings |
| `text-4xl` | 36px | 40px | Hero headings |
| `text-5xl` | 48px | 48px | Display text |
| `text-6xl` | 60px | 60px | Large display |
| `text-7xl` | 72px | 72px | Hero display |

### Font Weights

| Class | Weight | Usage |
|-------|--------|-------|
| `font-thin` | 100 | Decorative |
| `font-extralight` | 200 | Decorative |
| `font-light` | 300 | Subtle emphasis |
| `font-normal` | 400 | Body text (default) |
| `font-medium` | 500 | Navigation, labels |
| `font-semibold` | 600 | Headings, emphasis |
| `font-bold` | 700 | Strong headings |
| `font-extrabold` | 800 | Very strong emphasis |
| `font-black` | 900 | Maximum emphasis |

### Typography Examples

```tsx
// Page heading
<h1 className="text-3xl font-bold text-white">Dashboard</h1>

// Section heading
<h2 className="text-xl font-semibold text-gray-200">Recent Activity</h2>

// Body text
<p className="text-base text-gray-300">Your AI orchestration platform.</p>

// Small label
<span className="text-xs text-gray-500">Updated 5m ago</span>

// Code snippet
<code className="font-mono text-sm">npm install</code>
```

---

## Spacing

### 8px Base System

Spacing follows an 8px base unit system for consistent rhythm and alignment.

| Class | Size | Pixels | Usage |
|-------|------|--------|-------|
| `0` | 0 | 0px | No spacing |
| `0.5` | 0.125rem | 2px | Hairline gaps |
| `1` | 0.25rem | 4px | Tiny spacing |
| `1.5` | 0.375rem | 6px | Small spacing |
| `2` | 0.5rem | 8px | **Base unit** |
| `3` | 0.75rem | 12px | Moderate spacing |
| `4` | 1rem | 16px | Standard spacing (2x base) |
| `6` | 1.5rem | 24px | Large spacing (3x base) |
| `8` | 2rem | 32px | Extra large (4x base) |
| `10` | 2.5rem | 40px | Section spacing (5x base) |
| `12` | 3rem | 48px | Page section (6x base) |
| `16` | 4rem | 64px | Large page section (8x base) |

**Guidelines**:
- Use multiples of base unit (8px) for major spacing
- Use half-increments (4px, 12px) for fine-tuning
- Prefer `gap-4` over individual margins for flex/grid layouts
- Use `space-y-4` for vertical rhythm in stacks

### Spacing Examples

```tsx
// Card padding
<div className="p-4">Content</div>  {/* 16px padding */}

// Section spacing
<section className="py-12 px-6">Section</section>  {/* 48px vertical, 24px horizontal */}

// Stack spacing
<div className="space-y-6">
  <p>Item 1</p>
  <p>Item 2</p>
</div>

// Grid gap
<div className="grid grid-cols-2 gap-4">...</div>
```

---

## Shadows

### Shadow Scale

| Class | Usage |
|-------|-------|
| `shadow-sm` | Subtle elevation (buttons, inputs) |
| `shadow` | Default elevation (cards) |
| `shadow-md` | Medium elevation (dropdowns) |
| `shadow-lg` | High elevation (modals) |
| `shadow-xl` | Very high elevation (popovers) |
| `shadow-2xl` | Maximum elevation (large modals) |
| `shadow-inner` | Inset shadow (pressed states) |
| `shadow-none` | No shadow |

### Colored Elevation (Light Mode)

Special shadows with brand color tint for enhanced elevation in light mode:

- `shadow-elevation-sm`: Subtle brand-tinted shadow
- `shadow-elevation-md`: Medium brand-tinted shadow
- `shadow-elevation-lg`: Strong brand-tinted shadow

**Usage**:
```tsx
// Light mode card with elevation
<div className="bg-white shadow-elevation-md rounded-xl">
  Card content
</div>

// Dark mode card (standard shadow)
<div className="dark:bg-surface-light dark:shadow-lg rounded-xl">
  Card content
</div>
```

---

## Border Radius

Consistent rounding for visual cohesion.

| Class | Size | Usage |
|-------|------|-------|
| `rounded-none` | 0 | Sharp corners |
| `rounded-sm` | 4px | Minimal rounding |
| `rounded` / `rounded-md` | 8px | **Buttons, inputs** (default) |
| `rounded-lg` | 12px | **Cards, panels** |
| `rounded-xl` | 16px | **Modals, large cards** |
| `rounded-2xl` | 24px | Hero sections |
| `rounded-3xl` | 32px | Large hero elements |
| `rounded-full` | 9999px | Pills, avatars |

**Guidelines**:
- Buttons and inputs: `rounded` (8px)
- Cards: `rounded-lg` or `rounded-xl` (12px or 16px)
- Modals: `rounded-xl` (16px)
- Status badges: `rounded-full`

---

## Animations

### Duration Scale

| Class | Duration | Usage |
|-------|----------|-------|
| `duration-fast` | 150ms | Quick interactions |
| `duration` / `duration-normal` | 200ms | **Default transitions** |
| `duration-medium` | 300ms | Page transitions |
| `duration-slow` | 500ms | Complex animations |

### Timing Functions

| Class | Easing | Usage |
|-------|--------|-------|
| `ease-linear` | Linear | Continuous animations |
| `ease-in` | Ease in | Accelerating |
| `ease-out` | Ease out | **Default** (decelerating) |
| `ease-in-out` | Ease in-out | Smooth start/end |
| `ease-out-expo` | Expo out | Snappy, polished |
| `ease-in-out-expo` | Expo in-out | Dramatic |
| `bounce` | Bounce | Playful |

### Built-in Animations

| Class | Animation | Usage |
|-------|-----------|-------|
| `animate-fade-in` | Fade in 200ms | Page loads |
| `animate-fade-out` | Fade out 200ms | Dismissals |
| `animate-slide-up` | Slide up + fade 300ms | Modals, toasts |
| `animate-slide-down` | Slide down + fade 300ms | Dropdowns |
| `animate-slide-left` | Slide left + fade 300ms | Side panels |
| `animate-slide-right` | Slide right + fade 300ms | Side panels |
| `animate-shimmer` | Shimmer 2s infinite | Loading skeletons |
| `animate-spin` | Rotate 1s infinite | Spinners |
| `animate-pulse` | Pulse 2s infinite | Loading states |

### Animation Examples

```tsx
// Fade in on mount
<div className="animate-fade-in">Content</div>

// Slide up modal
<div className="animate-slide-up">Modal</div>

// Loading skeleton
<div className="bg-gray-200 animate-shimmer">Loading...</div>

// Custom transition
<button className="transition-all duration-200 hover:scale-105">
  Hover me
</button>
```

### Accessibility: Reduced Motion

Always respect user preferences for reduced motion:

```tsx
<div className="motion-reduce:transition-none motion-reduce:animate-none">
  Animated content
</div>
```

---

## Framer Motion Animation System

### Animation Variants

The design system includes centralized animation variants using Framer Motion for consistent, performant animations. All variants are defined in `src/utils/animations.ts`.

#### Page Transitions

```tsx
import { motion } from "framer-motion";
import { pageVariants } from "@/utils/animations";

<motion.div
  initial="initial"
  animate="animate"
  exit="exit"
  variants={pageVariants}
>
  Page content
</motion.div>
```

**Behavior**: Fade in with subtle 20px upward slide on enter (200ms), fade out with 10px downward slide on exit (150ms).

#### Stagger Animations

For lists and card grids that animate in sequence:

```tsx
import { motion } from "framer-motion";
import { staggerContainerVariants, staggerItemVariants } from "@/utils/animations";

<motion.div variants={staggerContainerVariants} initial="initial" animate="animate">
  {items.map((item) => (
    <motion.div key={item.id} variants={staggerItemVariants}>
      {item.content}
    </motion.div>
  ))}
</motion.div>
```

**Available stagger patterns**:
- `staggerContainerVariants` + `staggerItemVariants`: Cards and grids (50ms stagger)
- `listContainerVariants` + `listItemVariants`: Lists (30ms stagger)

#### Modal/Dialog Animations

```tsx
import { motion, AnimatePresence } from "framer-motion";
import { modalVariants } from "@/utils/animations";

<AnimatePresence>
  {isOpen && (
    <motion.div
      variants={modalVariants}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      Modal content
    </motion.div>
  )}
</AnimatePresence>
```

**Behavior**: Scale from 95% to 100% with fade (200ms).

#### Button Scale Effects

```tsx
import { motion } from "framer-motion";
import { scaleVariants } from "@/utils/animations";

<motion.button
  variants={scaleVariants}
  initial="rest"
  whileHover="hover"
  whileTap="tap"
>
  Click me
</motion.button>
```

**Behavior**: Scale to 102% on hover, 98% on tap.

#### Card Hover Effects

```tsx
import { motion } from "framer-motion";
import { cardHoverVariants } from "@/utils/animations";

<motion.div
  variants={cardHoverVariants}
  initial="rest"
  whileHover="hover"
>
  Card content
</motion.div>
```

**Behavior**: Lift by 2px with enhanced shadow on hover (200ms).

#### Toast Notifications

```tsx
import { motion } from "framer-motion";
import { toastVariants } from "@/utils/animations";

<motion.div variants={toastVariants} initial="initial" animate="animate" exit="exit">
  Toast message
</motion.div>
```

**Behavior**: Slide in from top-right, slide out to the right.

### Accessibility: Reduced Motion

All animation variants automatically respect the user's `prefers-reduced-motion` system setting. When reduced motion is preferred, animations are disabled (duration: 0).

```tsx
import { prefersReducedMotion, getTransition } from "@/utils/animations";

// Check reduced motion preference
if (prefersReducedMotion()) {
  // Skip animation
}

// Or use getTransition helper
const transition = getTransition({
  duration: 0.3,
  ease: "easeOut"
}); // Returns { duration: 0 } if reduced motion is preferred
```

### Spring Physics

For natural, bouncy animations (sidebar slide, mobile menu):

```tsx
<motion.div
  animate={{ x: isOpen ? 0 : "-100%" }}
  transition={{
    type: "spring",
    damping: 30,
    stiffness: 300
  }}
>
  Sidebar content
</motion.div>
```

**Common spring configurations**:
- **Snappy**: `damping: 30, stiffness: 300` (sidebar, drawers)
- **Smooth**: `damping: 20, stiffness: 100` (progress bars)
- **Bouncy**: `damping: 15, stiffness: 200` (playful interactions)

### Custom Easing Curves

```tsx
import { easings } from "@/utils/animations";

<motion.div
  animate={{ opacity: 1 }}
  transition={{
    duration: 0.3,
    ease: easings.easeOut // [0.0, 0.0, 0.2, 1]
  }}
>
  Content
</motion.div>
```

**Available easings**:
- `easeOut`: [0.0, 0.0, 0.2, 1] - Default, decelerating
- `easeIn`: [0.4, 0.0, 1, 1] - Accelerating
- `easeInOut`: [0.4, 0.0, 0.2, 1] - Smooth start and end
- `sharp`: [0.4, 0.0, 0.6, 1] - Quick, snappy

---

## Component Library

### Button Component

Pre-built animated button with scale effects and multiple variants.

**Location**: `src/components/common/Button.tsx`

```tsx
import Button from "@/components/common/Button";

// Primary button
<Button variant="primary" size="md" onClick={handleClick}>
  Save Changes
</Button>

// Secondary button
<Button variant="secondary" size="sm">
  Cancel
</Button>

// Ghost button
<Button variant="ghost" size="lg">
  Learn More
</Button>

// Danger button
<Button variant="danger" disabled>
  Delete
</Button>
```

**Variants**:
- `primary`: Accent background with white text
- `secondary`: Surface background with border
- `ghost`: Transparent background, text only
- `danger`: Red background, destructive actions

**Sizes**:
- `sm`: Small (px-3 py-1.5 text-xs)
- `md`: Medium (px-4 py-2 text-sm) - Default
- `lg`: Large (px-6 py-3 text-base)

**Features**:
- Automatic hover/tap scale animations
- Disabled state support
- Focus ring accessibility

### Card Component

Pre-built animated card with hover lift effect.

**Location**: `src/components/common/Card.tsx`

```tsx
import Card from "@/components/common/Card";

// Hoverable card
<Card hoverable>
  <div className="p-6">
    <h3 className="font-semibold mb-2">Card Title</h3>
    <p className="text-sm text-gray-400">Card content</p>
  </div>
</Card>

// Clickable card
<Card onClick={() => navigate('/details')} hoverable>
  Clickable content
</Card>

// Static card (no hover)
<Card hoverable={false}>
  Static content
</Card>
```

**Features**:
- Automatic hover lift animation (2px upward)
- Enhanced shadow on hover
- Optional click handler
- Theme-aware styling

### StatusBadge Component

Status indicator with semantic colors and animations.

**Location**: `src/components/common/StatusBadge.tsx`

```tsx
import StatusBadge from "@/components/common/StatusBadge";

<StatusBadge status="completed" />
<StatusBadge status="running" stale />
<StatusBadge status="failed" />
```

**Available statuses**:
- `queued`: Blue
- `running`: Yellow (with pulse animation)
- `completed`: Green
- `failed`: Red
- `cancelled`: Gray
- `awaiting_input`: Purple (with pulse animation)
- `timed_out`: Orange

**Features**:
- Pulse animation for active states
- Stale indicator for long-running tasks
- Semantic color coding
- Rounded pill design

### Skeleton Component

Loading skeleton with shimmer effect.

**Location**: `src/components/common/Skeleton.tsx`

```tsx
import Skeleton from "@/components/common/Skeleton";

<Skeleton className="h-6 w-48 mb-2" /> {/* Text line */}
<Skeleton className="h-32 w-full" />   {/* Content block */}
```

**Features**:
- Shimmer animation
- Theme-aware colors
- Respects reduced motion preference

### Spinner Component

Loading spinner for inline loading states.

**Location**: `src/components/common/Spinner.tsx`

```tsx
import Spinner from "@/components/common/Spinner";

<Spinner size="sm" />  {/* 16px */}
<Spinner size="md" />  {/* 24px - default */}
<Spinner size="lg" />  {/* 32px */}
```

**Features**:
- Smooth rotation animation
- Accent color
- Multiple sizes

### LoadingScreen Component

Full-screen branded loading state.

**Location**: `src/components/common/LoadingScreen.tsx`

```tsx
import LoadingScreen from "@/components/common/LoadingScreen";

<LoadingScreen />
```

**Features**:
- Nexus logo with pulse animation
- Animated progress bar
- Gradient background
- Theme-aware styling

### Modal Component

Animated modal dialog with backdrop.

**Location**: `src/components/common/Modal.tsx`

```tsx
import Modal from "@/components/common/Modal";

<Modal
  isOpen={isOpen}
  onClose={() => setIsOpen(false)}
  title="Confirm Action"
  size="md"
>
  <p>Modal content</p>
  <Button onClick={() => setIsOpen(false)}>Close</Button>
</Modal>
```

**Sizes**:
- `sm`: 400px max width
- `md`: 500px max width (default)
- `lg`: 600px max width
- `xl`: 800px max width

**Features**:
- Backdrop with click-to-close
- Scale animation on enter/exit
- Escape key support
- Focus trap
- Accessible close button

### EmptyState Component

Placeholder for empty data states.

**Location**: `src/components/common/EmptyState.tsx`

```tsx
import EmptyState from "@/components/common/EmptyState";
import { Inbox } from "lucide-react";

<EmptyState
  icon={Inbox}
  title="No messages"
  description="Your inbox is empty"
  action={
    <Button variant="primary" onClick={handleCreate}>
      Compose Message
    </Button>
  }
/>
```

**Features**:
- Icon support
- Title and description
- Optional CTA button
- Centered layout

### ProgressBar Component

Animated progress indicator.

**Location**: `src/components/common/ProgressBar.tsx`

```tsx
import ProgressBar from "@/components/common/ProgressBar";

<ProgressBar progress={75} />
```

**Features**:
- Spring physics animation
- Accent color
- Percentage-based (0-100)

### ThemeToggle Component

Light/dark mode switcher.

**Location**: `src/components/common/ThemeToggle.tsx`

```tsx
import ThemeToggle from "@/components/common/ThemeToggle";

<ThemeToggle />
```

**Features**:
- Icon-based (Sun/Moon)
- Persists to localStorage
- Smooth transitions

### SkipToContent Component

Accessibility skip link for keyboard navigation.

**Location**: `src/components/common/SkipToContent.tsx`

```tsx
import SkipToContent from "@/components/common/SkipToContent";

<SkipToContent />
```

**Features**:
- Hidden until focused
- Jumps to main content
- WCAG 2.1 AA compliance

---

## Component Patterns

### Buttons

```tsx
// Primary button
<button className="bg-accent hover:bg-accent-hover text-white px-4 py-2 rounded-lg font-medium transition-colors">
  Primary Action
</button>

// Secondary button
<button className="bg-surface-light hover:bg-surface-lighter text-gray-200 px-4 py-2 rounded-lg font-medium transition-colors border border-border">
  Secondary Action
</button>

// Ghost button
<button className="text-accent hover:bg-accent/10 px-4 py-2 rounded-lg font-medium transition-colors">
  Tertiary Action
</button>
```

### Cards

```tsx
// Dark theme card
<div className="bg-surface-light border border-border rounded-xl p-6">
  Card content
</div>

// Light theme card
<div className="bg-white border border-light-border rounded-xl p-6 shadow-md">
  Card content
</div>

// Theme-aware card
<div className="bg-surface-light dark:bg-surface-light border border-border dark:border-border rounded-xl p-6">
  Adaptive card
</div>
```

### Status Badges

```tsx
// Success badge
<span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-success/20 text-success">
  Active
</span>

// Warning badge
<span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-warning/20 text-warning">
  Pending
</span>

// Error badge
<span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-error/20 text-error">
  Failed
</span>
```

### Form Inputs

```tsx
// Text input
<input
  type="text"
  className="w-full px-3 py-2 bg-surface-light border border-border rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-colors"
  placeholder="Enter text..."
/>

// Select
<select className="w-full px-3 py-2 bg-surface-light border border-border rounded-lg text-gray-200 focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-colors">
  <option>Option 1</option>
  <option>Option 2</option>
</select>
```

---

## Theme System

### Dark Mode (Default)

Dark mode is the default theme, optimized for reduced eye strain and focus.

**Background hierarchy**:
1. `bg-surface` (#1a1b23) - Page background
2. `bg-surface-light` (#22232d) - Cards, panels
3. `bg-surface-lighter` (#2a2b37) - Elevated elements, hover

**Text hierarchy**:
1. `text-white` - Primary headings
2. `text-gray-200` - Body text
3. `text-gray-400` - Secondary text
4. `text-gray-500` - Disabled, metadata

### Light Mode

Light mode provides a bright, clean aesthetic for daytime use.

**Background hierarchy**:
1. `bg-light-surface` (#ffffff) - Page background
2. `bg-light-surface-secondary` (#f9fafb) - Cards, panels
3. `bg-light-surface-tertiary` (#f3f4f6) - Elevated elements, hover

**Text hierarchy**:
1. `text-gray-900` - Primary headings
2. `text-gray-700` - Body text
3. `text-gray-500` - Secondary text
4. `text-gray-400` - Disabled, metadata

### Implementing Dark Mode

Use the `dark:` variant for dark mode styles:

```tsx
<div className="bg-white dark:bg-surface-light text-gray-900 dark:text-gray-100">
  Theme-aware content
</div>
```

---

## Accessibility Guidelines

### Color Contrast

All text meets WCAG AA standards (4.5:1 for body text, 3:1 for large text).

**Dark mode**:
- Primary text: white on #1a1b23 (21:1) ✅
- Body text: #e5e7eb on #1a1b23 (14:1) ✅
- Secondary text: #9ca3af on #1a1b23 (7:1) ✅

**Light mode**:
- Primary text: #111827 on white (18:1) ✅
- Body text: #374151 on white (12:1) ✅
- Secondary text: #6b7280 on white (5.4:1) ✅

### Keyboard Navigation

- All interactive elements must be keyboard accessible
- Focus states must be visible: `focus:ring-2 focus:ring-accent`
- Use semantic HTML (`<button>`, `<a>`, etc.)
- Implement skip-to-content links

### Screen Readers

- Use ARIA labels where needed: `aria-label="Close dialog"`
- Ensure logical heading hierarchy (h1 → h2 → h3)
- Provide alt text for images
- Announce dynamic content changes

### Reduced Motion

Respect user preferences:

```tsx
<div className="transition-transform motion-reduce:transition-none">
  Animated element
</div>
```

---

## Grid System

Use Tailwind's built-in grid for layouts:

```tsx
// Responsive grid
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  <div>Column 1</div>
  <div>Column 2</div>
  <div>Column 3</div>
</div>

// Dashboard layout
<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
  <Card>Left</Card>
  <Card>Right</Card>
</div>
```

---

## Brand Assets

### Logo Files

The Nexus brand identity includes the following logo assets:

**Logo Icon** (`/public/logo-icon.svg`):
- Hexagonal network node design
- Used in sidebar, loading screens, favicons
- Minimum size: 24×24px
- Clear space: 8px on all sides

**Usage**:
```tsx
// Sidebar brand
<img src="/logo-icon.svg" alt="Nexus" className="h-7 w-7" />

// Loading screen
<img src="/logo-icon.svg" alt="Nexus" className="h-16 w-16" />

// Favicon (already configured in index.html)
```

### Logo Usage Guidelines

**Do's** ✅:
- Maintain original aspect ratio
- Provide adequate clear space (minimum 8px)
- Use on contrasting backgrounds
- Ensure minimum size of 24×24px for clarity

**Don'ts** ❌:
- Don't distort or stretch the logo
- Don't rotate the logo
- Don't apply filters or effects
- Don't change the logo colors
- Don't place on busy backgrounds

### Brand Name

**Official name**: Nexus

**Usage**:
- Always capitalize: "Nexus" (not "nexus" or "NEXUS")
- Tag line: "Your AI orchestration platform"
- Full brand mark: Nexus logo + "Nexus" wordmark in semibold

```tsx
// Header branding
<div className="flex items-center gap-2.5">
  <img src="/logo-icon.svg" alt="Nexus" className="h-7 w-7" />
  <span className="text-lg font-semibold text-gray-900 dark:text-white">
    Nexus
  </span>
</div>
```

### Favicons

Configured in `index.html` with multiple sizes for different platforms:

- `/favicon.svg` - SVG favicon (modern browsers)
- `/favicon.ico` - ICO fallback (legacy browsers)
- `/logo-192.png` - PWA icon 192×192
- `/logo-512.png` - PWA icon 512×512

### Social Media Assets

When creating social media graphics or external materials:

- **Primary color**: `#6366f1` (brand-500)
- **Background**: Dark (`#1a1b23`) or white
- **Typography**: Inter font family
- **Tone**: Modern, intelligent, connected

---

## Code Splitting & Performance

### Route-Based Code Splitting

All pages are lazy-loaded to optimize initial bundle size:

**Configuration** (`src/App.tsx`):
```tsx
import { lazy, Suspense } from "react";
import LoadingScreen from "@/components/common/LoadingScreen";

// Lazy load pages
const HomePage = lazy(() => import("@/pages/HomePage"));
const TasksPage = lazy(() => import("@/pages/TasksPage"));
const ChatPage = lazy(() => import("@/pages/ChatPage"));

// Wrap routes in Suspense
<Suspense fallback={<LoadingScreen />}>
  <Routes>
    <Route path="/" element={<HomePage />} />
    <Route path="/tasks" element={<TasksPage />} />
    <Route path="/chat" element={<ChatPage />} />
  </Routes>
</Suspense>
```

### Vendor Chunk Splitting

Dependencies are split into logical chunks for optimal caching:

**Configuration** (`vite.config.ts`):
```ts
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        "react-vendor": ["react", "react-dom", "react-router-dom"],
        "framer-motion": ["framer-motion"],
        "markdown": ["react-markdown", "remark-gfm"],
        "lucide": ["lucide-react"],
      },
    },
  },
  chunkSizeWarningLimit: 1000,
}
```

**Benefits**:
- Shared vendor code cached across pages
- Individual page chunks: 0.2 KB - 27 KB
- Total chunks: 38+ (optimal granularity)
- No large chunk warnings

### Performance Best Practices

1. **Image Optimization**:
   - Use SVG for logos and icons
   - Lazy load images with `loading="lazy"`
   - Provide appropriate sizes with `srcset`

2. **Animation Performance**:
   - Prefer `transform` and `opacity` (GPU-accelerated)
   - Avoid animating `width`, `height`, or `top`/`left`
   - Use `will-change` sparingly

3. **Bundle Size**:
   - Monitor with `npm run build`
   - Analyze with `npm run build -- --analyze`
   - Tree-shake unused code

4. **Caching Strategy**:
   - Vendor chunks: Long-term cache (hash-based)
   - Page chunks: Per-route invalidation
   - Assets: Immutable caching

---

## Responsive Design Guidelines

### Breakpoints

Tailwind default breakpoints:

| Breakpoint | Min Width | Usage |
|------------|-----------|-------|
| `sm` | 640px | Small tablets |
| `md` | 768px | Tablets, small laptops |
| `lg` | 1024px | Laptops, desktops |
| `xl` | 1280px | Large desktops |
| `2xl` | 1536px | Extra large screens |

### Mobile-First Approach

Always design for mobile first, then enhance for larger screens:

```tsx
// ✅ Mobile-first (correct)
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
  Content
</div>

// ❌ Desktop-first (avoid)
<div className="grid grid-cols-3 lg:grid-cols-2 md:grid-cols-1">
  Content
</div>
```

### Touch Target Sizing

All interactive elements must meet minimum touch target size:

**WCAG 2.1 Level AA requirement**: 44×44px minimum

```tsx
// ✅ Adequate touch target
<button className="p-2.5 rounded"> {/* 44×44px */}
  <Icon size={20} />
</button>

// ❌ Too small
<button className="p-1 rounded"> {/* 32×32px */}
  <Icon size={14} />
</button>
```

### Responsive Typography

Use responsive text sizes for optimal readability:

```tsx
// Page heading
<h1 className="text-2xl md:text-3xl lg:text-4xl font-bold">
  Dashboard
</h1>

// Body text (no change needed, base size is readable)
<p className="text-base">Content</p>
```

### Mobile Navigation

The sidebar uses a mobile-optimized drawer pattern:

- **Desktop** (`md:`): Persistent sidebar (224px width)
- **Mobile** (`<md`): Slide-out drawer with backdrop
- **Animation**: Spring physics for natural feel
- **Accessibility**: Focus trap when open, Escape key to close

```tsx
// Mobile overlay backdrop
<motion.div
  className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm md:hidden"
  onClick={onClose}
/>

// Sidebar with responsive positioning
<motion.aside
  className="fixed md:static inset-y-0 left-0 z-40 w-56 md:translate-x-0"
  animate={{ x: open ? 0 : "-100%" }}
/>
```

### Responsive Patterns

**Grid Layouts**:
```tsx
// 1 column → 2 columns → 3 columns
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {items.map(item => <Card key={item.id}>{item.content}</Card>)}
</div>
```

**Flex Layouts**:
```tsx
// Stack vertically on mobile, horizontally on desktop
<div className="flex flex-col md:flex-row gap-4">
  <div>Sidebar content</div>
  <div className="flex-1">Main content</div>
</div>
```

**Conditional Rendering**:
```tsx
// Show different UI based on screen size
<div>
  <span className="hidden md:inline">Full description</span>
  <span className="md:hidden">Short</span>
</div>
```

---

## Best Practices

### Do's ✅

- Use semantic color tokens (e.g., `bg-accent`, not `bg-indigo-500`)
- Follow the 8px spacing system
- Respect theme context (use `dark:` variants)
- Maintain consistent border radius across similar components
- Use transitions for interactive elements
- Test in both light and dark modes
- Ensure adequate color contrast
- Provide keyboard navigation

### Don'ts ❌

- Don't use arbitrary color values (e.g., `bg-[#123456]`)
- Don't skip spacing units (e.g., use `gap-4`, not `gap-[17px]`)
- Don't mix border radius sizes randomly
- Don't forget hover/focus states on interactive elements
- Don't rely solely on color to convey information
- Don't animate elements excessively
- Don't ignore accessibility requirements

---

## Resources

- **Tailwind CSS Documentation**: https://tailwindcss.com/docs
- **Color Contrast Checker**: https://webaim.org/resources/contrastchecker/
- **Inter Font**: https://fonts.google.com/specimen/Inter
- **Lucide Icons**: https://lucide.dev/

---

## Changelog

### v1.1.0 (2026-02-16)
- Added Framer Motion animation system documentation
- Documented all pre-built components (Button, Card, Modal, etc.)
- Added brand asset usage guidelines
- Documented code splitting and performance optimization
- Added responsive design patterns and mobile navigation
- Enhanced accessibility guidelines with touch target requirements
- Added component library reference

### v1.0.0 (2026-02-16)
- Initial design system documentation
- Comprehensive color tokens for light/dark themes
- Typography scale with Inter font
- 8px spacing system
- Shadow and border radius tokens
- Animation utilities
- Component patterns and examples
- Accessibility guidelines
