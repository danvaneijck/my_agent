/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#1a1b23",
          light: "#22232d",
          lighter: "#2a2b37",
        },
        border: {
          DEFAULT: "#33344a",
          light: "#44456a",
        },
        accent: {
          DEFAULT: "#6366f1",
          hover: "#818cf8",
        },
      },
    },
  },
  plugins: [],
};
