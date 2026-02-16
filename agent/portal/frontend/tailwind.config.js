/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      // Nexus Brand Colors
      colors: {
        // Primary brand colors
        brand: {
          50: "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1", // Primary brand color
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
          950: "#1e1b4b",
        },

        // Surface colors (light theme)
        surface: {
          DEFAULT: "#1a1b23", // Dark theme default
          light: "#22232d",
          lighter: "#2a2b37",
        },

        // Light theme surfaces (applied when not in dark mode)
        "light-surface": {
          DEFAULT: "#ffffff",
          secondary: "#f9fafb",
          tertiary: "#f3f4f6",
        },

        // Border colors
        border: {
          DEFAULT: "#33344a", // Dark theme
          light: "#44456a",
        },

        "light-border": {
          DEFAULT: "#e5e7eb", // Light theme
          light: "#d1d5db",
        },

        // Accent colors (interactive elements)
        accent: {
          DEFAULT: "#6366f1",
          hover: "#818cf8",
          light: "#a5b4fc",
          dark: "#4f46e5",
        },

        // Semantic colors
        success: {
          DEFAULT: "#4ade80",
          light: "#86efac",
          dark: "#22c55e",
          bg: "#dcfce7",
        },
        warning: {
          DEFAULT: "#fbbf24",
          light: "#fcd34d",
          dark: "#f59e0b",
          bg: "#fef3c7",
        },
        error: {
          DEFAULT: "#f87171",
          light: "#fca5a5",
          dark: "#ef4444",
          bg: "#fee2e2",
        },
        info: {
          DEFAULT: "#60a5fa",
          light: "#93c5fd",
          dark: "#3b82f6",
          bg: "#dbeafe",
        },
      },

      // Typography scale
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }], // 10px
        xs: ["0.75rem", { lineHeight: "1rem" }], // 12px
        sm: ["0.875rem", { lineHeight: "1.25rem" }], // 14px
        base: ["1rem", { lineHeight: "1.5rem" }], // 16px
        lg: ["1.125rem", { lineHeight: "1.75rem" }], // 18px
        xl: ["1.25rem", { lineHeight: "1.75rem" }], // 20px
        "2xl": ["1.5rem", { lineHeight: "2rem" }], // 24px
        "3xl": ["1.875rem", { lineHeight: "2.25rem" }], // 30px
        "4xl": ["2.25rem", { lineHeight: "2.5rem" }], // 36px
        "5xl": ["3rem", { lineHeight: "1" }], // 48px
        "6xl": ["3.75rem", { lineHeight: "1" }], // 60px
        "7xl": ["4.5rem", { lineHeight: "1" }], // 72px
      },

      // Font families
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          '"Helvetica Neue"',
          "Arial",
          "sans-serif",
        ],
        mono: [
          '"JetBrains Mono"',
          '"Fira Code"',
          '"Cascadia Code"',
          "Consolas",
          "Monaco",
          '"Courier New"',
          "monospace",
        ],
      },

      // Font weights
      fontWeight: {
        thin: "100",
        extralight: "200",
        light: "300",
        normal: "400",
        medium: "500",
        semibold: "600",
        bold: "700",
        extrabold: "800",
        black: "900",
      },

      // Spacing scale (8px base system)
      spacing: {
        0: "0",
        0.5: "0.125rem", // 2px
        1: "0.25rem", // 4px
        1.5: "0.375rem", // 6px
        2: "0.5rem", // 8px (base unit)
        2.5: "0.625rem", // 10px
        3: "0.75rem", // 12px
        3.5: "0.875rem", // 14px
        4: "1rem", // 16px (2x base)
        5: "1.25rem", // 20px
        6: "1.5rem", // 24px (3x base)
        7: "1.75rem", // 28px
        8: "2rem", // 32px (4x base)
        9: "2.25rem", // 36px
        10: "2.5rem", // 40px (5x base)
        11: "2.75rem", // 44px
        12: "3rem", // 48px (6x base)
        14: "3.5rem", // 56px (7x base)
        16: "4rem", // 64px (8x base)
        20: "5rem", // 80px (10x base)
        24: "6rem", // 96px (12x base)
        28: "7rem", // 112px (14x base)
        32: "8rem", // 128px (16x base)
        36: "9rem", // 144px (18x base)
        40: "10rem", // 160px (20x base)
      },

      // Box shadows
      boxShadow: {
        sm: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        DEFAULT:
          "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)",
        md: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)",
        lg: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",
        xl: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
        "2xl": "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
        inner: "inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)",
        none: "none",
        // Colored shadows for elevation in light mode
        "elevation-sm": "0 1px 3px 0 rgba(99, 102, 241, 0.1)",
        "elevation-md": "0 4px 6px -1px rgba(99, 102, 241, 0.15)",
        "elevation-lg": "0 10px 15px -3px rgba(99, 102, 241, 0.2)",
      },

      // Border radius (consistent rounding)
      borderRadius: {
        none: "0",
        sm: "0.25rem", // 4px
        DEFAULT: "0.5rem", // 8px (buttons, inputs)
        md: "0.5rem", // 8px
        lg: "0.75rem", // 12px (cards)
        xl: "1rem", // 16px (modals, large cards)
        "2xl": "1.5rem", // 24px
        "3xl": "2rem", // 32px
        full: "9999px",
      },

      // Animation durations
      transitionDuration: {
        fast: "150ms",
        DEFAULT: "200ms",
        normal: "200ms",
        medium: "300ms",
        slow: "500ms",
      },

      // Animation timing functions
      transitionTimingFunction: {
        "ease-out-expo": "cubic-bezier(0.19, 1, 0.22, 1)",
        "ease-in-expo": "cubic-bezier(0.95, 0.05, 0.795, 0.035)",
        "ease-in-out-expo": "cubic-bezier(0.87, 0, 0.13, 1)",
        bounce: "cubic-bezier(0.68, -0.55, 0.265, 1.55)",
      },

      // Keyframes for custom animations
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "fade-out": {
          from: { opacity: "1" },
          to: { opacity: "0" },
        },
        "slide-up": {
          from: { transform: "translateY(20px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        "slide-down": {
          from: { transform: "translateY(-20px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        "slide-left": {
          from: { transform: "translateX(20px)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
        "slide-right": {
          from: { transform: "translateX(-20px)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
        shimmer: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
        spin: {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
        pulse: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
      },

      // Animation classes
      animation: {
        "fade-in": "fade-in 200ms ease-out",
        "fade-out": "fade-out 200ms ease-out",
        "slide-up": "slide-up 300ms ease-out",
        "slide-down": "slide-down 300ms ease-out",
        "slide-left": "slide-left 300ms ease-out",
        "slide-right": "slide-right 300ms ease-out",
        shimmer: "shimmer 2s infinite",
        spin: "spin 1s linear infinite",
        pulse: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },

      // Z-index scale
      zIndex: {
        0: "0",
        10: "10",
        20: "20",
        30: "30",
        40: "40",
        50: "50",
        auto: "auto",
      },
    },
  },
  plugins: [],
};
