# ModuFlow Brand Guidelines

## Overview

ModuFlow is a modular LLM agent framework that empowers developers to build intelligent, task-orchestrating AI assistants. Our brand identity communicates professionalism, modularity, and technical sophistication while remaining approachable and modern.

**Brand Name:** ModuFlow
**Tagline:** Your Modular AI Agent Framework
**Domain:** agent.danvan.xyz

## Brand Personality

- **Professional yet approachable** - Sophisticated without being intimidating
- **Modular and flexible** - Emphasizing the plug-and-play architecture
- **Tech-forward** - Cutting-edge without being overly complex
- **Reliable and trustworthy** - Enterprise-grade quality with developer-friendly experience

## Logo Usage

### Logo Variants

We provide four logo variants to accommodate different use cases:

1. **Full Logo (`logo.svg`)** - Wordmark with icon, 200×48px
   - Use for: Headers, landing pages, main navigation
   - Minimum width: 160px

2. **Icon Only (`icon.svg`)** - Standalone icon, 80×80px
   - Use for: Favicons, app icons, social media avatars, compact layouts
   - Minimum size: 32×32px

3. **Favicon (`favicon.svg`)** - Optimized icon for browser tabs, 32×32px
   - Use for: Browser favicon, PWA icons

4. **Apple Touch Icon (`apple-touch-icon.svg`)** - iOS-optimized icon, 180×180px
   - Use for: iOS home screen icons, Apple-specific contexts

### Logo Construction

The ModuFlow logo consists of:

