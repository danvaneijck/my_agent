# Dashboard and Portal Style and Branding Project

## Executive Summary

This project will transform the current "Agent Portal" and "Agent Admin Dashboard" into a polished, branded product with a professional identity. We'll establish a cohesive brand name, implement modern UI/UX patterns with light/dark theme support, add smooth animations, and create a deployment-ready experience.

## Current State Analysis

### Portal (User-Facing Web Interface)
- **Tech Stack**: React 19 + TypeScript + Vite + Tailwind CSS
- **Location**: `agent/portal/frontend/`
- **Pages**: 18 pages including Home, Chat, Tasks, Projects, Files, Repos, PRs, Code, Deployments, Schedule, Usage, Settings
- **Current Branding**: Generic "Agent Portal" text, no logo, no brand identity
- **Styling**: Dark-only theme using custom Tailwind config with surface colors (`#1a1b23`, `#22232d`, `#2a2b37`) and indigo accent (`#6366f1`)
- **Animations**: Basic CSS transitions only (no framer-motion or animation library)
- **Icons**: lucide-react library
- **Current Gaps**:
  - No light mode support
  - No brand identity or logo
  - No page transition animations
  - No card fade-in/stagger effects
  - Generic UI feels like an MVP rather than a polished product

### Admin Dashboard (Internal Admin Interface)
- **Tech Stack**: FastAPI + Vanilla JavaScript + Custom CSS
- **Location**: `agent/dashboard/static/`
- **Pages**: `index.html` (analytics), `admin.html` (CRUD management)
- **Current Branding**: Generic "Agent Admin Dashboard" text
- **Styling**: Dark-only theme using CSS variables (`--bg: #0f1117`, `--surface: #1a1d27`, `--accent: #6c8cff`)
- **Current Gaps**:
  - No light mode
  - No brand identity
  - No modern framework (vanilla JS)
  - Minimal interactivity

## Brand Identity Design

### Proposed Brand Names (Final Selection Required)

**Option A: "Nexus"** (Recommended)
- **Rationale**: Short, memorable, suggests connection and orchestration
- **Tag line**: "Your AI orchestration platform"
- **Domain availability**: Check nexus.ai, usenexus.com, getnexus.ai
- **Visual identity**: Modern, clean, network/node imagery

**Option B: "Conductor"**
- **Rationale**: Directly references orchestration, musical metaphor
- **Tag line**: "Orchestrate your AI agents"
- **Considerations**: Longer name, but very descriptive

**Option C: "Hive"**
- **Rationale**: Suggests collaboration, modular architecture, agents working together
- **Tag line**: "Connected AI intelligence"
- **Considerations**: May imply swarm behavior

**Option D: "Prism"**
- **Rationale**: Suggests light refraction, multiple capabilities, clarity
- **Tag line**: "Multi-dimensional AI platform"
- **Considerations**: Abstract but elegant

### Brand Identity Elements

1. **Logo Design Requirements**
   - SVG format for scalability
   - Monochrome version for sidebar/header
   - Color version for login page and marketing
   - Icon-only variant for favicon
   - Minimum sizes: 16x16 (favicon), 32x32 (sidebar), 48x48 (header), 256x256 (full logo)

2. **Color System**
   - **Primary Brand Color**: Refined indigo/blue-purple (`#6366f1` → custom brand color)
   - **Secondary Colors**: Complementary accent for CTAs and highlights
   - **Semantic Colors**: Success (green), warning (yellow), error (red), info (blue)
   - **Light Theme Palette**: Whites, light grays, subtle backgrounds
   - **Dark Theme Palette**: Current dark palette with refinements

3. **Typography**
   - **Primary Font**: Inter or Geist (modern, readable, professional)
   - **Monospace Font**: JetBrains Mono or Fira Code (already used for logs)
   - **Font Loading**: Self-hosted or Google Fonts CDN

