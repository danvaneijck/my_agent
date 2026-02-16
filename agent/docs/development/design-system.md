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

### v1.0.0 (2026-02-16)
- Initial design system documentation
- Comprehensive color tokens for light/dark themes
- Typography scale with Inter font
- 8px spacing system
- Shadow and border radius tokens
- Animation utilities
- Component patterns and examples
- Accessibility guidelines
