/**
 * ModuFlow Brand Colors
 *
 * Central constants file for brand colors. Use these when you need direct access
 * to color values in JavaScript/TypeScript (e.g., for canvas, charts, or dynamic styling).
 *
 * For general styling, prefer Tailwind utility classes (e.g., bg-primary, text-secondary).
 */

export const brandColors = {
  // Primary brand color (Indigo)
  primary: {
    DEFAULT: "#6366f1",
    hover: "#818cf8",
    light: "#a5b4fc",
    dark: "#4f46e5",
  },

  // Secondary brand color (Teal/Cyan)
  secondary: {
    DEFAULT: "#06b6d4",
    hover: "#22d3ee",
    light: "#67e8f9",
    dark: "#0891b2",
  },

  // Success (Green)
  success: {
    DEFAULT: "#10b981",
    hover: "#34d399",
    light: "#6ee7b7",
    dark: "#059669",
  },

  // Warning (Amber)
  warning: {
    DEFAULT: "#f59e0b",
    hover: "#fbbf24",
    light: "#fcd34d",
    dark: "#d97706",
  },

  // Danger/Error (Red)
  danger: {
    DEFAULT: "#ef4444",
    hover: "#f87171",
    light: "#fca5a5",
    dark: "#dc2626",
  },

  // Surface (Dark theme backgrounds)
  surface: {
    DEFAULT: "#1a1b23",
    light: "#22232d",
    lighter: "#2a2b37",
  },

  // Border
  border: {
    DEFAULT: "#33344a",
    light: "#44456a",
  },
} as const;

/**
 * Gradient definitions as CSS strings
 */
export const brandGradients = {
  brand: "linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)",
  primary: "linear-gradient(135deg, #6366f1 0%, #818cf8 100%)",
  secondary: "linear-gradient(135deg, #06b6d4 0%, #22d3ee 100%)",
  hero: "linear-gradient(135deg, #1a1b23 0%, #2a2b37 50%, #1a1b23 100%)",
} as const;

/**
 * Get a color value by semantic name
 *
 * @example
 * ```ts
 * const primaryColor = getColor("primary"); // "#6366f1"
 * const successHover = getColor("success", "hover"); // "#34d399"
 * ```
 */
export function getColor(
  name: keyof typeof brandColors,
  variant: "DEFAULT" | "hover" | "light" | "dark" = "DEFAULT"
): string {
  const colorGroup = brandColors[name];
  return colorGroup[variant as keyof typeof colorGroup] || colorGroup.DEFAULT;
}

/**
 * Get a gradient CSS string
 *
 * @example
 * ```ts
 * const gradient = getGradient("brand");
 * // "linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)"
 * ```
 */
export function getGradient(name: keyof typeof brandGradients): string {
  return brandGradients[name];
}