4. **Visual Style**
   - **Design Language**: Minimal, modern, clean
   - **Card Style**: Soft shadows in light mode, subtle borders in dark mode
   - **Border Radius**: Consistent (8px for buttons, 12px for cards, 16px for modals)
   - **Spacing**: 8px base unit system
   - **Micro-interactions**: Hover states, focus rings, loading states

## Theme System Architecture

### Light/Dark Mode Implementation

**Storage & Persistence**
- Store theme preference in `localStorage` key: `theme`
- Values: `'light'`, `'dark'`, or `'system'` (auto-detect OS preference)
- Default: `'system'`

**React Context Approach**
```typescript
// agent/portal/frontend/src/contexts/ThemeContext.tsx
interface ThemeContextValue {
  theme: 'light' | 'dark' | 'system';
  resolvedTheme: 'light' | 'dark'; // actual theme in use
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
}
```

**Tailwind Dark Mode Configuration**
- Use `class` strategy (not `media`) for manual control
- Add `dark` class to `<html>` element based on resolved theme
- All components use `dark:` variants for dark mode styles

**Color Token Strategy**
- Define semantic tokens (not hard-coded colors)
- Example: `bg-primary`, `text-primary`, `border-primary`
- Tailwind config maps tokens to light/dark values

### Admin Dashboard Theme Migration
- Port admin dashboard to use same theme system
- Convert CSS variables to support both light/dark modes
- Add theme toggle to admin interface
- Synchronize theme preference across both interfaces (shared localStorage key)

## Animation System with Framer Motion

### Installation & Setup
```bash
# Add framer-motion to portal frontend
cd agent/portal/frontend
npm install framer-motion
```

### Animation Patterns

**1. Page Transitions**
- Fade in on route change
- Slide up subtle effect
- Duration: 200-300ms for snappy feel

**2. Card Stagger Animations**
- Dashboard cards fade in with stagger effect
- Each card delays by 50-100ms
- Initial opacity 0 → 1, translateY(20px) → 0

**3. List Item Animations**
- Tasks, projects, PRs animate in when data loads
- Stagger effect for items
- Layout animations on reorder/filter

**4. Micro-interactions**
- Button hover scale (1.0 → 1.02)
- Card hover lift (subtle shadow increase)
- Modal enter/exit animations
- Toast notifications slide in from top-right

**5. Loading States**
- Skeleton components with shimmer animation
- Spinner components with smooth rotation
- Progress bars with animated fills

### Performance Considerations
- Use `layoutId` for shared element transitions
- Implement `AnimatePresence` for exit animations
- Lazy load framer-motion on interaction (code splitting)
- Reduce motion for `prefers-reduced-motion` users

## Implementation Phases

---

## Phase 1: Brand Identity & Design System

**Goal**: Establish brand name, create logo, define comprehensive design tokens

### Tasks

#### Task 1.1: Brand Name Finalization
**Description**: Choose final brand name from options (Nexus, Conductor, Hive, Prism) and validate domain availability.

**Acceptance Criteria**:
- Brand name selected and documented
- Tag line written
- Domain availability checked (not purchased, just verified)
- Brand name added to `PLAN.md` as final decision

**Files**: `PLAN.md`

---

#### Task 1.2: Logo Design & Asset Creation
**Description**: Design brand logo in multiple formats and sizes for use across portal and dashboard.

**Acceptance Criteria**:
- SVG logo created (full logo with text)
- SVG icon-only variant created
- Monochrome version for dark mode
- Color version for light mode
- Favicon generated (16x16, 32x32, ICO format)
- All assets stored in `agent/portal/frontend/public/` directory
- Assets also copied to `agent/dashboard/static/` for admin dashboard

**Files**:
- `agent/portal/frontend/public/logo.svg` (full logo)
- `agent/portal/frontend/public/logo-icon.svg` (icon only)
- `agent/portal/frontend/public/logo-light.svg` (light theme variant)
- `agent/portal/frontend/public/logo-dark.svg` (dark theme variant)
- `agent/portal/frontend/public/favicon.ico`
- `agent/portal/frontend/public/favicon-32x32.png`
- `agent/portal/frontend/public/favicon-16x16.png`
- `agent/dashboard/static/logo.svg`
- `agent/dashboard/static/logo-icon.svg`
- `agent/dashboard/static/favicon.ico`

