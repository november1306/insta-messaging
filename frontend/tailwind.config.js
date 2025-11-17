/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'instagram-blue': '#0095F6',
        'instagram-gray': '#8E8E8E',
        'instagram-border': '#DBDBDB',
        'instagram-bg': '#FAFAFA',
      },
    },
  },
  plugins: [],
}
