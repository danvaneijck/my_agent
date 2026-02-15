# ModuFlow Brand Components

This directory contains reusable brand components and utilities for maintaining consistent branding across the ModuFlow application.

## Components

### Logo

The Logo component displays the ModuFlow brand logo with flexible sizing and variants.

**Props:**
- `size?: "xs" | "sm" | "md" | "lg" | "xl"` - Size variant (default: "md")
- `variant?: "full" | "icon"` - Display full logo or icon only (default: "full")
- `className?: string` - Additional CSS classes

**Examples:**

```tsx
import { Logo } from "@/components/brand";

// Full logo with wordmark (default)
<Logo size="md" />

// Icon only
<Logo size="sm" variant="icon" />

// Large logo in header
<Logo size="lg" className="mx-auto" />

// Extra small logo in navigation
<Logo size="xs" />
```

**Sizes:**
- `xs`: 24px height (icon: 32px)
- `sm`: 32px height (icon: 48px)
- `md`: 48px height (icon: 64px)
- `lg`: 64px height (icon: 96px)
- `xl`: 80px height (icon: 128px)

### GradientText

Applies brand gradient to text using CSS background-clip.

**Props:**
- `variant?: "brand" | "primary" | "secondary"` - Gradient variant (default: "brand")
- `as?: "span" | "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | "p"` - HTML element (default: "span")
- `className?: string` - Additional CSS classes
- `children: React.ReactNode` - Text content

**Examples:**

```tsx
import { GradientText } from "@/components/brand";

// Hero heading with brand gradient
<GradientText variant="brand" as="h1" className="text-6xl font-bold">
  ModuFlow
</GradientText>

// Inline gradient text
<p>
  Welcome to <GradientText variant="primary">ModuFlow</GradientText>
</p>

// Secondary gradient heading
<GradientText variant="secondary" as="h2" className="text-3xl">
  Your Modular AI Agent Framework
</GradientText>
```

**Gradient Variants:**
- `brand`: Primary (#6366f1) → Secondary (#06b6d4) - Use for main brand elements
- `primary`: Indigo gradient - Use for primary emphasis
- `secondary`: Teal/cyan gradient - Use for secondary emphasis

## Utilities

### Brand Colors

Direct access to brand color values for JavaScript/TypeScript usage.

```tsx
import { brandColors, getColor, getGradient } from "@/components/brand";

// Access color directly
const primaryColor = brandColors.primary.DEFAULT; // "#6366f1"
const successHover = brandColors.success.hover; // "#34d399"

// Using helper function
const color = getColor("primary"); // "#6366f1"
const colorVariant = getColor("danger", "hover"); // "#f87171"

// Get gradient CSS
const gradient = getGradient("brand");
// "linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)"
```

**Available Color Categories:**
- `primary` - Indigo (main brand color)
- `secondary` - Teal/cyan (accent color)
- `success` - Green
- `warning` - Amber
- `danger` - Red
- `surface` - Dark backgrounds
- `border` - Border colors

**Color Variants:**
- `DEFAULT` - Base color
- `hover` - Hover state
- `light` - Lighter shade
- `dark` - Darker shade

**Available Gradients:**
- `brand` - Primary → Secondary
- `primary` - Indigo gradient
- `secondary` - Teal gradient
- `hero` - Subtle dark background gradient

## Tailwind Usage

For most cases, prefer Tailwind utility classes over direct color imports:

```tsx
// Background colors
<div className="bg-primary hover:bg-primary-hover">

// Text colors
<span className="text-secondary">

// Borders
<div className="border border-primary">

// Gradients
<div className="bg-gradient-brand">

// Multiple colors
<button className="bg-primary text-white border border-primary-dark">
```

See `BRAND_COLORS.md` in the frontend root for complete color documentation.

## Integration Examples

### Header with Logo

```tsx
import { Logo } from "@/components/brand";

export function Header() {
  return (
    <header className="bg-surface border-b border-border">
      <div className="container mx-auto px-4 py-3">
        <Logo size="sm" />
      </div>
    </header>
  );
}
```

### Hero Section

```tsx
import { Logo, GradientText } from "@/components/brand";

export function Hero() {
  return (
    <section className="bg-gradient-hero py-20">
      <div className="container mx-auto text-center">
        <Logo size="xl" className="mx-auto mb-6" />
        <GradientText variant="brand" as="h1" className="text-6xl font-bold mb-4">
          Your Modular AI Agent Framework
        </GradientText>
        <p className="text-xl text-gray-300 mb-8">
          Build powerful AI assistants with a modular, extensible framework
        </p>
        <button className="bg-primary hover:bg-primary-hover text-white px-8 py-3 rounded-lg text-lg font-semibold">
          Get Started
        </button>
      </div>
    </section>
  );
}
```

### Status Badge with Semantic Colors

```tsx
import { brandColors } from "@/components/brand";

function StatusBadge({ status }: { status: "success" | "warning" | "danger" }) {
  const colorMap = {
    success: "bg-success-dark text-success-light border-success",
    warning: "bg-warning-dark text-warning-light border-warning",
    danger: "bg-danger-dark text-danger-light border-danger",
  };

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium border ${colorMap[status]}`}>
      {status.toUpperCase()}
    </span>
  );
}
```

## Best Practices

1. **Use Logo component for all logo displays** - Don't reference logo SVG files directly
2. **Prefer Tailwind classes** - Use color constants only when necessary (charts, canvas, etc.)
3. **Use semantic colors appropriately** - success/warning/danger for feedback, primary/secondary for brand
4. **Gradients sparingly** - Reserve for hero sections and special emphasis
5. **Maintain dark theme** - All colors are optimized for dark backgrounds
6. **Document usage** - Add comments when using colors in non-obvious ways