---

#### Task 1.3: Design Token System
**Description**: Define comprehensive design token system in Tailwind config for colors, spacing, typography, shadows, and animations.

**Acceptance Criteria**:
- Semantic color tokens defined for light and dark modes
- Typography scale established (font families, sizes, weights)
- Spacing scale refined (based on 8px system)
- Shadow system defined (sm, md, lg, xl)
- Border radius tokens standardized
- Animation duration tokens defined
- All tokens documented in `agent/docs/development/design-system.md`

**Files**:
- `agent/portal/frontend/tailwind.config.js` (updated with comprehensive theme)
- `agent/docs/development/design-system.md` (new documentation)

---

#### Task 1.4: Font Integration
**Description**: Integrate professional font families (Inter for UI, keep JetBrains Mono for code).

**Acceptance Criteria**:
- Inter font added to project (via CDN or self-hosted)
- Font loaded in `index.html` or CSS
- Tailwind config updated to use Inter as default `sans` font
- Monospace font stack preserved for code/logs
- Font loading optimized (font-display: swap)

**Files**:
- `agent/portal/frontend/index.html` (font link in `<head>`)
- `agent/portal/frontend/src/index.css` (font-face declarations if self-hosted)
- `agent/portal/frontend/tailwind.config.js` (fontFamily config)

---

## Phase 2: Theme System Implementation

**Goal**: Implement fully functional light/dark/system theme with persistence and smooth transitions

### Tasks

#### Task 2.1: Theme Context & Provider
**Description**: Create React context for theme management with localStorage persistence and system preference detection.

**Acceptance Criteria**:
- `ThemeContext` created with theme state and setter
- Theme stored in localStorage with key `theme`
- System preference detection using `window.matchMedia('(prefers-color-scheme: dark)')`
- Theme change listener for OS-level preference changes
- `useTheme` hook exported for components
- Provider wraps entire app in `main.tsx`

**Files**:
- `agent/portal/frontend/src/contexts/ThemeContext.tsx` (new)
- `agent/portal/frontend/src/main.tsx` (wrap with ThemeProvider)

---

#### Task 2.2: Theme Toggle Component
**Description**: Create accessible theme toggle component with light/dark/system options.

**Acceptance Criteria**:
- Toggle component with three states: light, dark, system
- Visual icons for each state (Sun, Moon, Monitor)
- Dropdown or segmented control UI pattern
- Accessible with keyboard navigation
- Current theme visually indicated
- Smooth transition when switching themes

**Files**:
- `agent/portal/frontend/src/components/common/ThemeToggle.tsx` (new)

---

#### Task 2.3: Tailwind Dark Mode Configuration
**Description**: Configure Tailwind to use class-based dark mode and apply dark class to HTML element based on theme context.

**Acceptance Criteria**:
- Tailwind config updated with `darkMode: 'class'`
- Theme context applies `dark` class to `<html>` element on mount and theme change
- All existing dark-mode colors preserved
- Light mode colors defined for all semantic tokens
- No visual regressions in dark mode

**Files**:
- `agent/portal/frontend/tailwind.config.js` (darkMode: 'class')
- `agent/portal/frontend/src/contexts/ThemeContext.tsx` (apply class to HTML)

---

#### Task 2.4: Light Mode Color System
**Description**: Define complete light mode color palette and apply to all components.

**Acceptance Criteria**:
- Light mode background colors defined (white, light grays)
- Light mode text colors defined (dark grays, blacks)
- Light mode border colors defined (subtle grays)
- Light mode surface colors defined (off-white, light surfaces)
- Light mode accent colors adjusted for contrast
- All status colors (success, warning, error) work in both themes
- WCAG AA contrast ratios met for all text

