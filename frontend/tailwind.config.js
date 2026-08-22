/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "Segoe UI", "sans-serif"],
      },
      colors: {
        ink: "#12202b",
        paper: "#f4efe6",
        brass: "#c4a574",
      },
    },
  },
  plugins: [],
};