- **Icon**: Three connected hexagons representing modular components
  - Left hexagon: Primary indigo (#6366f1)
  - Middle hexagon: Brand gradient (indigo → teal)
  - Right hexagon: Secondary teal (#06b6d4)
  - Connection lines: Light indigo (#818cf8)

- **Wordmark**: "ModuFlow" in Inter Bold (700 weight)
  - Color: Light gray (#f1f5f9)
  - Spacing: 10px gap between icon and text

### Clear Space

Maintain clear space around the logo equal to the height of one hexagon (20px minimum) on all sides.

### Logo Don'ts

❌ Do not change logo colors
❌ Do not rotate or skew the logo
❌ Do not add effects (shadows, outlines, glows)
❌ Do not place on busy backgrounds that reduce readability
❌ Do not stretch or distort proportions
❌ Do not recreate or modify the logo

### Logo on Backgrounds

- **Dark backgrounds (recommended)**: Use full-color logo as-is
- **Light backgrounds**: Use sparingly; ensure sufficient contrast
- **Image backgrounds**: Place on solid overlay with 80%+ opacity

## Color Palette

### Primary Colors

#### Primary - Indigo
The main brand color representing intelligence and reliability.

- **Default**: `#6366f1`
  - Tailwind: `bg-primary`, `text-primary`
  - Usage: Primary CTAs, links, main interactive elements

- **Hover**: `#818cf8`
  - Tailwind: `bg-primary-hover`, `hover:bg-primary-hover`
  - Usage: Hover states for primary elements

- **Light**: `#a5b4fc`
  - Tailwind: `bg-primary-light`, `text-primary-light`
  - Usage: Subtle highlights, disabled states

- **Dark**: `#4f46e5`
  - Tailwind: `bg-primary-dark`, `text-primary-dark`
  - Usage: Borders, darker accents

#### Secondary - Teal/Cyan
Accent color representing flow and connectivity.

- **Default**: `#06b6d4`
  - Tailwind: `bg-secondary`, `text-secondary`
  - Usage: Accents, highlights, complementary elements

- **Hover**: `#22d3ee`
  - Tailwind: `bg-secondary-hover`, `hover:bg-secondary-hover`
  - Usage: Hover states for secondary elements

- **Light**: `#67e8f9`
  - Tailwind: `bg-secondary-light`, `text-secondary-light`
  - Usage: Subtle accents, badges

- **Dark**: `#0891b2`
  - Tailwind: `bg-secondary-dark`, `text-secondary-dark`
  - Usage: Borders, darker accents

### Semantic Colors

#### Success - Green
Positive feedback and completion states.

- **Default**: `#10b981`
- **Hover**: `#34d399`
- **Light**: `#6ee7b7`
- **Dark**: `#059669`

Usage: Success messages, completed tasks, positive confirmations

#### Warning - Amber
Caution and important notices.

- **Default**: `#f59e0b`
- **Hover**: `#fbbf24`
- **Light**: `#fcd34d`
- **Dark**: `#d97706`

Usage: Warning messages, pending states, important notices

#### Danger - Red
Errors and destructive actions.

- **Default**: `#ef4444`
- **Hover**: `#f87171`
- **Light**: `#fca5a5`
- **Dark**: `#dc2626`

Usage: Error messages, destructive buttons, critical alerts

### Neutral Colors

#### Surface (Dark Theme Base)
Foundation colors for dark mode interface.

- **Default**: `#1a1b23` - Main background
- **Light**: `#22232d` - Cards, elevated surfaces
- **Lighter**: `#2a2b37` - Hover states, secondary surfaces

#### Border
Subtle borders for dark theme.

- **Default**: `#33344a` - Standard borders
- **Light**: `#44456a` - Emphasized borders

### Color Usage Principles

1. **Primary for main actions** - Use indigo (#6366f1) for primary CTAs, important links, and key interactive elements
2. **Secondary for accents** - Use teal (#06b6d4) to complement primary color and highlight features
3. **Semantic colors appropriately** - Use success/warning/danger for feedback, not decoration
4. **Maintain hierarchy** - Primary > Secondary > Semantic in visual weight
5. **Dark theme first** - All colors optimized for dark backgrounds

### Accessibility

All color combinations must meet WCAG 2.1 AA standards:
- Normal text: minimum 4.5:1 contrast ratio
- Large text (18pt+): minimum 3:1 contrast ratio
- Interactive elements: 3:1 contrast with adjacent colors

## Gradients

### Brand Gradient
**Primary → Secondary** (`#6366f1` → `#06b6d4`)

```css
background: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%);
```

Tailwind: `bg-gradient-brand`

**Usage**: Hero sections, main headings, brand emphasis, special features

### Primary Gradient
**Indigo gradient** (`#6366f1` → `#818cf8`)

```css
background: linear-gradient(135deg, #6366f1 0%, #818cf8 100%);
```

Tailwind: `bg-gradient-primary`

**Usage**: Primary elements that need visual interest

### Secondary Gradient
**Teal gradient** (`#06b6d4` → `#22d3ee`)

```css
background: linear-gradient(135deg, #06b6d4 0%, #22d3ee 100%);
```

Tailwind: `bg-gradient-secondary`

**Usage**: Secondary elements that need visual interest

### Hero Background Gradient
**Subtle dark surface gradient**

```css
background: linear-gradient(135deg, #1a1b23 0%, #2a2b37 50%, #1a1b23 100%);
```

Tailwind: `bg-gradient-hero`

**Usage**: Hero sections, landing page backgrounds, large background areas

### Gradient Best Practices

✅ Use sparingly for maximum impact
✅ Reserve for hero sections and brand elements
✅ Apply to text using `bg-clip-text` for headings
✅ Use 135deg angle for consistency
❌ Don't use on small UI elements
❌ Don't combine multiple gradients in one view
❌ Don't use for body text or long-form content

## Typography

### Font Family

**Primary Font**: Inter
**Source**: Google Fonts
**Weights**: 400 (Regular), 500 (Medium), 600 (Semi-Bold), 700 (Bold)
**Fallback Stack**: system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif

Inter is a modern, highly legible sans-serif typeface optimized for user interfaces. Its geometric letterforms and excellent spacing make it ideal for both display and body text.

### Type Scale

```
text-xs     → 12px / 16px line-height  → Small labels, metadata
text-sm     → 14px / 20px line-height  → Body text (small), secondary content
text-base   → 16px / 24px line-height  → Body text (primary)
text-lg     → 18px / 28px line-height  → Emphasized text, large body
text-xl     → 20px / 28px line-height  → Subheadings, section headers
text-2xl    → 24px / 32px line-height  → Card titles, small headings
text-3xl    → 30px / 36px line-height  → Page headings
text-4xl    → 36px / 40px line-height  → Section headings
text-5xl    → 48px / 48px line-height  → Large headings
text-6xl    → 60px / 60px line-height  → Hero headings
```

### Font Weights

- **Regular (400)**: Body text, descriptions, secondary content
- **Medium (500)**: Emphasized body text, labels, UI elements
- **Semi-Bold (600)**: Subheadings, buttons, navigation items
- **Bold (700)**: Headings, brand elements, strong emphasis

### Typography Examples

#### Hero Heading
```tsx
<h1 className="text-6xl font-bold">
  <GradientText variant="brand">ModuFlow</GradientText>
</h1>
```

#### Section Heading
```tsx
<h2 className="text-3xl font-bold text-gray-100">
  Build Powerful AI Agents
</h2>
```

#### Body Text
```tsx
<p className="text-base font-normal text-gray-300">
  A modular framework for building intelligent assistants.
</p>
```

#### Button Text
```tsx
<button className="text-base font-semibold">
  Get Started
</button>
```

### Typography Best Practices

1. **Hierarchy through size and weight** - Don't rely solely on color
2. **Limit type styles** - Use 2-3 weights per page maximum
3. **Line length** - Keep body text between 50-75 characters per line
4. **Line height** - Use generous line spacing (1.5-1.75 for body text)
5. **Contrast** - Ensure text has sufficient contrast on backgrounds

## Component Examples

### Logo Component

```tsx
import { Logo } from "@/components/brand";

// Full logo (default)
<Logo size="md" />

// Icon only
<Logo size="sm" variant="icon" />

// Large hero logo
<Logo size="xl" className="mx-auto" />
```

**Sizes**: xs (24px), sm (32px), md (48px), lg (64px), xl (80px)

### Gradient Text

```tsx
import { GradientText } from "@/components/brand";

// Brand gradient heading
<GradientText variant="brand" as="h1" className="text-6xl font-bold">
  ModuFlow
</GradientText>

// Inline gradient text
<p>
  Welcome to <GradientText>ModuFlow</GradientText>
</p>
```

**Variants**: brand (default), primary, secondary

### Primary Button

```tsx
<button className="bg-primary hover:bg-primary-hover text-white px-6 py-3 rounded-lg font-semibold transition-colors">
  Get Started
</button>
```

### Secondary Button

```tsx
<button className="bg-secondary hover:bg-secondary-hover text-white px-6 py-3 rounded-lg font-semibold transition-colors">
  Learn More
</button>
```

### Outline Button

```tsx
<button className="border-2 border-primary text-primary hover:bg-primary hover:text-white px-6 py-3 rounded-lg font-semibold transition-all">
  Documentation
</button>
```

### Card Component

```tsx
<div className="bg-surface-light border border-border rounded-lg p-6 hover:border-border-light transition-colors">
  <h3 className="text-xl font-semibold text-gray-100 mb-2">
    Module Name
  </h3>
  <p className="text-gray-300">
    Module description goes here
  </p>
</div>
```

### Status Badge

```tsx
// Success
<span className="bg-success-dark text-success-light border border-success px-3 py-1 rounded-full text-sm font-medium">
  Active
</span>

// Warning
<span className="bg-warning-dark text-warning-light border border-warning px-3 py-1 rounded-full text-sm font-medium">
  Pending
</span>

// Danger
<span className="bg-danger-dark text-danger-light border border-danger px-3 py-1 rounded-full text-sm font-medium">
  Failed
</span>
```

### Alert Component

```tsx
// Success alert
<div className="bg-success-dark border border-success text-success-light p-4 rounded-lg">
  <p className="font-medium">Success! Your changes have been saved.</p>
</div>

// Warning alert
<div className="bg-warning-dark border border-warning text-warning-light p-4 rounded-lg">
  <p className="font-medium">Warning: This action cannot be undone.</p>
</div>

// Error alert
<div className="bg-danger-dark border border-danger text-danger-light p-4 rounded-lg">
  <p className="font-medium">Error: Something went wrong.</p>
</div>
```

## Brand Voice & Messaging

### Voice Characteristics

- **Clear and concise** - Explain complex concepts simply
- **Technically accurate** - Use proper terminology without jargon
- **Confident but humble** - Acknowledge what works and what's in progress
- **Developer-focused** - Speak to technical users with respect
- **Helpful and supportive** - Guide users toward success

### Key Messages

**Primary Message**: "ModuFlow is your modular AI agent framework for building intelligent, task-orchestrating assistants."

**Supporting Messages**:
- Build powerful AI agents with a plug-and-play architecture
- Connect to multiple LLM providers with automatic fallback
- Extend functionality with independent microservice modules
- Self-hosted for privacy and control
- Enterprise-grade reliability with developer-friendly experience

### Writing Style

#### Headlines
- Start with action verbs
- Focus on benefits, not features
- Keep under 60 characters when possible

Examples:
- ✅ "Build Powerful AI Agents in Minutes"
- ✅ "Your Modular AI Agent Framework"
- ❌ "A Framework That Lets You Build AI Agents"

#### Body Copy
- Use active voice
- Short paragraphs (2-3 sentences)
- Break up long content with subheadings
- Use bullet points for lists
- Include code examples where relevant

#### Calls to Action
- Use strong action verbs
- Create urgency when appropriate
- Be specific about the outcome

Examples:
- ✅ "Get Started", "Deploy Now", "View Documentation"
- ❌ "Click Here", "Submit", "Go"

## Application & Implementation

### File Locations

**Logo Assets**:
- `agent/portal/frontend/public/logo.svg` - Full logo
- `agent/portal/frontend/public/icon.svg` - Icon only
- `agent/portal/frontend/public/favicon.svg` - Favicon
- `agent/portal/frontend/public/apple-touch-icon.svg` - iOS icon

**Brand Components**:
- `agent/portal/frontend/src/components/brand/Logo.tsx`
- `agent/portal/frontend/src/components/brand/GradientText.tsx`
- `agent/portal/frontend/src/components/brand/colors.ts`
- `agent/portal/frontend/src/components/brand/index.ts`

**Configuration**:
- `agent/portal/frontend/tailwind.config.js` - Color system and gradients
- `agent/portal/frontend/index.html` - Font loading and meta tags

**Documentation**:
- `agent/portal/frontend/BRAND_COLORS.md` - Color usage reference
- `agent/portal/frontend/src/components/brand/README.md` - Component docs
- `agent/docs/BRANDING.md` - This file (comprehensive guidelines)

### Implementation Checklist

When applying ModuFlow branding to new pages or features:

- [ ] Use Logo component for all logo displays
- [ ] Apply brand colors using Tailwind utilities
- [ ] Use Inter font (automatically applied)
- [ ] Implement proper type hierarchy
- [ ] Use semantic colors for feedback (success/warning/danger)
- [ ] Apply gradients sparingly (hero sections, headings)
- [ ] Ensure WCAG AA contrast standards
- [ ] Test on dark backgrounds
- [ ] Maintain clear space around logos
- [ ] Follow component patterns from examples

### Code Review Guidelines

When reviewing brand implementation:

1. **Visual consistency** - Does it match established patterns?
2. **Color usage** - Are colors used semantically and appropriately?
3. **Typography** - Is the type hierarchy clear and consistent?
4. **Component reuse** - Are brand components used instead of custom implementations?
5. **Accessibility** - Do color combinations meet contrast requirements?
6. **Responsive design** - Does branding scale well across devices?

## Resources & Tools

### Design Files
- All logo variants available in `agent/portal/frontend/public/`
- SVG format for scalability and web optimization

### Color Tools
- Tailwind IntelliSense extension for VSCode
- Use DevTools to verify contrast ratios

### Typography
- [Inter on Google Fonts](https://fonts.google.com/specimen/Inter)
- Font weights: 400, 500, 600, 700

### Accessibility
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)

## Updates & Maintenance

This brand guide is a living document. Updates should be made when:

- New brand assets are created
- Color palette is expanded or modified
- New component patterns are established
- User feedback suggests improvements
- Accessibility standards change

**Last Updated**: February 15, 2026
**Version**: 1.0
**Maintained By**: ModuFlow Development Team

For questions or suggestions regarding brand guidelines, please open an issue in the project repository.