**Files**:
- `agent/portal/frontend/tailwind.config.js` (extend light mode colors)
- `agent/docs/development/design-system.md` (document light palette)

---

#### Task 2.5: Component Light Mode Styling
**Description**: Update all existing components to support light mode with dark: variants.

**Acceptance Criteria**:
- Layout components (Sidebar, Header, Layout) support light mode
- All page components render correctly in light mode
- Card components have appropriate light mode backgrounds and borders
- Form inputs readable in light mode
- Buttons maintain contrast in light mode
- Status badges work in both themes
- Code blocks and log viewers readable in light mode
- No hardcoded color values remaining (all use Tailwind tokens)

**Files** (update with light mode styles):
- `agent/portal/frontend/src/components/layout/Sidebar.tsx`
- `agent/portal/frontend/src/components/layout/Header.tsx`
- `agent/portal/frontend/src/components/layout/Layout.tsx`
- All page components in `agent/portal/frontend/src/pages/`
- All common components in `agent/portal/frontend/src/components/common/`
- All feature-specific components in `agent/portal/frontend/src/components/*/`

---

#### Task 2.6: Theme Toggle Integration
**Description**: Add theme toggle to Header component and Settings page.

**Acceptance Criteria**:
- Theme toggle added to Header (top-right, near logout)
- Theme toggle added to Settings page with full three-option control
- Toggle accessible on mobile
- Theme preference persists across sessions
- Theme changes apply immediately without page reload

**Files**:
- `agent/portal/frontend/src/components/layout/Header.tsx` (add toggle)
- `agent/portal/frontend/src/pages/SettingsPage.tsx` (add theme section)

---

## Phase 3: Admin Dashboard Modernization

**Goal**: Apply branding and theme system to admin dashboard

### Tasks

#### Task 3.1: Admin Dashboard Brand Integration
**Description**: Update admin dashboard HTML files with new brand name and logo.

**Acceptance Criteria**:
- Page titles updated to brand name (e.g., "Nexus Admin Dashboard")
- Logo added to header
- Favicon updated
- Color scheme aligned with portal brand colors
- Typography updated to match portal font (system font stack or web font)

**Files**:
- `agent/dashboard/static/index.html` (update branding)
- `agent/dashboard/static/admin.html` (update branding)

---

#### Task 3.2: Admin Dashboard Theme System
**Description**: Implement light/dark theme toggle in admin dashboard using localStorage and CSS variables.

**Acceptance Criteria**:
- CSS variables defined for both light and dark themes
- JavaScript theme toggle implementation
- Theme toggle button added to header
- Theme preference synced with portal (shared localStorage key)
- Light mode colors defined and applied
- Dark mode matches existing styling

**Files**:
- `agent/dashboard/static/index.html` (add theme system CSS and JS)
- `agent/dashboard/static/admin.html` (add theme system CSS and JS)

---

## Phase 4: Animation System with Framer Motion

**Goal**: Add smooth, professional animations throughout portal UI

### Tasks

#### Task 4.1: Framer Motion Installation & Base Setup
**Description**: Install framer-motion and create base animation configuration utilities.

**Acceptance Criteria**:
- `framer-motion` added to package.json dependencies
- Animation configuration file created with reusable variants
- `prefers-reduced-motion` detection and respect implemented
- Base animation utilities exported for use in components

**Files**:
- `agent/portal/frontend/package.json` (add framer-motion dependency)
- `agent/portal/frontend/src/utils/animations.ts` (new - animation configs)

---

#### Task 4.2: Page Transition Animations
**Description**: Implement smooth fade-in transitions for page navigation using AnimatePresence.

**Acceptance Criteria**:
- Pages wrap content in `motion.div` with fade-in animation
- AnimatePresence wraps route components in App.tsx
- Page transition duration: 200ms
- Fade + subtle slide-up effect (20px translateY)
- Exit animations work correctly
- No animation jank or layout shift

