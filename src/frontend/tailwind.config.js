/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          gold: "#D4AF37",
          dark: "#0F172A",
          charcoal: "#1E293B",
          card: "#182234"
        }
      }
    },
  },
  plugins: [],
}
