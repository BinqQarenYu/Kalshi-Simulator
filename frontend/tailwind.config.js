/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        kalshi: {
          bg: "#0d1117",
          card: "#161b22",
          cardBorder: "#21262d",
          hover: "#1f242c",
          text: "#f0f6fc",
          subtext: "#8b949e",
          green: "#00d084",
          greenLight: "#e6f9f2",
          greenBg: "rgba(0, 208, 132, 0.12)",
          red: "#ff4d4d",
          redLight: "#fdeeed",
          redBg: "rgba(255, 77, 77, 0.12)",
          btc: "#f7931a",
          amber: "#f59e0b",
          blue: "#3b82f6",
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Courier New', 'monospace'],
      }
    },
  },
  plugins: [],
}