**Files**:
- `agent/portal/frontend/src/App.tsx` (wrap routes with AnimatePresence)
- All page components (wrap content in motion.div with variants)

---

#### Task 4.3: Dashboard Card Stagger Animations
**Description**: Add staggered fade-in animations to dashboard cards on HomePage.

**Acceptance Criteria**:
- Dashboard card wrapper uses `motion.div` with stagger container
- Each card fades in with 50-100ms stagger delay
- Animation: opacity 0→1, translateY(20px)→0
- Animation only runs on initial load (not on every render)
- Loading state shows skeleton, then cards animate in
- Smooth, polished feel

**Files**:
- `agent/portal/frontend/src/pages/HomePage.tsx` (add stagger animation)

---

#### Task 4.4: List Item Animations
**Description**: Add animations to list items in task lists, project lists, and other data tables.

**Acceptance Criteria**:
- Task list items animate in with stagger
- Project list items animate in with stagger
- PR list items animate in with stagger
- Deployment list items animate in with stagger
- Layout animations on filter/sort changes
- Exit animations when items removed
- Performance optimized (no lag with 100+ items)

**Files**:
- `agent/portal/frontend/src/pages/TasksPage.tsx`
- `agent/portal/frontend/src/pages/ProjectsPage.tsx`
- `agent/portal/frontend/src/pages/PullRequestsPage.tsx`
- `agent/portal/frontend/src/pages/DeploymentsPage.tsx`
- Reusable list animation component: `agent/portal/frontend/src/components/common/AnimatedList.tsx` (new)

---

#### Task 4.5: Micro-interaction Animations
**Description**: Add subtle hover, focus, and interaction animations to buttons, cards, and interactive elements.

**Acceptance Criteria**:
- Buttons scale slightly on hover (1.0 → 1.02)
- Cards lift with subtle shadow increase on hover
- Interactive list items have smooth hover state transitions
- Modal/dialog enter animations (scale + fade)
- Toast notification slide-in from top-right
- Loading spinners with smooth easing
- Focus rings with smooth transitions

**Files**:
- `agent/portal/frontend/src/components/common/Button.tsx` (new - animated button component)
- `agent/portal/frontend/src/components/common/Card.tsx` (new - animated card wrapper)
- `agent/portal/frontend/src/components/common/Modal.tsx` (if exists, add animations)
- `agent/portal/frontend/src/components/layout/Layout.tsx` (toast animations)

---

#### Task 4.6: Loading State Animations
**Description**: Enhance skeleton loaders and loading states with smooth animations.

**Acceptance Criteria**:
- Skeleton components have shimmer animation (gradient sweep)
- Spinner components use framer-motion for smooth rotation
- Progress bars animate with spring physics
- Loading → content transition is smooth (no pop-in)
- Skeleton → content crossfade implemented

**Files**:
- `agent/portal/frontend/src/components/common/Skeleton.tsx` (enhance with shimmer)
- `agent/portal/frontend/src/components/common/Spinner.tsx` (new - animated spinner)
- `agent/portal/frontend/src/components/common/ProgressBar.tsx` (new - animated progress)

---

## Phase 5: Branding & Polish

**Goal**: Apply brand identity across all touchpoints and add polish

### Tasks

#### Task 5.1: Login Page Brand Overhaul
**Description**: Redesign login page with brand logo, updated copy, and polished UI.

**Acceptance Criteria**:
- Large brand logo displayed prominently
- Brand tag line shown
- OAuth buttons styled with brand colors
- Background gradient or subtle pattern
- Responsive design (mobile-friendly)
- Login animation (logo fade in, buttons slide up)
- Professional, trust-building design

**Files**:
- `agent/portal/frontend/src/App.tsx` (login screen section)
- `agent/portal/frontend/src/components/auth/LoginScreen.tsx` (if extracted)

---

#### Task 5.2: Sidebar Branding
**Description**: Update sidebar with brand logo and name.

**Acceptance Criteria**:
- Brand icon logo in sidebar header
- Brand name next to logo (hidden on mobile/collapsed)
- Logo links to home page
- Consistent branding across all pages
- Logo respects theme (dark/light variants)

