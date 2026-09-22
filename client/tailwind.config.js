/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#4F46E5",
          dark: "#3730A3",
        },
        accent: "#14B8A6",
        success: "#22C55E",
        warning: "#F59E0B",
        danger: "#EF4444",
        gold: {
          DEFAULT: "#D8B478",
          soft: "#EAD9B0",
        },
        lavender: "#B9A6DA",
        teal: "#6FCFC4",
        canvas: {
          dark: "#0A0E1B",
          light: "#FAFAFA",
        },
        surface: {
          dark: "#141826",
          light: "#FFFFFF",
        },
        ink: {
          dark: "#F4F0E6",
          dim: "#9D97AE",
          light: "#1E1E24",
        },
      },
      fontFamily: {
        sans: ["Jost", "Manrope", "system-ui", "sans-serif"],
        display: ["Playfair Display", "Sora", "serif"],
        serif: ["Playfair Display", "serif"],
        jost: ["Jost", "sans-serif"],
      },
      fontSize: {
        body: ["16px", { lineHeight: "1.6" }],
        h3: ["20px", { lineHeight: "1.4" }],
        h2: ["26px", { lineHeight: "1.3" }],
        h1: ["42px", { lineHeight: "1.15" }],
      },
      spacing: {
        8: "8px",
        13: "13px",
        21: "21px",
        34: "34px",
        55: "55px",
        89: "89px",
      },
      width: {
        golden: "61.8%",
        "golden-side": "38.2%",
      },
      aspectRatio: {
        golden: "1.618 / 1",
        "golden-portrait": "1 / 1.618",
      },
      borderRadius: {
        card: "13px",
      },
    },
  },
  plugins: [],
};
