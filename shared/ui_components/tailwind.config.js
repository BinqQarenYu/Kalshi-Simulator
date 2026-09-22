/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "../../app_*/dashboard/src/**/*.{js,ts,jsx,tsx}",
    "./src/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        institutional: {
          bg: '#0c0f12',
          panel: '#111827',
          border: '#1e293b'
        }
      }
    },
  },
  plugins: [],
}