**Files**:
- `agent/portal/frontend/src/components/layout/Sidebar.tsx`

---

#### Task 5.3: Page Headers & Titles
**Description**: Update all page titles and meta tags with brand name.

**Acceptance Criteria**:
- HTML `<title>` tag includes brand name (e.g., "Nexus - Dashboard")
- All page headers consistent with brand tone
- Meta tags updated (description, og:title, og:description)
- Favicon loads correctly in all browsers

**Files**:
- `agent/portal/frontend/index.html` (update meta tags)
- All page components (update titles if dynamic)

---

#### Task 5.4: Empty States & Illustrations
**Description**: Create branded empty state components for when lists/tables are empty.

**Acceptance Criteria**:
- Empty state component created with optional illustration
- Brand colors used in illustrations
- Helpful copy guides users to take action
- Consistent empty state across all list views
- Call-to-action buttons when relevant

**Files**:
- `agent/portal/frontend/src/components/common/EmptyState.tsx` (new)
- Update pages to use EmptyState component:
  - `agent/portal/frontend/src/pages/ProjectsPage.tsx`
  - `agent/portal/frontend/src/pages/TasksPage.tsx`
  - `agent/portal/frontend/src/pages/FilesPage.tsx`
  - `agent/portal/frontend/src/pages/ReposPage.tsx`
  - `agent/portal/frontend/src/pages/DeploymentsPage.tsx`

---

#### Task 5.5: Error States & Messages
**Description**: Create branded error components with helpful messaging.

**Acceptance Criteria**:
- Error boundary component with brand styling
- 404 page created with brand elements
- Error messages consistent in tone (helpful, not technical)
- Retry/back-to-home actions provided
- Error states match brand design language

**Files**:
- `agent/portal/frontend/src/components/common/ErrorBoundary.tsx` (new)
- `agent/portal/frontend/src/pages/NotFoundPage.tsx` (new)
- `agent/portal/frontend/src/App.tsx` (add routes and error boundary)

---

#### Task 5.6: Loading Screen
**Description**: Create branded loading screen for initial app load.

**Acceptance Criteria**:
- Loading screen displays during React hydration
- Brand logo with loading animation
- Smooth transition to app once loaded
- Matches theme (light/dark)
- Minimal, fast-loading (inline CSS)

**Files**:
- `agent/portal/frontend/index.html` (add loading screen HTML/CSS)
- `agent/portal/frontend/src/main.tsx` (remove loading screen on mount)

---

## Phase 6: Responsive Design & Accessibility

**Goal**: Ensure mobile responsiveness and WCAG AA accessibility compliance

### Tasks

#### Task 6.1: Mobile Navigation Enhancements
**Description**: Improve mobile menu interactions with animations and better UX.

**Acceptance Criteria**:
- Mobile menu slides in smoothly (framer-motion)
- Backdrop blur effect on overlay
- Swipe-to-close gesture support (optional, nice-to-have)
- Menu items animate in with stagger
- Close button accessible and visible
- Navigation smooth on small screens

**Files**:
- `agent/portal/frontend/src/components/layout/Sidebar.tsx`

---

#### Task 6.2: Responsive Table/List Views
**Description**: Improve data table responsiveness for mobile devices.

**Acceptance Criteria**:
- Tables stack vertically on mobile or use horizontal scroll
- List views prioritize key information on mobile
- Filters and actions accessible on mobile
- No horizontal overflow issues
- Touch targets meet 44x44px minimum
- Tested on mobile devices (Chrome DevTools mobile view)

**Files**:
- Update table components across all pages
- Consider creating reusable responsive table component

---

#### Task 6.3: Accessibility Audit & Fixes
**Description**: Perform accessibility audit and fix issues to meet WCAG AA standards.

