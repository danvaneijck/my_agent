# ModuFlow Brand Colors

## Color Palette

### Primary (Indigo)
- **Usage**: Main brand color, primary CTAs, interactive elements
- **Default**: `#6366f1` - `bg-primary`, `text-primary`
- **Hover**: `#818cf8` - `bg-primary-hover`
- **Light**: `#a5b4fc` - `bg-primary-light`
- **Dark**: `#4f46e5` - `bg-primary-dark`

### Secondary (Teal/Cyan)
- **Usage**: Accent elements, highlights, complementary to primary
- **Default**: `#06b6d4` - `bg-secondary`, `text-secondary`
- **Hover**: `#22d3ee` - `bg-secondary-hover`
- **Light**: `#67e8f9` - `bg-secondary-light`
- **Dark**: `#0891b2` - `bg-secondary-dark`

### Success (Green)
- **Usage**: Success messages, completed states, positive feedback
- **Default**: `#10b981` - `bg-success`, `text-success`
- **Hover**: `#34d399` - `bg-success-hover`
- **Light**: `#6ee7b7` - `bg-success-light`
- **Dark**: `#059669` - `bg-success-dark`

### Warning (Amber)
- **Usage**: Warning messages, caution states, important notices
- **Default**: `#f59e0b` - `bg-warning`, `text-warning`
- **Hover**: `#fbbf24` - `bg-warning-hover`
- **Light**: `#fcd34d` - `bg-warning-light`
- **Dark**: `#d97706` - `bg-warning-dark`

### Danger (Red)
- **Usage**: Error messages, destructive actions, critical alerts
- **Default**: `#ef4444` - `bg-danger`, `text-danger`
- **Hover**: `#f87171` - `bg-danger-hover`
- **Light**: `#fca5a5` - `bg-danger-light`
- **Dark**: `#dc2626` - `bg-danger-dark`

### Surface (Dark Theme Base)
- **Default**: `#1a1b23` - `bg-surface`
- **Light**: `#22232d` - `bg-surface-light`
- **Lighter**: `#2a2b37` - `bg-surface-lighter`

### Border
- **Default**: `#33344a` - `border-border`
- **Light**: `#44456a` - `border-border-light`

## Gradient Utilities

### Brand Gradient (Primary → Secondary)
```jsx
<div className="bg-gradient-brand">
  Primary to Secondary gradient
</div>
```

### Primary Gradient
```jsx
<div className="bg-gradient-primary">
  Indigo gradient
</div>
```

### Secondary Gradient
```jsx
<div className="bg-gradient-secondary">
  Teal/cyan gradient
</div>
```

### Hero Background Gradient
```jsx
<div className="bg-gradient-hero">
  Subtle dark surface gradient
</div>
```

## Usage Examples

### Primary Button
```jsx
<button className="bg-primary hover:bg-primary-hover text-white">
  Primary Action
</button>
```

### Secondary Button
```jsx
<button className="bg-secondary hover:bg-secondary-hover text-white">
  Secondary Action
</button>
```

### Success Alert
```jsx
<div className="bg-success-dark border border-success text-success-light">
  Success message
</div>
```

### Gradient Text
```jsx
<h1 className="bg-gradient-brand bg-clip-text text-transparent">
  ModuFlow
</h1>
```

## Design Principles

1. **Primary for main actions**: Use indigo for primary CTAs and key interactive elements
2. **Secondary for accents**: Use teal/cyan to complement primary, highlight features
3. **Semantic colors**: Use success/warning/danger appropriately for feedback
4. **Gradients sparingly**: Reserve for hero sections, special emphasis, and brand elements
5. **Dark theme first**: All colors are optimized for dark backgrounds
