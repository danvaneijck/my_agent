/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surface colors for dark theme
        surface: {
          DEFAULT: "#1a1b23",
          light: "#22232d",
          lighter: "#2a2b37",
        },
        // Border colors
        border: {
          DEFAULT: "#33344a",
          light: "#44456a",
        },
        // Primary brand color (indigo)
        primary: {
          DEFAULT: "#6366f1",
          hover: "#818cf8",
          light: "#a5b4fc",
          dark: "#4f46e5",
        },
        // Keep accent as alias for backwards compatibility
        accent: {
          DEFAULT: "#6366f1",
          hover: "#818cf8",
        },
        // Secondary brand color (teal/cyan)
        secondary: {
          DEFAULT: "#06b6d4",
          hover: "#22d3ee",
          light: "#67e8f9",
          dark: "#0891b2",
        },
        // Success color (green)
        success: {
          DEFAULT: "#10b981",
          hover: "#34d399",
          light: "#6ee7b7",
          dark: "#059669",
        },
        // Warning color (amber)
        warning: {
          DEFAULT: "#f59e0b",
          hover: "#fbbf24",
          light: "#fcd34d",
          dark: "#d97706",
        },
        // Danger/error color (red)
        danger: {
          DEFAULT: "#ef4444",
          hover: "#f87171",
          light: "#fca5a5",
          dark: "#dc2626",
        },
      },
      // Gradient utilities
      backgroundImage: {
        "gradient-primary": "linear-gradient(135deg, #6366f1 0%, #818cf8 100%)",
        "gradient-secondary": "linear-gradient(135deg, #06b6d4 0%, #22d3ee 100%)",
        "gradient-brand": "linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)",
        "gradient-hero": "linear-gradient(135deg, #1a1b23 0%, #2a2b37 50%, #1a1b23 100%)",
      },
      // Font families
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