**Acceptance Criteria**:
- All interactive elements keyboard accessible (tab navigation)
- Focus indicators visible and styled
- ARIA labels added where needed
- Color contrast meets WCAG AA (4.5:1 for text)
- Screen reader tested (basic navigation)
- Skip-to-content link added
- Form inputs have associated labels
- Error messages announced to screen readers

**Files**:
- All components (add ARIA attributes and keyboard handlers)
- `agent/portal/frontend/src/components/common/SkipToContent.tsx` (new)

---

#### Task 6.4: Performance Optimization
**Description**: Optimize bundle size, code splitting, and runtime performance.

**Acceptance Criteria**:
- Framer-motion lazy loaded where possible
- Route-based code splitting implemented
- Images optimized (SVGs, PNGs compressed)
- Lighthouse performance score > 90
- First Contentful Paint < 1.5s
- Time to Interactive < 3.5s
- No layout shift (CLS < 0.1)

**Files**:
- `agent/portal/frontend/src/App.tsx` (lazy load routes)
- `agent/portal/frontend/vite.config.ts` (bundle optimizations)

---

## Phase 7: Documentation & Deployment Prep

**Goal**: Document design system and prepare for deployment

### Tasks

#### Task 7.1: Design System Documentation
**Description**: Create comprehensive design system documentation for developers and designers.

**Acceptance Criteria**:
- Color palette documented with hex codes and usage
- Typography scale documented
- Spacing system documented
- Component library documented
- Animation guidelines documented
- Accessibility guidelines documented
- Brand asset usage guidelines documented
- Markdown documentation created in `agent/docs/development/design-system.md`

**Files**:
- `agent/docs/development/design-system.md` (comprehensive design system docs)

---

#### Task 7.2: Storybook or Component Showcase (Optional)
**Description**: Create a component showcase page or Storybook integration for design system reference.

**Acceptance Criteria**:
- All reusable components showcased
- Theme toggle to view components in light/dark mode
- Interactive examples for each component
- Code snippets for usage
- Accessible via `/showcase` route in development

**Files**:
- `agent/portal/frontend/src/pages/ComponentShowcase.tsx` (new, dev-only)

---

#### Task 7.3: Environment-Specific Branding
**Description**: Add environment indicators for staging/development environments.

**Acceptance Criteria**:
- Visual indicator for non-production environments (banner or badge)
- Different colors for dev (blue), staging (yellow), production (none)
- Environment badge subtle but visible
- Does not block UI or interfere with testing

**Files**:
- `agent/portal/frontend/src/components/layout/EnvironmentBanner.tsx` (new)
- `agent/portal/frontend/src/components/layout/Layout.tsx` (add banner)

---

#### Task 7.4: Browser Compatibility Testing
**Description**: Test portal and dashboard across major browsers and fix compatibility issues.

**Acceptance Criteria**:
- Chrome (latest) tested and working
- Firefox (latest) tested and working
- Safari (latest) tested and working
- Edge (latest) tested and working
- Mobile Safari tested
- Mobile Chrome tested
- CSS vendor prefixes added where needed
- Polyfills added if necessary

**Files**:
- Document findings in `agent/docs/development/browser-compatibility.md`
- Fix issues in relevant component files

---

#### Task 7.5: Final QA & Polish Pass
**Description**: Comprehensive QA pass for visual inconsistencies, bugs, and polish issues.

**Acceptance Criteria**:
- All pages tested in light and dark mode
- All animations smooth and intentional (no jank)
- No console errors or warnings
- All links functional
- All buttons and interactions work as expected
- Typography consistent across all pages
- Spacing consistent across all pages
- Colors consistent with design tokens
- No visual regressions from original dark theme
- Mobile experience tested and polished

**Files**:
- Fix issues across all components as identified

---

## Technical Considerations

### Design System Scalability
- All design tokens centralized in Tailwind config
- CSS custom properties used where Tailwind tokens insufficient
- Component library approach for consistency
- Documentation keeps system maintainable

### Performance
- Framer-motion tree-shaking via ES modules
- Code splitting at route level
- Image optimization (SVG for logos, compressed PNGs for screenshots)
- Font subsetting if self-hosting fonts
- Lighthouse audits before and after implementation

### Accessibility
- WCAG AA compliance throughout
- Keyboard navigation fully supported
- Screen reader testing
- Reduced motion preference respected
- Color contrast verified with tools (WebAIM, Stark)

### Browser Support
- Modern browsers (Chrome, Firefox, Safari, Edge - latest 2 versions)
- Graceful degradation for older browsers
- CSS feature detection with @supports where needed

### Maintenance
- Design system documented for future contributors
- Component patterns established and documented
- Storybook or showcase for component reference
- Clear naming conventions for tokens and components

## Dependencies

### New Dependencies to Add
```json
{
  "framer-motion": "^11.0.0",  // Animation library
  "@fontsource/inter": "^5.0.0"  // Self-hosted Inter font (optional)
}
```

### Optional Dependencies (Nice-to-have)
```json
{
  "react-hot-toast": "^2.4.0",  // Better toast notifications with animations
  "react-select": "^5.8.0"  // Accessible select components (if needed)
}
```

## Success Metrics

### Quantitative Metrics
- Lighthouse Performance Score: > 90
- Lighthouse Accessibility Score: 100
- First Contentful Paint: < 1.5s
- Time to Interactive: < 3.5s
- Cumulative Layout Shift: < 0.1
- Bundle size increase: < 100KB (gzipped)

### Qualitative Metrics
- Users can describe the brand identity
- UI feels "polished" and "professional" (user feedback)
- Light mode is comfortable for daytime use
- Dark mode is comfortable for nighttime use
- Animations feel smooth and intentional (not distracting)
- Empty states are helpful and encouraging
- Error states are clear and actionable

## Deployment Checklist

- [ ] Brand name finalized
- [ ] Logo assets created and integrated
- [ ] Light theme fully implemented and tested
- [ ] Dark theme refined and tested
- [ ] Animations implemented across all key interactions
- [ ] Admin dashboard updated with branding and theme
- [ ] Mobile responsiveness verified
- [ ] Accessibility audit passed
- [ ] Performance benchmarks met
- [ ] Browser compatibility verified
- [ ] Documentation completed
- [ ] QA pass completed
- [ ] Staging environment tested
- [ ] Production deployment plan reviewed

## Risk Mitigation

### Potential Risks

1. **Brand name conflicts**: Trademark search and domain availability check early
2. **Animation performance**: Profile and optimize animations, respect reduced motion
3. **Theme bugs**: Comprehensive testing in both modes before merge
4. **Scope creep**: Stick to defined phases, defer nice-to-have features to future iterations
5. **Breaking changes**: Incremental rollout, feature flags if needed

### Rollback Plan
- Each phase can be rolled back independently (git branches per phase)
- Theme toggle allows users to revert to familiar dark mode if light mode has issues
- Feature flags for animations (can disable via config if performance issues arise)

## Post-Launch Iterations

### Future Enhancements (Out of Scope)
- Custom color theme builder (user-configurable brand colors)
- Advanced animations (page transitions, shared element transitions)
- Dark mode auto-switch based on time of day
- Animated charts and data visualizations
- Marketing landing page with brand showcased
- Multi-language support (i18n)

## Conclusion

This project will transform the agent platform from an MVP into a polished, professional product ready for deployment. By establishing a strong brand identity, implementing a modern design system with light/dark modes, and adding thoughtful animations, we'll create a user experience that feels both powerful and delightful.

The phased approach ensures incremental progress with clear milestones, while the comprehensive task breakdown provides actionable steps for implementation. Each phase builds upon the previous, culminating in a deployment-ready product that reflects the sophistication of the underlying AI orchestration system.

---

**Total Estimated Tasks**: 43 concrete, implementable tasks across 7 phases
**Recommended Brand Name**: Nexus (pending final selection in Task 1.1)
**Target Completion**: All phases can be executed incrementally with working software at each milestone
